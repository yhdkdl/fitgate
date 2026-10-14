"""Tests for staff provisioning (Sprint 6).

Covers:
- Listing staff members (with role and is_active filters).
- Manager/Trainer/Reception invite flow with single-use expiring token.
- Invited staff email verification status and unusable password before completion.
- Set-password completion and post-activation login.
- Enforcing Owner can invite Manager, Trainer, Reception.
- Enforcing Manager can invite Trainer and Reception only (Manager inviting Manager gets 403).
- Deactivation immediately blocking login and invalidating outstanding JWT tokens.
- Deactivation never hard-deleting; preserving row and history; absence of hard-delete route.
- Reactivation restoring active status without validating obsolete tokens.
- Cross-tenant isolation and fail-closed tenant checks.
- First-run checklist automatic completion upon staff creation.
"""

import pytest
from django.core import mail
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import AuthToken, User
from apps.accounts.tokens import get_tokens_for_user
from apps.tenants.models import GymTenant
from apps.tenants.services import get_first_run_checklist


@pytest.fixture
def gym_a(db):
    return GymTenant.objects.create(
        name="Apex Fitness A",
        subdomain="apex-a",
        tier="growth",
        currency="ETB",
        contact_name="Owner A",
        contact_email="owner_a@apex-a.com",
        contact_phone="+251911000001",
        tls_confirmed_at=timezone.now(),
    )


@pytest.fixture
def gym_b(db):
    return GymTenant.objects.create(
        name="Bole Gym B",
        subdomain="bole-b",
        tier="starter",
        currency="ETB",
        contact_name="Owner B",
        contact_email="owner_b@bole-b.com",
        contact_phone="+251911000002",
        tls_confirmed_at=timezone.now(),
    )


@pytest.fixture
def owner_a(db, gym_a):
    return User.objects.create_user(
        email="owner@apex-a.com",
        password="OwnerPassword123!",
        gym=gym_a,
        role=User.ROLE_OWNER,
        must_change_password=False,
    )


@pytest.fixture
def manager_a(db, gym_a):
    return User.objects.create_user(
        email="manager@apex-a.com",
        password="ManagerPassword123!",
        gym=gym_a,
        role=User.ROLE_MANAGER,
        must_change_password=False,
    )


@pytest.fixture
def trainer_a(db, gym_a):
    return User.objects.create_user(
        email="trainer@apex-a.com",
        password="TrainerPassword123!",
        gym=gym_a,
        role=User.ROLE_TRAINER,
        must_change_password=False,
    )


@pytest.fixture
def reception_a(db, gym_a):
    return User.objects.create_user(
        email="reception@apex-a.com",
        password="ReceptionPassword123!",
        gym=gym_a,
        role=User.ROLE_RECEPTION,
        must_change_password=False,
    )


@pytest.fixture
def member_a(db, gym_a):
    return User.objects.create_user(
        email="member@apex-a.com",
        password="MemberPassword123!",
        gym=gym_a,
        role=User.ROLE_MEMBER,
        must_change_password=False,
    )


@pytest.fixture
def owner_b(db, gym_b):
    return User.objects.create_user(
        email="owner@bole-b.com",
        password="OwnerPasswordB123!",
        gym=gym_b,
        role=User.ROLE_OWNER,
        must_change_password=False,
    )


@pytest.fixture
def super_admin(db):
    return User.objects.create_superuser(
        email="superadmin@fitgate.org",
        password="SuperPassword123!",
    )


def auth_client_for(user: User, subdomain: str | None = None) -> APIClient:
    client = APIClient()
    tokens = get_tokens_for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
    if subdomain:
        client.defaults["HTTP_HOST"] = f"{subdomain}.localhost"
    else:
        client.defaults["HTTP_HOST"] = "localhost"
    return client


@pytest.mark.django_db
class TestStaffProvisioning:
    """Test suite for staff invite, list, deactivation, and reactivation."""

    def test_owner_can_list_staff_and_filter_by_role_and_active(
        self, owner_a, manager_a, trainer_a, reception_a, gym_a
    ):
        client = auth_client_for(owner_a, gym_a.subdomain)
        resp = client.get("/api/gym/staff/")
        assert resp.status_code == status.HTTP_200_OK
        emails = [s["email"] for s in resp.data]
        assert owner_a.email in emails
        assert manager_a.email in emails
        assert trainer_a.email in emails
        assert reception_a.email in emails

        # Filter by role
        resp_trainers = client.get("/api/gym/staff/?role=trainer")
        assert resp_trainers.status_code == status.HTTP_200_OK
        assert len(resp_trainers.data) == 1
        assert resp_trainers.data[0]["email"] == trainer_a.email

        # Filter by is_active
        trainer_a.is_active = False
        trainer_a.save(update_fields=["is_active"])
        resp_inactive = client.get("/api/gym/staff/?is_active=false")
        assert resp_inactive.status_code == status.HTTP_200_OK
        assert len(resp_inactive.data) == 1
        assert resp_inactive.data[0]["email"] == trainer_a.email

    def test_owner_can_invite_manager_trainer_and_reception(
        self, owner_a, gym_a, django_capture_on_commit_callbacks
    ):
        client = auth_client_for(owner_a, gym_a.subdomain)

        roles_to_invite = [
            ("new_manager@apex-a.com", "manager", "Abebe Manager", "+251911111111"),
            ("new_trainer@apex-a.com", "trainer", "Chala Trainer", "+251911111112"),
            (
                "new_reception@apex-a.com",
                "reception",
                "Sara Reception",
                "+251911111113",
            ),
        ]

        for email, role, full_name, phone in roles_to_invite:
            with django_capture_on_commit_callbacks(execute=True):
                resp = client.post(
                    "/api/gym/staff/",
                    {
                        "email": email,
                        "role": role,
                        "full_name": full_name,
                        "phone": phone,
                    },
                    format="json",
                )
            assert resp.status_code == status.HTTP_201_CREATED
            data = resp.data["user"]
            assert data["email"] == email
            assert data["role"] == role
            assert data["full_name"] == full_name
            assert data["is_active"] is True
            assert data["email_verified_at"] is not None

            # Verify in database
            user = User.all_objects.get(email=email)
            assert user.gym_id == gym_a.id
            assert user.role == role
            assert user.has_usable_password() is False
            assert user.email_verified_at is not None

            # Verify AuthToken created
            token_obj = AuthToken.objects.filter(
                user=user, purpose=AuthToken.PURPOSE_INVITE, used_at__isnull=True
            ).first()
            assert token_obj is not None
            assert token_obj.expires_at > timezone.now()

        # Verify email notifications were sent
        assert len(mail.outbox) == 3
        for email_msg in mail.outbox:
            assert "Invitation to join" in email_msg.subject
            assert "/set-password?token=" in email_msg.body

    def test_manager_can_invite_trainer_and_reception(
        self, manager_a, gym_a, django_capture_on_commit_callbacks
    ):
        client = auth_client_for(manager_a, gym_a.subdomain)

        with django_capture_on_commit_callbacks(execute=True):
            resp = client.post(
                "/api/gym/staff/",
                {
                    "email": "mgr_invited_trainer@apex-a.com",
                    "role": "trainer",
                    "full_name": "Tadesse Trainer",
                },
                format="json",
            )
        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.data["user"]["role"] == "trainer"

        with django_capture_on_commit_callbacks(execute=True):
            resp_rec = client.post(
                "/api/gym/staff/",
                {
                    "email": "mgr_invited_rec@apex-a.com",
                    "role": "reception",
                    "full_name": "Tigist Reception",
                },
                format="json",
            )
        assert resp_rec.status_code == status.HTTP_201_CREATED
        assert resp_rec.data["user"]["role"] == "reception"

    def test_manager_cannot_invite_manager_account_returns_403(self, manager_a, gym_a):
        client = auth_client_for(manager_a, gym_a.subdomain)
        resp = client.post(
            "/api/gym/staff/",
            {
                "email": "manager_attempt@apex-a.com",
                "role": "manager",
            },
            format="json",
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN
        assert "Managers cannot invite or manage Manager accounts." in str(resp.data)

    def test_unauthorized_roles_cannot_invite_staff(
        self, trainer_a, reception_a, member_a, super_admin, gym_a
    ):
        # Trainer gets 403
        client_trainer = auth_client_for(trainer_a, gym_a.subdomain)
        resp = client_trainer.post(
            "/api/gym/staff/",
            {"email": "unauth@apex-a.com", "role": "reception"},
            format="json",
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN

        # Reception gets 403
        client_reception = auth_client_for(reception_a, gym_a.subdomain)
        resp = client_reception.post(
            "/api/gym/staff/",
            {"email": "unauth2@apex-a.com", "role": "reception"},
            format="json",
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN

        # Member gets 403
        client_member = auth_client_for(member_a, gym_a.subdomain)
        resp = client_member.post(
            "/api/gym/staff/",
            {"email": "unauth3@apex-a.com", "role": "reception"},
            format="json",
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN

        # Super Admin on apex host gets 403
        client_sa_apex = auth_client_for(super_admin)
        resp = client_sa_apex.post(
            "/api/gym/staff/",
            {"email": "unauth4@apex-a.com", "role": "reception"},
            format="json",
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN

        # Super Admin on gym host is rejected (401 tenant_mismatch by JWTAuthentication)
        client_sa_gym = auth_client_for(super_admin, gym_a.subdomain)
        resp = client_sa_gym.post(
            "/api/gym/staff/",
            {"email": "unauth5@apex-a.com", "role": "reception"},
            format="json",
        )
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

        # Anonymous gets 401
        anon_client = APIClient()
        anon_client.defaults["HTTP_HOST"] = f"{gym_a.subdomain}.localhost"
        resp = anon_client.post(
            "/api/gym/staff/",
            {"email": "unauth6@apex-a.com", "role": "reception"},
            format="json",
        )
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_invited_staff_cannot_login_before_setting_password(
        self, owner_a, gym_a, django_capture_on_commit_callbacks
    ):
        client = auth_client_for(owner_a, gym_a.subdomain)
        with django_capture_on_commit_callbacks(execute=True):
            resp = client.post(
                "/api/gym/staff/",
                {"email": "pending_staff@apex-a.com", "role": "trainer"},
                format="json",
            )
        assert resp.status_code == status.HTTP_201_CREATED

        # Attempt to log in before setting password
        anon_client = APIClient()
        anon_client.defaults["HTTP_HOST"] = f"{gym_a.subdomain}.localhost"
        login_resp = anon_client.post(
            "/api/auth/login/",
            {"email": "pending_staff@apex-a.com", "password": "AnyPassword123!"},
            format="json",
        )
        assert login_resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_invited_staff_completes_set_password_and_can_login(
        self, owner_a, gym_a, django_capture_on_commit_callbacks
    ):
        client = auth_client_for(owner_a, gym_a.subdomain)
        with django_capture_on_commit_callbacks(execute=True):
            resp = client.post(
                "/api/gym/staff/",
                {
                    "email": "activate_me@apex-a.com",
                    "role": "reception",
                    "full_name": "Active Reception",
                },
                format="json",
            )
        assert resp.status_code == status.HTTP_201_CREATED

        # Extract invite link token from sent email
        assert len(mail.outbox) == 1
        body = mail.outbox[0].body
        token = body.split("token=")[1].split()[0].strip()

        # Consume invite token to set password
        anon_client = APIClient()
        anon_client.defaults["HTTP_HOST"] = f"{gym_a.subdomain}.localhost"
        set_pw_resp = anon_client.post(
            "/api/auth/set-password/",
            {"token": token, "new_password": "ActivatedStaffPassword123!"},
            format="json",
        )
        assert set_pw_resp.status_code == status.HTTP_200_OK

        # Verify token is consumed
        set_pw_reused = anon_client.post(
            "/api/auth/set-password/",
            {"token": token, "new_password": "SecondPassword123!"},
            format="json",
        )
        assert set_pw_reused.status_code == status.HTTP_400_BAD_REQUEST

        # Log in with newly set password
        login_resp = anon_client.post(
            "/api/auth/login/",
            {
                "email": "activate_me@apex-a.com",
                "password": "ActivatedStaffPassword123!",
            },
            format="json",
        )
        assert login_resp.status_code == status.HTTP_200_OK
        assert "access" in login_resp.data
        assert "refresh" in login_resp.data
        assert login_resp.data["user"]["role"] == "reception"

    def test_duplicate_email_rejected_across_all_gyms(self, owner_a, owner_b, gym_a):
        client = auth_client_for(owner_a, gym_a.subdomain)
        # Attempt to invite with email of owner_b from Gym B
        resp = client.post(
            "/api/gym/staff/",
            {"email": owner_b.email, "role": "trainer"},
            format="json",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert "already exists" in str(resp.data)

    def test_owner_can_deactivate_manager_trainer_reception(
        self, owner_a, manager_a, trainer_a, reception_a, gym_a
    ):
        client = auth_client_for(owner_a, gym_a.subdomain)

        for staff_user in [manager_a, trainer_a, reception_a]:
            resp = client.post(
                f"/api/gym/staff/{staff_user.id}/deactivate/",
                format="json",
            )
            assert resp.status_code == status.HTTP_200_OK
            assert resp.data["user"]["is_active"] is False
            staff_user.refresh_from_db()
            assert staff_user.is_active is False

    def test_manager_can_deactivate_trainer_and_reception_only(
        self, manager_a, owner_a, trainer_a, reception_a, gym_a
    ):
        client = auth_client_for(manager_a, gym_a.subdomain)

        # Allowed: Manager deactivating trainer and reception
        resp_t = client.post(
            f"/api/gym/staff/{trainer_a.id}/deactivate/",
            format="json",
        )
        assert resp_t.status_code == status.HTTP_200_OK
        assert resp_t.data["user"]["is_active"] is False

        resp_r = client.post(
            f"/api/gym/staff/{reception_a.id}/deactivate/",
            format="json",
        )
        assert resp_r.status_code == status.HTTP_200_OK

        # Denied (403): Manager deactivating manager
        another_mgr = User.objects.create_user(
            email="another_mgr@apex-a.com",
            password="MgrPassword123!",
            gym=gym_a,
            role=User.ROLE_MANAGER,
        )
        resp_mgr = client.post(
            f"/api/gym/staff/{another_mgr.id}/deactivate/",
            format="json",
        )
        assert resp_mgr.status_code == status.HTTP_403_FORBIDDEN
        assert "Managers cannot deactivate Manager or Owner accounts." in str(
            resp_mgr.data
        )

        # Denied (403): Manager deactivating owner
        resp_owner = client.post(
            f"/api/gym/staff/{owner_a.id}/deactivate/",
            format="json",
        )
        assert resp_owner.status_code == status.HTTP_403_FORBIDDEN

    def test_owner_cannot_deactivate_owner(self, owner_a, gym_a):
        client = auth_client_for(owner_a, gym_a.subdomain)
        # Cannot deactivate self
        resp_self = client.post(
            f"/api/gym/staff/{owner_a.id}/deactivate/",
            format="json",
        )
        assert resp_self.status_code == status.HTTP_403_FORBIDDEN

    def test_deactivation_immediately_blocks_login_and_invalidates_jwt_tokens(
        self, owner_a, trainer_a, gym_a
    ):
        # 1. Staff obtains valid JWT tokens
        tokens = get_tokens_for_user(trainer_a)
        access_token = tokens["access"]
        refresh_token = tokens["refresh"]

        trainer_client = APIClient()
        trainer_client.defaults["HTTP_HOST"] = f"{gym_a.subdomain}.localhost"
        trainer_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")

        # Verify access token works initially
        resp_me = trainer_client.get("/api/auth/me/")
        assert resp_me.status_code == status.HTTP_200_OK

        # 2. Owner deactivates staff member
        owner_client = auth_client_for(owner_a, gym_a.subdomain)
        deact_resp = owner_client.post(
            f"/api/gym/staff/{trainer_a.id}/deactivate/",
            format="json",
        )
        assert deact_resp.status_code == status.HTTP_200_OK

        # 3. Existing access token is IMMEDIATELY rejected (401)
        resp_me_after = trainer_client.get("/api/auth/me/")
        assert resp_me_after.status_code == status.HTTP_401_UNAUTHORIZED

        # 4. Token refresh is rejected (401)
        anon_client = APIClient()
        anon_client.defaults["HTTP_HOST"] = f"{gym_a.subdomain}.localhost"
        refresh_resp = anon_client.post(
            "/api/auth/refresh/",
            {"refresh": refresh_token},
            format="json",
        )
        assert refresh_resp.status_code == status.HTTP_401_UNAUTHORIZED

        # 5. Password login is rejected (401)
        login_resp = anon_client.post(
            "/api/auth/login/",
            {"email": trainer_a.email, "password": "TrainerPassword123!"},
            format="json",
        )
        assert login_resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_deactivation_does_not_delete_user_row_and_has_no_hard_delete_route(
        self, owner_a, trainer_a, gym_a
    ):
        owner_client = auth_client_for(owner_a, gym_a.subdomain)
        owner_client.post(
            f"/api/gym/staff/{trainer_a.id}/deactivate/",
            format="json",
        )

        # Database row still exists
        assert User.all_objects.filter(id=trainer_a.id).exists() is True
        trainer_a.refresh_from_db()
        assert trainer_a.is_active is False

        # Attempt DELETE HTTP method on staff endpoints -> 405 Method Not Allowed
        del_resp = owner_client.delete("/api/gym/staff/")
        assert del_resp.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

        del_user_resp = owner_client.delete(f"/api/gym/staff/{trainer_a.id}/")
        assert del_user_resp.status_code == status.HTTP_404_NOT_FOUND

    def test_reactivation_restores_login_without_reviving_old_tokens(
        self, owner_a, trainer_a, gym_a
    ):
        old_tokens = get_tokens_for_user(trainer_a)
        owner_client = auth_client_for(owner_a, gym_a.subdomain)

        # Deactivate
        owner_client.post(
            f"/api/gym/staff/{trainer_a.id}/deactivate/",
            format="json",
        )
        trainer_a.refresh_from_db()
        assert trainer_a.is_active is False

        # Reactivate
        react_resp = owner_client.post(
            f"/api/gym/staff/{trainer_a.id}/reactivate/",
            format="json",
        )
        assert react_resp.status_code == status.HTTP_200_OK
        assert react_resp.data["user"]["is_active"] is True
        trainer_a.refresh_from_db()
        assert trainer_a.is_active is True

        # Fresh login works
        anon_client = APIClient()
        anon_client.defaults["HTTP_HOST"] = f"{gym_a.subdomain}.localhost"
        login_resp = anon_client.post(
            "/api/auth/login/",
            {"email": trainer_a.email, "password": "TrainerPassword123!"},
            format="json",
        )
        assert login_resp.status_code == status.HTTP_200_OK

        # Old tokens remain invalid (because password_changed_at was updated on deactivation)
        stale_client = APIClient()
        stale_client.defaults["HTTP_HOST"] = f"{gym_a.subdomain}.localhost"
        stale_client.credentials(HTTP_AUTHORIZATION=f"Bearer {old_tokens['access']}")
        assert (
            stale_client.get("/api/auth/me/").status_code
            == status.HTTP_401_UNAUTHORIZED
        )

    def test_cross_tenant_staff_isolation_returns_404(
        self, owner_a, owner_b, gym_a, gym_b
    ):
        # Gym B has a trainer
        trainer_b = User.objects.create_user(
            email="trainer_b@bole-b.com",
            password="TrainerPasswordB123!",
            gym=gym_b,
            role=User.ROLE_TRAINER,
        )

        # Gym A Owner attempts to deactivate Gym B Trainer -> 404 (IDOR protected)
        client_a = auth_client_for(owner_a, gym_a.subdomain)
        resp = client_a.post(
            f"/api/gym/staff/{trainer_b.id}/deactivate/",
            format="json",
        )
        assert resp.status_code == status.HTTP_404_NOT_FOUND
        assert resp.data["detail"] == "Staff member not found."

    def test_first_run_checklist_automated_upon_staff_creation(
        self, owner_a, gym_a, django_capture_on_commit_callbacks
    ):
        # Create fresh gym with only an owner
        fresh_gym = GymTenant.objects.create(
            name="Fresh Gym",
            subdomain="fresh-gym",
            tier="starter",
            currency="ETB",
            contact_name="Fresh Owner",
            contact_email="fresh@fresh.com",
            contact_phone="+251911999999",
            tls_confirmed_at=timezone.now(),
        )
        fresh_owner = User.objects.create_user(
            email="fresh_owner@fresh.com",
            password="FreshPassword123!",
            gym=fresh_gym,
            role=User.ROLE_OWNER,
        )

        checklist_before = get_first_run_checklist(fresh_gym)
        assert checklist_before["items"]["add_staff"]["completed"] is False

        # Owner invites a receptionist
        client = auth_client_for(fresh_owner, fresh_gym.subdomain)
        with django_capture_on_commit_callbacks(execute=True):
            resp = client.post(
                "/api/gym/staff/",
                {"email": "fresh_rec@fresh.com", "role": "reception"},
                format="json",
            )
        assert resp.status_code == status.HTTP_201_CREATED

        # Checklist updates automatically from real DB state
        checklist_after = get_first_run_checklist(fresh_gym)
        assert checklist_after["items"]["add_staff"]["completed"] is True
