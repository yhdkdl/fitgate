"""Tests for JWT authentication, tokens, host-scoped login, and session validity."""

from unittest.mock import patch

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.tokens import get_tokens_for_user
from apps.tenants.models import GymTenant


@pytest.mark.django_db
@pytest.mark.urls("apps.accounts.tests.urls")
class TestJWTAuthenticationAndSessionValidity:
    """Test JWT authentication class, 401 handling, session invalidation, and host scoping."""

    @pytest.fixture
    def setup_entities(self):
        """Create platform and gym entities for auth testing."""
        gym_a = GymTenant.objects.create(name="Apex Gym", subdomain="apexgym")
        gym_b = GymTenant.objects.create(name="Beta Gym", subdomain="betagym")

        super_admin = User.objects.create_superuser(
            email="admin@fitgate.org",
            password="SuperPassword123!",
        )

        gym_user = User.objects.create_user(
            email="member@apexgym.com",
            password="MemberPassword123!",
            role=User.ROLE_MEMBER,
            gym=gym_a,
        )

        return {
            "gym_a": gym_a,
            "gym_b": gym_b,
            "super_admin": super_admin,
            "gym_user": gym_user,
        }

    def test_protected_view_without_token_returns_401(self):
        """A request to a protected endpoint with no token returns 401 with WWW-Authenticate header."""
        client = APIClient()
        response = client.get("/api/health/")  # public
        assert response.status_code == 200

        # Protected dummy view with no token
        client = APIClient()
        response = client.get("/api/test/protected/")
        assert response.status_code == 401
        assert "WWW-Authenticate" in response.headers
        assert "Bearer" in response.headers["WWW-Authenticate"]

    def test_protected_view_with_invalid_token_returns_401(self):
        """A request with a malformed or invalid token returns 401."""
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer invalid-token-string")
        response = client.get("/api/test/protected/")
        assert response.status_code == 401

    def test_successful_login_returns_tokens_and_dashboard_config(self, setup_entities):
        """Valid credentials return access and refresh tokens, user summary, and dashboard."""
        client = APIClient()
        # Super Admin logs in on apex domain (localhost)
        response = client.post(
            "/api/auth/login/",
            {"email": "admin@fitgate.org", "password": "SuperPassword123!"},
            HTTP_HOST="localhost",
        )
        assert response.status_code == 200
        data = response.json()
        assert "access" in data
        assert "refresh" in data
        assert data["user"]["email"] == "admin@fitgate.org"
        assert data["user"]["role"] == "super_admin"
        assert data["dashboard"]["role"] == "super_admin"
        assert "widgets" in data["dashboard"]

    def test_refresh_issues_new_access_token(self, setup_entities):
        """POST /api/auth/refresh/ issues a new access token without requiring password."""
        user = setup_entities["super_admin"]
        tokens = get_tokens_for_user(user)

        client = APIClient()
        response = client.post(
            "/api/auth/refresh/",
            {"refresh": tokens["refresh"]},
            HTTP_HOST="localhost",
        )
        assert response.status_code == 200
        assert "access" in response.json()

    def test_logout_blacklists_refresh_token(self, setup_entities):
        """POST /api/auth/logout/ blacklists the refresh token so it cannot be reused."""
        user = setup_entities["super_admin"]
        tokens = get_tokens_for_user(user)

        client = APIClient()
        logout_response = client.post(
            "/api/auth/logout/",
            {"refresh": tokens["refresh"]},
            HTTP_HOST="localhost",
        )
        assert logout_response.status_code == 200
        assert logout_response.json()["detail"] == "Successfully logged out."

        # Attempt to use blacklisted refresh token
        refresh_response = client.post(
            "/api/auth/refresh/",
            {"refresh": tokens["refresh"]},
            HTTP_HOST="localhost",
        )
        assert refresh_response.status_code == 401

    def test_host_scoped_login_prevents_wrong_host_authentication(self, setup_entities):
        """
        Login is host-scoped:
        - At apex: gym user credentials find no user, return generic 401, failed_login_count unchanged.
        - On gym subdomain: super admin credentials find no user, return generic 401, failed_login_count unchanged.
        """
        gym_user = setup_entities["gym_user"]
        super_admin = setup_entities["super_admin"]
        initial_gym_count = gym_user.failed_login_count
        initial_admin_count = super_admin.failed_login_count

        client = APIClient()

        # 1. Gym user tries to log in on apex
        apex_response = client.post(
            "/api/auth/login/",
            {"email": gym_user.email, "password": "MemberPassword123!"},
            HTTP_HOST="localhost",
        )
        assert apex_response.status_code == 401
        assert apex_response.json() == {"detail": "Invalid credentials."}
        gym_user.refresh_from_db()
        assert gym_user.failed_login_count == initial_gym_count

        # 2. Super Admin tries to log in on gym subdomain
        subdomain_response = client.post(
            "/api/auth/login/",
            {"email": super_admin.email, "password": "SuperPassword123!"},
            HTTP_HOST="apexgym.localhost",
        )
        assert subdomain_response.status_code == 401
        assert subdomain_response.json() == {"detail": "Invalid credentials."}
        super_admin.refresh_from_db()
        assert super_admin.failed_login_count == initial_admin_count

        # 3. Gym user from Gym A tries to log in on Gym B subdomain
        gym_b_response = client.post(
            "/api/auth/login/",
            {"email": gym_user.email, "password": "MemberPassword123!"},
            HTTP_HOST="betagym.localhost",
        )
        assert gym_b_response.status_code == 401
        assert gym_b_response.json() == {"detail": "Invalid credentials."}
        gym_user.refresh_from_db()
        assert gym_user.failed_login_count == initial_gym_count

    def test_identical_generic_401_error_body_across_all_failure_modes(
        self, setup_entities
    ):
        """
        Verify every failure mode returns the exact same 401 body, status, and Content-Type:
        1. Unknown email
        2. Wrong password
        3. Wrong host
        4. Locked account
        5. Inactive account
        """
        gym_user = setup_entities["gym_user"]
        client = APIClient()

        # 1. Unknown email
        resp_unknown = client.post(
            "/api/auth/login/",
            {"email": "unknown@example.com", "password": "anypassword"},
            HTTP_HOST="apexgym.localhost",
        )

        # 2. Wrong password
        resp_wrong_pw = client.post(
            "/api/auth/login/",
            {"email": gym_user.email, "password": "WrongPassword123!"},
            HTTP_HOST="apexgym.localhost",
        )

        # 3. Wrong host
        resp_wrong_host = client.post(
            "/api/auth/login/",
            {"email": gym_user.email, "password": "MemberPassword123!"},
            HTTP_HOST="localhost",
        )

        # 4. Locked account
        gym_user.failed_login_count = 5
        gym_user.locked_until = pytest.importorskip(
            "django.utils.timezone"
        ).now() + pytest.importorskip("datetime").timedelta(minutes=15)
        gym_user.save()

        resp_locked = client.post(
            "/api/auth/login/",
            {"email": gym_user.email, "password": "MemberPassword123!"},
            HTTP_HOST="apexgym.localhost",
        )

        # 5. Inactive account
        gym_user.locked_until = None
        gym_user.is_active = False
        gym_user.save()

        resp_inactive = client.post(
            "/api/auth/login/",
            {"email": gym_user.email, "password": "MemberPassword123!"},
            HTTP_HOST="apexgym.localhost",
        )

        responses = [
            resp_unknown,
            resp_wrong_pw,
            resp_wrong_host,
            resp_locked,
            resp_inactive,
        ]

        for resp in responses:
            assert resp.status_code == 401
            assert resp.json() == {"detail": "Invalid credentials."}
            assert resp.headers.get("Content-Type") == "application/json"

    def test_timing_mitigation_dummy_password_check_called_for_unknown_user(self):
        """When an email is unknown or not on this host, dummy password check is executed."""
        client = APIClient()
        with patch(
            "apps.accounts.views.perform_dummy_password_check"
        ) as mock_dummy_check:
            client.post(
                "/api/auth/login/",
                {"email": "nonexistent@example.com", "password": "testpassword"},
                HTTP_HOST="localhost",
            )
            mock_dummy_check.assert_called_once_with("testpassword")

    def test_token_invalidation_on_deactivation(self, setup_entities):
        """A deactivated user's existing token is immediately rejected with 401."""
        gym_user = setup_entities["gym_user"]
        tokens = get_tokens_for_user(gym_user)

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

        # Initially valid on gym subdomain
        valid_resp = client.get("/api/test/protected/", HTTP_HOST="apexgym.localhost")
        assert valid_resp.status_code == 200

        # Deactivate user
        gym_user.is_active = False
        gym_user.save()

        # Next request with old token is rejected
        invalid_resp = client.get("/api/test/protected/", HTTP_HOST="apexgym.localhost")
        assert invalid_resp.status_code == 401

    def test_token_invalidation_on_password_change_via_set_password(
        self, setup_entities
    ):
        """
        Changing password directly through user.set_password() immediately invalidates
        old access token AND old refresh token.
        """
        gym_user = setup_entities["gym_user"]
        tokens = get_tokens_for_user(gym_user)

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

        # Token works initially
        resp = client.get("/api/test/protected/", HTTP_HOST="apexgym.localhost")
        assert resp.status_code == 200

        # Password changed directly via set_password() (e.g. by admin or command)
        gym_user.set_password("NewPassword456!")
        gym_user.save()

        # Access token is immediately rejected
        resp_after = client.get("/api/test/protected/", HTTP_HOST="apexgym.localhost")
        assert resp_after.status_code == 401

        # Refresh token is also rejected
        refresh_resp = client.post(
            "/api/auth/refresh/",
            {"refresh": tokens["refresh"]},
            HTTP_HOST="apexgym.localhost",
        )
        assert refresh_resp.status_code == 401

    def test_token_tenant_host_mismatch_returns_401(self, setup_entities):
        """
        Token gym_id must match the active request.tenant:
        - Gym A token used on Gym B domain returns 401.
        - Gym token used on apex domain returns 401.
        - Apex token used on gym domain returns 401.
        """
        gym_user = setup_entities["gym_user"]
        super_admin = setup_entities["super_admin"]

        gym_tokens = get_tokens_for_user(gym_user)
        admin_tokens = get_tokens_for_user(super_admin)

        client = APIClient()

        # 1. Gym A token on Gym B subdomain
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {gym_tokens['access']}")
        resp_mismatch_gym = client.get(
            "/api/test/protected/", HTTP_HOST="betagym.localhost"
        )
        assert resp_mismatch_gym.status_code == 401

        # 2. Gym A token on apex
        resp_gym_on_apex = client.get("/api/test/protected/", HTTP_HOST="localhost")
        assert resp_gym_on_apex.status_code == 401

        # 3. Super Admin token on gym subdomain
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {admin_tokens['access']}")
        resp_admin_on_gym = client.get(
            "/api/test/protected/", HTTP_HOST="apexgym.localhost"
        )
        assert resp_admin_on_gym.status_code == 401

    def test_refresh_token_at_wrong_host_rejected_with_401(self, setup_entities):
        """
        Refresh token host scoping matches access token rules:
        - Gym A refresh token used on Gym B returns 401.
        - Gym refresh token used on apex domain returns 401.
        - Super Admin refresh token used on gym domain returns 401.
        """
        gym_user = setup_entities["gym_user"]
        super_admin = setup_entities["super_admin"]

        gym_tokens = get_tokens_for_user(gym_user)
        admin_tokens = get_tokens_for_user(super_admin)

        client = APIClient()

        # 1. Gym A refresh token on Gym B subdomain
        resp_mismatch_gym = client.post(
            "/api/auth/refresh/",
            {"refresh": gym_tokens["refresh"]},
            HTTP_HOST="betagym.localhost",
        )
        assert resp_mismatch_gym.status_code == 401

        # 2. Gym A refresh token on apex domain
        resp_gym_on_apex = client.post(
            "/api/auth/refresh/",
            {"refresh": gym_tokens["refresh"]},
            HTTP_HOST="localhost",
        )
        assert resp_gym_on_apex.status_code == 401

        # 3. Super Admin refresh token on gym subdomain
        resp_admin_on_gym = client.post(
            "/api/auth/refresh/",
            {"refresh": admin_tokens["refresh"]},
            HTTP_HOST="apexgym.localhost",
        )
        assert resp_admin_on_gym.status_code == 401

    def test_token_claim_password_changed_at_is_integer_microseconds(
        self, setup_entities
    ):
        """
        Token password_changed_at claim is explicitly an integer representation of microseconds.
        """
        from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

        gym_user = setup_entities["gym_user"]
        tokens = get_tokens_for_user(gym_user)

        access_token = AccessToken(tokens["access"])
        refresh_token = RefreshToken(tokens["refresh"])

        assert isinstance(access_token["password_changed_at"], int)
        assert isinstance(refresh_token["password_changed_at"], int)
        assert access_token["password_changed_at"] > 0
        assert (
            refresh_token["password_changed_at"] == access_token["password_changed_at"]
        )
