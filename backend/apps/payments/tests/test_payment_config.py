"""Tests for gym payment configuration RBAC, encryption at rest, connection test, and audit logging."""

from unittest.mock import patch

import pytest
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import AuditLog, User
from apps.payments.models import GymPaymentConfig
from apps.tenants.models import GymTenant


@pytest.mark.django_db
class TestGymPaymentConfig:
    """RBAC and encryption tests for gym payment gateway credentials."""

    @pytest.fixture
    def setup_data(self):
        gym_a = GymTenant.objects.create(
            name="Gym Alpha", subdomain="alpha", tls_confirmed_at=timezone.now()
        )
        gym_b = GymTenant.objects.create(
            name="Gym Beta", subdomain="beta", tls_confirmed_at=timezone.now()
        )

        owner_a = User.objects.create_user(
            email="owner@alpha.test",
            password="OwnerPassword123!",
            gym=gym_a,
            role=User.ROLE_OWNER,
        )
        manager_a = User.objects.create_user(
            email="manager@alpha.test",
            password="ManagerPassword123!",
            gym=gym_a,
            role=User.ROLE_MANAGER,
        )
        reception_a = User.objects.create_user(
            email="reception@alpha.test",
            password="ReceptionPassword123!",
            gym=gym_a,
            role=User.ROLE_RECEPTION,
        )
        member_a = User.objects.create_user(
            email="member@alpha.test",
            password="MemberPassword123!",
            gym=gym_a,
            role=User.ROLE_MEMBER,
        )
        owner_b = User.objects.create_user(
            email="owner@beta.test",
            password="OwnerPassword123!",
            gym=gym_b,
            role=User.ROLE_OWNER,
        )
        super_admin = User.objects.create_superuser(
            email="admin@fitgate.test",
            password="AdminPassword123!",
        )

        return {
            "gym_a": gym_a,
            "gym_b": gym_b,
            "owner_a": owner_a,
            "manager_a": manager_a,
            "reception_a": reception_a,
            "member_a": member_a,
            "owner_b": owner_b,
            "super_admin": super_admin,
        }

    def test_owner_can_configure_chapa_keys_and_stored_encrypted(self, setup_data):
        client = APIClient()
        owner = setup_data["owner_a"]
        gym = setup_data["gym_a"]
        client.force_authenticate(user=owner)

        payload = {
            "public_key": "CHAPUBK_TEST-abc123xyz789",
            "secret_key": "CHASECK_TEST-secret789xyz123",
            "webhook_secret": "webhooksecret123456",
        }
        response = client.put(
            "/api/gym/payment-config/",
            payload,
            format="json",
            HTTP_HOST="alpha.localhost",
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Masked response check
        assert data["is_configured"] is True
        assert data["is_test_mode"] is True
        assert data["is_verified"] is False
        assert data["has_secret_key"] is True
        assert data["has_webhook_secret"] is True
        assert data["masked_public_key"] == "CHAPUBK_TEST-****z789"
        # Ensure plaintext secret keys are NEVER returned in response
        assert "secret_key" not in data
        assert "webhook_secret" not in data
        assert "CHASECK_TEST-secret789xyz123" not in str(data)

        # Database inspection: raw fields must be ciphertext, NOT plaintext
        config = GymPaymentConfig.all_objects.get(gym=gym)
        assert config.encrypted_secret_key != "CHASECK_TEST-secret789xyz123"
        assert config.encrypted_webhook_secret != "webhooksecret123456"
        assert config.secret_key == "CHASECK_TEST-secret789xyz123"

        # Audit log verification: must record update without leaking secret keys
        audit = AuditLog.all_objects.filter(
            gym=gym,
            action_type="payment_config_updated",
        ).first()
        assert audit is not None
        assert audit.actor == owner
        assert "secret789xyz123" not in str(audit.metadata)

    def test_payment_config_rbac_denies_unauthorized_roles(self, setup_data):
        client = APIClient()

        # Manager denied (403)
        client.force_authenticate(user=setup_data["manager_a"])
        resp = client.get("/api/gym/payment-config/", HTTP_HOST="alpha.localhost")
        assert resp.status_code == status.HTTP_403_FORBIDDEN

        # Receptionist denied (403)
        client.force_authenticate(user=setup_data["reception_a"])
        resp = client.get("/api/gym/payment-config/", HTTP_HOST="alpha.localhost")
        assert resp.status_code == status.HTTP_403_FORBIDDEN

        # Member denied (403)
        client.force_authenticate(user=setup_data["member_a"])
        resp = client.get("/api/gym/payment-config/", HTTP_HOST="alpha.localhost")
        assert resp.status_code == status.HTTP_403_FORBIDDEN

        # Super Admin denied on tenant config (cannot read or set tenant payment keys)
        client.force_authenticate(user=setup_data["super_admin"])
        resp = client.get("/api/gym/payment-config/", HTTP_HOST="alpha.localhost")
        assert resp.status_code == status.HTTP_403_FORBIDDEN

        # Cross-gym owner denied (Owner of Gym B cannot access Gym A)
        client.force_authenticate(user=setup_data["owner_b"])
        resp = client.get("/api/gym/payment-config/", HTTP_HOST="alpha.localhost")
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_connection_test_success_sets_is_verified(self, setup_data):
        client = APIClient()
        owner = setup_data["owner_a"]
        gym = setup_data["gym_a"]
        client.force_authenticate(user=owner)

        config = GymPaymentConfig.all_objects.create(gym=gym)
        config.public_key = "CHAPUBK_TEST-abc"
        config.secret_key = "CHASECK_TEST-sec"
        config.save()

        with patch(
            "apps.payments.chapa_client.ChapaClient.test_connection",
            return_value=(True, "Success"),
        ):
            resp = client.post(
                "/api/gym/payment-config/test/",
                HTTP_HOST="alpha.localhost",
            )
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["is_verified"] is True

        config.refresh_from_db()
        assert config.is_verified is True
        assert config.verified_at is not None

        # Audit log check
        audit = AuditLog.all_objects.filter(
            gym=gym, action_type="payment_config_tested"
        ).first()
        assert audit is not None
        assert audit.metadata["result"] == "success"

    def test_connection_test_failure_leaves_unverified(self, setup_data):
        client = APIClient()
        owner = setup_data["owner_a"]
        gym = setup_data["gym_a"]
        client.force_authenticate(user=owner)

        config = GymPaymentConfig.objects.create(gym=gym)
        config.public_key = "CHAPUBK_TEST-abc"
        config.secret_key = "CHASECK_TEST-sec"
        config.save()

        with patch(
            "apps.payments.chapa_client.ChapaClient.test_connection",
            return_value=(False, "Invalid key"),
        ):
            resp = client.post(
                "/api/gym/payment-config/test/",
                HTTP_HOST="alpha.localhost",
            )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        config.refresh_from_db()
        assert config.is_verified is False

    def test_super_admin_can_view_mode_without_keys(self, setup_data):
        client = APIClient()
        super_admin = setup_data["super_admin"]
        gym = setup_data["gym_a"]
        client.force_authenticate(user=super_admin)

        config = GymPaymentConfig.all_objects.create(gym=gym)
        config.public_key = "CHAPUBK_TEST-12345"

        config.secret_key = "CHASECK_TEST-67890"
        config.is_test_mode = True
        config.is_verified = True
        config.save()

        resp = client.get(
            f"/api/platform/gyms/{gym.id}/payment-status/",
            HTTP_HOST="localhost",
        )
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["is_configured"] is True
        assert data["is_test_mode"] is True
        assert data["is_verified"] is True
        # Zero secret keys exposed to Super Admin
        assert "secret_key" not in data
        assert "public_key" not in data
        assert "encrypted_secret_key" not in data
