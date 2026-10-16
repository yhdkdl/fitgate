"""Tests proving invite and verification links/tokens are NEVER returned in API responses.

SPEC & Owner Decision:
Invite and verification links/tokens are dispatched via transactional on_commit emails ONLY.
No API response payload (gym creation, staff invite, member self-service or staff-assisted registration)
ever leaks tokens or links.
"""

import pytest
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.tokens import get_tokens_for_user
from apps.tenants.models import GymConfig, GymTenant


@pytest.fixture
def test_gym(db):
    gym = GymTenant.objects.create(
        name="No Leak Gym",
        subdomain="noleak-gym",
        tier=GymTenant.TIER_GROWTH,
        status=GymTenant.STATUS_ACTIVE,
        contact_phone="+251911223344",
        location="Bole, Addis Ababa",
        tls_confirmed_at=timezone.now(),
    )
    GymConfig.objects.get_or_create(gym=gym)
    return gym


@pytest.fixture
def super_admin(db):
    user = User.objects.create_superuser(
        email="superadmin_leak_test@example.com",
        password="AdminPassword123!",
        full_name="Super Admin",
        must_change_password=False,
    )
    return user


@pytest.fixture
def gym_owner(db, test_gym):
    user = User.objects.create_user(
        email="owner_noleak@example.com",
        password="OwnerPassword123!",
        gym=test_gym,
        role=User.ROLE_OWNER,
        full_name="Gym Owner",
        is_active=True,
        must_change_password=False,
        email_verified_at=timezone.now(),
    )
    return user


@pytest.mark.django_db
class TestApiTokenLeakPrevention:
    """Explicitly verify that invite and verification tokens/links never appear in API responses."""

    FORBIDDEN_KEYS = [
        "token",
        "raw_token",
        "raw_invite_token",
        "invite_token",
        "verification_token",
        "invite_link",
        "invite_url",
        "verification_link",
        "verification_url",
        "set_password_url",
    ]

    def test_create_gym_api_response_does_not_leak_invite_token_or_link(
        self, super_admin, monkeypatch
    ):
        """POST /api/platform/gyms/ returns gym, config, owner summary, and payment_id — NO tokens/links."""

        tokens = get_tokens_for_user(super_admin)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

        payload = {
            "name": "Token Leak Test Gym",
            "subdomain": "tokenleak-test",
            "tier": "growth",
            "location": "Addis Ababa",
            "contact_name": "Test Contact",
            "contact_phone": "+251911002233",
            "contact_email": "contact@tokenleak.com",
            "owner_name": "Test Owner",
            "owner_email": "owner@tokenleak.com",
            "payment_amount": "30000.00",
            "payment_reference": "TX-LEAK-TEST-01",
        }

        resp = client.post(
            "/api/platform/gyms/", payload, format="json", HTTP_HOST="localhost"
        )
        assert resp.status_code == status.HTTP_201_CREATED
        data = resp.json()

        for forbidden in self.FORBIDDEN_KEYS:
            assert (
                forbidden not in data
            ), f"Key '{forbidden}' was leaked in gym creation response"
            assert forbidden not in data.get(
                "owner", {}
            ), f"Key '{forbidden}' was leaked in owner summary"

    def test_staff_invite_api_response_does_not_leak_invite_token_or_link(
        self, gym_owner, test_gym
    ):
        """POST /api/gym/staff/ returns detail message and user summary — NO tokens/links."""
        tokens = get_tokens_for_user(gym_owner)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

        payload = {
            "email": "invited_trainer@noleak.com",
            "role": "trainer",
            "full_name": "Trainer Bob",
            "phone": "+251911998877",
        }

        resp = client.post(
            "/api/gym/staff/",
            payload,
            format="json",
            HTTP_HOST=f"{test_gym.subdomain}.localhost",
        )
        assert resp.status_code == status.HTTP_201_CREATED
        data = resp.json()

        for forbidden in self.FORBIDDEN_KEYS:
            assert (
                forbidden not in data
            ), f"Key '{forbidden}' was leaked in staff invite response"
            assert forbidden not in data.get(
                "user", {}
            ), f"Key '{forbidden}' was leaked in staff user summary"

    def test_member_self_service_registration_does_not_leak_token_or_link(
        self, test_gym
    ):
        """POST /api/public/members/register/ returns detail and member summary — NO tokens/links."""
        client = APIClient()
        payload = {
            "full_name": "Self Reg Member",
            "email": "selfreg@example.com",
            "phone": "+251911223344",
            "password": "SecurePassword123!",
            "waiver_accepted": True,
            "date_of_birth": "1996-01-01",
            "gender": "female",
            "emergency_contact": "Emergency - +251911000000",
        }

        resp = client.post(
            "/api/public/members/register/",
            payload,
            format="json",
            HTTP_HOST=f"{test_gym.subdomain}.localhost",
        )
        assert resp.status_code == status.HTTP_201_CREATED
        data = resp.json()

        for forbidden in self.FORBIDDEN_KEYS:
            assert (
                forbidden not in data
            ), f"Key '{forbidden}' was leaked in self-service member response"
            assert forbidden not in data.get(
                "member", {}
            ), f"Key '{forbidden}' was leaked in member summary"

    def test_member_staff_assisted_registration_does_not_leak_token_or_link(
        self, gym_owner, test_gym
    ):
        """POST /api/gym/members/ returns detail and member summary — NO tokens/links."""
        tokens = get_tokens_for_user(gym_owner)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

        payload = {
            "full_name": "Staff Assisted Member",
            "email": "staffassisted@example.com",
            "phone": "+251922334455",
            "waiver_accepted": True,
            "date_of_birth": "1994-02-02",
            "gender": "male",
            "emergency_contact": "Contact - +251922000000",
        }

        resp = client.post(
            "/api/gym/members/",
            payload,
            format="json",
            HTTP_HOST=f"{test_gym.subdomain}.localhost",
        )
        assert resp.status_code == status.HTTP_201_CREATED
        data = resp.json()

        for forbidden in self.FORBIDDEN_KEYS:
            assert (
                forbidden not in data
            ), f"Key '{forbidden}' was leaked in staff-assisted member response"
            assert forbidden not in data.get(
                "member", {}
            ), f"Key '{forbidden}' was leaked in member summary"
