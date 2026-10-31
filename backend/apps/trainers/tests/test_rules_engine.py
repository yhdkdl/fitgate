from datetime import date, timedelta

import pytest
from django.utils import timezone

from apps.accounts.models import User
from apps.memberships.models import (
    BodyMetrics,
    Member,
    MembershipPlan,
    MemberSubscription,
)
from apps.tenants.models import GymConfig, GymTenant
from apps.trainers.models import FitnessProfile, TrainerAssignment
from apps.trainers.rules_engine import (
    AdaptiveRecoveryStrategy,
    LinearPeriodizationStrategy,
    RulesEngineGatekeeperError,
    build_ai_generation_context,
    determine_training_phase,
    filter_prescribed_equipment,
    validate_generation_eligibility,
)


@pytest.fixture
def gym_tenant(db):
    gym = GymTenant.objects.create(
        name="FitGate Bole Hub",
        subdomain="bolehub",
        tier=GymTenant.TIER_GROWTH,
        status=GymTenant.STATUS_ACTIVE,
        contact_phone="+251911223344",
        location="Bole, Addis Ababa",
        tls_confirmed_at="2026-10-11T10:00:00Z",
    )
    GymConfig.objects.update_or_create(
        gym=gym,
        defaults={"has_trainer_module": True, "has_ai_plans": True},
    )
    gym.refresh_from_db()
    return gym


@pytest.fixture
def trainer_user(db, gym_tenant):
    user = User.objects.create_user(
        email="trainer_rules@bolehub.com",
        password="TrainerPassword123!",
        full_name="Abebe Bikila",
        gym=gym_tenant,
        role=User.ROLE_TRAINER,
        must_change_password=False,
    )
    return user


@pytest.fixture
def member_bundle(db, gym_tenant, trainer_user):
    member_user = User.objects.create_user(
        email="member_secret@bolehub.com",
        password="MemberPassword123!",
        full_name="Makeda Saba",
        gym=gym_tenant,
        role=User.ROLE_MEMBER,
        must_change_password=False,
    )
    member = Member.objects.create(
        gym=gym_tenant,
        user=member_user,
        full_name="Makeda Saba",
        phone="+251911998877",
        gender="female",
        date_of_birth=date(1996, 5, 12),
        status=Member.STATUS_ACTIVE,
        waiver_accepted_at=timezone.now(),
    )
    plan = MembershipPlan.objects.create(
        gym=gym_tenant,
        name="Growth VIP Athlete",
        price_etb=5000,
        duration_value=3,
        duration_unit=MembershipPlan.DURATION_MONTHS,
        trainer_inclusive=True,
        is_active=True,
    )
    today = timezone.localdate()
    sub = MemberSubscription.objects.create(
        gym=gym_tenant,
        member=member,
        plan=plan,
        start_date=today - timedelta(days=10),
        end_date=today + timedelta(days=80),
        status=MemberSubscription.STATUS_ACTIVE,
    )
    trainer_profile = trainer_user.trainer_profile
    TrainerAssignment.objects.create(
        gym=gym_tenant,
        member=member,
        trainer=trainer_profile,
    )
    profile = FitnessProfile.objects.create(
        gym=gym_tenant,
        member=member,
        goal="fat_loss",
        fitness_level="beginner",
        training_days_per_week=4,
        session_length_minutes=60,
        health_limitations="Mild lower back stiffness on heavy loads",
        equipment_access="Full commercial gym",
        dietary_notes="Orthodox fasting observed (Wednesday and Friday vegan)",
    )
    metrics = BodyMetrics.objects.create(
        gym=gym_tenant,
        member=member,
        recorded_by=trainer_user,
        weight_kg=68.0,
        height_cm=165.0,
        measurements={
            "waist_cm": 76.0,
            "neck_cm": 34.0,
            "resting_heart_rate": 66,
            "body_fat_percentage": 24.5,
        },
    )
    return {
        "gym": gym_tenant,
        "member": member,
        "subscription": sub,
        "trainer": trainer_profile,
        "profile": profile,
        "metrics": metrics,
    }


class TestRulesEnginePhaseAndStrategies:
    """Tests phase derivation, swappable intensity strategies, and equipment filtering."""

    def test_determine_training_phase_progression(self):
        start = date(2026, 1, 1)
        end = date(2026, 3, 31)  # ~90 days

        # Foundation: day 10
        assert determine_training_phase(start, end, date(2026, 1, 11)) == "foundation"

        # Build: day 45
        assert determine_training_phase(start, end, date(2026, 2, 15)) == "build"

        # Peak: day 75
        assert determine_training_phase(start, end, date(2026, 3, 17)) == "peak"

    def test_beginner_foundation_intensity(self):
        strategy = LinearPeriodizationStrategy()
        res = strategy.calculate_intensity(
            phase="foundation",
            fitness_level="beginner",
            checkin={"energy": 3, "recovery": 3, "motivation": 3},
        )
        assert res["intensity_tier"] == "low-moderate"
        assert res["target_rpe"] == "6-7"
        assert res["rep_range"] == "12-15"
        assert res["estimated_percentage_1rm"] == 60

    def test_advanced_peak_intensity(self):
        strategy = LinearPeriodizationStrategy()
        res = strategy.calculate_intensity(
            phase="peak",
            fitness_level="advanced",
            checkin={"energy": 5, "recovery": 5, "motivation": 5},
        )
        assert res["intensity_tier"] == "peak"
        assert res["target_rpe"] == "8.5-9.5"
        assert res["rep_range"] == "3-5"
        assert res["estimated_percentage_1rm"] == 91  # 88 base + 3 increase
        assert res["progression_decision"] == "progressive_increase"

    def test_two_swappable_intensity_strategies_produce_different_outputs(self):
        """
        Two different intensity strategies plugged in with the same input produce
        measurably different outputs with no change to caller interface.
        """
        input_kwargs = {
            "phase": "build",
            "fitness_level": "intermediate",
            "checkin": {"energy": 2, "recovery": 2, "motivation": 3},
        }

        linear = LinearPeriodizationStrategy()
        adaptive = AdaptiveRecoveryStrategy()

        linear_res = linear.calculate_intensity(**input_kwargs)
        adaptive_res = adaptive.calculate_intensity(**input_kwargs)

        # Linear steps down slightly to 70% load and RPE 6-7
        assert linear_res["estimated_percentage_1rm"] == 70
        assert linear_res["progression_decision"] == "deload_step"

        # Adaptive aggressively drops to active recovery 50% load and RPE 5-6
        assert adaptive_res["estimated_percentage_1rm"] == 50
        assert adaptive_res["intensity_tier"] == "active_recovery"
        assert adaptive_res["target_rpe"] == "5-6"
        assert adaptive_res["progression_decision"] == "active_recovery_deload"

        # Outputs are distinctly different
        assert (
            linear_res["estimated_percentage_1rm"]
            != adaptive_res["estimated_percentage_1rm"]
        )
        assert linear_res["target_rpe"] != adaptive_res["target_rpe"]

    def test_equipment_filter_with_limitations_and_out_of_service(self):
        # Case A: Lower back limitation excludes barbell and squat rack
        res_back = filter_prescribed_equipment(
            equipment_access="full gym",
            health_limitations="Lower back lumbar tension",
        )
        assert "barbell" in res_back["excluded_equipment"]
        assert "squat_rack" in res_back["excluded_equipment"]
        assert "dumbbells" in res_back["available_equipment"]
        assert "spinal axial loading" in res_back["exclusion_reasons"]["barbell"]

        # Case B: Dumbbell-only access
        res_db = filter_prescribed_equipment(
            equipment_access="Dumbbells only at home",
            health_limitations="None",
        )
        assert "barbell" in res_db["excluded_equipment"]
        assert "cable_machine" in res_db["excluded_equipment"]
        assert "dumbbells" in res_db["available_equipment"]

        # Case C: Gym out of service / under maintenance equipment
        res_maint = filter_prescribed_equipment(
            equipment_access="full gym",
            health_limitations="None",
            unavailable_equipment=["leg_press", "cable_machine"],
        )
        assert "leg_press" in res_maint["excluded_equipment"]
        assert "cable_machine" in res_maint["excluded_equipment"]
        assert "maintenance" in res_maint["exclusion_reasons"]["leg_press"]


@pytest.mark.django_db
class TestRulesEngineGatekeeperAndPrivacy:
    """Verifies gatekeeper refusals and zero personal identifier leakage."""

    def test_gatekeeper_refuses_when_gym_ai_plans_disabled(self, member_bundle):
        gym = member_bundle["gym"]
        gym.config.has_ai_plans = False
        gym.config.save()

        with pytest.raises(RulesEngineGatekeeperError) as exc_info:
            validate_generation_eligibility(member_bundle["member"], gym)
        assert exc_info.value.code == "gym_ai_disabled"

    def test_gatekeeper_refuses_when_not_trainer_inclusive_plan(self, member_bundle):
        sub = member_bundle["subscription"]
        sub.plan.trainer_inclusive = False
        sub.plan.save()

        with pytest.raises(RulesEngineGatekeeperError) as exc_info:
            validate_generation_eligibility(
                member_bundle["member"], member_bundle["gym"]
            )
        assert exc_info.value.code == "no_trainer_plan"

    def test_gatekeeper_refuses_when_no_assigned_trainer(self, member_bundle):
        TrainerAssignment.all_objects.filter(member=member_bundle["member"]).delete()

        with pytest.raises(RulesEngineGatekeeperError) as exc_info:
            validate_generation_eligibility(
                member_bundle["member"], member_bundle["gym"]
            )
        assert exc_info.value.code == "no_assigned_trainer"

    def test_gatekeeper_refuses_when_profile_incomplete(self, member_bundle):
        profile = member_bundle["profile"]
        profile.goal = ""
        profile.save()

        with pytest.raises(RulesEngineGatekeeperError) as exc_info:
            validate_generation_eligibility(
                member_bundle["member"], member_bundle["gym"]
            )
        assert exc_info.value.code == "incomplete_profile"

    def test_gatekeeper_refuses_when_no_measurements_recorded(self, member_bundle):
        BodyMetrics.all_objects.filter(member=member_bundle["member"]).delete()

        with pytest.raises(RulesEngineGatekeeperError) as exc_info:
            validate_generation_eligibility(
                member_bundle["member"], member_bundle["gym"]
            )
        assert exc_info.value.code == "no_measurements"

    def test_ai_context_contains_zero_personal_identifiers(self, member_bundle):
        """
        No personal identifiers (name, phone, email, member id) are ever sent to the provider.
        Only age, gender, goal, fitness level, training days, session length, equipment, limitations,
        dietary notes, trainer note, and latest measurements.
        """
        member = member_bundle["member"]
        gym = member_bundle["gym"]
        week_start = timezone.localdate()

        context = build_ai_generation_context(
            member=member,
            gym=gym,
            week_start_date=week_start,
            trainer_note_for_week="Focus on glute activation and tempo reps",
            checkin={"energy": 4, "recovery": 4, "motivation": 4},
        )

        import json

        payload_str = json.dumps(context)

        # STRICT PRIVACY ASSERTIONS:
        assert member.full_name not in payload_str
        assert "Makeda" not in payload_str
        assert "Saba" not in payload_str
        assert member.phone not in payload_str
        assert "+251911998877" not in payload_str
        assert member.user.email not in payload_str
        assert "member_secret" not in payload_str
        assert str(member.id) not in payload_str

        # Safe biometric and parameter checks
        assert context["demographics"]["gender"] == "female"
        assert context["demographics"]["age"] is not None
        assert context["biometrics"]["weight_kg"] == 68.0
        assert context["biometrics"]["height_cm"] == 165.0
        assert context["profile"]["goal"] == "fat_loss"
        assert context["profile"]["fitness_level"] == "beginner"
        assert (
            context["plan_parameters"]["trainer_note_for_week"]
            == "Focus on glute activation and tempo reps"
        )
        assert "barbell" in context["plan_parameters"]["excluded_equipment"]
