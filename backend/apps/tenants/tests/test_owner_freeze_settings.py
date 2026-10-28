"""
Tests for Item 16: Owner freeze settings and enforcement.
[TEST: Owner value above the cap is refused; a freeze request beyond the Owner's value is refused.]
"""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.tokens import get_tokens_for_user
from apps.memberships.models import (
    Member,
    MembershipPlan,
    MemberSubscription,
)
from apps.tenants.models import GymConfig, GymTenant


@pytest.fixture
def gym_tenant(db):
    tenant = GymTenant.objects.create(
        name="FitGate Bole Hub",
        subdomain="bolehub",
        tier=GymTenant.TIER_GROWTH,
        status=GymTenant.STATUS_ACTIVE,
        tls_confirmed_at=timezone.now(),
    )
    config, _ = GymConfig.objects.get_or_create(gym=tenant)
    config.freeze_days_cap = 14
    config.freeze_days_allowed = 14
    config.save()
    return tenant


@pytest.fixture
def owner_user(db, gym_tenant):
    user = User.objects.create_user(
        email="owner_freeze@bolehub.com",
        password="ValidPassword123!",
        role=User.ROLE_OWNER,
        gym=gym_tenant,
        full_name="Bole Owner",
        must_change_password=False,
    )
    user.password_changed_at = timezone.now()
    user.save()
    return user


@pytest.fixture
def member_user(db, gym_tenant):
    user = User.objects.create_user(
        email="member_freeze@bolehub.com",
        password="ValidPassword123!",
        role=User.ROLE_MEMBER,
        gym=gym_tenant,
        full_name="Freeze Member",
        must_change_password=False,
    )
    user.password_changed_at = timezone.now()
    user.save()
    return user


@pytest.fixture
def member_with_subscription(db, gym_tenant, member_user):
    member = Member.all_objects.create(
        gym=gym_tenant,
        user=member_user,
        full_name=member_user.full_name,
        phone="+251911887766",
        status=Member.STATUS_ACTIVE,
        waiver_accepted_at=timezone.now(),
    )
    plan = MembershipPlan.objects.create(
        gym=gym_tenant,
        name="Standard Plan",
        duration_value=1,
        duration_unit="months",
        price_etb=Decimal("1500.00"),
        is_active=True,
    )
    start_d = timezone.localdate()
    end_d = start_d + timedelta(days=30)
    MemberSubscription.all_objects.create(
        gym=gym_tenant,
        member=member,
        plan=plan,
        start_date=start_d,
        end_date=end_d,
        status=MemberSubscription.STATUS_ACTIVE,
    )
    return member


def auth_client_for(user):
    client = APIClient()
    tokens = get_tokens_for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
    return client


@pytest.mark.django_db
class TestOwnerFreezeSettings:
    def test_owner_setting_freeze_days_above_cap_is_refused(
        self, gym_tenant, owner_user
    ):
        client = auth_client_for(owner_user)
        # Cap is 14; Owner tries to set 20
        resp = client.patch(
            "/api/gym/settings/",
            {"freeze_days_allowed": 20},
            format="json",
            HTTP_HOST=f"{gym_tenant.subdomain}.localhost",
        )
        assert resp.status_code == 400
        assert "freeze allowance cap" in str(resp.json()).lower()

    def test_owner_setting_freeze_days_within_cap_succeeds(
        self, gym_tenant, owner_user
    ):
        client = auth_client_for(owner_user)
        # Cap is 14; Owner sets 7
        resp = client.patch(
            "/api/gym/settings/",
            {"freeze_days_allowed": 7},
            format="json",
            HTTP_HOST=f"{gym_tenant.subdomain}.localhost",
        )
        assert resp.status_code == 200
        gym_tenant.config.refresh_from_db()
        assert gym_tenant.config.freeze_days_allowed == 7

    def test_freeze_request_beyond_owner_value_is_refused(
        self, gym_tenant, owner_user, member_user, member_with_subscription
    ):
        # 1. Owner sets freeze_days_allowed to 5
        owner_client = auth_client_for(owner_user)
        resp_set = owner_client.patch(
            "/api/gym/settings/",
            {"freeze_days_allowed": 5},
            format="json",
            HTTP_HOST=f"{gym_tenant.subdomain}.localhost",
        )
        assert resp_set.status_code == 200

        # 2. Member requests freeze of 7 days (> 5 days allowed by Owner)
        member_client = auth_client_for(member_user)
        today = timezone.localdate()
        resp_req = member_client.post(
            "/api/memberships/freezes/",
            {
                "start_date": str(today + timedelta(days=1)),
                "end_date": str(today + timedelta(days=8)),  # 7 days
                "reason": "Travel out of town",
            },
            format="json",
            HTTP_HOST=f"{gym_tenant.subdomain}.localhost",
        )
        assert resp_req.status_code == 400
        assert (
            "exceeds" in str(resp_req.json()).lower()
            or "allowance" in str(resp_req.json()).lower()
        )

        # 3. Member requests freeze of 4 days (<= 5 days allowed by Owner) -> succeeds
        resp_valid = member_client.post(
            "/api/memberships/freezes/",
            {
                "start_date": str(today + timedelta(days=1)),
                "end_date": str(today + timedelta(days=5)),  # 4 days
                "reason": "Short business trip",
            },
            format="json",
            HTTP_HOST=f"{gym_tenant.subdomain}.localhost",
        )
        assert resp_valid.status_code == 201
