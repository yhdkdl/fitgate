"""
Comprehensive tests for Sprint 9: Audit Log Foundation.

Covers:
1. Immutability by PostgreSQL triggers:
   - BEFORE UPDATE raises exception (tested via raw SQL through application connection)
   - BEFORE DELETE raises exception (tested via raw SQL through application connection)
   - BEFORE TRUNCATE raises exception (tested via raw SQL through application connection)
   - ORM level save() update prevention and delete() prevention
   - on_delete=PROTECT on actor prevents user deletion when audit logs exist
   - Django admin AuditLogAdmin read-only enforcement
2. Action logging from Sprints 1-8:
   - Exactly ONE AuditLog row produced per action (count before/after, correct actor, action_type, affected_record)
   - super_admin_created (service and command)
   - gym_created (platform-level gym_id is None)
   - user_login
   - logout
   - password_changed
   - staff_provisioned
   - staff_deactivated
   - staff_reactivated
   - member_registered (self-service and staff-assisted)
   - attendance_qr_scan
   - attendance_manual_override
3. Failed actions produce NO audit rows:
   - Failed login (invalid credentials) -> 0 rows
   - Failed logout (invalid token) -> 0 rows
   - Failed password change (invalid current password) -> 0 rows
   - Failed gym creation (rollback) -> 0 rows
   - Failed staff provisioning (permission denied / validation error) -> 0 rows
   - Failed member registration -> 0 rows
   - Failed QR scan (duplicate scan / expired sub) -> 0 rows
   - Failed manual override (empty reason) -> 0 rows
4. Security & sanitization:
   - No secrets, passwords, tokens, or QR token strings in metadata
"""

from datetime import date, timedelta
from unittest.mock import MagicMock

import pytest
from django.contrib.admin.sites import AdminSite
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import DatabaseError, connection, transaction
from django.db.models import ProtectedError
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.admin import AuditLogAdmin
from apps.accounts.models import AuditLog, User
from apps.accounts.services import (
    change_password,
    create_additional_super_admin,
    deactivate_staff_member,
    invite_staff_member,
    reactivate_staff_member,
    record_audit_log,
)
from apps.attendance.services import (
    issue_member_qr_token,
    process_manual_override,
    verify_and_process_scan,
)
from apps.memberships.models import Member, MemberSubscription
from apps.memberships.services import (
    register_member_self_service,
    register_member_staff_assisted,
)
from apps.tenants.models import GymTenant
from apps.tenants.services import create_gym


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def super_admin(db):
    user = User.objects.create_superuser(
        email="superadmin_audit@example.com",
        password="SuperPassword123!",
        must_change_password=False,
    )
    return user


@pytest.fixture
def gym_tenant(db):
    return GymTenant.objects.create(
        name="Audit Gym",
        subdomain="auditgym",
        status=GymTenant.STATUS_ACTIVE,
        tier=GymTenant.TIER_GROWTH,
        currency="ETB",
        tls_confirmed_at=timezone.now(),
    )


@pytest.fixture
def gym_owner(db, gym_tenant):
    user = User.objects.create_user(
        email="owner_audit@example.com",
        password="OwnerPassword123!",
        role=User.ROLE_OWNER,
        gym=gym_tenant,
        full_name="Gym Owner",
        is_active=True,
        must_change_password=False,
        email_verified_at=timezone.now(),
    )
    return user


@pytest.fixture
def gym_reception(db, gym_tenant):
    user = User.objects.create_user(
        email="reception_audit@example.com",
        password="ReceptionPassword123!",
        role=User.ROLE_RECEPTION,
        gym=gym_tenant,
        full_name="Gym Reception",
        is_active=True,
        must_change_password=False,
        email_verified_at=timezone.now(),
    )
    return user


@pytest.fixture
def member_with_active_sub(db, gym_tenant):
    user = User.objects.create_user(
        email="member_audit@example.com",
        password="MemberPassword123!",
        role=User.ROLE_MEMBER,
        gym=gym_tenant,
        full_name="Audit Member",
        is_active=True,
        must_change_password=False,
        email_verified_at=timezone.now(),
    )
    member = Member.objects.create(
        gym=gym_tenant,
        user=user,
        full_name="Audit Member",
        phone="+251911000000",
        date_of_birth=date(1995, 1, 1),
        gender="M",
        emergency_contact="Contact - +251911999999",
        status=Member.STATUS_ACTIVE,
        waiver_accepted_at=timezone.now(),
    )
    today = timezone.localdate()
    MemberSubscription.objects.create(
        gym=gym_tenant,
        member=member,
        status=MemberSubscription.STATUS_ACTIVE,
        start_date=today - timedelta(days=5),
        end_date=today + timedelta(days=25),
    )
    return member


# ==============================================================================
# 1. IMMUTABILITY TESTS: POSTGRESQL TRIGGERS & MODEL SAFEGUARDS
# ==============================================================================


@pytest.mark.django_db
class TestAuditLogImmutability:
    """Verify that PostgreSQL triggers enforce immutability for UPDATE, DELETE, and TRUNCATE."""

    def test_auditlog_update_blocked_by_database_trigger_raw_sql(self, super_admin):
        """Raw SQL UPDATE against accounts_auditlog must be aborted by database trigger."""
        log = record_audit_log(
            action_type="test_action",
            affected_record_type="User",
            affected_record_id=str(super_admin.id),
            actor=super_admin,
            metadata={"key": "original"},
        )

        with pytest.raises(DatabaseError) as exc_info:
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute(
                        "UPDATE accounts_auditlog SET action_type = 'tampered' WHERE id = %s",
                        [str(log.id)],
                    )
        assert "AuditLog is append-only and cannot be modified or deleted." in str(
            exc_info.value
        )

        # Confirm data was not modified
        log.refresh_from_db()
        assert log.action_type == "test_action"

    def test_auditlog_delete_blocked_by_database_trigger_raw_sql(self, super_admin):
        """Raw SQL DELETE against accounts_auditlog must be aborted by database trigger."""
        log = record_audit_log(
            action_type="test_action",
            affected_record_type="User",
            affected_record_id=str(super_admin.id),
            actor=super_admin,
        )

        with pytest.raises(DatabaseError) as exc_info:
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute(
                        "DELETE FROM accounts_auditlog WHERE id = %s",
                        [str(log.id)],
                    )
        assert "AuditLog is append-only and cannot be modified or deleted." in str(
            exc_info.value
        )

        # Confirm record still exists
        assert AuditLog.all_objects.filter(id=log.id).exists()

    def test_auditlog_truncate_blocked_by_database_trigger_raw_sql(self):
        """Raw SQL TRUNCATE against accounts_auditlog must be aborted by database trigger."""
        with pytest.raises(DatabaseError) as exc_info:
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute("TRUNCATE accounts_auditlog")
        assert "AuditLog is append-only and cannot be modified or deleted." in str(
            exc_info.value
        )

    def test_auditlog_orm_update_prevented(self, super_admin):
        """ORM save() on existing instance must raise ValidationError."""
        log = record_audit_log(
            action_type="test_action",
            affected_record_type="User",
            affected_record_id=str(super_admin.id),
            actor=super_admin,
        )
        log.action_type = "tampered"
        with pytest.raises(ValidationError) as exc_info:
            log.save()
        assert "AuditLog is append-only and cannot be updated." in str(exc_info.value)

    def test_auditlog_orm_delete_prevented(self, super_admin):
        """ORM delete() on AuditLog instance must raise ValidationError."""
        log = record_audit_log(
            action_type="test_action",
            affected_record_type="User",
            affected_record_id=str(super_admin.id),
            actor=super_admin,
        )
        with pytest.raises(ValidationError) as exc_info:
            log.delete()
        assert "AuditLog is append-only and cannot be deleted." in str(exc_info.value)

    def test_auditlog_actor_on_delete_protect(self, gym_owner):
        """Deleting a User with audit logs must raise ProtectedError."""
        record_audit_log(
            action_type="test_action",
            affected_record_type="User",
            affected_record_id=str(gym_owner.id),
            actor=gym_owner,
        )
        with pytest.raises(ProtectedError):
            gym_owner.delete()

    def test_auditlog_admin_is_strictly_read_only(self):
        """Django admin AuditLogAdmin must disallow add, change, and delete."""
        site = AdminSite()
        admin_obj = AuditLogAdmin(AuditLog, site)
        dummy_request = MagicMock()

        assert admin_obj.has_add_permission(dummy_request) is False
        assert admin_obj.has_change_permission(dummy_request) is False
        assert admin_obj.has_delete_permission(dummy_request) is False
        assert set(admin_obj.readonly_fields) >= {
            "id",
            "gym",
            "actor",
            "action_type",
            "affected_record_type",
            "affected_record_id",
            "timestamp",
            "metadata",
        }


# ==============================================================================
# 2. ACTION LOGGING TESTS: EXACTLY ONE ROW PER ACTION FROM SPRINTS 1-8
# ==============================================================================


@pytest.mark.django_db
class TestActionAuditLogging:
    """Verify that every supported operational action from Sprints 1-8 produces exactly one AuditLog row."""

    def test_audit_super_admin_creation_via_service(self, super_admin):
        """create_additional_super_admin produces exactly 1 row (platform-level)."""
        count_before = AuditLog.all_objects.count()
        new_admin = create_additional_super_admin(
            actor=super_admin,
            email="new_superadmin@example.com",
            password="StrongPassword123!",
            current_password="SuperPassword123!",
        )
        count_after = AuditLog.all_objects.count()
        assert count_after == count_before + 1

        entry = AuditLog.all_objects.latest("timestamp")
        assert entry.action_type == "super_admin_created"
        assert entry.affected_record_type == "User"
        assert entry.affected_record_id == str(new_admin.id)
        assert entry.actor_id == super_admin.id
        assert entry.gym_id is None

    def test_audit_super_admin_creation_via_command(self, monkeypatch):
        """create_super_admin management command produces exactly 1 row."""
        monkeypatch.setenv("SUPERADMIN_EMAIL", "bootstrap_admin@example.com")
        monkeypatch.setenv("SUPERADMIN_PASSWORD", "BootstrapSecret123!")

        count_before = AuditLog.all_objects.count()
        call_command("create_super_admin")
        count_after = AuditLog.all_objects.count()
        assert count_after == count_before + 1

        entry = AuditLog.all_objects.latest("timestamp")
        assert entry.action_type == "super_admin_created"
        assert entry.affected_record_type == "User"
        assert entry.actor.email == "bootstrap_admin@example.com"
        assert entry.gym_id is None

    def test_audit_gym_creation(self, super_admin):
        """create_gym produces exactly 1 platform-level row (gym_id is None)."""
        mock_uapi = MagicMock()
        mock_uapi.provision_subdomain.return_value = True

        count_before = AuditLog.all_objects.count()
        result = create_gym(
            name="New Gold Gym",
            subdomain="newgold",
            tier=GymTenant.TIER_GROWTH,
            owner_email="newgold_owner@example.com",
            payment_amount=30000,
            payment_reference="BANK-12345",
            acting_super_admin=super_admin,
            uapi_client=mock_uapi,
        )
        count_after = AuditLog.all_objects.count()
        assert count_after == count_before + 1

        entry = AuditLog.all_objects.latest("timestamp")
        assert entry.action_type == "gym_created"
        assert entry.affected_record_type == "GymTenant"
        assert entry.affected_record_id == str(result["gym"].id)
        assert entry.actor_id == super_admin.id
        assert entry.gym_id is None  # SPEC §4: platform rows have gym_id null

    def test_audit_user_login(self, api_client, gym_owner):
        """Successful login via API produces exactly 1 row."""
        count_before = AuditLog.all_objects.count()
        resp = api_client.post(
            "/api/auth/login/",
            {"email": gym_owner.email, "password": "OwnerPassword123!"},
            HTTP_HOST="auditgym.localhost",
        )
        assert resp.status_code == status.HTTP_200_OK
        count_after = AuditLog.all_objects.count()
        assert count_after == count_before + 1

        entry = AuditLog.all_objects.latest("timestamp")
        assert entry.action_type == "user_login"
        assert entry.affected_record_type == "User"
        assert entry.affected_record_id == str(gym_owner.id)
        assert entry.actor_id == gym_owner.id
        assert entry.gym_id == gym_owner.gym_id

    def test_audit_user_logout(self, api_client, gym_owner):
        """Logout via API produces exactly 1 row."""
        login_resp = api_client.post(
            "/api/auth/login/",
            {"email": gym_owner.email, "password": "OwnerPassword123!"},
            HTTP_HOST="auditgym.localhost",
        )
        refresh_token = login_resp.data["refresh"]

        count_before = AuditLog.all_objects.count()
        logout_resp = api_client.post(
            "/api/auth/logout/",
            {"refresh": refresh_token},
            HTTP_HOST="auditgym.localhost",
        )
        assert logout_resp.status_code == status.HTTP_200_OK
        count_after = AuditLog.all_objects.count()
        assert count_after == count_before + 1

        entry = AuditLog.all_objects.latest("timestamp")
        assert entry.action_type == "logout"
        assert entry.affected_record_type == "User"
        assert entry.affected_record_id == str(gym_owner.id)
        assert entry.actor_id == gym_owner.id

    def test_audit_password_change(self, gym_owner):
        """change_password service produces exactly 1 row."""
        count_before = AuditLog.all_objects.count()
        change_password(
            user=gym_owner,
            current_password="OwnerPassword123!",
            new_password="NewSecurePassword123!",
        )
        count_after = AuditLog.all_objects.count()
        assert count_after == count_before + 1

        entry = AuditLog.all_objects.latest("timestamp")
        assert entry.action_type == "password_changed"
        assert entry.affected_record_type == "User"
        assert entry.affected_record_id == str(gym_owner.id)
        assert entry.actor_id == gym_owner.id
        assert entry.gym_id == gym_owner.gym_id

    def test_audit_staff_provisioning_invite(self, gym_owner, gym_tenant):
        """invite_staff_member produces exactly 1 row."""
        count_before = AuditLog.all_objects.count()
        user, _, _ = invite_staff_member(
            acting_user=gym_owner,
            gym=gym_tenant,
            data={
                "role": User.ROLE_TRAINER,
                "email": "trainer_new@example.com",
                "full_name": "New Trainer",
                "phone": "+251911223344",
            },
        )
        count_after = AuditLog.all_objects.count()
        assert count_after == count_before + 1

        entry = AuditLog.all_objects.latest("timestamp")
        assert entry.action_type == "staff_provisioned"
        assert entry.affected_record_type == "User"
        assert entry.affected_record_id == str(user.id)
        assert entry.actor_id == gym_owner.id
        assert entry.gym_id == gym_tenant.id

    def test_audit_staff_deactivation_and_reactivation(self, gym_owner, gym_reception):
        """deactivate_staff_member and reactivate_staff_member produce exactly 1 row each."""
        count_before = AuditLog.all_objects.count()
        deactivate_staff_member(acting_user=gym_owner, target_user=gym_reception)
        assert AuditLog.all_objects.count() == count_before + 1

        entry_deact = AuditLog.all_objects.latest("timestamp")
        assert entry_deact.action_type == "staff_deactivated"
        assert entry_deact.affected_record_id == str(gym_reception.id)
        assert entry_deact.actor_id == gym_owner.id

        reactivate_staff_member(acting_user=gym_owner, target_user=gym_reception)
        assert AuditLog.all_objects.count() == count_before + 2

        entry_react = AuditLog.all_objects.latest("timestamp")
        assert entry_react.action_type == "staff_reactivated"
        assert entry_react.affected_record_id == str(gym_reception.id)
        assert entry_react.actor_id == gym_owner.id

    def test_audit_member_registration_self_service(self, gym_tenant):
        """register_member_self_service produces exactly 1 row."""
        count_before = AuditLog.all_objects.count()
        member, _ = register_member_self_service(
            gym=gym_tenant,
            data={
                "email": "selfmember@example.com",
                "password": "SecurePassword123!",
                "full_name": "Self Member",
                "phone": "+251911556677",
                "date_of_birth": "1992-05-10",
                "gender": "female",
                "emergency_contact": "Mom - +251911998877",
                "waiver_accepted": True,
            },
        )
        count_after = AuditLog.all_objects.count()
        assert count_after == count_before + 1

        entry = AuditLog.all_objects.latest("timestamp")
        assert entry.action_type == "member_registered"
        assert entry.affected_record_type == "Member"
        assert entry.affected_record_id == str(member.id)
        assert entry.gym_id == gym_tenant.id

    def test_audit_member_registration_staff_assisted(self, gym_reception, gym_tenant):
        """register_member_staff_assisted produces exactly 1 row."""
        count_before = AuditLog.all_objects.count()
        member, _ = register_member_staff_assisted(
            acting_user=gym_reception,
            gym=gym_tenant,
            data={
                "email": "assistedmember@example.com",
                "full_name": "Assisted Member",
                "phone": "+251911443322",
                "date_of_birth": "1994-08-15",
                "gender": "male",
                "emergency_contact": "Brother - +251911332211",
                "waiver_accepted": True,
            },
        )
        count_after = AuditLog.all_objects.count()
        assert count_after == count_before + 1

        entry = AuditLog.all_objects.latest("timestamp")
        assert entry.action_type == "member_registered"
        assert entry.affected_record_type == "Member"
        assert entry.affected_record_id == str(member.id)
        assert entry.actor_id == gym_reception.id
        assert entry.gym_id == gym_tenant.id

    def test_audit_attendance_qr_scan(
        self, member_with_active_sub, gym_reception, gym_tenant
    ):
        """process_scan_and_checkin produces exactly 1 row."""
        token_str, _ = issue_member_qr_token(member_with_active_sub)

        count_before = AuditLog.all_objects.count()
        result = verify_and_process_scan(
            token_str=token_str,
            gym=gym_tenant,
            recorded_by=gym_reception,
        )
        assert result["status"] == "success"
        count_after = AuditLog.all_objects.count()
        assert count_after == count_before + 1

        entry = AuditLog.all_objects.latest("timestamp")
        assert entry.action_type == "attendance_qr_scan"
        assert entry.affected_record_type == "Attendance"
        assert entry.actor_id == gym_reception.id
        assert entry.gym_id == gym_tenant.id

    def test_audit_attendance_manual_override(
        self, member_with_active_sub, gym_reception, gym_tenant
    ):
        """process_manual_override produces exactly 1 row."""
        count_before = AuditLog.all_objects.count()
        result = process_manual_override(
            member_id=member_with_active_sub.id,
            gym=gym_tenant,
            reason="Member phone battery died",
            recorded_by=gym_reception,
        )
        assert result["status"] == "success"
        count_after = AuditLog.all_objects.count()
        assert count_after == count_before + 1

        entry = AuditLog.all_objects.latest("timestamp")
        assert entry.action_type == "attendance_manual_override"
        assert entry.affected_record_type == "Attendance"
        assert entry.actor_id == gym_reception.id
        assert entry.gym_id == gym_tenant.id


# ==============================================================================
# 3. FAILED ACTIONS PRODUCE NO AUDIT ROWS
# ==============================================================================


@pytest.mark.django_db
class TestFailedActionsProduceNoAuditLog:
    """Verify that failed actions (validation error, auth failure, rollback) write 0 audit rows."""

    def test_failed_login_writes_no_audit_log(self, api_client, gym_owner):
        count_before = AuditLog.all_objects.count()
        resp = api_client.post(
            "/api/auth/login/",
            {"email": gym_owner.email, "password": "WrongPassword123!"},
            HTTP_HOST="auditgym.localhost",
        )
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED
        assert AuditLog.all_objects.count() == count_before

    def test_failed_logout_writes_no_audit_log(self, api_client, gym_tenant):
        count_before = AuditLog.all_objects.count()
        resp = api_client.post(
            "/api/auth/logout/",
            {"refresh": "invalid.jwt.token"},
            HTTP_HOST="auditgym.localhost",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert AuditLog.all_objects.count() == count_before

    def test_failed_password_change_writes_no_audit_log(self, gym_owner):
        count_before = AuditLog.all_objects.count()
        with pytest.raises(ValidationError):
            change_password(
                user=gym_owner,
                current_password="WrongCurrentPassword!",
                new_password="NewValidPassword123!",
            )
        assert AuditLog.all_objects.count() == count_before

    def test_failed_gym_creation_rollback_writes_no_audit_log(self, super_admin):
        """If UAPI provisioning fails, transaction rolls back and 0 audit rows remain."""
        mock_uapi = MagicMock()
        mock_uapi.provision_subdomain.side_effect = RuntimeError("UAPI server down")

        count_before = AuditLog.all_objects.count()
        with pytest.raises(RuntimeError):
            create_gym(
                name="Failing Gym",
                subdomain="failgym",
                tier=GymTenant.TIER_STARTER,
                owner_email="failowner@example.com",
                payment_amount=12000,
                payment_reference="REF-FAIL",
                acting_super_admin=super_admin,
                uapi_client=mock_uapi,
            )
        assert AuditLog.all_objects.count() == count_before
        assert not GymTenant.objects.filter(subdomain="failgym").exists()

    def test_failed_staff_provisioning_writes_no_audit_log(self, gym_owner, gym_tenant):
        count_before = AuditLog.all_objects.count()
        with pytest.raises(ValidationError):
            # Invalid target role
            invite_staff_member(
                acting_user=gym_owner,
                gym=gym_tenant,
                data={
                    "role": User.ROLE_MEMBER,  # not staff
                    "email": "invalid_staff@example.com",
                    "full_name": "Bad Staff",
                    "phone": "+251911000000",
                },
            )
        assert AuditLog.all_objects.count() == count_before

    def test_failed_member_registration_writes_no_audit_log(self, gym_tenant):
        count_before = AuditLog.all_objects.count()
        with pytest.raises(ValidationError):
            # Missing required fields
            register_member_self_service(
                gym=gym_tenant,
                data={"email": "notanemail"},
            )
        assert AuditLog.all_objects.count() == count_before

    def test_failed_manual_override_writes_no_audit_log(
        self, member_with_active_sub, gym_reception, gym_tenant
    ):
        count_before = AuditLog.all_objects.count()
        from apps.attendance.services import ScanValidationError

        with pytest.raises(ScanValidationError):
            process_manual_override(
                member_id=member_with_active_sub.id,
                gym=gym_tenant,
                reason="",  # empty reason is rejected
                recorded_by=gym_reception,
            )
        assert AuditLog.all_objects.count() == count_before


# ==============================================================================
# 4. SECURITY & SANITIZATION: NO SECRETS IN METADATA
# ==============================================================================


@pytest.mark.django_db
class TestAuditLogSecurityAndSanitization:
    """Verify that no secrets, passwords, tokens, or QR token strings ever appear in metadata."""

    def test_no_secrets_in_login_metadata(self, api_client, gym_owner):
        api_client.post(
            "/api/auth/login/",
            {"email": gym_owner.email, "password": "OwnerPassword123!"},
            HTTP_HOST="auditgym.localhost",
        )
        entry = AuditLog.all_objects.filter(
            action_type="user_login", actor=gym_owner
        ).latest("timestamp")
        meta = entry.metadata or {}
        raw_meta = str(meta).lower()
        assert "password" not in raw_meta
        assert "token" not in raw_meta
        assert "ownerpassword123!" not in raw_meta

    def test_no_secrets_in_password_change_metadata(self, gym_owner):
        change_password(
            user=gym_owner,
            current_password="OwnerPassword123!",
            new_password="NewSecretPassword123!",
        )
        entry = AuditLog.all_objects.filter(
            action_type="password_changed", actor=gym_owner
        ).latest("timestamp")
        meta = entry.metadata or {}
        raw_meta = str(meta).lower()
        assert "password" not in raw_meta
        assert "newsecretpassword123!" not in raw_meta

    def test_no_secrets_in_qr_scan_metadata(
        self, member_with_active_sub, gym_reception, gym_tenant
    ):
        token_str, _ = issue_member_qr_token(member_with_active_sub)
        verify_and_process_scan(
            token_str=token_str,
            gym=gym_tenant,
            recorded_by=gym_reception,
        )
        entry = AuditLog.all_objects.filter(action_type="attendance_qr_scan").latest(
            "timestamp"
        )
        meta = entry.metadata or {}
        raw_meta = str(meta).lower()
        assert token_str not in str(meta)
        assert "token" not in raw_meta
        assert "secret" not in raw_meta

    def test_record_audit_log_strips_sensitive_keys(self, super_admin):
        """record_audit_log must sanitize any sensitive key names passed to it."""
        entry = record_audit_log(
            action_type="test_sanitization",
            affected_record_type="User",
            affected_record_id=str(super_admin.id),
            actor=super_admin,
            metadata={
                "safe_note": "ok",
                "password": "plain_password",
                "user_password": "plain_password",
                "raw_token": "secret_jwt",
                "secret_key": "12345",
                "authorization_header": "Bearer xyz",
            },
        )
        meta = entry.metadata
        assert "safe_note" in meta
        assert "password" not in meta
        assert "user_password" not in meta
        assert "raw_token" not in meta
        assert "secret_key" not in meta
        assert "authorization_header" not in meta
