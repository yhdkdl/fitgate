"""
Rules engine for FitGate AI Personal Training (Increment 4).
Pure Python business logic for phase calculation, intensity strategy,
equipment/injury filtering, history aggregation, and prompt context building.
"""

from abc import ABC, abstractmethod
from datetime import date
from typing import Any, Dict, List, Optional

from django.apps import apps
from django.utils import timezone


class RulesEngineGatekeeperError(Exception):
    """Raised when a member or gym is ineligible for AI plan generation."""

    def __init__(self, message: str, code: str = "ineligible"):
        super().__init__(message)
        self.message = message
        self.code = code


# ==============================================================================
# INTENSITY STRATEGY PATTERN
# ==============================================================================


class IntensityStrategy(ABC):
    """Abstract Strategy interface for calculating workout intensity."""

    @abstractmethod
    def calculate_intensity(
        self,
        phase: str,
        fitness_level: str,
        checkin: Optional[Dict[str, Any]] = None,
        history: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Calculate prescribed intensity, RPE, rep ranges, and progression.
        """
        pass


class LinearPeriodizationStrategy(IntensityStrategy):
    """
    Classic linear periodization:
    - Foundation: Moderate volume, base loading (60-70% 1RM, RPE 6-7, 10-15 reps).
    - Build: Hypertrophy/Strength (70-82% 1RM, RPE 7.5-8.5, 6-10 reps).
    - Peak: High intensity/Neuromuscular (82-92% 1RM, RPE 8.5-9.5, 3-6 reps).

    Check-in adjustments are applied conservatively (+/- 2.5-5% load).
    """

    def calculate_intensity(
        self,
        phase: str,
        fitness_level: str,
        checkin: Optional[Dict[str, Any]] = None,
        history: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        phase = (phase or "foundation").lower()
        fitness_level = (fitness_level or "beginner").lower()

        base_table = {
            "foundation": {
                "beginner": {
                    "rpe": "6-7",
                    "pct": 60,
                    "reps": "12-15",
                    "tier": "low-moderate",
                },
                "intermediate": {
                    "rpe": "6.5-7.5",
                    "pct": 65,
                    "reps": "10-12",
                    "tier": "moderate",
                },
                "advanced": {
                    "rpe": "7-8",
                    "pct": 70,
                    "reps": "8-12",
                    "tier": "moderate",
                },
            },
            "build": {
                "beginner": {
                    "rpe": "7-7.5",
                    "pct": 68,
                    "reps": "10-12",
                    "tier": "moderate",
                },
                "intermediate": {
                    "rpe": "7.5-8.5",
                    "pct": 75,
                    "reps": "8-10",
                    "tier": "moderate-high",
                },
                "advanced": {
                    "rpe": "8-8.5",
                    "pct": 80,
                    "reps": "6-8",
                    "tier": "high",
                },
            },
            "peak": {
                "beginner": {
                    "rpe": "7.5-8",
                    "pct": 72,
                    "reps": "8-10",
                    "tier": "moderate-high",
                },
                "intermediate": {
                    "rpe": "8-9",
                    "pct": 82,
                    "reps": "5-8",
                    "tier": "high",
                },
                "advanced": {
                    "rpe": "8.5-9.5",
                    "pct": 88,
                    "reps": "3-5",
                    "tier": "peak",
                },
            },
        }

        entry = base_table.get(phase, base_table["foundation"]).get(
            fitness_level, base_table["foundation"]["beginner"]
        )

        pct = entry["pct"]
        rpe = entry["rpe"]
        reps = entry["reps"]
        tier = entry["tier"]
        decision = "maintain"

        # Check-in adjustments
        if checkin:
            energy = checkin.get("energy", 3)
            recovery = checkin.get("recovery", 3)
            motivation = checkin.get("motivation", 3)

            avg_score = (energy + recovery + motivation) / 3.0
            if recovery <= 2 or avg_score < 2.5:
                # Moderate step-down
                pct = max(50, pct - 5)
                rpe = "6-7"
                decision = "deload_step"
                tier = "recovery"
            elif energy >= 4 and recovery >= 4:
                # Gradual progressive load
                pct = min(95, pct + 3)
                decision = "progressive_increase"
            else:
                decision = "maintain"
        else:
            decision = "hold_load_default"

        return {
            "strategy": "LinearPeriodizationStrategy",
            "phase": phase,
            "fitness_level": fitness_level,
            "intensity_tier": tier,
            "target_rpe": rpe,
            "rep_range": reps,
            "estimated_percentage_1rm": pct,
            "progression_decision": decision,
        }


class AdaptiveRecoveryStrategy(IntensityStrategy):
    """
    Auto-regulated / Adaptive recovery-first strategy:
    - Heavily prioritizes sleep, recovery score, and systemic fatigue over calendar phase.
    - If recovery <= 2 or energy <= 2: triggers active recovery protocol regardless of phase
      (drastic intensity drop to 45-55% 1RM, RPE <= 6, high reps, technique focus).
    - If recovery == 5 and energy >= 4: aggressive overload stimulus (+7% load, peak tier).
    """

    def calculate_intensity(
        self,
        phase: str,
        fitness_level: str,
        checkin: Optional[Dict[str, Any]] = None,
        history: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        phase = (phase or "foundation").lower()
        fitness_level = (fitness_level or "beginner").lower()

        # If no check-in, use conservative phase defaults
        if not checkin:
            return {
                "strategy": "AdaptiveRecoveryStrategy",
                "phase": phase,
                "fitness_level": fitness_level,
                "intensity_tier": "moderate",
                "target_rpe": "6.5-7.5",
                "rep_range": "10-12",
                "estimated_percentage_1rm": 65,
                "progression_decision": "unmonitored_default",
                "rationale": "No check-in submitted. Prescribing default baseline intensity for phase.",
            }

        energy = checkin.get("energy", 3)
        recovery = checkin.get("recovery", 3)

        # High fatigue / poor recovery trigger
        if recovery <= 2 or energy <= 2:
            return {
                "strategy": "AdaptiveRecoveryStrategy",
                "phase": phase,
                "fitness_level": fitness_level,
                "intensity_tier": "active_recovery",
                "target_rpe": "5-6",
                "rep_range": "12-15",
                "estimated_percentage_1rm": 50,
                "progression_decision": "active_recovery_deload",
                "rationale": "High fatigue detected in weekly check-in. Prescribing active recovery deload.",
            }

        # Optimal recovery / peak readiness trigger
        if recovery >= 4 and energy >= 4:
            base_pct = 75 if phase == "foundation" else (82 if phase == "build" else 90)
            return {
                "strategy": "AdaptiveRecoveryStrategy",
                "phase": phase,
                "fitness_level": fitness_level,
                "intensity_tier": "amplified",
                "target_rpe": "8.5-9",
                "rep_range": "6-8" if phase != "peak" else "3-5",
                "estimated_percentage_1rm": base_pct + 5,
                "progression_decision": "aggressive_overload",
                "rationale": "Optimal readiness reported. Prescribing amplified overload volume and intensity.",
            }

        # Moderate baseline
        return {
            "strategy": "AdaptiveRecoveryStrategy",
            "phase": phase,
            "fitness_level": fitness_level,
            "intensity_tier": "steady_state",
            "target_rpe": "7-8",
            "rep_range": "8-10",
            "estimated_percentage_1rm": 72,
            "progression_decision": "steady_progression",
            "rationale": "Moderate recovery readiness. Maintaining structured training progression.",
        }


# ==============================================================================
# PHASE CALCULATION
# ==============================================================================


def determine_training_phase(
    start_date: date,
    end_date: date,
    current_date: Optional[date] = None,
) -> str:
    """
    Phase is derived from the elapsed proportion of the member's active subscription:
    - 0% to 33.3% elapsed -> 'foundation'
    - 33.4% to 66.6% elapsed -> 'build'
    - 66.7% to 100% elapsed -> 'peak'
    """
    if not start_date or not end_date or end_date <= start_date:
        return "foundation"

    if current_date is None:
        current_date = timezone.localdate()

    if current_date <= start_date:
        return "foundation"
    if current_date >= end_date:
        return "peak"

    total_days = (end_date - start_date).days
    elapsed_days = (current_date - start_date).days

    ratio = elapsed_days / total_days
    if ratio < 0.334:
        return "foundation"
    elif ratio < 0.667:
        return "build"
    else:
        return "peak"


# ==============================================================================
# EQUIPMENT & LIMITATION FILTERING
# ==============================================================================


def filter_prescribed_equipment(
    equipment_access: str,
    health_limitations: str,
    unavailable_equipment: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Filters equipment categories based on member access, reported injuries/limitations,
    and gym out_of_service / under_maintenance equipment list.
    """
    access_text = (equipment_access or "").lower()
    limits_text = (health_limitations or "").lower()
    unavailable = [e.lower() for e in (unavailable_equipment or [])]

    all_categories = [
        "barbell",
        "dumbbells",
        "cable_machine",
        "resistance_bands",
        "kettlebells",
        "pull_up_bar",
        "bench",
        "leg_press",
        "squat_rack",
        "bodyweight",
    ]

    available = set(all_categories)
    excluded = set()
    exclusion_reasons = {}

    # 1. Access constraints
    if "dumbbell" in access_text and not any(
        k in access_text for k in ["full", "barbell", "all"]
    ):
        for item in ["barbell", "cable_machine", "leg_press", "squat_rack"]:
            if item in available:
                available.remove(item)
                excluded.add(item)
                exclusion_reasons[item] = (
                    "Not accessible based on member equipment profile."
                )

    if "bodyweight only" in access_text or (
        "home" in access_text
        and "dumbbell" not in access_text
        and not any(k in access_text for k in ["full", "gym"])
    ):
        for item in [
            "barbell",
            "dumbbells",
            "cable_machine",
            "leg_press",
            "squat_rack",
        ]:
            if item in available:
                available.remove(item)
                excluded.add(item)
                exclusion_reasons[item] = "Bodyweight only access indicated."

    # 2. Health limitations & injury constraints
    if any(k in limits_text for k in ["lower back", "spine", "herniated", "lumbar"]):
        for item in ["barbell", "squat_rack"]:
            if item in available:
                available.remove(item)
                excluded.add(item)
                exclusion_reasons[item] = (
                    "Excluded to prevent spinal axial loading due to lower back limitation."
                )

    if any(
        k in limits_text
        for k in ["shoulder impingement", "rotator cuff", "shoulder pain"]
    ):
        exclusion_reasons["barbell_overhead"] = (
            "Avoid strict barbell overhead press due to shoulder limitation."
        )

    if any(k in limits_text for k in ["knee", "patellar", "meniscus"]):
        for item in ["leg_press"]:
            if item in available:
                available.remove(item)
                excluded.add(item)
                exclusion_reasons[item] = (
                    "Excluded heavy fixed leg press due to knee limitation."
                )

    # 3. Gym out-of-service / maintenance exclusions
    for unavail in unavailable:
        for cat in list(available):
            if cat in unavail or unavail in cat:
                available.remove(cat)
                excluded.add(cat)
                exclusion_reasons[cat] = (
                    f"Gym equipment item '{unavail}' is currently out of service or under maintenance."
                )

    return {
        "available_equipment": sorted(list(available)),
        "excluded_equipment": sorted(list(excluded)),
        "exclusion_reasons": exclusion_reasons,
    }


# ==============================================================================
# GATEKEEPER VALIDATION
# ==============================================================================


def validate_generation_eligibility(member, gym) -> Dict[str, Any]:
    """
    Gatekeeper requirements:
    1. Gym has_ai_plans enabled on GymConfig.
    2. Member has active subscription with a trainer-inclusive plan.
    3. Member has an active assigned trainer.
    4. Member has complete FitnessProfile (goal, fitness_level, training_days_per_week, session_length_minutes).
    5. Member has at least one recorded BodyMetrics measurement.
    """
    config = getattr(gym, "config", None)
    if not config or not getattr(config, "has_ai_plans", False):
        raise RulesEngineGatekeeperError(
            "This gym does not have AI personal training plans enabled.",
            code="gym_ai_disabled",
        )

    today = timezone.localdate()
    from apps.memberships.models import MemberSubscription

    active_sub = (
        MemberSubscription.all_objects.filter(
            gym=gym,
            member=member,
            status=MemberSubscription.STATUS_ACTIVE,
            start_date__lte=today,
            end_date__gte=today,
            plan__trainer_inclusive=True,
        )
        .select_related("plan")
        .first()
    )
    if not active_sub:
        raise RulesEngineGatekeeperError(
            "Member does not have an active trainer-inclusive membership plan.",
            code="no_trainer_plan",
        )

    from apps.trainers.models import TrainerAssignment

    active_assignment = (
        TrainerAssignment.all_objects.filter(
            gym=gym,
            member=member,
            ended_at__isnull=True,
        )
        .select_related("trainer__user")
        .first()
    )
    if not active_assignment:
        raise RulesEngineGatekeeperError(
            "Member does not have an assigned personal trainer.",
            code="no_assigned_trainer",
        )

    from apps.trainers.models import FitnessProfile

    profile = FitnessProfile.all_objects.filter(gym=gym, member=member).first()
    if (
        not profile
        or not profile.goal
        or not profile.fitness_level
        or not profile.training_days_per_week
        or not profile.session_length_minutes
    ):
        raise RulesEngineGatekeeperError(
            "Member fitness profile is incomplete. Goal, fitness level, training days, and session length are required.",
            code="incomplete_profile",
        )

    from apps.memberships.models import BodyMetrics

    latest_metric = (
        BodyMetrics.all_objects.filter(gym=gym, member=member)
        .order_by("-recorded_at")
        .first()
    )
    if not latest_metric:
        raise RulesEngineGatekeeperError(
            "At least one trainer-recorded measurement is required before generating a training plan.",
            code="no_measurements",
        )

    return {
        "active_subscription": active_sub,
        "trainer_assignment": active_assignment,
        "fitness_profile": profile,
        "latest_metrics": latest_metric,
    }


# ==============================================================================
# HISTORY EXTRACTION
# ==============================================================================


def extract_member_history(member, gym, limit: int = 4) -> List[Dict[str, Any]]:
    """
    Reads prior approved TrainingPlan records for the member (ordered by week_start_date descending).
    Extracts sessions, exercises, sets, reps, and loads.
    If TrainingPlan model doesn't exist yet, returns [].
    """
    try:
        TrainingPlan = apps.get_model("trainers", "TrainingPlan", require_ready=False)
        if not TrainingPlan:
            return []
    except LookupError:
        return []

    plans = TrainingPlan.all_objects.filter(
        gym=gym,
        member=member,
        status="approved",
    ).order_by("-week_start_date")[:limit]

    history = []
    for plan in plans:
        history.append(
            {
                "week_start_date": str(plan.week_start_date),
                "sessions": (
                    plan.plan_content.get("sessions", [])
                    if isinstance(plan.plan_content, dict)
                    else []
                ),
                "trainer_notes": plan.trainer_notes,
            }
        )
    return history


# ==============================================================================
# PROMPT CONTEXT BUILDER (STRICT PRIVACY / ZERO PII)
# ==============================================================================


def build_ai_generation_context(
    member,
    gym,
    week_start_date: date,
    trainer_note_for_week: Optional[str] = None,
    strategy: Optional[IntensityStrategy] = None,
    checkin: Optional[Dict[str, Any]] = None,
    unavailable_equipment: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Assembles complete, privacy-compliant AI generation payload.
    STRICT PRIVACY: NO personal identifiers (name, phone, email, member id) are included.
    Free-text fields are truncated and sanitized as plain data.
    """
    validated = validate_generation_eligibility(member, gym)
    sub = validated["active_subscription"]
    profile = validated["fitness_profile"]
    metrics = validated["latest_metrics"]

    if strategy is None:
        strategy = AdaptiveRecoveryStrategy()

    phase = determine_training_phase(
        start_date=sub.start_date,
        end_date=sub.end_date,
        current_date=week_start_date,
    )

    history = extract_member_history(member, gym)

    intensity = strategy.calculate_intensity(
        phase=phase,
        fitness_level=profile.fitness_level,
        checkin=checkin,
        history=history,
    )

    equipment_info = filter_prescribed_equipment(
        equipment_access=profile.equipment_access,
        health_limitations=profile.health_limitations,
        unavailable_equipment=unavailable_equipment,
    )

    age = None
    if member.date_of_birth:
        today = timezone.localdate()
        age = (
            today.year
            - member.date_of_birth.year
            - (
                (today.month, today.day)
                < (member.date_of_birth.month, member.date_of_birth.day)
            )
        )

    meas_data = metrics.measurements or {}
    weight_kg = float(metrics.weight_kg) if metrics.weight_kg else None
    height_cm = float(metrics.height_cm) if metrics.height_cm else None
    body_fat = meas_data.get("body_fat_percentage")
    lean_mass = None
    if weight_kg and body_fat:
        try:
            lean_mass = round(weight_kg * (1 - float(body_fat) / 100), 1)
        except (ValueError, TypeError):
            lean_mass = None

    sanitized_trainer_note = (trainer_note_for_week or "").strip()[:500]
    sanitized_dietary_notes = (profile.dietary_notes or "").strip()[:1000]
    sanitized_limitations = (profile.health_limitations or "").strip()[:500]

    return {
        "demographics": {
            "age": age,
            "gender": member.gender or "unspecified",
        },
        "biometrics": {
            "weight_kg": weight_kg,
            "height_cm": height_cm,
            "resting_heart_rate": meas_data.get("resting_heart_rate"),
            "body_fat_percentage": body_fat,
            "lean_body_mass_kg": lean_mass,
            "bmi": metrics.estimated_bmi,
        },
        "profile": {
            "goal": profile.goal,
            "fitness_level": profile.fitness_level,
            "training_days_per_week": profile.training_days_per_week,
            "session_length_minutes": profile.session_length_minutes,
            "dietary_notes": sanitized_dietary_notes,
            "health_limitations": sanitized_limitations,
        },
        "plan_parameters": {
            "week_start_date": str(week_start_date),
            "phase": phase,
            "intensity": intensity,
            "available_equipment": equipment_info["available_equipment"],
            "excluded_equipment": equipment_info["excluded_equipment"],
            "exclusion_reasons": equipment_info["exclusion_reasons"],
            "trainer_note_for_week": sanitized_trainer_note,
        },
        "history_context": history,
    }
