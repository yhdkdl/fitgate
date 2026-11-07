from datetime import timedelta
from typing import List, Optional

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.accounts.notifications import create_notification
from apps.classes.constants import (
    BOOKING_STATUS_BOOKED,
    BOOKING_STATUS_CANCELLED,
    CLASS_DURATION_CHOICES,
    CLASS_TITLE_OTHER,
    SESSION_STATUS_CANCELLED,
    SESSION_STATUS_SCHEDULED,
)
from apps.classes.models import ClassBooking, ClassSession
from apps.memberships.models import Member
from apps.trainers.models import Trainer


def validate_no_trainer_overlap(
    gym,
    trainer: Trainer,
    start_time,
    end_time,
    exclude_session_id=None,
):
    """
    Ensure the trainer is not already scheduled for an overlapping session
    in the same start-to-end window.
    """
    qs = ClassSession.all_objects.filter(
        gym=gym,
        trainer=trainer,
        status=SESSION_STATUS_SCHEDULED,
        start_time__lt=end_time,
        end_time__gt=start_time,
    )
    if exclude_session_id:
        qs = qs.exclude(id=exclude_session_id)

    conflict = qs.first()
    if conflict:
        st_str = timezone.localtime(conflict.start_time).strftime("%Y-%m-%d %H:%M")
        et_str = timezone.localtime(conflict.end_time).strftime("%H:%M")
        raise ValidationError(
            f"Trainer is already scheduled for another class ({conflict.display_title}) from {st_str} to {et_str}."
        )


def validate_no_member_overlap(gym, member: Member, start_time, end_time):
    """
    Ensure the member does not have another active booking for an overlapping session.
    """
    conflict_booking = (
        ClassBooking.all_objects.filter(
            gym=gym,
            member=member,
            status=BOOKING_STATUS_BOOKED,
            session__status=SESSION_STATUS_SCHEDULED,
            session__start_time__lt=end_time,
            session__end_time__gt=start_time,
        )
        .select_related("session")
        .first()
    )

    if conflict_booking:
        st_str = timezone.localtime(conflict_booking.session.start_time).strftime(
            "%H:%M"
        )
        et_str = timezone.localtime(conflict_booking.session.end_time).strftime("%H:%M")
        raise ValidationError(
            f"You already have a class booking ({conflict_booking.session.display_title}) from {st_str} to {et_str} that overlaps with this class."
        )


def create_class_sessions(
    gym,
    title: str,
    other_title: str,
    trainer: Trainer,
    start_time,
    duration_minutes: int,
    capacity: int,
    repeat_weeks: int = 1,
) -> List[ClassSession]:
    """
    Create 1 to 12 separate sessions (one per week).
    All weeks validated for trainer overlap before saving.
    """
    if trainer.gym_id != gym.id:
        raise ValidationError("Trainer does not belong to this gym.")

    if not trainer.user.is_active or trainer.user.role != User.ROLE_TRAINER:
        raise ValidationError("Trainer is not active.")

    if start_time <= timezone.now():
        raise ValidationError("Class start time must be in the future.")

    valid_durations = [d[0] for d in CLASS_DURATION_CHOICES]
    if duration_minutes not in valid_durations:
        raise ValidationError(f"Duration must be one of: {valid_durations} minutes.")

    if capacity < 1 or capacity > 200:
        raise ValidationError("Capacity must be between 1 and 200.")

    if repeat_weeks < 1 or repeat_weeks > 12:
        raise ValidationError("Repeat weeks must be between 1 and 12.")

    if title == CLASS_TITLE_OTHER:
        if not other_title or not other_title.strip():
            raise ValidationError("Custom class title is required when title is Other.")
        if len(other_title.strip()) > 50:
            raise ValidationError("Custom class title cannot exceed 50 characters.")
    else:
        other_title = ""

    sessions_to_create = []

    with transaction.atomic():
        for i in range(repeat_weeks):
            s_time = start_time + timedelta(weeks=i)
            e_time = s_time + timedelta(minutes=duration_minutes)

            # Check overlap against DB
            validate_no_trainer_overlap(gym, trainer, s_time, e_time)

            session = ClassSession(
                gym=gym,
                title=title,
                other_title=other_title.strip(),
                trainer=trainer,
                start_time=s_time,
                duration_minutes=duration_minutes,
                end_time=e_time,
                capacity=capacity,
                status=SESSION_STATUS_SCHEDULED,
            )
            sessions_to_create.append(session)

        created = ClassSession.all_objects.bulk_create(sessions_to_create)
        return created


def update_class_session(
    session: ClassSession,
    title: Optional[str] = None,
    other_title: Optional[str] = None,
    trainer: Optional[Trainer] = None,
    start_time=None,
    duration_minutes: Optional[int] = None,
    capacity: Optional[int] = None,
) -> ClassSession:
    """
    Update a scheduled class session.
    Past sessions cannot be edited.
    Sends notifications to booked members if start_time or trainer changes.
    """
    if session.is_past:
        raise ValidationError("Past sessions cannot be edited.")

    if session.status == SESSION_STATUS_CANCELLED:
        raise ValidationError("Cancelled sessions cannot be edited.")

    old_trainer = session.trainer
    old_start = session.start_time
    old_end = session.end_time

    new_trainer = trainer or session.trainer
    new_start = start_time or session.start_time
    new_duration = duration_minutes or session.duration_minutes
    new_end = new_start + timedelta(minutes=new_duration)

    if new_trainer.gym_id != session.gym_id:
        raise ValidationError("Trainer does not belong to this gym.")
    if not new_trainer.user.is_active or new_trainer.user.role != User.ROLE_TRAINER:
        raise ValidationError("Trainer is not active.")

    if new_start <= timezone.now():
        raise ValidationError("Class start time must be in the future.")

    if capacity is not None:
        if capacity < 1 or capacity > 200:
            raise ValidationError("Capacity must be between 1 and 200.")
        active_bookings = session.bookings.filter(status=BOOKING_STATUS_BOOKED).count()
        if capacity < active_bookings:
            raise ValidationError(
                f"Capacity cannot be reduced below current booked count ({active_bookings})."
            )
        session.capacity = capacity

    if title is not None:
        session.title = title
        if title == CLASS_TITLE_OTHER:
            session.other_title = (other_title or "").strip()[:50]
        else:
            session.other_title = ""

    # Validate overlap if time or trainer changed
    if new_trainer != old_trainer or new_start != old_start or new_end != old_end:
        validate_no_trainer_overlap(
            session.gym,
            new_trainer,
            new_start,
            new_end,
            exclude_session_id=session.id,
        )

    session.trainer = new_trainer
    session.start_time = new_start
    session.duration_minutes = new_duration
    session.end_time = new_end
    session.save()

    # Notify booked members if time or trainer changed
    time_or_trainer_changed = (new_start != old_start) or (
        new_trainer.id != old_trainer.id
    )
    if time_or_trainer_changed:
        booked_bookings = ClassBooking.all_objects.filter(
            session=session, status=BOOKING_STATUS_BOOKED
        ).select_related("member__user")
        st_str = timezone.localtime(session.start_time).strftime("%Y-%m-%d %H:%M")
        et_str = timezone.localtime(session.end_time).strftime("%H:%M")
        trainer_name = session.trainer.user.full_name or session.trainer.user.email

        for booking in booked_bookings:
            if booking.member.user:
                create_notification(
                    recipient=booking.member.user,
                    notification_type="class_rescheduled",
                    message=(
                        f"Your class '{session.display_title}' has been updated. "
                        f"New time: {st_str}–{et_str}, Trainer: {trainer_name}."
                    ),
                    gym=session.gym,
                )

    return session


def cancel_class_session(
    session: ClassSession, cancelled_by: Optional[User] = None
) -> ClassSession:
    """
    Cancel a scheduled class session.
    Past sessions cannot be cancelled.
    Leaves session on schedule with status cancelled and notifies booked members.
    """
    if session.is_past:
        raise ValidationError("Past sessions cannot be cancelled.")

    if session.status == SESSION_STATUS_CANCELLED:
        raise ValidationError("Session is already cancelled.")

    session.status = SESSION_STATUS_CANCELLED
    session.save(update_fields=["status"])

    booked_bookings = ClassBooking.all_objects.filter(
        session=session, status=BOOKING_STATUS_BOOKED
    ).select_related("member__user")
    st_str = timezone.localtime(session.start_time).strftime("%Y-%m-%d %H:%M")

    for booking in booked_bookings:
        booking.status = BOOKING_STATUS_CANCELLED
        booking.cancelled_at = timezone.now()
        booking.cancelled_by = cancelled_by
        booking.save(update_fields=["status", "cancelled_at", "cancelled_by"])

        if booking.member.user:
            create_notification(
                recipient=booking.member.user,
                notification_type="class_cancelled",
                message=f"Your class '{session.display_title}' scheduled for {st_str} has been cancelled.",
                gym=session.gym,
            )

    return session


def book_class_session(
    gym, session_id, member: Member, booked_by: Optional[User] = None
) -> ClassBooking:
    """
    Book a class slot for an active member with row-level locking.
    """
    if member.gym_id != gym.id:
        raise ValidationError("Member does not belong to this gym.")

    if member.status != "active":
        contact_line = getattr(gym, "contact_line", "")
        extra = f" Please contact the front desk{' ' + contact_line if contact_line else ''}."
        raise ValidationError(
            f"Member is not active (current status: {member.status}). Only active members can book classes.{extra}"
        )

    with transaction.atomic():
        # Row-lock the session to prevent race conditions exceeding capacity
        try:
            session = ClassSession.all_objects.select_for_update().get(
                id=session_id, gym=gym
            )
        except ClassSession.DoesNotExist:
            raise ValidationError("Class session not found.")

        if session.status != SESSION_STATUS_SCHEDULED:
            raise ValidationError("This class is cancelled and cannot be booked.")

        if session.start_time <= timezone.now():
            raise ValidationError("Cannot book past classes.")

        # Check if already booked
        if ClassBooking.all_objects.filter(
            session=session,
            member=member,
            status=BOOKING_STATUS_BOOKED,
        ).exists():
            raise ValidationError(
                "Member already has an active booking for this class."
            )

        # Check overlapping sessions for member
        validate_no_member_overlap(gym, member, session.start_time, session.end_time)

        # Check capacity
        active_count = ClassBooking.all_objects.filter(
            session=session,
            status=BOOKING_STATUS_BOOKED,
        ).count()
        if active_count >= session.capacity:
            raise ValidationError("Class is full.")

        booking = ClassBooking.all_objects.create(
            gym=gym,
            session=session,
            member=member,
            booked_by=booked_by,
            status=BOOKING_STATUS_BOOKED,
        )
        return booking


def cancel_class_booking(gym, booking_id, cancelled_by: User) -> ClassBooking:
    """
    Cancel an active class booking.
    Member self-service: strictly allowed up to 2 hours before start.
    Staff (Owner, Manager, Reception): allowed anytime before start.
    """
    try:
        booking = ClassBooking.all_objects.select_related("session", "member").get(
            id=booking_id, gym=gym
        )
    except ClassBooking.DoesNotExist:
        raise ValidationError("Class booking not found.")

    if booking.status == BOOKING_STATUS_CANCELLED:
        raise ValidationError("Booking is already cancelled.")

    now = timezone.now()
    session = booking.session

    if session.start_time <= now:
        raise ValidationError(
            "Cannot cancel booking for a class that has already started."
        )

    is_staff = cancelled_by.role in [
        User.ROLE_OWNER,
        User.ROLE_MANAGER,
        User.ROLE_RECEPTION,
    ]

    if not is_staff:
        # Member self-cancellation: 2-hour window
        cutoff = session.start_time - timedelta(hours=2)
        if now > cutoff:
            raise ValidationError(
                "Bookings can only be cancelled up to 2 hours before the class begins."
            )

    booking.status = BOOKING_STATUS_CANCELLED
    booking.cancelled_at = now
    booking.cancelled_by = cancelled_by
    booking.save(update_fields=["status", "cancelled_at", "cancelled_by"])

    return booking


def mark_class_attendance(
    gym,
    session_id,
    member_id,
    attended: bool,
    marked_by: User,
) -> ClassBooking:
    """
    Mark member attendance on a class session.
    Allowed window: from session start_time until 24 hours after session end_time.
    Allowed roles: Owner, Manager, or the assigned Trainer.
    Does NOT create a daily Attendance row.
    """
    try:
        session = ClassSession.all_objects.select_related("trainer__user").get(
            id=session_id, gym=gym
        )
    except ClassSession.DoesNotExist:
        raise ValidationError("Class session not found.")

    now = timezone.now()
    if now < session.start_time:
        raise ValidationError(
            "Attendance can only be marked once the class has started."
        )

    cutoff = session.end_time + timedelta(hours=24)
    if now > cutoff:
        raise ValidationError(
            "Attendance can only be marked within 24 hours after class end."
        )

    if marked_by.role == User.ROLE_TRAINER:
        if session.trainer.user_id != marked_by.id:
            raise ValidationError(
                "Trainers can only mark attendance for their own assigned classes."
            )

    try:
        booking = ClassBooking.all_objects.get(
            session=session,
            member_id=member_id,
            status=BOOKING_STATUS_BOOKED,
        )
    except ClassBooking.DoesNotExist:
        raise ValidationError("No active booking found for this member in this class.")

    booking.attended = attended
    booking.marked_at = now
    booking.marked_by = marked_by
    booking.save(update_fields=["attended", "marked_at", "marked_by"])

    return booking
