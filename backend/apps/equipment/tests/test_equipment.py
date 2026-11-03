"""Tests for Sprint 25: Equipment management, maintenance logs, and AI rules engine integration."""

from datetime import date

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Notification, User
from apps.accounts.tokens import get_tokens_for_user
from apps.equipment.constants import (
    CONDITION_GOOD,
    CONDITION_NEEDS_MAINTENANCE,
    CONDITION_OUT_OF_SERVICE,
    CONDITION_UNDER_MAINTENANCE,
)
from apps.equipment.models import Equipment, MaintenanceLog
from apps.tenants.models import GymTenant


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def gym_tenant(db):
    return GymTenant.objects.create(
        name="FitGate Bole",
        subdomain="fitgate-bole",
        status=GymTenant.STATUS_ACTIVE,
        tls_confirmed_at=timezone.now(),
    )


@pytest.fixture
def other_gym_tenant(db):
    return GymTenant.objects.create(
        name="FitGate Kazanchis",
        subdomain="fitgate-kazanchis",
        status=GymTenant.STATUS_ACTIVE,
        tls_confirmed_at=timezone.now(),
    )


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


@pytest.mark.django_db
class TestEquipmentPermissions:
    def test_owner_can_crud_equipment(self, api_client, gym_tenant):
        owner = create_user(gym_tenant, User.ROLE_OWNER, "owner@fitgate.com")
        auth_client(api_client, owner, gym_tenant)

        # Create
        res = api_client.post(
            "/api/gym/equipment/",
            {
                "category": "barbell",
                "name": "Olympic Barbell 20kg",
                "serial_number": "OB-001",
                "quantity": 5,
                "min_qty_threshold": 2,
                "condition": "good",
            },
            format="json",
        )
        assert res.status_code == 201
        eq_id = res.data["id"]

        # List
        res_list = api_client.get("/api/gym/equipment/")
        assert res_list.status_code == 200
        assert len(res_list.data) == 1

        # Update
        res_update = api_client.put(
            f"/api/gym/equipment/{eq_id}/",
            {
                "category": "barbell",
                "name": "Olympic Barbell 20kg Updated",
                "quantity": 4,
                "min_qty_threshold": 2,
                "condition": "good",
            },
            format="json",
        )
        assert res_update.status_code == 200
        assert res_update.data["name"] == "Olympic Barbell 20kg Updated"

        # Delete
        res_del = api_client.delete(f"/api/gym/equipment/{eq_id}/")
        assert res_del.status_code == 204

    def test_manager_can_crud_equipment(self, api_client, gym_tenant):
        manager = create_user(gym_tenant, User.ROLE_MANAGER, "manager@fitgate.com")
        auth_client(api_client, manager, gym_tenant)

        res = api_client.post(
            "/api/gym/equipment/",
            {
                "category": "dumbbells",
                "name": "Rubber Hex Dumbbell Set",
                "quantity": 10,
                "min_qty_threshold": 3,
                "condition": "good",
            },
            format="json",
        )
        assert res.status_code == 201

    def test_trainer_and_reception_cannot_create_or_delete(
        self, api_client, gym_tenant
    ):
        trainer = create_user(gym_tenant, User.ROLE_TRAINER, "trainer@fitgate.com")
        eq = Equipment.all_objects.create(
            gym=gym_tenant,
            category="dumbbells",
            name="Dumbbells",
            quantity=5,
            min_qty_threshold=1,
        )

        auth_client(api_client, trainer, gym_tenant)
        res_get = api_client.get(f"/api/gym/equipment/{eq.id}/")
        assert res_get.status_code == 200

        res_post = api_client.post(
            "/api/gym/equipment/", {"name": "Test"}, format="json"
        )
        assert res_post.status_code == 403

        res_del = api_client.delete(f"/api/gym/equipment/{eq.id}/")
        assert res_del.status_code == 403

    def test_super_admin_blocked_from_gym_equipment(self, api_client, gym_tenant):
        admin = User.objects.create_user(
            email="admin@fitgate.internal",
            password="ValidPassword123!",
            role=User.ROLE_SUPER_ADMIN,
            is_active=True,
        )
        admin.force_password_change = False
        admin.must_change_password = False
        admin.save()

        # At apex domain: blocked with 403 (PermissionDenied: Tenant context required)
        auth_client(api_client, admin, gym=None)
        res_apex = api_client.get("/api/gym/equipment/")
        assert res_apex.status_code == 403

        # At gym subdomain: blocked with 401 (tenant mismatch)
        auth_client(api_client, admin, gym_tenant)
        res_sub = api_client.get("/api/gym/equipment/")
        assert res_sub.status_code == 401


@pytest.mark.django_db
class TestEquipmentTenantIsolation:
    def test_cross_tenant_access_denied(self, api_client, gym_tenant, other_gym_tenant):
        owner_a = create_user(gym_tenant, User.ROLE_OWNER, "owner_a@fitgate.com")
        eq_b = Equipment.all_objects.create(
            gym=other_gym_tenant,
            category="barbell",
            name="Gym B Barbell",
            quantity=2,
            min_qty_threshold=1,
        )

        auth_client(api_client, owner_a, gym_tenant)

        # Gym A cannot retrieve Gym B equipment
        res = api_client.get(f"/api/gym/equipment/{eq_b.id}/")
        assert res.status_code == 404

        # Gym A list does not contain Gym B equipment
        res_list = api_client.get("/api/gym/equipment/")
        assert res_list.status_code == 200
        assert len(res_list.data) == 0


@pytest.mark.django_db
class TestLowQuantityAlert:
    def test_boundary_low_quantity_alert(self, api_client, gym_tenant):
        owner = create_user(gym_tenant, User.ROLE_OWNER, "owner_thresh@fitgate.com")
        auth_client(api_client, owner, gym_tenant)

        # Exact boundary: quantity == min_qty_threshold -> is_low_quantity is True
        eq_equal = Equipment.all_objects.create(
            gym=gym_tenant,
            category="resistance_bands",
            name="Resistance Band Set",
            quantity=2,
            min_qty_threshold=2,
        )
        # Above boundary: quantity > min_qty_threshold -> is_low_quantity is False
        eq_above = Equipment.all_objects.create(
            gym=gym_tenant,
            category="kettlebells",
            name="Kettlebell 16kg",
            quantity=3,
            min_qty_threshold=2,
        )

        res_eq = api_client.get(f"/api/gym/equipment/{eq_equal.id}/")
        assert res_eq.data["is_low_quantity"] is True

        res_above = api_client.get(f"/api/gym/equipment/{eq_above.id}/")
        assert res_above.data["is_low_quantity"] is False


@pytest.mark.django_db
class TestIssueReportingAndConditionTransitions:
    def test_report_issue_notifies_owner_and_updates_condition(
        self, api_client, gym_tenant
    ):
        owner = create_user(gym_tenant, User.ROLE_OWNER, "owner_notif@fitgate.com")
        trainer = create_user(
            gym_tenant, User.ROLE_TRAINER, "trainer_report@fitgate.com"
        )
        eq = Equipment.all_objects.create(
            gym=gym_tenant,
            category="cable_machine",
            name="Dual Cable Cross",
            quantity=1,
            min_qty_threshold=1,
            condition=CONDITION_GOOD,
        )

        auth_client(api_client, trainer, gym_tenant)

        # Trainer reports issue
        res = api_client.post(
            f"/api/gym/equipment/{eq.id}/report-issue/",
            {
                "issue_reason": "broken",
                "other_details": "Right pulley cable snapped during use.",
            },
            format="json",
        )
        assert res.status_code == 201

        # Equipment condition transitions to needs_maintenance
        eq.refresh_from_db()
        assert eq.condition == CONDITION_NEEDS_MAINTENANCE

        # Owner has notification
        notif = Notification.all_objects.filter(
            recipient=owner, type="equipment_issue"
        ).first()
        assert notif is not None
        assert "Dual Cable Cross" in notif.message

        # Log created
        log = MaintenanceLog.all_objects.filter(equipment=eq).first()
        assert log is not None
        assert log.reported_by == trainer
        assert log.issue_reason == "broken"
        assert log.resolved_at is None

    def test_duplicate_report_on_under_maintenance_rejected(
        self, api_client, gym_tenant
    ):
        trainer = create_user(gym_tenant, User.ROLE_TRAINER, "trainer_dup@fitgate.com")
        eq = Equipment.all_objects.create(
            gym=gym_tenant,
            category="cable_machine",
            name="Pulley Station",
            quantity=1,
            min_qty_threshold=1,
            condition=CONDITION_UNDER_MAINTENANCE,
        )

        auth_client(api_client, trainer, gym_tenant)

        res = api_client.post(
            f"/api/gym/equipment/{eq.id}/report-issue/",
            {"issue_reason": "worn_out"},
            format="json",
        )
        assert res.status_code == 400
        detail_msg = res.data.get("detail", "")
        if isinstance(detail_msg, list):
            detail_msg = " ".join(detail_msg)
        assert "already under maintenance" in detail_msg.lower()

    def test_resolve_maintenance_on_condition_good(self, api_client, gym_tenant):
        owner = create_user(gym_tenant, User.ROLE_OWNER, "owner_resolve@fitgate.com")
        eq = Equipment.all_objects.create(
            gym=gym_tenant,
            category="barbell",
            name="Bent Barbell",
            quantity=1,
            min_qty_threshold=1,
            condition=CONDITION_NEEDS_MAINTENANCE,
        )
        log = MaintenanceLog.all_objects.create(
            gym=gym_tenant,
            equipment=eq,
            reported_by=owner,
            issue_reason="broken",
            reported_at=timezone.now(),
        )

        auth_client(api_client, owner, gym_tenant)

        # Owner marks equipment good
        res = api_client.patch(
            f"/api/gym/equipment/{eq.id}/condition/",
            {
                "condition": CONDITION_GOOD,
                "resolution_notes": "Replaced bar with new tested Olympic barbell.",
            },
            format="json",
        )
        assert res.status_code == 200

        eq.refresh_from_db()
        assert eq.condition == CONDITION_GOOD

        log.refresh_from_db()
        assert log.resolved_at is not None
        assert log.resolved_by == owner
        assert "Replaced bar" in log.resolution_notes


@pytest.mark.django_db
class TestMemberVisibility:
    def test_member_visibility_respects_gym_setting(self, api_client, gym_tenant):
        member_user = create_user(gym_tenant, User.ROLE_MEMBER, "member@fitgate.com")
        auth_client(api_client, member_user, gym_tenant)

        # 1 usable item
        Equipment.all_objects.create(
            gym=gym_tenant,
            category="dumbbells",
            name="Dumbbells",
            quantity=5,
            min_qty_threshold=1,
            condition=CONDITION_GOOD,
        )
        # 1 out of service item
        Equipment.all_objects.create(
            gym=gym_tenant,
            category="leg_press",
            name="Broken Leg Press",
            quantity=1,
            min_qty_threshold=1,
            condition=CONDITION_OUT_OF_SERVICE,
        )

        # By default, show_unavailable_equipment_to_members is False
        res = api_client.get("/api/gym/equipment/")
        assert res.status_code == 200
        names = [item["name"] for item in res.data]
        assert "Dumbbells" in names
        assert "Broken Leg Press" not in names

        # Enable show_unavailable_equipment_to_members
        from apps.tenants.models import GymConfig

        config, _ = GymConfig.objects.get_or_create(gym=gym_tenant)
        config.show_unavailable_equipment = True
        config.save()

        res_all = api_client.get("/api/gym/equipment/")
        assert res_all.status_code == 200
        names_all = [item["name"] for item in res_all.data]
        assert "Dumbbells" in names_all
        assert "Broken Leg Press" in names_all


@pytest.mark.django_db
class TestAIRulesEngineEquipmentIntegration:
    def test_out_of_service_equipment_excluded_from_ai_rules(self, gym_tenant):
        from apps.trainers.rules_engine import filter_prescribed_equipment

        res = filter_prescribed_equipment(
            equipment_codes=["full_gym"],
            limitation_codes=["none"],
            unavailable_equipment=[
                {"name": "Broken Barbell", "category": "barbell"},
                {"name": "Out of Stock Bands", "category": "resistance_bands"},
            ],
        )

        assert "barbell" in res["excluded_equipment"]
        assert "resistance_bands" in res["excluded_equipment"]
        assert "unavailable" in res["exclusion_reasons"]["barbell"]

    def test_build_ai_generation_context_auto_excludes_out_of_service(self, gym_tenant):
        from apps.memberships.models import Member, MembershipPlan, MemberSubscription
        from apps.tenants.models import GymConfig
        from apps.trainers.models import FitnessProfile, Trainer, TrainerAssignment
        from apps.trainers.rules_engine import build_ai_generation_context

        GymConfig.objects.update_or_create(
            gym=gym_tenant,
            defaults={"has_trainer_module": True, "has_ai_plans": True},
        )
        gym_tenant.refresh_from_db()
        trainer_user = create_user(
            gym_tenant, User.ROLE_TRAINER, "trainer_ai@fitgate.com"
        )
        trainer_profile = getattr(trainer_user, "trainer_profile", None)
        if not trainer_profile:
            trainer_profile = Trainer.all_objects.create(
                user=trainer_user, gym=gym_tenant, is_active=True
            )

        member_user = create_user(gym_tenant, User.ROLE_MEMBER, "member_ai@fitgate.com")
        member = Member.all_objects.create(
            gym=gym_tenant,
            user=member_user,
            full_name="Abebe Bikila",
            phone="+251911223344",
            date_of_birth=date(1995, 5, 1),
            gender="male",
            status=Member.STATUS_ACTIVE,
            waiver_accepted_at=timezone.now(),
        )
        TrainerAssignment.all_objects.create(
            gym=gym_tenant,
            member=member,
            trainer=trainer_profile,
        )
        plan = MembershipPlan.all_objects.create(
            gym=gym_tenant,
            name="Gold Plan",
            price_etb=2000,
            duration_value=1,
            duration_unit=MembershipPlan.DURATION_MONTHS,
            trainer_inclusive=True,
            is_active=True,
        )
        MemberSubscription.all_objects.create(
            gym=gym_tenant,
            member=member,
            plan=plan,
            start_date=date(2026, 11, 1),
            end_date=date(2026, 11, 30),
            status=MemberSubscription.STATUS_ACTIVE,
        )
        FitnessProfile.all_objects.create(
            gym=gym_tenant,
            member=member,
            goal="muscle_gain",
            fitness_level="intermediate",
            training_days_per_week=4,
            session_length_minutes=60,
            equipment_access=["full_gym"],
            health_limitations=["none"],
        )
        from apps.memberships.models import BodyMetrics

        BodyMetrics.all_objects.create(
            gym=gym_tenant,
            member=member,
            recorded_by=trainer_user,
            weight_kg=75.0,
            height_cm=180.0,
        )

        # Create equipment: 1 good barbell, 1 out-of-service leg press
        Equipment.all_objects.create(
            gym=gym_tenant,
            category="barbell",
            name="Olympic Barbell",
            quantity=2,
            condition=CONDITION_GOOD,
        )
        Equipment.all_objects.create(
            gym=gym_tenant,
            category="leg_press",
            name="Incline Leg Press",
            quantity=1,
            condition=CONDITION_OUT_OF_SERVICE,
        )

        ctx = build_ai_generation_context(
            member=member,
            gym=gym_tenant,
            week_start_date=date(2026, 11, 2),
        )

        assert "barbell" in ctx["plan_parameters"]["available_equipment"]
        assert "leg_press" in ctx["plan_parameters"]["excluded_equipment"]
        assert "unavailable" in ctx["plan_parameters"]["exclusion_reasons"]["leg_press"]
