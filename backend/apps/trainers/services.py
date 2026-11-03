import logging
import os
from datetime import datetime, timedelta
from datetime import timezone as dt_timezone
from typing import Any, Dict, List, Optional, Tuple

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from apps.accounts.models import Notification, User
from apps.accounts.notifications import create_notification
from apps.accounts.services import record_audit_log
from apps.memberships.models import Member, MemberSubscription
from apps.tenants.models import GymConfig
from apps.trainers.models import Trainer, TrainerAssignment

logger = logging.getLogger(__name__)


def auto_assign_trainer_for_subscription(
    subscription: MemberSubscription,
) -> Optional[TrainerAssignment]:
    """
    Automatically assign an eligible trainer to a member upon activation of a trainer-inclusive plan.
    Safe under concurrency: locks candidate trainers during selection.
    Never raises an uncaught exception (logs error and notifies Owner/Manager so payments/subscriptions never fail).
    """
    gym = subscription.gym
    member = subscription.member
    plan = subscription.plan

    # Server-side gating: if gym has trainer module disabled, do nothing (no error, no side-effect)
    config = getattr(gym, "config", None)
    if not config or not config.has_trainer_module:
        config = GymConfig.objects.filter(gym_id=gym.id).first()
        if not config or not config.has_trainer_module:
            return None

    # Only assign for active trainer-inclusive plans
    if (
        subscription.status != MemberSubscription.STATUS_ACTIVE
        or not plan.trainer_inclusive
    ):
        return None

    # If member already has an active assignment, keep it (a renewal never reassigns)
    existing = TrainerAssignment.all_objects.filter(
        member=member,
        gym=gym,
        ended_at__isnull=True,
    ).first()
    if existing:
        return existing

    try:
        with transaction.atomic():
            # Check existing again within atomic block to guard against concurrent triggers
            existing = TrainerAssignment.all_objects.filter(
                member=member,
                gym=gym,
                ended_at__isnull=True,
            ).first()
            if existing:
                return existing

            # Lock candidate trainers belonging to this gym
            candidate_trainers = list(
                Trainer.all_objects.select_for_update()
                .filter(gym=gym, user__is_active=True)
                .select_related("user")
            )

            eligible: List[Tuple[int, datetime, Trainer]] = []
            epoch_start = datetime(1970, 1, 1, tzinfo=dt_timezone.utc)

            for t in candidate_trainers:
                active_count = TrainerAssignment.all_objects.filter(
                    trainer=t,
                    gym=gym,
                    ended_at__isnull=True,
                ).count()

                if active_count >= t.max_clients:
                    continue  # Trainer at capacity is never picked

                last_assignment = (
                    TrainerAssignment.all_objects.filter(trainer=t, gym=gym)
                    .order_by("-assigned_at")
                    .first()
                )
                last_time = (
                    last_assignment.assigned_at if last_assignment else epoch_start
                )
                eligible.append((active_count, last_time, t))

            if not eligible:
                # Nobody eligible: record single notification for Owner and Manager (not repeated)
                already_notified = Notification.all_objects.filter(
                    gym=gym,
                    type="trainer_capacity_exhausted",
                    message__contains=str(member.id),
                ).exists()

                if not already_notified:
                    staff_recipients = User.all_objects.filter(
                        gym=gym,
                        role__in=[User.ROLE_OWNER, User.ROLE_MANAGER],
                        is_active=True,
                    )
                    for staff in staff_recipients:
                        create_notification(
                            recipient=staff,
                            notification_type="trainer_capacity_exhausted",
                            message=(
                                f"No trainer available to assign for member {member.full_name} "
                                f"(Member ID: {member.id}). All trainers are at capacity or unavailable."
                            ),
                            gym=gym,
                        )
                return None

            # Sort: lowest current client count first; tie-break: oldest last assignment first
            eligible.sort(key=lambda item: (item[0], item[1], item[2].created_at))
            chosen_trainer = eligible[0][2]

            assignment = TrainerAssignment.all_objects.create(
                gym=gym,
                member=member,
                trainer=chosen_trainer,
                assigned_by=None,
                assigned_at=timezone.now(),
            )

            # Record notifications
            create_notification(
                recipient=chosen_trainer.user,
                notification_type="trainer_assigned",
                message=f"You have been assigned a new client: {member.full_name} ({plan.name}).",
                gym=gym,
            )

            if getattr(member, "user", None):
                trainer_display = (
                    chosen_trainer.user.full_name or chosen_trainer.user.email
                )
                create_notification(
                    recipient=member.user,
                    notification_type="trainer_assigned",
                    message=f"You have been assigned a trainer: {trainer_display}.",
                    gym=gym,
                )

            record_audit_log(
                action_type="trainer_assigned_automatic",
                affected_record_type="TrainerAssignment",
                affected_record_id=str(assignment.id),
                actor=None,
                gym=gym,
                metadata={
                    "member_id": str(member.id),
                    "member_name": member.full_name,
                    "trainer_id": str(chosen_trainer.id),
                    "trainer_name": chosen_trainer.user.full_name
                    or chosen_trainer.user.email,
                    "plan_id": str(plan.id),
                    "plan_name": plan.name,
                },
            )
            return assignment

    except Exception as exc:
        logger.exception(
            "Automatic trainer assignment failed for member %s: %s", member.id, exc
        )
        try:
            staff_recipients = User.all_objects.filter(
                gym=gym,
                role__in=[User.ROLE_OWNER, User.ROLE_MANAGER],
                is_active=True,
            )
            for staff in staff_recipients:
                create_notification(
                    recipient=staff,
                    notification_type="trainer_assignment_error",
                    message=(
                        f"Automatic trainer assignment failed for member {member.full_name} "
                        f"(Member ID: {member.id}): {exc}"
                    ),
                    gym=gym,
                )
        except Exception:
            logger.exception("Failed to send staff notification for assignment failure")
        return None


def reassign_trainer(
    member: Member,
    new_trainer: Trainer,
    actor: User,
    confirm_over_capacity: bool = False,
    context: str = "manual",
) -> TrainerAssignment:
    """
    Manually assign or reassign a trainer to a member.
    Owner and Manager only.
    Closes the prior assignment (ended_at) and opens a new one in ONE transaction.
    Refuses cross-gym trainers, inactive trainers, or members without active trainer-inclusive plan.
    Exceeding capacity requires explicit confirm_over_capacity=True.
    """
    if str(new_trainer.gym_id) != str(member.gym_id):
        raise ValidationError(
            {"trainer": "Trainer from another gym cannot be assigned."}
        )

    if not new_trainer.user.is_active:
        raise ValidationError({"trainer": "Inactive trainer cannot be assigned."})

    today = timezone.localdate()
    has_active_trainer_plan = MemberSubscription.all_objects.filter(
        gym=member.gym,
        member=member,
        status=MemberSubscription.STATUS_ACTIVE,
        plan__trainer_inclusive=True,
        end_date__gte=today,
    ).exists()

    if not has_active_trainer_plan:
        raise ValidationError(
            {
                "member": "Member does not have an active trainer-inclusive membership plan."
            }
        )

    current_clients = new_trainer.client_count
    if current_clients >= new_trainer.max_clients and not confirm_over_capacity:
        raise ValidationError(
            {
                "detail": (
                    f"Trainer {new_trainer.user.full_name or new_trainer.user.email} is at capacity "
                    f"({current_clients}/{new_trainer.max_clients}). "
                    "Confirmation is required to exceed capacity."
                ),
                "requires_confirmation": True,
                "trainer_client_count": current_clients,
                "trainer_max_clients": new_trainer.max_clients,
            }
        )

    with transaction.atomic():
        old_assignment = TrainerAssignment.all_objects.filter(
            member=member,
            gym=member.gym,
            ended_at__isnull=True,
        ).first()

        old_trainer = old_assignment.trainer if old_assignment else None
        now = timezone.now()

        if old_assignment:
            old_assignment.ended_at = now
            old_assignment.save(update_fields=["ended_at"])

        new_assignment = TrainerAssignment.all_objects.create(
            gym=member.gym,
            member=member,
            trainer=new_trainer,
            assigned_by=actor,
            assigned_at=now,
        )

        # Notify old trainer
        if old_trainer and old_trainer.id != new_trainer.id:
            create_notification(
                recipient=old_trainer.user,
                notification_type="trainer_reassigned",
                message=(
                    f"Client {member.full_name} has been reassigned to "
                    f"{new_trainer.user.full_name or new_trainer.user.email}."
                ),
                gym=member.gym,
            )

        # Notify new trainer
        create_notification(
            recipient=new_trainer.user,
            notification_type="trainer_assigned",
            message=f"You have been assigned a client: {member.full_name}.",
            gym=member.gym,
        )

        # Notify member
        if getattr(member, "user", None):
            trainer_display = new_trainer.user.full_name or new_trainer.user.email
            create_notification(
                recipient=member.user,
                notification_type="trainer_assigned",
                message=f"Your assigned trainer is now {trainer_display}.",
                gym=member.gym,
            )

        # Audit log
        record_audit_log(
            action_type="trainer_reassigned",
            affected_record_type="TrainerAssignment",
            affected_record_id=str(new_assignment.id),
            actor=actor,
            gym=member.gym,
            metadata={
                "member_id": str(member.id),
                "member_name": member.full_name,
                "old_trainer_id": str(old_trainer.id) if old_trainer else None,
                "old_trainer_name": (
                    (old_trainer.user.full_name or old_trainer.user.email)
                    if old_trainer
                    else None
                ),
                "new_trainer_id": str(new_trainer.id),
                "new_trainer_name": new_trainer.user.full_name
                or new_trainer.user.email,
                "confirmed_over_capacity": bool(
                    current_clients >= new_trainer.max_clients
                ),
                "context": context,
            },
        )

        return new_assignment


def reassign_trainer_clients_on_deactivation(
    deactivated_trainer_user: User,
    acting_user: User,
    reassignments_data: Optional[Dict[str, Any]] = None,
) -> int:
    """
    Ensure every active client of a deactivated trainer is reassigned.
    If active clients exist and reassignments_data is missing or incomplete, raises ValidationError.
    Returns the number of reassigned clients.
    """
    gym = deactivated_trainer_user.gym
    trainer = Trainer.all_objects.filter(user=deactivated_trainer_user, gym=gym).first()
    if not trainer:
        return 0

    active_assignments = list(
        TrainerAssignment.all_objects.filter(
            trainer=trainer,
            gym=gym,
            ended_at__isnull=True,
        ).select_related("member")
    )

    if not active_assignments:
        return 0

    reassignments_data = reassignments_data or {}
    reassign_map: Dict[str, str] = {}

    # Support multiple input patterns:
    # 1. reassign_to_trainer_id: single trainer for all clients
    # 2. reassignments: dict of {member_id: trainer_id}
    # 3. reassignments: list of {"member_id": "...", "trainer_id": "..."}
    single_trainer_id = reassignments_data.get("reassign_to_trainer_id")
    if single_trainer_id:
        for a in active_assignments:
            reassign_map[str(a.member_id)] = str(single_trainer_id)
    elif "reassignments" in reassignments_data:
        raw_reassignments = reassignments_data["reassignments"]
        if isinstance(raw_reassignments, dict):
            reassign_map = {str(k): str(v) for k, v in raw_reassignments.items()}
        elif isinstance(raw_reassignments, list):
            for item in raw_reassignments:
                if (
                    isinstance(item, dict)
                    and "member_id" in item
                    and "trainer_id" in item
                ):
                    reassign_map[str(item["member_id"])] = str(item["trainer_id"])

    # Verify that EVERY active client is mapped
    missing_members = []
    for a in active_assignments:
        if str(a.member_id) not in reassign_map:
            missing_members.append(f"{a.member.full_name} ({a.member_id})")

    if missing_members:
        raise ValidationError(
            {
                "detail": (
                    f"Cannot deactivate trainer with {len(active_assignments)} active client(s) "
                    "unless every client is reassigned to an eligible trainer. "
                    f"Missing reassignment for: {', '.join(missing_members)}"
                ),
                "active_clients_count": len(active_assignments),
                "missing_reassignments": missing_members,
            }
        )

    # Reassign each client
    for a in active_assignments:
        target_trainer_id = reassign_map[str(a.member_id)]
        target_trainer = (
            Trainer.all_objects.filter(id=target_trainer_id, gym=gym)
            .select_related("user")
            .first()
        )
        if not target_trainer:
            raise ValidationError(
                {
                    "reassignments": f"Target trainer {target_trainer_id} not found in this gym."
                }
            )
        if target_trainer.id == trainer.id or not target_trainer.user.is_active:
            raise ValidationError(
                {
                    "reassignments": "Cannot reassign client to an inactive or self trainer."
                }
            )

        reassign_trainer(
            member=a.member,
            new_trainer=target_trainer,
            actor=acting_user,
            confirm_over_capacity=True,  # deactivation reassignment confirms capacity override
            context="trainer_deactivation",
        )

    return len(active_assignments)


def save_fitness_profile(
    *,
    member: Member,
    gym: Any,
    data: dict,
    acting_user: User,
):
    """
    Save or update fitness profile for a member using validated selectable lists.
    Enforces shared validators on all fields.
    Audit-logged with 'fitness_profile_saved'.
    """
    from apps.core.validators import (
        validate_dietary_choices,
        validate_equipment_access,
        validate_fitness_level,
        validate_goal,
        validate_health_limitations,
        validate_session_length,
        validate_training_days_per_week,
    )
    from apps.trainers.models import FitnessProfile

    goal = validate_goal(data.get("goal"))
    fitness_level = validate_fitness_level(data.get("fitness_level"))
    training_days = validate_training_days_per_week(data.get("training_days_per_week"))
    session_length = validate_session_length(data.get("session_length_minutes"))
    health_limitations, other_limitations = validate_health_limitations(
        data.get("health_limitations"), data.get("other_limitations")
    )
    equipment_access, other_equipment = validate_equipment_access(
        data.get("equipment_access"), data.get("other_equipment")
    )
    dietary_notes, other_dietary = validate_dietary_choices(
        data.get("dietary_notes"), data.get("other_dietary")
    )

    with transaction.atomic():
        profile, created = FitnessProfile.all_objects.update_or_create(
            member=member,
            gym=gym,
            defaults={
                "goal": goal,
                "fitness_level": fitness_level,
                "health_limitations": health_limitations,
                "other_limitations": other_limitations,
                "equipment_access": equipment_access,
                "other_equipment": other_equipment,
                "training_days_per_week": training_days,
                "session_length_minutes": session_length,
                "dietary_notes": dietary_notes,
                "other_dietary": other_dietary,
            },
        )
        record_audit_log(
            actor=acting_user,
            action_type="fitness_profile_saved",
            affected_record_type="FitnessProfile",
            affected_record_id=str(member.id),
            gym=gym,
            metadata={
                "created": created,
                "goal": goal,
                "fitness_level": fitness_level,
                "training_days": training_days,
                "session_length": session_length,
                "has_medical_caution": profile.has_medical_caution,
            },
        )
    return profile


# ==============================================================================
# SPRINT 22: TRAINING PLAN GENERATION & LIFECYCLE SERVICES
# ==============================================================================


def get_plan_generation_prerequisites(
    *,
    member: Member,
    gym: Any,
) -> Dict[str, Any]:
    """
    Evaluates whether a member meets all 5 preconditions for AI plan generation:
    1. Gym has AI plans enabled (gym.config.has_ai_plans)
    2. Member has active trainer-inclusive plan
    3. Member has assigned trainer
    4. Member has complete fitness profile
    5. At least one measurement exists
    Also returns draft counts and open draft status for this week and next week.
    """
    from apps.trainers.models import TrainingPlan
    from apps.trainers.rules_engine import (
        RulesEngineGatekeeperError,
        validate_generation_eligibility,
    )

    missing = []
    eligible = True

    try:
        validate_generation_eligibility(member, gym)
    except RulesEngineGatekeeperError as err:
        eligible = False
        if err.code == "gym_ai_disabled":
            missing.append("AI workout plan feature is not enabled for this gym.")
        elif err.code == "no_trainer_plan":
            missing.append(
                "Member is not on an active trainer-inclusive membership plan."
            )
        elif err.code == "no_assigned_trainer":
            missing.append("Member does not have an assigned trainer.")
        elif err.code == "incomplete_profile":
            missing.append(
                "Member fitness profile is incomplete (goal, level, days, or session length missing)."
            )
        elif err.code == "no_measurements":
            missing.append(
                "No body measurements recorded yet. At least one measurement is required."
            )
        elif err.code == "missing_dob":
            missing.append("Member date of birth is missing.")
        else:
            missing.append(err.message)

    today = timezone.localdate()
    this_monday = today - timedelta(days=today.weekday())
    next_monday = this_monday + timedelta(days=7)

    drafts_this_week = TrainingPlan.all_objects.filter(
        gym=gym, member=member, week_start_date=this_monday
    ).order_by("draft_number")
    drafts_next_week = TrainingPlan.all_objects.filter(
        gym=gym, member=member, week_start_date=next_monday
    ).order_by("draft_number")

    open_draft_this = drafts_this_week.filter(
        status=TrainingPlan.STATUS_PENDING_REVIEW
    ).first()
    open_draft_next = drafts_next_week.filter(
        status=TrainingPlan.STATUS_PENDING_REVIEW
    ).first()

    return {
        "eligible": eligible and (open_draft_this is None or open_draft_next is None),
        "can_generate_this_week": eligible
        and (open_draft_this is None)
        and (drafts_this_week.count() < 3),
        "can_generate_next_week": eligible
        and (open_draft_next is None)
        and (drafts_next_week.count() < 3),
        "missing_requirements": missing,
        "this_week_draft_count": drafts_this_week.count(),
        "next_week_draft_count": drafts_next_week.count(),
        "has_open_draft_this_week": open_draft_this is not None,
        "has_open_draft_next_week": open_draft_next is not None,
        "open_draft_id_this_week": str(open_draft_this.id) if open_draft_this else None,
        "open_draft_id_next_week": str(open_draft_next.id) if open_draft_next else None,
    }


def get_default_ai_provider():
    """Returns configured AI provider: Mock provider if specified/offline, else LiteLLM provider."""
    from apps.trainers.ai.litellm_provider import LiteLLMAIPlanProvider
    from apps.trainers.ai.mock_provider import MockAIPlanProvider

    use_mock = getattr(settings, "USE_MOCK_AI_PROVIDER", False)
    api_key = getattr(
        settings, "OPENROUTER_API_KEY", os.environ.get("OPENROUTER_API_KEY", "")
    )

    if use_mock or not api_key:
        return MockAIPlanProvider()
    return LiteLLMAIPlanProvider()


def generate_training_plan(
    *,
    member: Member,
    gym: Any,
    acting_user: User,
    week_choice: str = "this_week",
    focus_this_week: Optional[List[str]] = None,
    other_focus: Optional[str] = None,
    trainer_notes: Optional[str] = None,
    provider: Optional[Any] = None,
):
    """
    Generates a draft weekly training plan using AI provider.
    Enforces permissions, prerequisites, gym hourly rate limit (20/hr),
    and 3-draft weekly limit per member.
    """
    from apps.core.validators import validate_weekly_focus
    from apps.trainers.models import TrainingPlan
    from apps.trainers.rules_engine import (
        RulesEngineGatekeeperError,
        build_ai_generation_context,
        validate_generation_eligibility,
    )

    # 1. Permission check: Assigned trainer, gym Owner, or gym Manager
    if acting_user.role not in [User.ROLE_OWNER, User.ROLE_MANAGER]:
        if acting_user.role != User.ROLE_TRAINER:
            raise PermissionDenied(
                "Only the assigned trainer, gym Owner, or Manager can generate plans."
            )
        trainer_profile = getattr(acting_user, "trainer_profile", None)
        has_assignment = (
            trainer_profile is not None
            and TrainerAssignment.all_objects.filter(
                gym=gym,
                member=member,
                trainer=trainer_profile,
                ended_at__isnull=True,
            ).exists()
        )
        if not has_assignment:
            raise PermissionDenied(
                "Only the assigned trainer can generate plans for this member."
            )

    # 2. Prerequisites check
    try:
        validate_generation_eligibility(member, gym)
    except RulesEngineGatekeeperError as err:
        raise ValidationError(err.message)

    # 3. Rate limit check: 20 generations per gym per hour
    one_hour_ago = timezone.now() - timedelta(hours=1)
    recent_gym_generations = TrainingPlan.all_objects.filter(
        gym=gym,
        created_at__gte=one_hour_ago,
    ).count()
    if recent_gym_generations >= 20:
        raise ValidationError(
            "Gym rate limit reached: maximum 20 plan generations per hour. Please try again later."
        )

    # 4. Week calculation
    today = timezone.localdate()
    this_monday = today - timedelta(days=today.weekday())
    next_monday = this_monday + timedelta(days=7)
    week_start_date = next_monday if week_choice == "next_week" else this_monday

    # 5. Draft limits: max 3 per week, only 1 open draft
    existing_drafts = TrainingPlan.all_objects.filter(
        gym=gym,
        member=member,
        week_start_date=week_start_date,
    ).order_by("draft_number")

    open_draft = existing_drafts.filter(
        status=TrainingPlan.STATUS_PENDING_REVIEW
    ).first()
    if open_draft:
        raise ValidationError(
            "An open draft for this plan week is already pending review."
        )

    draft_count = existing_drafts.count()
    if draft_count >= 3:
        raise ValidationError(
            "Maximum draft limit reached: at most 3 drafts per member per plan week."
        )

    draft_number = draft_count + 1

    # 6. Validate focus
    cleaned_focus, cleaned_other_focus = validate_weekly_focus(
        focus_this_week or ["no_focus"], other_focus
    )

    # 7. Assemble PII-free AI context
    ai_context = build_ai_generation_context(
        member=member,
        gym=gym,
        week_start_date=week_start_date,
        trainer_note_for_week=trainer_notes,
    )
    ai_context["profile"]["focus_this_week"] = cleaned_focus
    ai_context["profile"]["other_focus"] = cleaned_other_focus
    ai_context["gym_id"] = str(gym.id)

    # 8. Call provider
    if provider is None:
        provider = get_default_ai_provider()

    result = provider.generate_plan(ai_context)
    plan_data = result["plan_data"]
    model_name = result["model_name"]

    # 9. Save plan and audit log
    with transaction.atomic():
        eq_source = ai_context.get("plan_parameters", {}).get(
            "equipment_source", "member profile only"
        )
        if isinstance(plan_data, dict):
            plan_data["equipment_source"] = eq_source

        plan = TrainingPlan.all_objects.create(
            gym=gym,
            member=member,
            week_start_date=week_start_date,
            draft_number=draft_number,
            status=TrainingPlan.STATUS_PENDING_REVIEW,
            generated_by_model=model_name,
            equipment_source=eq_source,
            plan_data=plan_data,
            focus_this_week=cleaned_focus,
            other_focus=cleaned_other_focus,
            trainer_notes=trainer_notes or "",
            has_medical_caution=member.fitness_profile.has_medical_caution,
        )

        record_audit_log(
            actor=acting_user,
            action_type="training_plan_generated",
            affected_record_type="TrainingPlan",
            affected_record_id=str(plan.id),
            gym=gym,
            metadata={
                "member_id": str(member.id),
                "week_start_date": str(week_start_date),
                "draft_number": draft_number,
                "model_name": model_name,
                "focus": cleaned_focus,
            },
        )

    return plan


def reject_training_plan(
    *,
    plan: Any,
    rejection_reasons: List[str],
    other_rejection_reason: str,
    acting_user: User,
    provider: Optional[Any] = None,
):
    """
    Rejects a pending draft and triggers regeneration of the next draft (up to draft 3).
    Draft 3 cannot be rejected.
    """
    from apps.core.validators import validate_plan_rejection_reasons
    from apps.trainers.models import TrainingPlan

    gym = plan.gym
    member = plan.member

    # Permission check
    if acting_user.role not in [User.ROLE_OWNER, User.ROLE_MANAGER]:
        if acting_user.role != User.ROLE_TRAINER:
            raise PermissionDenied(
                "Only the assigned trainer, gym Owner, or Manager can reject plans."
            )
        trainer_profile = getattr(acting_user, "trainer_profile", None)
        has_assignment = (
            trainer_profile is not None
            and TrainerAssignment.all_objects.filter(
                gym=gym,
                member=member,
                trainer=trainer_profile,
                ended_at__isnull=True,
            ).exists()
        )
        if not has_assignment:
            raise PermissionDenied(
                "Only the assigned trainer can reject plans for this member."
            )

    if plan.status != TrainingPlan.STATUS_PENDING_REVIEW:
        raise ValidationError("Only plans pending review can be rejected.")

    if plan.draft_number >= 3:
        raise ValidationError(
            "Draft 3 is the final draft and cannot be rejected. Please edit and approve this draft directly."
        )

    cleaned_reasons, cleaned_other = validate_plan_rejection_reasons(
        rejection_reasons, other_rejection_reason
    )

    orig_status = plan.status
    orig_reasons = plan.rejection_reasons
    orig_other = plan.other_rejection_reason

    # Mark as rejected so generate_training_plan does not hit the open draft constraint
    plan.status = TrainingPlan.STATUS_REJECTED
    plan.rejection_reasons = cleaned_reasons
    plan.other_rejection_reason = cleaned_other
    plan.save(
        update_fields=[
            "status",
            "rejection_reasons",
            "other_rejection_reason",
            "updated_at",
        ]
    )

    # Generate next draft using rejection feedback
    feedback_notes = f"Rejection feedback on draft {plan.draft_number}: " + ", ".join(
        cleaned_reasons
    )
    if cleaned_other:
        feedback_notes += f" ({cleaned_other})"

    try:
        new_draft = generate_training_plan(
            member=member,
            gym=gym,
            acting_user=acting_user,
            week_choice=(
                "next_week"
                if plan.week_start_date > timezone.localdate()
                else "this_week"
            ),
            focus_this_week=plan.focus_this_week,
            other_focus=plan.other_focus,
            trainer_notes=feedback_notes,
            provider=provider,
        )
    except Exception:
        # Revert plan state back to pending review so it is not left orphaned
        plan.status = orig_status
        plan.rejection_reasons = orig_reasons
        plan.other_rejection_reason = orig_other
        plan.save(
            update_fields=[
                "status",
                "rejection_reasons",
                "other_rejection_reason",
                "updated_at",
            ]
        )
        raise

    # Record audit log only upon successful generation of replacement draft
    record_audit_log(
        actor=acting_user,
        action_type="training_plan_rejected",
        affected_record_type="TrainingPlan",
        affected_record_id=str(plan.id),
        gym=gym,
        metadata={
            "draft_number": plan.draft_number,
            "rejection_reasons": cleaned_reasons,
            "other_reason": cleaned_other,
        },
    )

    return new_draft


def approve_training_plan(
    *,
    plan: Any,
    acting_user: User,
):
    """
    Approves a training plan. Records whether it was edited prior to approval.
    """
    from apps.trainers.models import TrainingPlan

    gym = plan.gym
    member = plan.member

    # Permission check
    if acting_user.role not in [User.ROLE_OWNER, User.ROLE_MANAGER]:
        if acting_user.role != User.ROLE_TRAINER:
            raise PermissionDenied(
                "Only the assigned trainer, gym Owner, or Manager can approve plans."
            )
        trainer_profile = getattr(acting_user, "trainer_profile", None)
        has_assignment = (
            trainer_profile is not None
            and TrainerAssignment.all_objects.filter(
                gym=gym,
                member=member,
                trainer=trainer_profile,
                ended_at__isnull=True,
            ).exists()
        )
        if not has_assignment:
            raise PermissionDenied(
                "Only the assigned trainer can approve plans for this member."
            )

    if plan.status != TrainingPlan.STATUS_PENDING_REVIEW:
        raise ValidationError("Only plans pending review can be approved.")

    with transaction.atomic():
        plan.status = TrainingPlan.STATUS_APPROVED
        plan.approved_by = acting_user
        plan.approved_at = timezone.now()
        plan.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])

        record_audit_log(
            actor=acting_user,
            action_type="training_plan_approved",
            affected_record_type="TrainingPlan",
            affected_record_id=str(plan.id),
            gym=gym,
            metadata={
                "draft_number": plan.draft_number,
                "was_edited": plan.was_edited,
                "approved_by": str(acting_user.id),
            },
        )

        # Notify the member: "Your training plan for the week of <date> is ready."
        date_str = (
            plan.week_start_date.isoformat()
            if hasattr(plan.week_start_date, "isoformat")
            else str(plan.week_start_date)
        )
        create_notification(
            recipient=member.user,
            notification_type="training_plan_ready",
            message=f"Your training plan for the week of {date_str} is ready.",
            gym=gym,
        )

    return plan


def edit_training_plan_draft(
    *,
    plan: Any,
    plan_data: Dict[str, Any],
    acting_user: User,
):
    """
    Directly edits exercises or nutrition guidance of a pending draft.
    Marks was_edited=True and audit logs the modification.
    """
    from apps.trainers.ai.schema import validate_training_plan_structure
    from apps.trainers.models import TrainingPlan

    gym = plan.gym
    member = plan.member

    # Permission check
    if acting_user.role not in [User.ROLE_OWNER, User.ROLE_MANAGER]:
        if acting_user.role != User.ROLE_TRAINER:
            raise PermissionDenied(
                "Only the assigned trainer, gym Owner, or Manager can edit plans."
            )
        trainer_profile = getattr(acting_user, "trainer_profile", None)
        has_assignment = (
            trainer_profile is not None
            and TrainerAssignment.all_objects.filter(
                gym=gym,
                member=member,
                trainer=trainer_profile,
                ended_at__isnull=True,
            ).exists()
        )
        if not has_assignment:
            raise PermissionDenied(
                "Only the assigned trainer can edit plans for this member."
            )

    if plan.status != TrainingPlan.STATUS_PENDING_REVIEW:
        raise ValidationError("Only plans pending review can be edited.")

    expected_days = plan.member.fitness_profile.training_days_per_week
    validated_data = validate_training_plan_structure(
        plan_data, expected_days=expected_days
    )

    with transaction.atomic():
        plan.plan_data = validated_data
        plan.was_edited = True
        plan.save(update_fields=["plan_data", "was_edited", "updated_at"])

        record_audit_log(
            actor=acting_user,
            action_type="training_plan_edited",
            affected_record_type="TrainingPlan",
            affected_record_id=str(plan.id),
            gym=gym,
            metadata={
                "draft_number": plan.draft_number,
            },
        )

    return plan
