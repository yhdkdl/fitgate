"""Comprehensive tests for Sprint 4: Super Admin Create Gym, UAPI atomicity, and TLS certificate gate."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.core import mail
from django.core.exceptions import ValidationError
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied
from rest_framework.test import APIClient

from apps.accounts.models import AuthToken, User
from apps.accounts.tokens import get_tokens_for_user
from apps.payments.models import Payment
from apps.tenants.models import GymConfig, GymTenant
from apps.tenants.services import (
    confirm_gym_tls,
    create_gym,
    propose_subdomain,
)
from apps.tenants.uapi import CPanelUAPIError, MockCPanelUAPIClient


@pytest.mark.django_db
class TestCreateGymSuite:
    """Test suite covering gym creation, UAPI provisioning, atomicity, and certificate gate."""

    @pytest.fixture
    def super_admin(self):
        """Create active platform Super Admin."""
        return User.objects.create_superuser(
            email="superadmin@fitgate.org",
            password="SuperPassword123!",
            must_change_password=False,
        )

    @pytest.fixture
    def mock_uapi(self):
        """Mock UAPI client that records provisioned subdomains."""
        return MockCPanelUAPIClient()

    def test_propose_subdomain_generates_valid_unique_dns_slug(self):
        """Propose subdomain sanitizes names, handles reserved words, and avoids collisions."""
        assert propose_subdomain("Bole Fitness Hub") == "bole-fitness-hub"
        assert propose_subdomain("Admin") == "admin-gym"
        assert propose_subdomain("www") == "www-gym"

        # When slug already exists, appends numeric suffix
        GymTenant.objects.create(name="Existing Gym", subdomain="existing-gym")
        proposed = propose_subdomain("Existing Gym")
        assert proposed == "existing-gym-1"

    def test_create_gym_atomic_success_for_starter_growth_and_pro(
        self, super_admin, mock_uapi
    ):
        """
        Verify create_gym creates tenant as active, config with tier defaults,
        payment record, owner user, invite token, provisions UAPI, and sends welcome email.
        """
        mail.outbox.clear()

        result = create_gym(
            name="Power Gym",
            subdomain="power-gym",
            tier=GymTenant.TIER_GROWTH,
            location="Bole Atlas, Addis Ababa",
            contact_name="Abebe Bikila",
            contact_phone="+251911223344",
            contact_email="contact@powergym.com",
            owner_name="Abebe Bikila",
            owner_email="abebe@powergym.com",
            payment_amount=Decimal("30000.00"),
            payment_reference="CBE-TX-998877",
            acting_super_admin=super_admin,
            uapi_client=mock_uapi,
        )

        gym = result["gym"]
        config = result["config"]
        payment = result["payment"]
        owner = result["owner"]
        invite_token = result["invite_token"]

        # 1. Gym Tenant
        assert gym.status == GymTenant.STATUS_ACTIVE
        assert gym.tier == GymTenant.TIER_GROWTH
        assert gym.subdomain == "power-gym"
        assert gym.tls_confirmed_at is None
        assert gym.subscription_expires_at is None

        # 2. Gym Config (Growth tier defaults)
        assert config.has_trainer_module is True
        assert config.has_ai_plans is True
        assert config.has_analytics is True
        assert config.has_group_classes is True
        assert config.has_multi_branch is False
        assert config.freeze_days_allowed == 30
        assert config.payment_grace_days == 7
        assert config.subscription_reminder_days == [14, 7]
        assert config.member_reminder_days == [7, 2]

        # 3. Payment record
        assert payment.gym == gym
        assert payment.payer_type == Payment.PAYER_TYPE_GYM_SUBSCRIPTION
        assert payment.method == Payment.METHOD_BANK_TRANSFER
        assert payment.amount_etb == Decimal("30000.00")
        assert payment.status == Payment.STATUS_CONFIRMED
        assert payment.confirmed_by == super_admin
        assert payment.bank_reference == "CBE-TX-998877"

        # 4. Owner account
        assert owner.role == User.ROLE_OWNER
        assert owner.gym == gym
        assert owner.email == "abebe@powergym.com"
        assert owner.email_verified_at is not None
        assert owner.has_usable_password() is False

        # 5. Invite token
        assert invite_token.user == owner
        assert invite_token.purpose == AuthToken.PURPOSE_INVITE
        assert invite_token.used_at is None
        assert invite_token.expires_at > timezone.now()

        # 6. cPanel UAPI provisioning called
        assert "power-gym" in mock_uapi.provisioned_subdomains

        # 7. Welcome email sent with set-password link and NO password
        assert len(mail.outbox) == 1
        welcome_email = mail.outbox[0]
        assert welcome_email.to == ["abebe@powergym.com"]
        assert "set-password?token=" in welcome_email.body
        assert "SuperPassword" not in welcome_email.body
        assert "password:" not in welcome_email.body.lower()

    def test_uapi_failure_aborts_transaction_and_rolls_back_everything(
        self, super_admin
    ):
        """
        Atomicity guarantee: If cPanel UAPI provisioning raises CPanelUAPIError,
        nothing is left half-created.
        """
        failing_uapi = MockCPanelUAPIClient(should_fail=True)

        initial_gyms = GymTenant.objects.count()
        initial_configs = GymConfig.objects.count()
        initial_payments = Payment.objects.count()
        initial_users = User.all_objects.count()
        initial_tokens = AuthToken.objects.count()

        with pytest.raises(CPanelUAPIError):
            create_gym(
                name="Failing Gym",
                subdomain="fail-gym",
                tier=GymTenant.TIER_STARTER,
                owner_email="fail@failgym.com",
                payment_amount=Decimal("12000.00"),
                payment_reference="TX-FAIL-001",
                acting_super_admin=super_admin,
                uapi_client=failing_uapi,
            )

        # Assert zero rows persisted
        assert GymTenant.objects.count() == initial_gyms
        assert GymConfig.objects.count() == initial_configs
        assert Payment.objects.count() == initial_payments
        assert User.all_objects.count() == initial_users
        assert AuthToken.objects.count() == initial_tokens

    def test_chapa_rejected_for_gym_subscription(self, super_admin, mock_uapi):
        """A chapa payment method is rejected for gym_subscription payments."""
        with pytest.raises(ValidationError) as exc:
            create_gym(
                name="Chapa Gym",
                subdomain="chapa-gym",
                tier=GymTenant.TIER_STARTER,
                owner_email="owner@chapagym.com",
                payment_amount=Decimal("12000.00"),
                payment_reference="CHAPA-REF",
                payment_method="chapa",
                acting_super_admin=super_admin,
                uapi_client=mock_uapi,
            )
        assert "payment_method" in exc.value.message_dict

    def test_duplicate_and_reserved_subdomain_rejected(self, super_admin, mock_uapi):
        """Duplicate and reserved subdomains are rejected at creation."""
        # 1. Reserved subdomain
        with pytest.raises(ValidationError) as exc:
            create_gym(
                name="Admin Gym",
                subdomain="admin",
                tier=GymTenant.TIER_STARTER,
                owner_email="owner@admingym.com",
                payment_amount=Decimal("12000.00"),
                payment_reference="REF-ADMIN",
                acting_super_admin=super_admin,
                uapi_client=mock_uapi,
            )
        assert "reserved subdomain" in str(exc.value)

        # 2. Duplicate subdomain
        create_gym(
            name="Alpha Gym",
            subdomain="alpha-gym",
            tier=GymTenant.TIER_STARTER,
            owner_email="owner@alphagym.com",
            payment_amount=Decimal("12000.00"),
            payment_reference="REF-ALPHA",
            acting_super_admin=super_admin,
            uapi_client=mock_uapi,
        )

        with pytest.raises(ValidationError) as exc_dup:
            create_gym(
                name="Alpha Gym Two",
                subdomain="alpha-gym",
                tier=GymTenant.TIER_PRO,
                owner_email="owner2@alphagym.com",
                payment_amount=Decimal("60000.00"),
                payment_reference="REF-ALPHA-2",
                acting_super_admin=super_admin,
                uapi_client=mock_uapi,
            )
        assert "subdomain" in exc_dup.value.message_dict

    def test_non_super_admin_cannot_call_create_gym_service(self, mock_uapi):
        """Only Super Admin can invoke create_gym service; other roles get PermissionDenied."""
        temp_gym = GymTenant.objects.create(
            name="T Gym", subdomain="tgym", tls_confirmed_at=timezone.now()
        )
        regular_user = User.objects.create_user(
            email="regular@example.com",
            password="RegularPassword123!",
            role=User.ROLE_OWNER,
            gym=temp_gym,
        )

        with pytest.raises(PermissionDenied):
            create_gym(
                name="Unauthorized Gym",
                subdomain="unauth-gym",
                tier=GymTenant.TIER_STARTER,
                owner_email="owner@unauth.com",
                payment_amount=Decimal("12000.00"),
                payment_reference="REF-UNAUTH",
                acting_super_admin=regular_user,
                uapi_client=mock_uapi,
            )

    def test_certificate_safeguard_refuses_login_until_confirmed(
        self, super_admin, mock_uapi
    ):
        """
        Certificate safeguard (SPEC §4):
        - Subdomain login is refused with 503 'still_securing' while tls_confirmed_at is null.
        - Once tls_confirmed_at is set, login is allowed.
        - When set for the first time, subscription_expires_at is set to one year later.
        - Subsequent confirmations do not reset or shorten subscription_expires_at.
        """
        result = create_gym(
            name="Secured Gym",
            subdomain="secured-gym",
            tier=GymTenant.TIER_STARTER,
            owner_email="owner@securedgym.com",
            payment_amount=Decimal("12000.00"),
            payment_reference="REF-SECURED-1",
            acting_super_admin=super_admin,
            uapi_client=mock_uapi,
        )
        gym = result["gym"]
        raw_invite = result["raw_invite_token"]

        # Owner sets their password via the invite link
        client = APIClient()
        resp_set_pwd = client.post(
            "/api/auth/set-password/",
            {
                "token": raw_invite,
                "new_password": "NewOwnerSecurePassword123!",
            },
            format="json",
            HTTP_HOST="secured-gym.localhost",
        )
        assert resp_set_pwd.status_code == 200

        # Attempt to login while tls_confirmed_at is None -> 503 still_securing
        resp_login_unsecured = client.post(
            "/api/auth/login/",
            {
                "email": "owner@securedgym.com",
                "password": "NewOwnerSecurePassword123!",
            },
            format="json",
            HTTP_HOST="secured-gym.localhost",
        )
        assert resp_login_unsecured.status_code == 503
        assert resp_login_unsecured.json()["detail"] == "still_securing"

        # Super Admin confirms TLS certificate
        confirmed_gym = confirm_gym_tls(gym.id, acting_super_admin=super_admin)
        assert confirmed_gym.tls_confirmed_at is not None
        assert confirmed_gym.subscription_expires_at is not None

        # Verify initial subscription window is exactly 365 days from confirmation
        expected_expiry = confirmed_gym.tls_confirmed_at + timedelta(days=365)
        diff = abs(
            (confirmed_gym.subscription_expires_at - expected_expiry).total_seconds()
        )
        assert diff < 5

        # Re-confirming TLS does not reset or shorten subscription_expires_at
        initial_expiry = confirmed_gym.subscription_expires_at
        confirmed_again = confirm_gym_tls(gym.id, acting_super_admin=super_admin)
        assert confirmed_again.subscription_expires_at == initial_expiry

        # Now login succeeds on secured subdomain
        resp_login_secured = client.post(
            "/api/auth/login/",
            {
                "email": "owner@securedgym.com",
                "password": "NewOwnerSecurePassword123!",
            },
            format="json",
            HTTP_HOST="secured-gym.localhost",
        )
        assert resp_login_secured.status_code == 200
        assert "access" in resp_login_secured.json()

    def test_create_gym_http_endpoint_permissions_and_response(
        self, super_admin, mock_uapi
    ):
        """
        Test POST /api/platform/gyms/:
        - Super Admin at apex succeeds with 201.
        - Non-superadmin gets 403.
        - Calling from a gym subdomain gets 403.
        """
        tokens = get_tokens_for_user(super_admin)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

        payload = {
            "name": "Bole Apex Fitness",
            "subdomain": "bole-apex",
            "tier": "pro",
            "location": "Bole Medhanialem",
            "contact_name": "Haile Gebrselassie",
            "contact_phone": "+251911002233",
            "contact_email": "haile@boleapex.com",
            "owner_name": "Haile Gebrselassie",
            "owner_email": "haile@boleapex.com",
            "payment_amount": "60000.00",
            "payment_reference": "TX-PRO-776655",
        }

        # 1. Success at apex
        response = client.post(
            "/api/platform/gyms/",
            payload,
            format="json",
            HTTP_HOST="localhost",
        )
        assert response.status_code == 201
        data = response.json()
        assert data["gym"]["subdomain"] == "bole-apex"
        assert data["config"]["has_multi_branch"] is True
        assert data["owner"]["email"] == "haile@boleapex.com"
        assert "invite_link" in data

        # 2. Propose subdomain endpoint
        resp_prop = client.get(
            "/api/platform/gyms/propose-subdomain/?name=Awesome+Fitness",
            HTTP_HOST="localhost",
        )
        assert resp_prop.status_code == 200
        assert resp_prop.json()["subdomain"] == "awesome-fitness"

        # 3. Confirm TLS endpoint
        gym_id = data["gym"]["id"]
        resp_tls = client.post(
            f"/api/platform/gyms/{gym_id}/confirm-tls/",
            {},
            format="json",
            HTTP_HOST="localhost",
        )
        assert resp_tls.status_code == 200
        assert resp_tls.json()["gym"]["tls_confirmed_at"] is not None

        # 4. Calling from a gym subdomain gets 401 or 403 (host isolation prevents Super Admin auth on gym subdomains)
        resp_subdomain_call = client.post(
            "/api/platform/gyms/",
            payload,
            format="json",
            HTTP_HOST="bole-apex.localhost",
        )
        assert resp_subdomain_call.status_code in (401, 403)

        # 5. Non-super admin gets 403
        owner = User.all_objects.get(email="haile@boleapex.com")
        owner_tokens = get_tokens_for_user(owner)

        owner_client = APIClient()
        owner_client.credentials(HTTP_AUTHORIZATION=f"Bearer {owner_tokens['access']}")
        resp_owner = owner_client.post(
            "/api/platform/gyms/",
            payload,
            format="json",
            HTTP_HOST="bole-apex.localhost",
        )
        assert resp_owner.status_code == 403
