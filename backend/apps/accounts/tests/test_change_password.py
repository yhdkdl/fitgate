"""Tests for POST /api/auth/change-password/ and change_password service."""

import pytest
from django.core.exceptions import ValidationError
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.services import change_password
from apps.accounts.tokens import get_tokens_for_user
from apps.tenants.models import GymTenant


@pytest.mark.django_db
class TestChangePasswordEndpointAndService:
    """Test change-password endpoint, service, password validation, and token invalidation."""

    @pytest.fixture
    def setup_user(self):
        """Create a gym and user."""
        gym = GymTenant.objects.create(name="FitCorp", subdomain="fitcorp")
        user = User.objects.create_user(
            email="member@fitcorp.com",
            password="OriginalPassword123!",
            role=User.ROLE_MEMBER,
            gym=gym,
            must_change_password=True,
        )
        return {"gym": gym, "user": user}

    def test_change_password_works_while_must_change_password_is_true_and_clears_it(
        self, setup_user
    ):
        """
        POST /api/auth/change-password/ succeeds even when must_change_password is True,
        and sets must_change_password to False.
        """
        user = setup_user["user"]
        assert user.must_change_password is True

        tokens = get_tokens_for_user(user)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

        response = client.post(
            "/api/auth/change-password/",
            {
                "current_password": "OriginalPassword123!",
                "new_password": "BrandNewSecurePassword123!",
            },
            HTTP_HOST="fitcorp.localhost",
        )
        assert response.status_code == 200
        data = response.json()
        assert "access" in data
        assert "refresh" in data
        assert "user" in data

        user.refresh_from_db()
        assert user.must_change_password is False
        assert user.check_password("BrandNewSecurePassword123!") is True

    def test_change_password_wrong_current_password_returns_400(self, setup_user):
        """POST /api/auth/change-password/ with incorrect current_password returns 400."""
        user = setup_user["user"]
        tokens = get_tokens_for_user(user)

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

        response = client.post(
            "/api/auth/change-password/",
            {
                "current_password": "WrongCurrentPassword123!",
                "new_password": "BrandNewSecurePassword123!",
            },
            HTTP_HOST="fitcorp.localhost",
        )
        assert response.status_code == 400
        assert "current_password" in response.json()

        # Database password remains unchanged
        user.refresh_from_db()
        assert user.check_password("OriginalPassword123!") is True

    def test_change_password_same_as_current_returns_400(self, setup_user):
        """POST /api/auth/change-password/ with new_password matching current_password returns 400."""
        user = setup_user["user"]
        tokens = get_tokens_for_user(user)

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

        response = client.post(
            "/api/auth/change-password/",
            {
                "current_password": "OriginalPassword123!",
                "new_password": "OriginalPassword123!",
            },
            HTTP_HOST="fitcorp.localhost",
        )
        assert response.status_code == 400
        assert (
            "new_password" in response.json()
            or "detail" in response.json()
            or "same" in str(response.json()).lower()
        )

    @pytest.mark.parametrize(
        "weak_password, reason",
        [
            ("Short1!", "too short (< 10 chars)"),
            ("password1234", "common password"),
            ("123456789012", "numeric-only"),
            ("member@fitcorp.com", "similar to email"),
        ],
    )
    def test_change_password_weak_password_rejected_with_400(
        self, setup_user, weak_password, reason
    ):
        """POST /api/auth/change-password/ rejects weak passwords per Django AUTH_PASSWORD_VALIDATORS."""
        user = setup_user["user"]
        tokens = get_tokens_for_user(user)

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

        response = client.post(
            "/api/auth/change-password/",
            {
                "current_password": "OriginalPassword123!",
                "new_password": weak_password,
            },
            HTTP_HOST="fitcorp.localhost",
        )
        assert response.status_code == 400
        assert "new_password" in response.json()

    def test_change_password_invalidates_old_access_and_refresh_tokens(
        self, setup_user
    ):
        """
        After password change:
        - Old access token returns 401 on protected endpoint.
        - Old refresh token returns 401 on /api/auth/refresh/ using fresh APIClient with NO credentials.
        - New tokens work.
        - Login with new password works (200).
        - Login with old password returns generic 401.
        """
        user = setup_user["user"]
        old_tokens = get_tokens_for_user(user)

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {old_tokens['access']}")

        # Change password
        response = client.post(
            "/api/auth/change-password/",
            {
                "current_password": "OriginalPassword123!",
                "new_password": "BrandNewSecurePassword123!",
            },
            HTTP_HOST="fitcorp.localhost",
        )
        assert response.status_code == 200
        new_tokens = response.json()

        # 1. Old access token returns 401 on protected endpoint
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {old_tokens['access']}")
        resp_old_access = client.get("/api/auth/me/", HTTP_HOST="fitcorp.localhost")
        assert resp_old_access.status_code == 401

        # 2. Old refresh token returns 401 on /api/auth/refresh/ using fresh client with NO credentials
        fresh_client = APIClient()
        resp_old_refresh = fresh_client.post(
            "/api/auth/refresh/",
            {"refresh": old_tokens["refresh"]},
            HTTP_HOST="fitcorp.localhost",
        )
        assert resp_old_refresh.status_code == 401

        # 3. New access token works on protected endpoint
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {new_tokens['access']}")
        resp_new_access = client.get("/api/auth/me/", HTTP_HOST="fitcorp.localhost")
        assert resp_new_access.status_code == 200

        # 4. Login with new password succeeds with 200
        login_client = APIClient()
        login_new = login_client.post(
            "/api/auth/login/",
            {
                "email": user.email,
                "password": "BrandNewSecurePassword123!",
            },
            HTTP_HOST="fitcorp.localhost",
        )
        assert login_new.status_code == 200

        # 5. Login with old password returns generic 401
        login_old = login_client.post(
            "/api/auth/login/",
            {
                "email": user.email,
                "password": "OriginalPassword123!",
            },
            HTTP_HOST="fitcorp.localhost",
        )
        assert login_old.status_code == 401
        assert login_old.json() == {"detail": "Invalid credentials."}

    def test_change_password_service_called_directly(self, setup_user):
        """Test the change_password service function directly."""
        user = setup_user["user"]

        # 1. Wrong current password raises ValidationError
        with pytest.raises(ValidationError) as exc_wrong:
            change_password(user, "IncorrectPassword!", "BrandNewSecurePassword123!")
        assert "current_password" in exc_wrong.value.message_dict

        # 2. Same password raises ValidationError
        with pytest.raises(ValidationError) as exc_same:
            change_password(user, "OriginalPassword123!", "OriginalPassword123!")
        assert (
            "new_password" in exc_same.value.message_dict
            or "__all__" in exc_same.value.message_dict
        )

        # 3. Weak password raises ValidationError
        with pytest.raises(ValidationError) as exc_weak:
            change_password(user, "OriginalPassword123!", "123")
        assert "new_password" in exc_weak.value.message_dict

        # 4. Valid password succeeds and clears must_change_password
        result = change_password(
            user, "OriginalPassword123!", "BrandNewSecurePassword123!"
        )
        assert "access" in result
        assert "refresh" in result
        assert "user" in result
        user.refresh_from_db()
        assert user.must_change_password is False
        assert user.check_password("BrandNewSecurePassword123!") is True
