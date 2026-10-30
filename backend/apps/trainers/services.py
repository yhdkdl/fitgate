import logging
from datetime import datetime
from datetime import timezone as dt_timezone
from typing import Any, Dict, List, Optional, Tuple

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

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
