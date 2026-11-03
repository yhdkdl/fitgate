from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.accounts.services import record_audit_log
from apps.equipment.constants import (
    CONDITION_GOOD,
    CONDITION_NEEDS_MAINTENANCE,
    CONDITION_OUT_OF_SERVICE,
    CONDITION_UNDER_MAINTENANCE,
)
from apps.equipment.models import Equipment, MaintenanceLog


def report_equipment_issue(
    *,
    equipment: Equipment,
    acting_user: User,
    issue_reason: str,
    other_details: str = "",
) -> MaintenanceLog:
    """
    Staff reports an equipment issue:
    - Creates a MaintenanceLog
    - Transitions Equipment.condition to needs_maintenance (if currently good)
    - Notifies the gym Owner
    - Reporting on an item already under_maintenance creates no duplicate
    """
    if equipment.condition == CONDITION_UNDER_MAINTENANCE:
        raise ValidationError("Equipment is already under maintenance.")

    with transaction.atomic():
        log = MaintenanceLog.all_objects.create(
            gym=equipment.gym,
            equipment=equipment,
            reported_by=acting_user,
            issue_reason=issue_reason,
            other_details=other_details,
            reported_at=timezone.now(),
        )

        if equipment.condition == CONDITION_GOOD:
            equipment.condition = CONDITION_NEEDS_MAINTENANCE
            equipment.save(update_fields=["condition", "updated_at"])

        # Notify Owner
        owner_user = User.all_objects.filter(
            gym=equipment.gym, role=User.ROLE_OWNER, is_active=True
        ).first()

        if owner_user:
            reason_label = dict(
                equipment.maintenance_logs.model.issue_reason.field.choices
            ).get(issue_reason, issue_reason)
            from apps.accounts.notifications import create_notification

            create_notification(
                recipient=owner_user,
                notification_type="equipment_issue",
                message=f"Issue reported for '{equipment.name}': {reason_label}.",
                gym=equipment.gym,
            )

        record_audit_log(
            actor=acting_user,
            action_type="equipment_issue_reported",
            affected_record_type="Equipment",
            affected_record_id=str(equipment.id),
            gym=equipment.gym,
            metadata={
                "equipment_name": equipment.name,
                "issue_reason": issue_reason,
                "other_details": other_details,
                "new_condition": equipment.condition,
            },
        )

    return log


def update_equipment_condition(
    *,
    equipment: Equipment,
    new_condition: str,
    acting_user: User,
    resolution_notes: str = "",
) -> Equipment:
    """
    Owner/Manager updates condition and logs resolutions.
    State machine:
    good -> needs_maintenance -> under_maintenance -> {good (resolved), out_of_service}
    out_of_service -> good
    When condition returns to good, resolves active open maintenance logs.
    """
    current = equipment.condition

    valid_transitions = {
        CONDITION_GOOD: {
            CONDITION_NEEDS_MAINTENANCE,
            CONDITION_UNDER_MAINTENANCE,
            CONDITION_OUT_OF_SERVICE,
        },
        CONDITION_NEEDS_MAINTENANCE: {
            CONDITION_UNDER_MAINTENANCE,
            CONDITION_GOOD,
            CONDITION_OUT_OF_SERVICE,
        },
        CONDITION_UNDER_MAINTENANCE: {CONDITION_GOOD, CONDITION_OUT_OF_SERVICE},
        CONDITION_OUT_OF_SERVICE: {CONDITION_GOOD, CONDITION_UNDER_MAINTENANCE},
    }

    if current != new_condition and new_condition not in valid_transitions.get(
        current, set()
    ):
        raise ValidationError(
            f"Invalid condition transition from '{current}' to '{new_condition}'."
        )

    with transaction.atomic():
        equipment.condition = new_condition
        equipment.save(update_fields=["condition", "updated_at"])

        if new_condition == CONDITION_GOOD:
            now = timezone.now()
            open_logs = MaintenanceLog.all_objects.filter(
                equipment=equipment, resolved_at__isnull=True
            )
            for log_item in open_logs:
                log_item.resolved_at = now
                log_item.resolved_by = acting_user
                log_item.resolution_notes = resolution_notes
                log_item.save(
                    update_fields=[
                        "resolved_at",
                        "resolved_by",
                        "resolution_notes",
                        "updated_at",
                    ]
                )

        record_audit_log(
            actor=acting_user,
            action_type="equipment_condition_updated",
            affected_record_type="Equipment",
            affected_record_id=str(equipment.id),
            gym=equipment.gym,
            metadata={
                "equipment_name": equipment.name,
                "previous_condition": current,
                "new_condition": new_condition,
                "resolution_notes": resolution_notes,
            },
        )

    return equipment
