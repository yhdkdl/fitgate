"""Tests for the /api/auth/me/ profile endpoint (GET and PATCH)."""

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.tokens import get_tokens_for_user
from apps.tenants.models import GymTenant


@pytest.mark.django_db
class TestUserProfileEndpoint:
    """Test GET and PATCH /api/auth/me/ across roles, tenancy scoping, validations, and security."""

    @pytest.fixture
    def setup_data(self):
        """Create gyms and users for multi-tenant profile tests."""
        gym_a = GymTenant.objects.create(name="Alpha Gym", subdomain="alpha")
        gym_b = GymTenant.objects.create(name="Beta Gym", subdomain="beta")

        super_admin = User.objects.create_superuser(
            email="admin@fitgate.org",
            password="AdminPassword123!",
        )

        owner_a = User.objects.create_user(
            email="owner@alpha.com",
            password="OwnerPassword123!",
            role=User.ROLE_OWNER,
            gym=gym_a,
        )

        member_a1 = User.objects.create_user(
            email="member1@alpha.com",
            password="MemberPassword123!",
            role=User.ROLE_MEMBER,
            gym=gym_a,
        )

        member_a2 = User.objects.create_user(
            email="member2@alpha.com",
            password="MemberPassword123!",
            role=User.ROLE_MEMBER,
            gym=gym_a,
        )

        member_b = User.objects.create_user(
            email="member@beta.com",
            password="MemberPassword123!",
            role=User.ROLE_MEMBER,
            gym=gym_b,
        )

        return {
            "gym_a": gym_a,
            "gym_b": gym_b,
            "super_admin": super_admin,
            "owner_a": owner_a,
            "member_a1": member_a1,
            "member_a2": member_a2,
            "member_b": member_b,
        }

    def test_get_me_returns_only_callers_own_data_across_users_and_gyms(
        self, setup_data
    ):
        """
        GET /api/auth/me/ returns only the caller's own data, even when other users
        exist in the same gym or in different gyms.
        """
        member_a1 = setup_data["member_a1"]
        member_a2 = setup_data["member_a2"]
        member_b = setup_data["member_b"]

        client = APIClient()

        # 1. Member A1 in Gym A
        tokens_a1 = get_tokens_for_user(member_a1)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens_a1['access']}")
        resp_a1 = client.get("/api/auth/me/", HTTP_HOST="alpha.localhost")
        assert resp_a1.status_code == 200
        data_a1 = resp_a1.json()
        assert data_a1["id"] == str(member_a1.id)
        assert data_a1["email"] == member_a1.email
        assert data_a1["role"] == User.ROLE_MEMBER
        assert data_a1["gym_id"] == str(setup_data["gym_a"].id)
        assert "full_name" in data_a1
        assert "phone" in data_a1
        assert "must_change_password" in data_a1
        assert data_a1["id"] != str(member_a2.id)

        # 2. Member A2 in Gym A
        tokens_a2 = get_tokens_for_user(member_a2)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens_a2['access']}")
        resp_a2 = client.get("/api/auth/me/", HTTP_HOST="alpha.localhost")
        assert resp_a2.status_code == 200
        assert resp_a2.json()["id"] == str(member_a2.id)
        assert resp_a2.json()["email"] == member_a2.email

        # 3. Member B in Gym B
        tokens_b = get_tokens_for_user(member_b)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens_b['access']}")
        resp_b = client.get("/api/auth/me/", HTTP_HOST="beta.localhost")
        assert resp_b.status_code == 200
        assert resp_b.json()["id"] == str(member_b.id)
        assert resp_b.json()["gym_id"] == str(setup_data["gym_b"].id)

    @pytest.mark.parametrize(
        "role_name, host",
        [
            (User.ROLE_SUPER_ADMIN, "localhost"),
            (User.ROLE_OWNER, "alpha.localhost"),
            (User.ROLE_MANAGER, "alpha.localhost"),
            (User.ROLE_TRAINER, "alpha.localhost"),
            (User.ROLE_RECEPTION, "alpha.localhost"),
            (User.ROLE_MEMBER, "alpha.localhost"),
        ],
    )
    def test_patch_me_updates_name_and_phone_for_each_role(
        self, setup_data, role_name, host
    ):
        """
        PATCH /api/auth/me/ successfully updates full_name and phone for each role.
        """
        gym = None if role_name == User.ROLE_SUPER_ADMIN else setup_data["gym_a"]
        user = User.objects.create_user(
            email=f"{role_name}@fitgate.test",
            password="RolePassword123!",
            role=role_name,
            gym=gym,
        )

        tokens = get_tokens_for_user(user)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

        payload = {
            "full_name": "Abebe Bikila",
            "phone": "+251 91 123 4567",
        }
        response = client.patch("/api/auth/me/", payload, HTTP_HOST=host)
        assert response.status_code == 200
        data = response.json()
        assert data["full_name"] == "Abebe Bikila"
        assert data["phone"] == "+251 91 123 4567"

        user.refresh_from_db()
        assert user.full_name == "Abebe Bikila"
        assert user.phone == "+251 91 123 4567"

        # Also verify blank phone clears it
        clear_resp = client.patch("/api/auth/me/", {"phone": ""}, HTTP_HOST=host)
        assert clear_resp.status_code == 200
        assert clear_resp.json()["phone"] == ""
        user.refresh_from_db()
        assert user.phone == ""

    @pytest.mark.parametrize(
        "invalid_phone",
        [
            "12345",  # too short (< 7 chars)
            "+251911234567890123456",  # too long (> 20 chars)
            "phone-with-letters",  # letters not allowed
            "++25191123456",  # more than one leading plus
            "251911234+56",  # plus in the middle
            "@#$%^&*()",  # invalid symbols
        ],
    )
    def test_patch_me_invalid_phone_returns_400(self, setup_data, invalid_phone):
        """PATCH /api/auth/me/ with invalid phone format returns 400."""
        member = setup_data["member_a1"]
        tokens = get_tokens_for_user(member)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

        response = client.patch(
            "/api/auth/me/", {"phone": invalid_phone}, HTTP_HOST="alpha.localhost"
        )
        assert response.status_code == 400
        assert "phone" in response.json()

    def test_patch_me_whitespace_only_name_returns_400(self, setup_data):
        """PATCH /api/auth/me/ with whitespace-only full_name returns 400."""
        member = setup_data["member_a1"]
        tokens = get_tokens_for_user(member)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

        response = client.patch(
            "/api/auth/me/", {"full_name": "   "}, HTTP_HOST="alpha.localhost"
        )
        assert response.status_code == 400
        assert "full_name" in response.json()

    @pytest.mark.parametrize(
        "privileged_field, attempt_value",
        [
            ("role", User.ROLE_SUPER_ADMIN),
            ("gym", "gym-id-value"),
            ("gym_id", "some-uuid"),
            ("is_active", False),
            ("status", "expired"),
            ("max_clients", 100),
            ("email", "hacked@alpha.com"),
            ("must_change_password", False),
            ("password_changed_at", 123456),
            ("failed_login_count", 99),
            ("locked_until", "2030-01-01T00:00:00Z"),
            ("is_staff", True),
            ("is_superuser", True),
        ],
    )
    def test_patch_me_privileged_field_rejected_with_400_and_db_unchanged(
        self, setup_data, privileged_field, attempt_value
    ):
        """
        PATCH /api/auth/me/ with any privileged field returns 400 naming the field,
        and leaves the database row completely unchanged.
        """
        member = setup_data["member_a1"]
        orig_role = member.role
        orig_email = member.email
        orig_active = member.is_active

        tokens = get_tokens_for_user(member)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

        payload = {privileged_field: attempt_value}
        response = client.patch(
            "/api/auth/me/",
            payload,
            HTTP_HOST="alpha.localhost",
        )
        assert response.status_code == 400
        err_data = response.json()
        assert (
            privileged_field in err_data
            or privileged_field in str(err_data)
            or "privileged" in str(err_data).lower()
        )

        member.refresh_from_db()
        assert member.role == orig_role
        assert member.email == orig_email
        assert member.is_active == orig_active

    def test_me_disallowed_http_methods_return_405(self, setup_data):
        """PUT and DELETE methods on /api/auth/me/ return 405 Method Not Allowed."""
        member = setup_data["member_a1"]
        tokens = get_tokens_for_user(member)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

        put_resp = client.put(
            "/api/auth/me/", {"full_name": "Test"}, HTTP_HOST="alpha.localhost"
        )
        assert put_resp.status_code == 405

        del_resp = client.delete("/api/auth/me/", HTTP_HOST="alpha.localhost")
        assert del_resp.status_code == 405

    def test_me_without_token_returns_401(self, setup_data):
        """Requesting /api/auth/me/ without an Authorization header returns 401."""
        client = APIClient()
        response = client.get("/api/auth/me/", HTTP_HOST="alpha.localhost")
        assert response.status_code == 401

        apex_resp = client.get("/api/auth/me/", HTTP_HOST="localhost")
        assert apex_resp.status_code == 401

    def test_me_with_wrong_host_token_returns_401(self, setup_data):
        """A valid token used at the wrong gym host returns 401."""
        member_a = setup_data["member_a1"]
        tokens_a = get_tokens_for_user(member_a)

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens_a['access']}")

        # Attempting to use Gym A token at Gym B subdomain
        response = client.get("/api/auth/me/", HTTP_HOST="beta.localhost")
        assert response.status_code == 401

    def test_me_blocked_if_must_change_password_is_true(self, setup_data):
        """
        While must_change_password is True, /api/auth/me/ returns 403 password_change_required.
        """
        member = setup_data["member_a1"]
        member.must_change_password = True
        member.save()

        tokens = get_tokens_for_user(member)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

        get_resp = client.get("/api/auth/me/", HTTP_HOST="alpha.localhost")
        assert get_resp.status_code == 403
        assert get_resp.json() == {"detail": "password_change_required"}

        patch_resp = client.patch(
            "/api/auth/me/", {"full_name": "Changed"}, HTTP_HOST="alpha.localhost"
        )
        assert patch_resp.status_code == 403
        assert patch_resp.json() == {"detail": "password_change_required"}
