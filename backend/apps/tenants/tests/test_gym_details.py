"""
Tests for gym details editing and role refusals.
Asserts:
- Gym Owner can GET and PATCH /api/gym/details/ (updates public_contact_phone and location).
- Non-Owner gym roles (Manager, Reception, Trainer, Member) are refused with 403 on /api/gym/details/.
- Super Admin can PATCH /api/platform/gyms/<id>/details/ (updates name, location, public_contact_phone, contact details).
- Non-Super-Admin roles are refused on /api/platform/gyms/<id>/details/.
"""

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import AuditLog, User
from apps.accounts.tokens import get_tokens_for_user
from apps.tenants.models import GymConfig, GymTenant


@pytest.fixture
def active_gym(db):
    tenant = GymTenant.objects.create(
        name="Atlas Fitness Center",
        subdomain="atlas",
        tier=GymTenant.TIER_GROWTH,
        status=GymTenant.STATUS_ACTIVE,
        location="Bole Atlas",
        contact_name="Abebe Bikila",
        contact_phone="+251911223344",
        contact_email="contact@atlas.et",
        public_contact_phone="+251911223344",
        tls_confirmed_at=timezone.now(),
    )
    GymConfig.objects.get_or_create(gym=tenant)
    return tenant


def create_role_user(gym, role, email):
    user = User.objects.create_user(
        email=email,
        password="ValidPassword123!",
        role=role,
        gym=gym,
        full_name=f"User {role}",
        must_change_password=False,
    )
    user.password_changed_at = timezone.now()
    user.save()
    return user


def auth_client_for(user):
    client = APIClient()
    tokens = get_tokens_for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
    return client


@pytest.mark.django_db
class TestGymDetailsRoleRefusals:
    def test_owner_can_view_and_update_gym_details(self, active_gym):
        owner = create_role_user(active_gym, User.ROLE_OWNER, "owner@atlas.et")
        client = auth_client_for(owner)

        # GET
        res_get = client.get(
            "/api/gym/details/",
            HTTP_HOST=f"{active_gym.subdomain}.localhost",
        )
        assert res_get.status_code == 200
        assert res_get.data["public_contact_phone"] == "+251911223344"
        assert res_get.data["location"] == "Bole Atlas"

        # PATCH
        res_patch = client.patch(
            "/api/gym/details/",
            {
                "public_contact_phone": "+251922334455",
                "location": "Bole Medhanialem, Addis Ababa",
            },
            format="json",
            HTTP_HOST=f"{active_gym.subdomain}.localhost",
        )
        assert res_patch.status_code == 200
        active_gym.refresh_from_db()
        assert active_gym.public_contact_phone == "+251922334455"
        assert active_gym.location == "Bole Medhanialem, Addis Ababa"

        # Verify gym audit log
        logs = AuditLog.all_objects.filter(
            gym=active_gym, action_type="gym_details_updated"
        )
        assert logs.count() == 2
        for log in logs:
            assert log.actor == owner
            assert log.metadata.get("field") in ["public_contact_phone", "location"]

    @pytest.mark.parametrize(
        "role,email",
        [
            (User.ROLE_MANAGER, "manager@atlas.et"),
            (User.ROLE_RECEPTION, "receptionist@atlas.et"),
            (User.ROLE_TRAINER, "trainer@atlas.et"),
            (User.ROLE_MEMBER, "member@atlas.et"),
        ],
    )
    def test_non_owner_roles_refused_on_gym_details(self, active_gym, role, email):
        user = create_role_user(active_gym, role, email)
        client = auth_client_for(user)

        # GET refused
        res_get = client.get(
            "/api/gym/details/",
            HTTP_HOST=f"{active_gym.subdomain}.localhost",
        )
        assert res_get.status_code == 403

        # PATCH refused
        res_patch = client.patch(
            "/api/gym/details/",
            {"public_contact_phone": "+251999999999"},
            format="json",
            HTTP_HOST=f"{active_gym.subdomain}.localhost",
        )
        assert res_patch.status_code == 403

    def test_super_admin_can_update_platform_gym_details(self, active_gym):
        admin = User.objects.create_superuser(
            email="superadmin_details@fitgate.et",
            password="AdminPassword123!",
            role=User.ROLE_SUPER_ADMIN,
        )
        admin.password_changed_at = timezone.now()
        admin.save()

        client = auth_client_for(admin)
        res = client.patch(
            f"/api/platform/gyms/{active_gym.id}/details/",
            {
                "name": "Atlas Premier Fitness",
                "location": "Atlas Central Square",
                "public_contact_phone": "+251933445566",
                "contact_name": "Kenenisa B",
                "contact_phone": "+251944556677",
                "contact_email": "kenenisa@atlas.et",
            },
            format="json",
        )
        assert res.status_code == 200

        active_gym.refresh_from_db()
        assert active_gym.name == "Atlas Premier Fitness"
        assert active_gym.location == "Atlas Central Square"
        assert active_gym.public_contact_phone == "+251933445566"
        assert active_gym.contact_name == "Kenenisa B"
        assert active_gym.contact_phone == "+251944556677"
        assert active_gym.contact_email == "kenenisa@atlas.et"

        # Verify platform audit log
        logs = AuditLog.all_objects.filter(
            action_type="gym_details_platform_updated",
            affected_record_id=str(active_gym.id),
        )
        assert logs.count() == 6
        for log in logs:
            assert log.actor == admin

    def test_non_super_admin_refused_on_platform_gym_details(self, active_gym):
        owner = create_role_user(active_gym, User.ROLE_OWNER, "owner_platform@atlas.et")
        client = auth_client_for(owner)

        # On gym domain, IsSuperAdmin refuses with 403
        res = client.patch(
            f"/api/platform/gyms/{active_gym.id}/details/",
            {"name": "Hacked Gym Name"},
            format="json",
            HTTP_HOST=f"{active_gym.subdomain}.localhost",
        )
        assert res.status_code == 403

        # On apex platform domain, tenant token is rejected with 401
        res_apex = client.patch(
            f"/api/platform/gyms/{active_gym.id}/details/",
            {"name": "Hacked Gym Name"},
            format="json",
        )
        assert res_apex.status_code in (401, 403)
