"""Tests for password reset flow: request, confirmation, security properties, and service layer."""

import hashlib
import re
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.conf import settings
from django.core import mail
from django.core.exceptions import ValidationError
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import AuthToken, User
from apps.accounts.services import confirm_password_reset, request_password_reset
from apps.accounts.tokens import get_tokens_for_user
from apps.tenants.models import GymTenant


@pytest.mark.django_db
class TestPasswordResetSuite:
    """Comprehensive test suite for password reset (request and confirm)."""

    @pytest.fixture
    def setup_data(self):
        """Create gyms, users, and super admin."""
        gym_a = GymTenant.objects.create(name="Gym Alpha", subdomain="gyma")
        gym_b = GymTenant.objects.create(name="Gym Beta", subdomain="gymb")

        user_a = User.objects.create_user(
            email="user_a@gyma.com",
            password="OriginalPassword123!",
            role=User.ROLE_MEMBER,
            gym=gym_a,
            full_name="Alpha User",
        )
        user_b = User.objects.create_user(
            email="user_b@gymb.com",
            password="OriginalPassword123!",
            role=User.ROLE_MEMBER,
            gym=gym_b,
            full_name="Beta User",
        )
        inactive_user = User.objects.create_user(
            email="inactive@gyma.com",
            password="OriginalPassword123!",
            role=User.ROLE_MEMBER,
            gym=gym_a,
            is_active=False,
            full_name="Inactive User",
        )
        super_admin = User.objects.create_superuser(
            email="admin@fitgate.org",
            password="SuperPassword123!",
            full_name="Platform Admin",
        )

        return {
            "gym_a": gym_a,
            "gym_b": gym_b,
            "user_a": user_a,
            "user_b": user_b,
            "inactive_user": inactive_user,
            "super_admin": super_admin,
        }

    # =========================================================================
    # Request Tests
    # =========================================================================

    def test_request_valid_user_right_host_sends_email_and_stores_hash_only(
        self, setup_data
    ):
        """
        Valid active user requesting on their gym's host receives 200, an email is sent,
        and raw token is never stored in DB (only sha256 hex digest).
        """
        client = APIClient()
        response = client.post(
            "/api/auth/password-reset/",
            {"email": "user_a@gyma.com"},
            format="json",
            HTTP_HOST="gyma.localhost",
        )

        assert response.status_code == 200
        assert response.json() == {
            "detail": "If the account exists, a reset link has been sent."
        }
        assert response.headers["Content-Type"] == "application/json"

        assert len(mail.outbox) == 1
        sent_email = mail.outbox[0]
        assert "user_a@gyma.com" in sent_email.to
        assert "reset-password?token=" in sent_email.body
        assert "ignore this email" in sent_email.body.lower()
        assert "60 minutes" in sent_email.body

        # Extract raw token from the link
        match = re.search(r"token=([A-Za-z0-9_-]+)", sent_email.body)
        assert match is not None
        raw_token = match.group(1)

        # Confirm raw token is NOT in database
        assert not AuthToken.objects.filter(token_hash=raw_token).exists()

        # Confirm sha256 hash IS in database
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        stored_token = AuthToken.objects.filter(
            token_hash=token_hash, purpose=AuthToken.PURPOSE_PASSWORD_RESET
        ).first()
        assert stored_token is not None
        assert stored_token.user == setup_data["user_a"]
        assert stored_token.used_at is None
        assert stored_token.expires_at > timezone.now()

    def test_request_unknown_email_returns_identical_response_and_sends_no_email(
        self, setup_data
    ):
        """Unknown email returns identical 200 status, body, and headers without sending email."""
        client = APIClient()
        response = client.post(
            "/api/auth/password-reset/",
            {"email": "nobody@nowhere.com"},
            format="json",
            HTTP_HOST="gyma.localhost",
        )

        assert response.status_code == 200
        assert response.json() == {
            "detail": "If the account exists, a reset link has been sent."
        }
        assert response.headers["Content-Type"] == "application/json"
        assert len(mail.outbox) == 0

    def test_request_inactive_user_returns_identical_response_and_sends_no_email(
        self, setup_data
    ):
        """Inactive user returns identical 200 response and sends no email."""
        client = APIClient()
        response = client.post(
            "/api/auth/password-reset/",
            {"email": "inactive@gyma.com"},
            format="json",
            HTTP_HOST="gyma.localhost",
        )

        assert response.status_code == 200
        assert response.json() == {
            "detail": "If the account exists, a reset link has been sent."
        }
        assert len(mail.outbox) == 0

    def test_request_wrong_host_gym_a_user_on_gym_b_returns_identical_response_no_email(
        self, setup_data
    ):
        """Requesting password reset for gym A user on gym B's host behaves like unknown email."""
        client = APIClient()
        response = client.post(
            "/api/auth/password-reset/",
            {"email": "user_a@gyma.com"},
            format="json",
            HTTP_HOST="gymb.localhost",
        )

        assert response.status_code == 200
        assert response.json() == {
            "detail": "If the account exists, a reset link has been sent."
        }
        assert len(mail.outbox) == 0

    def test_request_apex_with_gym_user_email_returns_identical_response_no_email(
        self, setup_data
    ):
        """Requesting password reset for gym user at the apex returns identical 200 and no email."""
        client = APIClient()
        response = client.post(
            "/api/auth/password-reset/",
            {"email": "user_a@gyma.com"},
            format="json",
            HTTP_HOST="localhost",
        )

        assert response.status_code == 200
        assert response.json() == {
            "detail": "If the account exists, a reset link has been sent."
        }
        assert len(mail.outbox) == 0

    def test_request_super_admin_at_gym_subdomain_returns_identical_response_no_email(
        self, setup_data
    ):
        """Super admin requesting reset at a gym subdomain behaves like an unknown email."""
        client = APIClient()
        response = client.post(
            "/api/auth/password-reset/",
            {"email": "admin@fitgate.org"},
            format="json",
            HTTP_HOST="gyma.localhost",
        )

        assert response.status_code == 200
        assert response.json() == {
            "detail": "If the account exists, a reset link has been sent."
        }
        assert len(mail.outbox) == 0

    def test_request_malformed_bodies_return_identical_200_never_500(self, setup_data):
        """Malformed payloads (non-dict, non-string, missing field) return identical 200, never 500."""
        client = APIClient()
        malformed_payloads = [
            ["user_a@gyma.com"],
            "user_a@gyma.com",
            {"email": 12345},
            {"email": True},
            {"email": None},
            {},
            {"other_key": "some_value"},
        ]

        for payload in malformed_payloads:
            response = client.post(
                "/api/auth/password-reset/",
                payload,
                format="json",
                HTTP_HOST="gyma.localhost",
            )
            assert response.status_code == 200
            assert response.json() == {
                "detail": "If the account exists, a reset link has been sent."
            }
            assert response.headers["Content-Type"] == "application/json"

        assert len(mail.outbox) == 0

    def test_request_link_ignores_hostile_headers_and_uses_tenant_subdomain_and_domain(
        self, setup_data
    ):
        """
        The reset link is built from user's gym subdomain and settings.DOMAIN,
        never from request Host or X-Forwarded-Host headers.
        """
        client = APIClient()
        client.post(
            "/api/auth/password-reset/",
            {"email": "user_a@gyma.com"},
            format="json",
            HTTP_HOST="gyma.localhost",
            HTTP_X_FORWARDED_HOST="evil-attacker.com",
            HTTP_X_FORWARDED_PROTO="https",
        )

        assert len(mail.outbox) == 1
        body = mail.outbox[0].body
        expected_scheme = getattr(settings, "PUBLIC_URL_SCHEME", "http")
        expected_prefix = (
            f"{expected_scheme}://gyma.{settings.DOMAIN}/reset-password?token="
        )
        assert expected_prefix in body
        assert "evil-attacker.com" not in body

    def test_request_cooldown_second_request_within_cooldown_sends_nothing(
        self, setup_data
    ):
        """Second reset request within PASSWORD_RESET_COOLDOWN_SECONDS sends no new email."""
        client = APIClient()

        # First request -> sends email
        resp1 = client.post(
            "/api/auth/password-reset/",
            {"email": "user_a@gyma.com"},
            format="json",
            HTTP_HOST="gyma.localhost",
        )
        assert resp1.status_code == 200
        assert len(mail.outbox) == 1

        # Second request immediately -> silent, sends nothing, same response
        resp2 = client.post(
            "/api/auth/password-reset/",
            {"email": "user_a@gyma.com"},
            format="json",
            HTTP_HOST="gyma.localhost",
        )
        assert resp2.status_code == 200
        assert resp2.json() == resp1.json()
        assert len(mail.outbox) == 1
        assert AuthToken.objects.filter(user=setup_data["user_a"]).count() == 1

    def test_request_cooldown_after_cooldown_new_token_invalidates_old_one(
        self, setup_data
    ):
        """Request after cooldown period creates a new token and invalidates the previous unused one."""
        client = APIClient()

        # First request
        client.post(
            "/api/auth/password-reset/",
            {"email": "user_a@gyma.com"},
            format="json",
            HTTP_HOST="gyma.localhost",
        )
        assert len(mail.outbox) == 1
        first_token = AuthToken.objects.get(user=setup_data["user_a"])
        assert first_token.used_at is None

        # Simulate passage of cooldown time (e.g. 130s ago)
        cooldown_seconds = getattr(settings, "PASSWORD_RESET_COOLDOWN_SECONDS", 120)
        past_time = timezone.now() - timedelta(seconds=cooldown_seconds + 10)
        AuthToken.objects.filter(pk=first_token.pk).update(created_at=past_time)

        # Second request after cooldown
        client.post(
            "/api/auth/password-reset/",
            {"email": "user_a@gyma.com"},
            format="json",
            HTTP_HOST="gyma.localhost",
        )
        assert len(mail.outbox) == 2

        first_token.refresh_from_db()
        assert first_token.used_at is not None  # Old token invalidated!

        second_token = (
            AuthToken.objects.filter(user=setup_data["user_a"])
            .exclude(pk=first_token.pk)
            .first()
        )
        assert second_token is not None
        assert second_token.used_at is None

    def test_request_send_mail_raising_still_returns_same_200(self, setup_data):
        """If send_mail raises an exception, it is logged and the endpoint still returns 200."""
        client = APIClient()

        with patch(
            "apps.accounts.notifications.send_mail",
            side_effect=RuntimeError("SMTP down"),
        ):
            response = client.post(
                "/api/auth/password-reset/",
                {"email": "user_a@gyma.com"},
                format="json",
                HTTP_HOST="gyma.localhost",
            )

        assert response.status_code == 200
        assert response.json() == {
            "detail": "If the account exists, a reset link has been sent."
        }

    # =========================================================================
    # Confirm Tests
    # =========================================================================

    def _get_reset_token_for(self, email, host="gyma.localhost"):
        """Helper to request password reset and extract raw token from outbox."""
        mail.outbox.clear()
        client = APIClient()
        resp = client.post(
            "/api/auth/password-reset/",
            {"email": email},
            format="json",
            HTTP_HOST=host,
        )
        assert resp.status_code == 200
        assert len(mail.outbox) == 1
        body = mail.outbox[0].body
        match = re.search(r"token=([A-Za-z0-9_-]+)", body)
        assert match is not None
        return match.group(1)

    def test_confirm_works_once_and_second_use_returns_token_invalid(self, setup_data):
        """Password reset token works once, and reusing it returns token_invalid."""
        raw_token = self._get_reset_token_for("user_a@gyma.com")
        client = APIClient()

        # First use -> success
        resp1 = client.post(
            "/api/auth/password-reset/confirm/",
            {"token": raw_token, "new_password": "NewStrongPassword123!"},
            format="json",
            HTTP_HOST="gyma.localhost",
        )
        assert resp1.status_code == 200
        assert resp1.json() == {"detail": "password_reset_complete"}

        # Second use -> token_invalid
        resp2 = client.post(
            "/api/auth/password-reset/confirm/",
            {"token": raw_token, "new_password": "AnotherPassword123!"},
            format="json",
            HTTP_HOST="gyma.localhost",
        )
        assert resp2.status_code == 400
        assert resp2.json() == {"detail": "token_invalid"}

    def test_confirm_expired_token_returns_token_expired(self, setup_data):
        """An expired token returns 400 token_expired."""
        raw_token = self._get_reset_token_for("user_a@gyma.com")
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

        # Expire token
        AuthToken.objects.filter(token_hash=token_hash).update(
            expires_at=timezone.now() - timedelta(minutes=5)
        )

        client = APIClient()
        response = client.post(
            "/api/auth/password-reset/confirm/",
            {"token": raw_token, "new_password": "NewStrongPassword123!"},
            format="json",
            HTTP_HOST="gyma.localhost",
        )
        assert response.status_code == 400
        assert response.json() == {"detail": "token_expired"}

    def test_confirm_unknown_token_returns_token_invalid(self, setup_data):
        """Unknown token returns 400 token_invalid."""
        client = APIClient()
        response = client.post(
            "/api/auth/password-reset/confirm/",
            {
                "token": "totally-unknown-token-value",
                "new_password": "NewStrongPassword123!",
            },
            format="json",
            HTTP_HOST="gyma.localhost",
        )
        assert response.status_code == 400
        assert response.json() == {"detail": "token_invalid"}

    def test_confirm_token_for_gym_a_used_on_gym_b_or_apex_returns_token_invalid(
        self, setup_data
    ):
        """
        Token for Gym A user submitted on Gym B host or apex returns token_invalid,
        and remains usable on the correct host.
        """
        raw_token = self._get_reset_token_for("user_a@gyma.com")
        client = APIClient()

        # Submit on Gym B host
        resp_b = client.post(
            "/api/auth/password-reset/confirm/",
            {"token": raw_token, "new_password": "NewStrongPassword123!"},
            format="json",
            HTTP_HOST="gymb.localhost",
        )
        assert resp_b.status_code == 400
        assert resp_b.json() == {"detail": "token_invalid"}

        # Submit on apex host
        resp_apex = client.post(
            "/api/auth/password-reset/confirm/",
            {"token": raw_token, "new_password": "NewStrongPassword123!"},
            format="json",
            HTTP_HOST="localhost",
        )
        assert resp_apex.status_code == 400
        assert resp_apex.json() == {"detail": "token_invalid"}

        # Still works on correct host
        resp_ok = client.post(
            "/api/auth/password-reset/confirm/",
            {"token": raw_token, "new_password": "NewStrongPassword123!"},
            format="json",
            HTTP_HOST="gyma.localhost",
        )
        assert resp_ok.status_code == 200
        assert resp_ok.json() == {"detail": "password_reset_complete"}

    def test_confirm_weak_password_returns_400_and_token_remains_usable(
        self, setup_data
    ):
        """
        A weak password returns 400 without consuming the token, allowing
        the user to submit a valid password with the same token afterwards.
        """
        raw_token = self._get_reset_token_for("user_a@gyma.com")
        client = APIClient()

        # Weak password attempt (short password)
        resp_weak = client.post(
            "/api/auth/password-reset/confirm/",
            {"token": raw_token, "new_password": "short"},
            format="json",
            HTTP_HOST="gyma.localhost",
        )
        assert resp_weak.status_code == 400
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        token_obj = AuthToken.objects.get(token_hash=token_hash)
        assert token_obj.used_at is None  # Token was NOT consumed

        # Resubmit with strong password -> succeeds
        resp_good = client.post(
            "/api/auth/password-reset/confirm/",
            {"token": raw_token, "new_password": "ValidStrongPassword123!"},
            format="json",
            HTTP_HOST="gyma.localhost",
        )
        assert resp_good.status_code == 200
        assert resp_good.json() == {"detail": "password_reset_complete"}

        token_obj.refresh_from_db()
        assert token_obj.used_at is not None  # Consumed now

    def test_confirm_double_submit_sequential_confirms_exactly_one_success(
        self, setup_data
    ):
        """Two sequential confirms with the exact same token yield exactly one success."""
        raw_token = self._get_reset_token_for("user_a@gyma.com")
        client = APIClient()

        resp1 = client.post(
            "/api/auth/password-reset/confirm/",
            {"token": raw_token, "new_password": "FirstAttemptPassword123!"},
            format="json",
            HTTP_HOST="gyma.localhost",
        )
        resp2 = client.post(
            "/api/auth/password-reset/confirm/",
            {"token": raw_token, "new_password": "SecondAttemptPassword123!"},
            format="json",
            HTTP_HOST="gyma.localhost",
        )

        assert resp1.status_code == 200
        assert resp1.json() == {"detail": "password_reset_complete"}
        assert resp2.status_code == 400
        assert resp2.json() == {"detail": "token_invalid"}

    def test_confirm_success_invalidates_old_access_and_refresh_tokens(
        self, setup_data
    ):
        """
        Successful password reset updates password_changed_at, immediately invalidating
        existing access and refresh tokens. Refreshing with old refresh token fails with 401.
        """
        user = setup_data["user_a"]
        old_tokens = get_tokens_for_user(user)

        # Confirm old access token was working
        client_auth = APIClient()
        client_auth.credentials(HTTP_AUTHORIZATION=f"Bearer {old_tokens['access']}")
        resp_me_before = client_auth.get("/api/auth/me/", HTTP_HOST="gyma.localhost")
        assert resp_me_before.status_code == 200

        # Perform password reset
        raw_token = self._get_reset_token_for(user.email)
        client = APIClient()
        resp_confirm = client.post(
            "/api/auth/password-reset/confirm/",
            {"token": raw_token, "new_password": "BrandNewPassword123!"},
            format="json",
            HTTP_HOST="gyma.localhost",
        )
        assert resp_confirm.status_code == 200

        # Old access token is now rejected
        resp_me_after = client_auth.get("/api/auth/me/", HTTP_HOST="gyma.localhost")
        assert resp_me_after.status_code == 401

        # Old refresh token is rejected on fresh APIClient without credentials
        fresh_client = APIClient()
        resp_refresh = fresh_client.post(
            "/api/auth/refresh/",
            {"refresh": old_tokens["refresh"]},
            format="json",
            HTTP_HOST="gyma.localhost",
        )
        assert resp_refresh.status_code == 401

    def test_confirm_success_clears_lockout_and_must_change_password(self, setup_data):
        """Password reset clears failed_login_count, locked_until, and must_change_password."""
        user = setup_data["user_a"]
        user.failed_login_count = 5
        user.locked_until = timezone.now() + timedelta(minutes=15)
        user.must_change_password = True
        user.save()

        raw_token = self._get_reset_token_for(user.email)
        client = APIClient()
        resp = client.post(
            "/api/auth/password-reset/confirm/",
            {"token": raw_token, "new_password": "BrandNewPassword123!"},
            format="json",
            HTTP_HOST="gyma.localhost",
        )
        assert resp.status_code == 200

        user.refresh_from_db()
        assert user.failed_login_count == 0
        assert user.locked_until is None
        assert user.must_change_password is False

    def test_confirm_login_with_new_password_works_and_old_gives_generic_401(
        self, setup_data
    ):
        """After reset, login succeeds with new password and fails with generic 401 on old."""
        user = setup_data["user_a"]
        raw_token = self._get_reset_token_for(user.email)
        client = APIClient()

        resp_reset = client.post(
            "/api/auth/password-reset/confirm/",
            {"token": raw_token, "new_password": "NewSecretPassword123!"},
            format="json",
            HTTP_HOST="gyma.localhost",
        )
        assert resp_reset.status_code == 200

        # Old password login -> 401 generic
        resp_old_login = client.post(
            "/api/auth/login/",
            {"email": user.email, "password": "OriginalPassword123!"},
            format="json",
            HTTP_HOST="gyma.localhost",
        )
        assert resp_old_login.status_code == 401
        assert resp_old_login.json() == {"detail": "Invalid credentials."}

        # New password login -> 200 with tokens
        resp_new_login = client.post(
            "/api/auth/login/",
            {"email": user.email, "password": "NewSecretPassword123!"},
            format="json",
            HTTP_HOST="gyma.localhost",
        )
        assert resp_new_login.status_code == 200
        assert "access" in resp_new_login.json()
        assert "refresh" in resp_new_login.json()

    def test_confirm_all_other_unused_reset_tokens_of_user_are_dead(self, setup_data):
        """Confirming one reset token marks all other unused reset tokens for that user as used."""
        user = setup_data["user_a"]

        # Directly create two reset tokens for user
        token1_raw = "token-number-one-unique-1"
        token2_raw = "token-number-two-unique-2"
        h1 = hashlib.sha256(token1_raw.encode("utf-8")).hexdigest()
        h2 = hashlib.sha256(token2_raw.encode("utf-8")).hexdigest()
        now = timezone.now()

        t1 = AuthToken.objects.create(
            user=user,
            purpose=AuthToken.PURPOSE_PASSWORD_RESET,
            token_hash=h1,
            expires_at=now + timedelta(hours=1),
        )
        t2 = AuthToken.objects.create(
            user=user,
            purpose=AuthToken.PURPOSE_PASSWORD_RESET,
            token_hash=h2,
            expires_at=now + timedelta(hours=1),
        )

        client = APIClient()
        resp = client.post(
            "/api/auth/password-reset/confirm/",
            {"token": token1_raw, "new_password": "NewPassword123!"},
            format="json",
            HTTP_HOST="gyma.localhost",
        )
        assert resp.status_code == 200

        t1.refresh_from_db()
        t2.refresh_from_db()
        assert t1.used_at is not None
        assert t2.used_at is not None

        # Trying to use t2 fails as token_invalid
        resp2 = client.post(
            "/api/auth/password-reset/confirm/",
            {"token": token2_raw, "new_password": "AnotherNewPassword123!"},
            format="json",
            HTTP_HOST="gyma.localhost",
        )
        assert resp2.status_code == 400
        assert resp2.json() == {"detail": "token_invalid"}

    def test_confirm_super_admin_reset_works_at_apex(self, setup_data):
        """Super Admin password reset request and confirm succeed at the apex domain."""
        super_admin = setup_data["super_admin"]
        raw_token = self._get_reset_token_for(super_admin.email, host="localhost")

        client = APIClient()
        resp = client.post(
            "/api/auth/password-reset/confirm/",
            {"token": raw_token, "new_password": "NewAdminPassword123!"},
            format="json",
            HTTP_HOST="localhost",
        )
        assert resp.status_code == 200
        assert resp.json() == {"detail": "password_reset_complete"}

        # Login at apex works with new password
        resp_login = client.post(
            "/api/auth/login/",
            {"email": super_admin.email, "password": "NewAdminPassword123!"},
            format="json",
            HTTP_HOST="localhost",
        )
        assert resp_login.status_code == 200

    def test_direct_service_calls_request_and_confirm(self, setup_data):
        """Direct invocation of request_password_reset and confirm_password_reset services."""
        user = setup_data["user_a"]
        gym = setup_data["gym_a"]

        # Direct service call to request
        mail.outbox.clear()
        raw_token = request_password_reset(email=user.email, tenant=gym)
        assert raw_token is not None
        assert len(mail.outbox) == 1

        # Direct service call on wrong tenant returns None
        assert request_password_reset(email=user.email, tenant=None) is None
        assert (
            request_password_reset(email=user.email, tenant=setup_data["gym_b"]) is None
        )

        # Direct service call to confirm with wrong tenant raises ValidationError
        with pytest.raises(ValidationError) as exc:
            confirm_password_reset(
                raw_token=raw_token,
                new_password="NewPassword123!",
                tenant=setup_data["gym_b"],
            )
        assert "token_invalid" in str(exc.value)

        # Direct service call to confirm with right tenant succeeds
        result = confirm_password_reset(
            raw_token=raw_token,
            new_password="NewPassword123!",
            tenant=gym,
        )
        assert result == {"detail": "password_reset_complete"}
