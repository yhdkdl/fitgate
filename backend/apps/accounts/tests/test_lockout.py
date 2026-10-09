"""Tests for login lockout, counter tracking, and notifications."""

from datetime import timedelta

import pytest
from django.core import mail
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.tenants.models import GymTenant


@pytest.mark.django_db
class TestLoginLockoutAndNotifications:
    """Test account lockout after 5 failures, counter resets, and owner email notifications."""

    @pytest.fixture
    def setup_data(self):
        """Create a gym, owner, member, and super admin."""
        gym = GymTenant.objects.create(name="FitCorp", subdomain="fitcorp")

        owner = User.objects.create_user(
            email="owner@fitcorp.com",
            password="OwnerPassword123!",
            role=User.ROLE_OWNER,
            gym=gym,
        )

        member = User.objects.create_user(
            email="member@fitcorp.com",
            password="MemberPassword123!",
            role=User.ROLE_MEMBER,
            gym=gym,
        )

        super_admin = User.objects.create_superuser(
            email="admin@fitgate.org",
            password="SuperPassword123!",
        )

        return {
            "gym": gym,
            "owner": owner,
            "member": member,
            "super_admin": super_admin,
        }

    def test_failed_login_increments_counter(self, setup_data):
        """Each incorrect password attempt increments failed_login_count."""
        member = setup_data["member"]
        client = APIClient()

        for attempt in range(1, 5):
            response = client.post(
                "/api/auth/login/",
                {"email": member.email, "password": "WrongPassword!"},
                HTTP_HOST="fitcorp.localhost",
            )
            assert response.status_code == 401
            member.refresh_from_db()
            assert member.failed_login_count == attempt
            assert member.locked_until is None

    def test_fifth_consecutive_failure_locks_account_and_emails_owner(self, setup_data):
        """
        On the 5th consecutive failure, the account is locked for LOGIN_LOCKOUT_MINUTES
        and an alert email is sent to the gym's Owner.
        """
        member = setup_data["member"]
        client = APIClient()

        mail.outbox.clear()

        # 4 failures
        for _ in range(4):
            client.post(
                "/api/auth/login/",
                {"email": member.email, "password": "WrongPassword!"},
                HTTP_HOST="fitcorp.localhost",
            )

        assert len(mail.outbox) == 0

        # 5th failure
        response = client.post(
            "/api/auth/login/",
            {"email": member.email, "password": "WrongPassword!"},
            HTTP_HOST="fitcorp.localhost",
        )
        assert response.status_code == 401

        member.refresh_from_db()
        assert member.failed_login_count == 5
        assert member.locked_until is not None
        assert member.locked_until > timezone.now()

        # Email sent to gym's owner
        assert len(mail.outbox) == 1
        email = mail.outbox[0]
        assert "owner@fitcorp.com" in email.to
        assert "Account locked" in email.subject
        assert member.email in email.body

    def test_locked_account_refuses_correct_password(self, setup_data):
        """While an account is locked, even the correct password is refused with 401."""
        member = setup_data["member"]
        member.failed_login_count = 5
        member.locked_until = timezone.now() + timedelta(minutes=15)
        member.save()

        client = APIClient()
        response = client.post(
            "/api/auth/login/",
            {
                "email": member.email,
                "password": "MemberPassword123!",
            },  # correct password
            HTTP_HOST="fitcorp.localhost",
        )
        assert response.status_code == 401
        assert response.json() == {"detail": "Invalid credentials."}

    def test_successful_login_resets_failed_counter(self, setup_data):
        """A successful login resets failed_login_count to 0 and clears locked_until."""
        member = setup_data["member"]
        member.failed_login_count = 3
        member.save()

        client = APIClient()
        response = client.post(
            "/api/auth/login/",
            {"email": member.email, "password": "MemberPassword123!"},
            HTTP_HOST="fitcorp.localhost",
        )
        assert response.status_code == 200

        member.refresh_from_db()
        assert member.failed_login_count == 0
        assert member.locked_until is None

    def test_super_admin_lockout_sends_no_email(self, setup_data):
        """
        Super Admin lockouts are logged only; no email is sent.
        """
        admin = setup_data["super_admin"]
        client = APIClient()

        mail.outbox.clear()

        for _ in range(5):
            client.post(
                "/api/auth/login/",
                {"email": admin.email, "password": "WrongPassword!"},
                HTTP_HOST="localhost",
            )

        admin.refresh_from_db()
        assert admin.failed_login_count == 5
        assert admin.locked_until is not None

        # Proves no email was sent for Super Admin
        assert len(mail.outbox) == 0

    def test_unknown_email_keeps_no_counter(self):
        """Failed attempts with unknown emails keep no counter and modify no DB records."""
        client = APIClient()

        response = client.post(
            "/api/auth/login/",
            {"email": "unknown@fitcorp.com", "password": "AnyPassword!"},
            HTTP_HOST="localhost",
        )
        assert response.status_code == 401
        assert not User.all_objects.filter(email="unknown@fitcorp.com").exists()
