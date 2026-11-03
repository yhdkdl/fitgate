"""Tests for Step 3: Equipment registry rules, prices, 3 plan modes, and member visibility."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import AuditLog, User
from apps.accounts.tokens import get_tokens_for_user
from apps.equipment.constants import (
    CONDITION_GOOD,
    CONDITION_NEEDS_MAINTENANCE,
    CONDITION_OUT_OF_SERVICE,
    CONDITION_UNDER_MAINTENANCE,
)
from apps.equipment.models import Equipment
from apps.memberships.models import (
    BodyMetrics,
    Member,
    MembershipPlan,
    MemberSubscription,
)
from apps.tenants.models import GymConfig, GymTenant
from apps.trainers.models import FitnessProfile, TrainerAssignment
from apps.trainers.rules_engine import (
    build_ai_generation_context,
)


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def gym_tenant(db):
    gym = GymTenant.objects.create(
        name="FitGate Central",
        subdomain="fitgate-central",
        status=GymTenant.STATUS_ACTIVE,
        tls_confirmed_at=timezone.now(),
    )
    GymConfig.objects.update_or_create(
        gym=gym,
        defaults={"has_trainer_module": True, "has_ai_plans": True},
    )
    gym.refresh_from_db()
    return gym


def create_user(gym, role, email):
    user = User.objects.create_user(
        email=email,
        password="ValidPassword123!",
        role=role,
        gym=gym,
        full_name=f"Test {role.capitalize()}",
        is_active=True,
    )
    user.force_password_change = False
    user.must_change_password = False
    user.save()
    return user


def auth_client(client, user, gym=None):
    tokens = get_tokens_for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
    if gym:
        client.defaults["HTTP_HOST"] = f"{gym.subdomain}.localhost"
    else:
        client.defaults["HTTP_HOST"] = "localhost"
    return client


@pytest.fixture
def member_bundle(db, gym_tenant):
    trainer_user = create_user(
        gym_tenant, User.ROLE_TRAINER, "trainer_bundle@central.com"
    )
    trainer_profile = trainer_user.trainer_profile

    member_user = create_user(gym_tenant, User.ROLE_MEMBER, "member_bundle@central.com")
    member = Member.objects.create(
        gym=gym_tenant,
        user=member_user,
        full_name="Bundle Member",
        phone="+251911998877",
        gender="female",
        date_of_birth=date(1996, 5, 12),
        status=Member.STATUS_ACTIVE,
        waiver_accepted_at=timezone.now(),
    )
    plan = MembershipPlan.objects.create(
        gym=gym_tenant,
        name="Trainer Included VIP",
        price_etb=5000,
        duration_value=1,
        duration_unit=MembershipPlan.DURATION_MONTHS,
        trainer_inclusive=True,
        is_active=True,
    )
    today = timezone.localdate()
    sub = MemberSubscription.objects.create(
        gym=gym_tenant,
        member=member,
        plan=plan,
        start_date=today - timedelta(days=5),
        end_date=today + timedelta(days=25),
        status=MemberSubscription.STATUS_ACTIVE,
    )
    TrainerAssignment.objects.create(
        gym=gym_tenant,
        member=member,
        trainer=trainer_profile,
    )
    profile = FitnessProfile.objects.create(
        gym=gym_tenant,
        member=member,
        goal="muscle_gain",
        fitness_level="intermediate",
        training_days_per_week=4,
        session_length_minutes=60,
        equipment_access=["free_weights"],
    )
    BodyMetrics.objects.create(
        gym=gym_tenant,
        member=member,
        recorded_by=trainer_user,
        weight_kg=70.0,
        height_cm=175.0,
        measurements={},
    )
    return {
        "gym": gym_tenant,
        "member": member,
        "subscription": sub,
        "trainer": trainer_profile,
        "profile": profile,
    }


@pytest.mark.django_db
class TestEquipmentPriceAndVisibility:
    def test_owner_and_manager_see_and_edit_price(self, api_client, gym_tenant):
        owner = create_user(gym_tenant, User.ROLE_OWNER, "owner@fitgate.com")
        auth_client(api_client, owner, gym_tenant)

        # Create equipment with price
        res = api_client.post(
            "/api/gym/equipment/",
            {
                "category": "cardio_machines",
                "name": "Commercial Treadmill X1",
                "serial_number": "TR-101",
                "quantity": 2,
                "unit_purchase_price_etb": "85000.50",
                "condition": "good",
            },
            format="json",
        )
        assert res.status_code == 201
        eq_id = res.data["id"]
        assert res.data["unit_purchase_price_etb"] == "85000.50"

        # Manager can also see price and update it
        manager = create_user(gym_tenant, User.ROLE_MANAGER, "manager@fitgate.com")
        auth_client(api_client, manager, gym_tenant)

        res_get = api_client.get(f"/api/gym/equipment/{eq_id}/")
        assert res_get.status_code == 200
        assert res_get.data["unit_purchase_price_etb"] == "85000.50"

        # Update price as manager -> verify audit log created
        res_put = api_client.put(
            f"/api/gym/equipment/{eq_id}/",
            {
                "category": "cardio_machines",
                "name": "Commercial Treadmill X1",
                "serial_number": "TR-101",
                "quantity": 2,
                "unit_purchase_price_etb": "90000.00",
                "condition": "good",
            },
            format="json",
        )
        assert res_put.status_code == 200
        assert res_put.data["unit_purchase_price_etb"] == "90000.00"

        # Check audit log for equipment_price_updated
        audit = AuditLog.all_objects.filter(
            action_type="equipment_price_updated",
            affected_record_id=str(eq_id),
        ).first()
        assert audit is not None
        assert audit.metadata["old_price"] == "85000.50"
        assert audit.metadata["new_price"] == "90000.00"

    def test_trainer_reception_member_never_see_price(self, api_client, gym_tenant):
        create_user(gym_tenant, User.ROLE_OWNER, "owner_sec@fitgate.com")
        eq = Equipment.objects.create(
            gym=gym_tenant,
            category="cable_machine",
            name="Dual Cable Pulley",
            serial_number="CP-009",
            quantity=1,
            unit_purchase_price_etb=Decimal("150000.00"),
            condition=CONDITION_GOOD,
        )

        for role, email in [
            (User.ROLE_TRAINER, "trainer_sec@fitgate.com"),
            (User.ROLE_RECEPTION, "reception_sec@fitgate.com"),
        ]:
            user = create_user(gym_tenant, role, email)
            auth_client(api_client, user, gym_tenant)
            res = api_client.get(f"/api/gym/equipment/{eq.id}/")
            assert res.status_code == 200
            assert res.data.get("unit_purchase_price_etb") is None

            res_list = api_client.get("/api/gym/equipment/")
            assert res_list.status_code == 200
            for item in res_list.data:
                assert item.get("unit_purchase_price_etb") is None

    def test_member_visibility_and_restrictions(self, api_client, gym_tenant):
        member_user = create_user(
            gym_tenant, User.ROLE_MEMBER, "member_view@fitgate.com"
        )
        Member.objects.create(
            gym=gym_tenant,
            user=member_user,
            phone="+251911223344",
            waiver_accepted_at=timezone.now(),
        )

        # Create good item and out of service item
        good_eq = Equipment.objects.create(
            gym=gym_tenant,
            category="barbell",
            name="Power Bar",
            serial_number="SECRET-SERIAL-1",
            quantity=2,
            min_qty_threshold=1,
            unit_purchase_price_etb=Decimal("12000.00"),
            condition=CONDITION_GOOD,
        )
        broken_eq = Equipment.objects.create(
            gym=gym_tenant,
            category="cardio_machines",
            name="Broken Treadmill",
            serial_number="SECRET-SERIAL-2",
            quantity=1,
            unit_purchase_price_etb=Decimal("60000.00"),
            condition=CONDITION_OUT_OF_SERVICE,
        )

        auth_client(api_client, member_user, gym_tenant)

        # By default show_unavailable_equipment is False -> broken_eq hidden
        res = api_client.get("/api/gym/equipment/")
        assert res.status_code == 200
        ids = [item["id"] for item in res.data]
        assert str(good_eq.id) in ids
        assert str(broken_eq.id) not in ids

        # Member response strips serial_number, maintenance_logs, min_qty_threshold, price
        item = [i for i in res.data if i["id"] == str(good_eq.id)][0]
        assert item.get("serial_number") is None
        assert item.get("maintenance_logs") is None
        assert item.get("min_qty_threshold") is None
        assert item.get("unit_purchase_price_etb") is None

        # When show_unavailable_equipment is True, unavailable equipment is visible to member
        config, _ = GymConfig.objects.get_or_create(gym=gym_tenant)
        config.show_unavailable_equipment = True
        config.save()

        res2 = api_client.get("/api/gym/equipment/")
        assert res2.status_code == 200
        ids2 = [item["id"] for item in res2.data]
        assert str(good_eq.id) in ids2
        assert str(broken_eq.id) in ids2


@pytest.mark.django_db
class TestThreeEquipmentModes:
    def test_mode_1_registry_empty(self, member_bundle):
        gym = member_bundle["gym"]
        member = member_bundle["member"]

        # Gym has NO equipment registered
        assert Equipment.objects.filter(gym=gym).count() == 0
        context = build_ai_generation_context(member, gym, date(2026, 11, 2))
        assert context["plan_parameters"]["equipment_source"] == "member profile only"
        # Profile has barbell, dumbbells, bench, bodyweight_only -> mapped to available categories
        avail = context["plan_parameters"]["available_equipment"]
        assert "barbell" in avail
        assert "dumbbells" in avail
        assert "bench" in avail
        assert "bodyweight" in avail

    def test_mode_2_unusable_removed(self, member_bundle):
        gym = member_bundle["gym"]
        member = member_bundle["member"]

        # Setting is_equipment_list_complete is False
        config = GymConfig.objects.get(gym=gym)
        config.is_equipment_list_complete = False
        config.save()

        # Add usable barbell and bench
        Equipment.objects.create(
            gym=gym,
            category="barbell",
            name="Barbell",
            quantity=2,
            condition=CONDITION_GOOD,
        )
        Equipment.objects.create(
            gym=gym,
            category="bench",
            name="Flat Bench",
            quantity=1,
            condition=CONDITION_GOOD,
        )
        # Add dumbbells under maintenance (unusable)
        Equipment.objects.create(
            gym=gym,
            category="dumbbells",
            name="Dumbbells Set",
            quantity=5,
            condition=CONDITION_UNDER_MAINTENANCE,
        )

        context = build_ai_generation_context(member, gym, date(2026, 11, 2))
        assert (
            context["plan_parameters"]["equipment_source"]
            == "gym registry (unusable items removed)"
        )
        avail = context["plan_parameters"]["available_equipment"]
        excluded = context["plan_parameters"]["excluded_equipment"]
        # Dumbbells are under maintenance -> excluded!
        assert "dumbbells" in excluded
        assert "barbell" in avail
        assert "bench" in avail

    def test_mode_3_complete_registry_intersection(self, member_bundle):
        gym = member_bundle["gym"]
        member = member_bundle["member"]

        # Owner has checked "My equipment list is complete"
        config = GymConfig.objects.get(gym=gym)
        config.is_equipment_list_complete = True
        config.save()

        # Gym only registers barbell and bench as usable
        Equipment.objects.create(
            gym=gym,
            category="barbell",
            name="Barbell",
            quantity=5,
            condition=CONDITION_GOOD,
        )
        Equipment.objects.create(
            gym=gym,
            category="bench",
            name="Flat Bench",
            quantity=3,
            condition=CONDITION_NEEDS_MAINTENANCE,
        )

        context = build_ai_generation_context(member, gym, date(2026, 11, 2))
        assert (
            context["plan_parameters"]["equipment_source"]
            == "gym registry (complete list)"
        )
        avail = context["plan_parameters"]["available_equipment"]
        excluded = context["plan_parameters"]["excluded_equipment"]

        # Barbell and bench are in gym registry and in member profile -> available!
        assert "barbell" in avail
        assert "bench" in avail
        assert "bodyweight" in avail
        # Dumbbells were in profile but NOT registered in gym complete registry -> excluded!
        assert "dumbbells" in excluded
