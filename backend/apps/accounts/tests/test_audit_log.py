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
    confirm_password_reset,
    create_additional_super_admin,
    deactivate_staff_member,
    invite_staff_member,
    reactivate_staff_member,
    record_audit_log,
    request_password_reset,
    set_password_from_invite,
)
from apps.accounts.tokens import get_tokens_for_user
from apps.attendance.services import (
    ScanValidationError,
    issue_member_qr_token,
    process_manual_override,
    verify_and_process_scan,
)
from apps.memberships.models import Member, MemberSubscription
from apps.memberships.services import (
    register_member_self_service,
    register_member_staff_assisted,
    verify_member_email,
)
from apps.tenants.models import DemoRequest, GymTenant
from apps.tenants.services import (
    confirm_gym_tls,
    create_gym,
    dismiss_first_run_checklist,
    update_gym_settings,
)


def auth_client(api_client, user):
    tokens = get_tokens_for_user(user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
    return client


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
def gym_trainer(db, gym_tenant):
    user = User.objects.create_user(
        email="trainer_audit@example.com",
        password="TrainerPassword123!",
        role=User.ROLE_TRAINER,
        gym=gym_tenant,
        full_name="Gym Trainer",
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

    def test_auditlog_update_still_blocked_when_flush_setting_attempted(
        self, super_admin
    ):
        """Even if an attacker runs SET fitgate.allow_auditlog_flush = 'on', UPDATE is blocked."""
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
                    cursor.execute("SET fitgate.allow_auditlog_flush = 'on'")
                    cursor.execute(
                        "UPDATE accounts_auditlog SET action_type = 'tampered' WHERE id = %s",
                        [str(log.id)],
                    )
        assert "AuditLog is append-only and cannot be modified or deleted." in str(
            exc_info.value
        )

    def test_auditlog_delete_still_blocked_when_flush_setting_attempted(
        self, super_admin
    ):
        """Even if an attacker runs SET fitgate.allow_auditlog_flush = 'on', DELETE is blocked."""
        log = record_audit_log(
            action_type="test_action",
            affected_record_type="User",
            affected_record_id=str(super_admin.id),
            actor=super_admin,
        )
        with pytest.raises(DatabaseError) as exc_info:
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute("SET fitgate.allow_auditlog_flush = 'on'")
                    cursor.execute(
                        "DELETE FROM accounts_auditlog WHERE id = %s",
                        [str(log.id)],
                    )
        assert "AuditLog is append-only and cannot be modified or deleted." in str(
            exc_info.value
        )

    def test_auditlog_truncate_still_blocked_when_flush_setting_attempted(self):
        """Even if an attacker runs SET fitgate.allow_auditlog_flush = 'on', TRUNCATE is blocked."""
        with pytest.raises(DatabaseError) as exc_info:
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute("SET fitgate.allow_auditlog_flush = 'on'")
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
                "emergency_contact": "+251911998877",
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
                "emergency_contact": "+251911332211",
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

    def test_audit_gym_tls_confirmed(self, super_admin, gym_tenant):
        """confirm_gym_tls produces exactly 1 row (platform-level)."""
        count_before = AuditLog.all_objects.count()
        confirm_gym_tls(gym_id=gym_tenant.id, acting_super_admin=super_admin)
        assert AuditLog.all_objects.count() == count_before + 1

        entry = AuditLog.all_objects.latest("timestamp")
        assert entry.action_type == "gym_tls_confirmed"
        assert entry.affected_record_type == "GymTenant"
        assert entry.affected_record_id == str(gym_tenant.id)
        assert entry.actor_id == super_admin.id
        assert entry.gym == gym_tenant

    def test_audit_gym_settings_updated(self, gym_owner, gym_tenant):
        """update_gym_settings produces exactly 1 row."""
        count_before = AuditLog.all_objects.count()
        update_gym_settings(
            gym=gym_tenant,
            acting_user=gym_owner,
            data={"brand_color": "#123456"},
        )
        assert AuditLog.all_objects.count() == count_before + 1

        entry = AuditLog.all_objects.latest("timestamp")
        assert entry.action_type == "gym_settings_updated"
        assert entry.affected_record_type == "GymConfig"
        assert entry.affected_record_id == str(gym_tenant.config.pk)
        assert entry.actor_id == gym_owner.id
        assert entry.gym_id == gym_tenant.id

    def test_audit_checklist_dismissed(self, gym_owner, gym_tenant):
        """dismiss_first_run_checklist produces exactly 1 row."""
        count_before = AuditLog.all_objects.count()
        dismiss_first_run_checklist(gym=gym_tenant, acting_user=gym_owner)
        assert AuditLog.all_objects.count() == count_before + 1

        entry = AuditLog.all_objects.latest("timestamp")
        assert entry.action_type == "checklist_dismissed"
        assert entry.affected_record_type == "GymConfig"
        assert entry.actor_id == gym_owner.id
        assert entry.gym_id == gym_tenant.id

    def test_audit_gym_logo_uploaded(self, api_client, gym_owner, gym_tenant):
        """UploadGymLogoView produces exactly 1 row."""
        import io

        from django.core.files.uploadedfile import SimpleUploadedFile
        from PIL import Image

        img = Image.new("RGB", (100, 100), color="blue")
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="PNG")
        img_bytes.seek(0)
        upload_file = SimpleUploadedFile(
            "logo.png", img_bytes.read(), content_type="image/png"
        )

        client = auth_client(api_client, gym_owner)
        count_before = AuditLog.all_objects.count()
        resp = client.post(
            f"/api/media/gym-logo/{gym_tenant.id}/",
            {"file": upload_file},
            format="multipart",
            HTTP_HOST=f"{gym_tenant.subdomain}.localhost",
        )
        assert resp.status_code == 200
        assert AuditLog.all_objects.count() == count_before + 1

        entry = AuditLog.all_objects.latest("timestamp")
        assert entry.action_type == "gym_logo_uploaded"
        assert entry.actor_id == gym_owner.id
        assert entry.gym_id == gym_tenant.id

    def test_audit_member_photo_uploaded(
        self, api_client, gym_reception, gym_tenant, member_with_active_sub
    ):
        """UploadMemberPhotoView produces exactly 1 row."""
        import io

        from django.core.files.uploadedfile import SimpleUploadedFile
        from PIL import Image

        img = Image.new("RGB", (100, 100), color="green")
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="JPEG")
        img_bytes.seek(0)
        upload_file = SimpleUploadedFile(
            "photo.jpg", img_bytes.read(), content_type="image/jpeg"
        )

        client = auth_client(api_client, gym_reception)
        count_before = AuditLog.all_objects.count()
        resp = client.post(
            f"/api/media/member-photos/{gym_tenant.id}/",
            {"file": upload_file, "member_id": str(member_with_active_sub.id)},
            format="multipart",
            HTTP_HOST=f"{gym_tenant.subdomain}.localhost",
        )
        assert resp.status_code == 201
        assert AuditLog.all_objects.count() == count_before + 1

        entry = AuditLog.all_objects.latest("timestamp")
        assert entry.action_type == "member_photo_uploaded"
        assert entry.actor_id == gym_reception.id
        assert entry.gym_id == gym_tenant.id

    def test_audit_demo_request_updated(self, api_client, super_admin):
        """DemoRequestDetailView.patch produces exactly 1 row."""
        demo = DemoRequest.objects.create(
            gym_name="Demo Gym",
            contact_name="Abebe",
            email="abebe@demogym.com",
            phone="+251911112233",
            city="Addis Ababa",
            status=DemoRequest.STATUS_NEW,
        )
        client = auth_client(api_client, super_admin)
        count_before = AuditLog.all_objects.count()
        resp = client.patch(
            f"/api/platform/demo-requests/{demo.id}/",
            {"status": DemoRequest.STATUS_CONTACTED},
            format="json",
            HTTP_HOST="localhost",
        )
        assert resp.status_code == 200
        assert AuditLog.all_objects.count() == count_before + 1

        entry = AuditLog.all_objects.latest("timestamp")
        assert entry.action_type == "demo_request_updated"
        assert entry.actor_id == super_admin.id
        assert entry.affected_record_type == "DemoRequest"
        assert entry.affected_record_id == str(demo.id)

    def test_audit_password_reset_flow(self, gym_owner, gym_tenant):
        """request_password_reset and confirm_password_reset each produce exactly 1 row."""
        count_before = AuditLog.all_objects.count()
        raw_token = request_password_reset(email=gym_owner.email, tenant=gym_tenant)
        assert raw_token is not None
        assert AuditLog.all_objects.count() == count_before + 1

        entry_req = AuditLog.all_objects.latest("timestamp")
        assert entry_req.action_type == "password_reset_requested"
        assert entry_req.affected_record_type == "User"
        assert entry_req.affected_record_id == str(gym_owner.id)

        confirm_password_reset(
            raw_token=raw_token,
            new_password="NewConfirmedPassword123!",
            tenant=gym_tenant,
        )
        assert AuditLog.all_objects.count() == count_before + 2

        entry_conf = AuditLog.all_objects.latest("timestamp")
        assert entry_conf.action_type == "password_reset_completed"
        assert entry_conf.affected_record_type == "User"
        assert entry_conf.affected_record_id == str(gym_owner.id)

    def test_audit_set_password_from_invite(self, gym_owner, gym_tenant):
        """set_password_from_invite produces exactly 1 row."""
        user, _, invite_token = invite_staff_member(
            acting_user=gym_owner,
            gym=gym_tenant,
            data={
                "role": User.ROLE_TRAINER,
                "email": "invitee_audit@example.com",
                "full_name": "Invited Trainer",
                "phone": "+251911998877",
            },
        )
        count_before = AuditLog.all_objects.count()
        set_password_from_invite(
            raw_token=invite_token,
            new_password="NewTrainerPassword123!",
            tenant=gym_tenant,
        )
        assert AuditLog.all_objects.count() == count_before + 1

        entry = AuditLog.all_objects.latest("timestamp")
        assert entry.action_type == "password_set_from_invite"
        assert entry.affected_record_type == "User"
        assert entry.affected_record_id == str(user.id)
        assert entry.actor_id == user.id

    def test_audit_email_verified(self, gym_tenant):
        """verify_member_email produces exactly 1 row."""
        member, token = register_member_self_service(
            gym=gym_tenant,
            data={
                "email": "verify_me@example.com",
                "password": "VerifyPassword123!",
                "full_name": "Verify Me",
                "phone": "+251911887766",
                "date_of_birth": "1996-03-20",
                "gender": "male",
                "emergency_contact": "+251911998877",
                "waiver_accepted": True,
            },
        )
        count_before = AuditLog.all_objects.count()
        verify_member_email(raw_token=token, tenant=gym_tenant)
        assert AuditLog.all_objects.count() == count_before + 1

        entry = AuditLog.all_objects.latest("timestamp")
        assert entry.action_type == "email_verified"
        assert entry.affected_record_type == "User"
        assert entry.affected_record_id == str(member.user.id)
        assert entry.actor_id == member.user.id

    def test_audit_user_profile_updated(self, api_client, gym_owner, gym_tenant):
        """UserProfileView.patch produces exactly 1 row."""
        client = auth_client(api_client, gym_owner)
        count_before = AuditLog.all_objects.count()
        resp = client.patch(
            "/api/auth/me/",
            {"full_name": "Owner Updated Name", "phone": "+251911001122"},
            format="json",
            HTTP_HOST=f"{gym_tenant.subdomain}.localhost",
        )
        assert resp.status_code == 200
        assert AuditLog.all_objects.count() == count_before + 1

        entry = AuditLog.all_objects.latest("timestamp")
        assert entry.action_type == "user_profile_updated"
        assert entry.actor_id == gym_owner.id
        assert entry.affected_record_type == "User"
        assert entry.affected_record_id == str(gym_owner.id)

    def test_audit_member_updated(
        self, api_client, gym_owner, gym_tenant, member_with_active_sub
    ):
        """GymMemberDetailView.patch produces exactly 1 row."""
        client = auth_client(api_client, gym_owner)
        count_before = AuditLog.all_objects.count()
        resp = client.patch(
            f"/api/gym/members/{member_with_active_sub.id}/",
            {"emergency_contact": "+251911000999"},
            format="json",
            HTTP_HOST=f"{gym_tenant.subdomain}.localhost",
        )
        assert resp.status_code == 200
        assert AuditLog.all_objects.count() == count_before + 1

        entry = AuditLog.all_objects.latest("timestamp")
        assert entry.action_type == "member_updated"
        assert entry.actor_id == gym_owner.id
        assert entry.affected_record_type == "Member"
        assert entry.affected_record_id == str(member_with_active_sub.id)

    def test_audit_member_metrics_recorded(
        self, api_client, gym_trainer, gym_tenant, member_with_active_sub
    ):
        """GymMemberRecordMetricsView.post produces exactly 1 row."""
        client = auth_client(api_client, gym_trainer)
        count_before = AuditLog.all_objects.count()
        resp = client.post(
            f"/api/gym/members/{member_with_active_sub.id}/metrics/",
            {
                "weight_kg": 75.5,
                "height_cm": 180.0,
                "measurements": {"chest_cm": 100},
            },
            format="json",
            HTTP_HOST=f"{gym_tenant.subdomain}.localhost",
        )
        assert resp.status_code == 201
        assert AuditLog.all_objects.count() == count_before + 1

        entry = AuditLog.all_objects.latest("timestamp")
        assert entry.action_type == "member_metrics_recorded"
        assert entry.actor_id == gym_trainer.id
        assert entry.affected_record_type == "BodyMetrics"

    def test_audit_member_self_profile_refused(
        self, api_client, gym_tenant, member_with_active_sub
    ):
        """MemberSelfProfileView.patch is refused for member role (Item 14) and writes no audit log."""
        client = auth_client(api_client, member_with_active_sub.user)
        count_before = AuditLog.all_objects.count()
        resp = client.patch(
            "/api/members/me/",
            {"emergency_contact": "+251911000999"},
            format="json",
            HTTP_HOST=f"{gym_tenant.subdomain}.localhost",
        )
        assert resp.status_code == 403
        assert AuditLog.all_objects.count() == count_before


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

    def test_duplicate_scan_already_checked_in_writes_no_audit_log(
        self, gym_tenant, gym_reception, member_with_active_sub
    ):
        """A duplicate scan on the same day rejected with already_checked_in writes NO audit row."""
        token1, _ = issue_member_qr_token(member_with_active_sub)
        res1 = verify_and_process_scan(
            token_str=token1,
            gym=gym_tenant,
            recorded_by=gym_reception,
        )
        assert res1["status"] == "success"
        count_after_first = AuditLog.all_objects.count()

        # Issue another token for same member and scan on same day
        token2, _ = issue_member_qr_token(member_with_active_sub)
        with pytest.raises(ScanValidationError) as exc_info:
            verify_and_process_scan(
                token_str=token2,
                gym=gym_tenant,
                recorded_by=gym_reception,
            )
        assert exc_info.value.reason == "already_checked_in"
        assert AuditLog.all_objects.count() == count_after_first

    def test_token_consumed_scan_writes_no_audit_log(
        self, gym_tenant, gym_reception, member_with_active_sub
    ):
        """A replay scan with an already consumed token rejected with token_consumed writes NO audit row."""
        token_str, _ = issue_member_qr_token(member_with_active_sub)
        res1 = verify_and_process_scan(
            token_str=token_str,
            gym=gym_tenant,
            recorded_by=gym_reception,
        )
        assert res1["status"] == "success"
        count_after_first = AuditLog.all_objects.count()

        # Attempt to scan again with the SAME consumed token
        with pytest.raises(ScanValidationError) as exc_info:
            verify_and_process_scan(
                token_str=token_str,
                gym=gym_tenant,
                recorded_by=gym_reception,
            )
        assert exc_info.value.reason == "token_consumed"
        assert AuditLog.all_objects.count() == count_after_first

    def test_simulated_integrity_error_race_writes_no_audit_log(
        self, gym_tenant, gym_reception, member_with_active_sub
    ):
        """Simulated concurrent race / IntegrityError on scan rolls back and writes NO audit row."""
        token_str, _ = issue_member_qr_token(member_with_active_sub)
        count_before = AuditLog.all_objects.count()

        from unittest.mock import patch

        from django.db import IntegrityError

        from apps.attendance.models import Attendance

        with patch.object(
            Attendance.all_objects,
            "create",
            side_effect=IntegrityError(
                "duplicate key value violates unique constraint"
            ),
        ):
            with pytest.raises(ScanValidationError) as exc_info:
                verify_and_process_scan(
                    token_str=token_str,
                    gym=gym_tenant,
                    recorded_by=gym_reception,
                )
            assert exc_info.value.reason == "already_checked_in"

        assert AuditLog.all_objects.count() == count_before

    def test_failed_password_reset_confirm_writes_no_audit_log(self, gym_tenant):
        count_before = AuditLog.all_objects.count()
        with pytest.raises(ValidationError):
            confirm_password_reset(
                raw_token="invalid-token",
                new_password="NewSecurePassword123!",
                tenant=gym_tenant,
            )
        assert AuditLog.all_objects.count() == count_before

    def test_failed_set_password_from_invite_writes_no_audit_log(self, gym_tenant):
        count_before = AuditLog.all_objects.count()
        with pytest.raises(ValidationError):
            set_password_from_invite(
                raw_token="invalid-invite-token",
                new_password="NewSecurePassword123!",
                tenant=gym_tenant,
            )
        assert AuditLog.all_objects.count() == count_before

    def test_failed_email_verification_writes_no_audit_log(self, gym_tenant):
        count_before = AuditLog.all_objects.count()
        with pytest.raises(ValidationError):
            verify_member_email(raw_token="invalid-token", tenant=gym_tenant)
        assert AuditLog.all_objects.count() == count_before

    def test_failed_gym_tls_confirm_writes_no_audit_log(self, super_admin):
        import uuid

        count_before = AuditLog.all_objects.count()
        with pytest.raises(Exception):
            confirm_gym_tls(gym_id=uuid.uuid4(), acting_super_admin=super_admin)
        assert AuditLog.all_objects.count() == count_before

    def test_failed_gym_settings_update_writes_no_audit_log(
        self, gym_reception, gym_tenant
    ):
        count_before = AuditLog.all_objects.count()
        from rest_framework.exceptions import PermissionDenied

        with pytest.raises(PermissionDenied):
            update_gym_settings(
                gym=gym_tenant,
                acting_user=gym_reception,
                data={"brand_color": "#123456"},
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
