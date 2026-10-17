import os
import uuid
from datetime import date, timedelta
from typing import Optional, Tuple

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounts.models import Notification, User
from apps.accounts.services import record_audit_log
from apps.attendance.crypto import (
    InvalidTokenError,
    TokenExpiredError,
    hash_token,
    sign_qr_payload,
    verify_qr_jwt,
)
from apps.attendance.models import Attendance, QRToken
from apps.memberships.models import Member, MemberSubscription
from apps.tenants.models import GymTenant


def format_member_photo_url(gym_id: uuid.UUID, photo_url: Optional[str]) -> str:
    """
    Format member photo URL to a backend route path through permission-checked photo view.

    Route: /api/media/member-photos/<uuid:gym_id>/<str:filename>/
    Never returns a raw Cloudinary, S3, or external storage URL.
    """
    if not photo_url or not str(photo_url).strip():
        return ""
    cleaned = str(photo_url).strip()
    prefix = f"/api/media/member-photos/{gym_id}/"
    if cleaned.startswith(prefix):
        return cleaned
    filename = os.path.basename(cleaned)
    return f"{prefix}{filename}/"


class ScanValidationError(Exception):
    """
    Raised when QR scan or manual override validation fails.

    Carries a distinguishable machine-readable `reason` and human-readable `message`.
    Reasons include: 'expired', 'frozen', 'suspended', 'already_checked_in',
    'token_expired', 'token_consumed', 'invalid_token', 'gym_mismatch'.
    """

    def __init__(
        self,
        reason: str,
        message: str,
        member: Optional[Member] = None,
    ):
        super().__init__(message)
        self.reason = reason
        self.message = message
        self.member = member


class ManualOverrideError(ScanValidationError):
    """Alias for ScanValidationError for manual override workflows."""

    pass


def notify_staff_duplicate_scan(
    gym: GymTenant, member: Member, checkin_date: date
) -> None:
    """
    Notify gym staff (Owner, Manager, Reception) of duplicate check-in attempt.

    Merges repeated attempts: if staff have already been notified for this member today,
    does not create additional notifications.
    """
    prefix = f"Duplicate check-in attempted today ({checkin_date}) by member {member.full_name}"
    already_notified = Notification.objects.filter(
        gym=gym,
        type="duplicate_checkin_alert",
        created_at__date=checkin_date,
        message__startswith=prefix,
    ).exists()
    if already_notified:
        return

    staff_users = User.objects.filter(
        gym=gym,
        is_active=True,
        role__in=[User.ROLE_OWNER, User.ROLE_MANAGER, User.ROLE_RECEPTION],
    )
    notifications = [
        Notification(
            gym=gym,
            recipient=staff,
            type="duplicate_checkin_alert",
            message=(
                f"Duplicate check-in attempted today ({checkin_date}) by member "
                f"{member.full_name} ({member.phone})."
            ),
        )
        for staff in staff_users
    ]
    if notifications:
        Notification.objects.bulk_create(notifications)


def issue_member_qr_token(
    member: Member, valid_seconds: Optional[int] = None
) -> Tuple[str, QRToken]:
    """
    Issue a fresh signed asymmetric JWT QR token for an active member.

    SPEC §8 / SPRINTS.md:
    - 90-second expiration window
    - Single-use consumption tracking
    - Denied if member is not active or lacks an active subscription
    """
    if valid_seconds is None:
        valid_seconds = getattr(settings, "QR_TOKEN_WINDOW_SECONDS", 90)

    # Validate member account status
    if member.status != Member.STATUS_ACTIVE:
        raise ScanValidationError(
            reason=member.status,
            message=f"Member account is {member.status}.",
            member=member,
        )

    # Validate member subscription (fail closed: no subscription -> expired)
    today = timezone.localdate()
    latest_sub = (
        MemberSubscription.all_objects.filter(gym=member.gym, member=member)
        .order_by("-end_date")
        .first()
    )
    if not latest_sub:
        raise ScanValidationError(
            reason="expired",
            message="Member has no active subscription.",
            member=member,
        )
    if latest_sub.status == MemberSubscription.STATUS_SUSPENDED:
        raise ScanValidationError(
            reason="suspended",
            message="Member subscription is suspended.",
            member=member,
        )
    if latest_sub.status == MemberSubscription.STATUS_FROZEN:
        raise ScanValidationError(
            reason="frozen",
            message="Member subscription is frozen.",
            member=member,
        )
    if (
        latest_sub.status != MemberSubscription.STATUS_ACTIVE
        or latest_sub.end_date < today
    ):
        raise ScanValidationError(
            reason="expired",
            message="Member subscription has expired.",
            member=member,
        )

    now = timezone.now()
    expires_at = now + timedelta(seconds=valid_seconds)
    token_id = str(uuid.uuid4())

    payload = {
        "sub": str(member.id),
        "member_id": str(member.id),
        "gym_id": str(member.gym_id),
        "jti": token_id,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
        "type": "qr_checkin",
    }

    token_str = sign_qr_payload(payload)
    token_hex_hash = hash_token(token_str)

    # Deactivate existing active tokens for this member
    QRToken.all_objects.filter(gym=member.gym, member=member, is_active=True).update(
        is_active=False
    )

    qr_record = QRToken.all_objects.create(
        gym=member.gym,
        member=member,
        token_hash=token_hex_hash,
        issued_at=now,
        expires_at=expires_at,
        is_active=True,
    )

    return token_str, qr_record


def verify_and_process_scan(
    token_str: str,
    gym: GymTenant,
    recorded_by: Optional[User] = None,
    branch_id: Optional[uuid.UUID] = None,
) -> dict:
    """
    Verify asymmetric QR token and record attendance.

    Enforces:
    1. Signature validity (tampered -> 400 invalid_token)
    2. Expiration window (90s, zero leeway -> 400 token_expired)
    3. Gym tenant match (-> 400 gym_mismatch)
    4. Single-use consumption (reused -> 400 token_consumed)
    5. Active subscription (distinguishable reasons: expired/frozen/suspended)
    6. Single check-in per day (duplicate -> denied, no row, staff notified)
    7. Atomically records exactly 1 Attendance row, consumes token, issues next token.
    """
    if not token_str or not token_str.strip():
        raise ScanValidationError(
            reason="invalid_token", message="QR token is required."
        )

    # 1. Decode & verify JWT signature and expiration
    try:
        payload = verify_qr_jwt(token_str)
    except TokenExpiredError as e:
        raise ScanValidationError(
            reason="token_expired", message="QR token has expired."
        ) from e
    except InvalidTokenError as e:
        raise ScanValidationError(
            reason="invalid_token", message="Invalid or tampered QR token."
        ) from e

    # 2. Check token claims
    if payload.get("type") != "qr_checkin":
        raise ScanValidationError(reason="invalid_token", message="Invalid token type.")

    token_gym_id = payload.get("gym_id")
    if str(token_gym_id) != str(gym.id):
        raise ScanValidationError(
            reason="gym_mismatch",
            message="QR token belongs to a different gym tenant.",
        )

    member_id = payload.get("member_id") or payload.get("sub")
    if not member_id:
        raise ScanValidationError(
            reason="invalid_token", message="QR token missing member identity."
        )

    # 3. Lookup member
    member = (
        Member.all_objects.filter(gym=gym, id=member_id).select_related("gym").first()
    )
    if not member:
        raise ScanValidationError(
            reason="member_not_found", message="Member record not found."
        )

    # 4. Check member account status
    if member.status == Member.STATUS_SUSPENDED:
        raise ScanValidationError(
            reason="suspended",
            message="Member account is suspended.",
            member=member,
        )
    if member.status == Member.STATUS_FROZEN:
        raise ScanValidationError(
            reason="frozen",
            message="Member membership is frozen.",
            member=member,
        )
    if member.status == Member.STATUS_EXPIRED:
        raise ScanValidationError(
            reason="expired",
            message="Member membership has expired.",
            member=member,
        )
    if member.status != Member.STATUS_ACTIVE:
        raise ScanValidationError(
            reason=member.status,
            message=f"Member status is {member.status}.",
            member=member,
        )

    # 5. Check member subscription status (fail closed: no subscription -> expired)
    today = timezone.localdate()
    latest_sub = (
        MemberSubscription.all_objects.filter(gym=gym, member=member)
        .order_by("-end_date")
        .first()
    )
    if not latest_sub:
        raise ScanValidationError(
            reason="expired",
            message="Member has no active subscription.",
            member=member,
        )
    if latest_sub.status == MemberSubscription.STATUS_SUSPENDED:
        raise ScanValidationError(
            reason="suspended",
            message="Member subscription is suspended.",
            member=member,
        )
    if latest_sub.status == MemberSubscription.STATUS_FROZEN:
        raise ScanValidationError(
            reason="frozen",
            message="Member subscription is frozen.",
            member=member,
        )
    if (
        latest_sub.status != MemberSubscription.STATUS_ACTIVE
        or latest_sub.end_date < today
    ):
        raise ScanValidationError(
            reason="expired",
            message="Member subscription has expired.",
            member=member,
        )

    # 6. Check token consumption and active status in database
    token_hex_hash = hash_token(token_str)
    qr_record = QRToken.all_objects.filter(gym=gym, token_hash=token_hex_hash).first()

    if not qr_record or not qr_record.is_active or qr_record.used_at is not None:
        raise ScanValidationError(
            reason="token_consumed",
            message="This QR token has already been used.",
        )

    # 7. Check duplicate scan on the same calendar day
    existing_attendance = Attendance.all_objects.filter(
        gym=gym,
        member=member,
        date=today,
    ).first()

    if existing_attendance:
        # Deny duplicate, produce NO second row, notify staff
        notify_staff_duplicate_scan(gym, member, today)
        raise ScanValidationError(
            reason="already_checked_in",
            message=f"Member {member.full_name} has already checked in today.",
            member=member,
        )

    # 7. Atomically consume token, record attendance, and issue replacement token
    try:
        with transaction.atomic():
            updated = QRToken.all_objects.filter(
                id=qr_record.id,
                is_active=True,
                used_at__isnull=True,
            ).update(
                is_active=False,
                used_at=timezone.now(),
            )
            if updated == 0:
                raise ScanValidationError(
                    reason="token_consumed",
                    message="This QR token has already been used.",
                )

            attendance = Attendance.all_objects.create(
                gym=gym,
                member=member,
                branch_id=branch_id,
                date=today,
                status=Attendance.STATUS_CHECKED_IN,
                checked_in_at=timezone.now(),
                is_override=False,
                recorded_by=recorded_by,
            )

            next_token, _ = issue_member_qr_token(member)

            record_audit_log(
                action_type="attendance_qr_scan",
                affected_record_type="Attendance",
                affected_record_id=str(attendance.id),
                actor=recorded_by,
                gym=gym,
                metadata={
                    "member_id": str(member.id),
                    "member_name": member.full_name,
                    "date": str(today),
                },
            )
    except IntegrityError as e:
        notify_staff_duplicate_scan(gym, member, today)
        raise ScanValidationError(
            reason="already_checked_in",
            message=f"Member {member.full_name} has already checked in today.",
            member=member,
        ) from e

    return {
        "status": "success",
        "message": f"Welcome, {member.full_name}!",
        "member": {
            "id": str(member.id),
            "full_name": member.full_name,
            "photo_url": format_member_photo_url(gym.id, member.photo_url),
            "status": member.status,
            "phone": member.phone,
        },
        "attendance": {
            "id": str(attendance.id),
            "date": str(attendance.date),
            "checked_in_at": attendance.checked_in_at.isoformat(),
            "is_override": False,
        },
        "next_token": next_token,
    }


def process_manual_override(
    member_id: uuid.UUID,
    gym: GymTenant,
    reason: str,
    recorded_by: Optional[User] = None,
    branch_id: Optional[uuid.UUID] = None,
    actor: Optional[User] = None,
) -> dict:
    """
    Perform manual attendance check-in override by Reception / staff.

    Enforces:
    - Non-empty reason required
    - Active subscription required; refused for expired, frozen, suspended members
    - Refused if member already checked in today
    - Produces exactly one Attendance row (is_override=True, override_reason)
    - Produces an AuditLog entry
    """
    staff_user = recorded_by or actor
    if not staff_user:
        raise ValueError(
            "A staff user (recorded_by or actor) is required for manual override."
        )

    if not reason or not reason.strip():
        raise ScanValidationError(
            reason="reason_required",
            message="A non-empty reason is required for manual override.",
        )

    clean_reason = reason.strip()

    member = (
        Member.all_objects.filter(gym=gym, id=member_id).select_related("gym").first()
    )
    if not member:
        raise ScanValidationError(
            reason="member_not_found", message="Member record not found."
        )

    # Refused for expired, frozen, or suspended members
    if member.status == Member.STATUS_SUSPENDED:
        raise ScanValidationError(
            reason="suspended",
            message="Manual override refused: member account is suspended.",
            member=member,
        )
    if member.status == Member.STATUS_FROZEN:
        raise ScanValidationError(
            reason="frozen",
            message="Manual override refused: member membership is frozen.",
            member=member,
        )
    if member.status == Member.STATUS_EXPIRED:
        raise ScanValidationError(
            reason="expired",
            message="Manual override refused: member membership has expired.",
            member=member,
        )
    if member.status != Member.STATUS_ACTIVE:
        raise ScanValidationError(
            reason=member.status,
            message=f"Manual override refused: member status is {member.status}.",
            member=member,
        )

    # Validate member subscription (fail closed: no subscription -> expired)
    today = timezone.localdate()
    latest_sub = (
        MemberSubscription.all_objects.filter(gym=gym, member=member)
        .order_by("-end_date")
        .first()
    )
    if not latest_sub:
        raise ScanValidationError(
            reason="expired",
            message="Manual override refused: member has no active subscription.",
            member=member,
        )
    if latest_sub.status == MemberSubscription.STATUS_SUSPENDED:
        raise ScanValidationError(
            reason="suspended",
            message="Manual override refused: member subscription is suspended.",
            member=member,
        )
    if latest_sub.status == MemberSubscription.STATUS_FROZEN:
        raise ScanValidationError(
            reason="frozen",
            message="Manual override refused: member subscription is frozen.",
            member=member,
        )
    if (
        latest_sub.status != MemberSubscription.STATUS_ACTIVE
        or latest_sub.end_date < today
    ):
        raise ScanValidationError(
            reason="expired",
            message="Manual override refused: member subscription has expired.",
            member=member,
        )

    # Check duplicate check-in today
    today = timezone.localdate()
    if Attendance.all_objects.filter(gym=gym, member=member, date=today).exists():
        raise ScanValidationError(
            reason="already_checked_in",
            message=f"Member {member.full_name} has already checked in today.",
            member=member,
        )

    try:
        with transaction.atomic():
            attendance = Attendance.all_objects.create(
                gym=gym,
                member=member,
                branch_id=branch_id,
                date=today,
                status=Attendance.STATUS_CHECKED_IN,
                checked_in_at=timezone.now(),
                is_override=True,
                override_reason=clean_reason,
                recorded_by=staff_user,
            )

            record_audit_log(
                action_type="attendance_manual_override",
                affected_record_type="Attendance",
                affected_record_id=str(attendance.id),
                actor=staff_user,
                gym=gym,
                metadata={
                    "member_id": str(member.id),
                    "member_name": member.full_name,
                    "reason": clean_reason,
                    "date": str(today),
                },
            )
    except IntegrityError as e:
        raise ScanValidationError(
            reason="already_checked_in",
            message=f"Member {member.full_name} has already checked in today.",
            member=member,
        ) from e

    return {
        "status": "success",
        "message": f"Manual check-in recorded for {member.full_name}.",
        "member": {
            "id": str(member.id),
            "full_name": member.full_name,
            "photo_url": format_member_photo_url(gym.id, member.photo_url),
            "status": member.status,
            "phone": member.phone,
        },
        "attendance": {
            "id": str(attendance.id),
            "date": str(attendance.date),
            "checked_in_at": attendance.checked_in_at.isoformat(),
            "is_override": True,
            "override_reason": attendance.override_reason,
        },
    }


def get_member_attendance_log(member: Member, start_date: date, end_date: date) -> dict:
    """
    Generate daily attendance log showing ✓/✗ per day for date range.

    Derived from check-ins and member's subscription period:
    - Days inside subscription period with check-in: 'present' (✓)
    - Days inside subscription period without check-in: 'absent' (✗)
    - Days outside subscription period: 'blank' ("")
    """
    sub_start, sub_end = member.get_subscription_period()

    attendances = Attendance.all_objects.filter(
        gym=member.gym,
        member=member,
        date__range=[start_date, end_date],
    )
    attendance_by_date = {att.date: att for att in attendances}

    days = []
    curr = start_date
    while curr <= end_date:
        is_in_period = (
            sub_start is not None
            and sub_end is not None
            and sub_start <= curr <= sub_end
        )
        if not is_in_period:
            days.append(
                {
                    "date": str(curr),
                    "status": "blank",
                    "symbol": "",
                    "attended": False,
                }
            )
        else:
            att = attendance_by_date.get(curr)
            if att:
                days.append(
                    {
                        "date": str(curr),
                        "status": "present",
                        "symbol": "✓",
                        "attended": True,
                        "checked_in_at": att.checked_in_at.isoformat(),
                        "is_override": att.is_override,
                    }
                )
            else:
                days.append(
                    {
                        "date": str(curr),
                        "status": "absent",
                        "symbol": "✗",
                        "attended": False,
                    }
                )
        curr += timedelta(days=1)

    return {
        "member_id": str(member.id),
        "member_name": member.full_name,
        "start_date": str(start_date),
        "end_date": str(end_date),
        "subscription_period": {
            "start_date": str(sub_start) if sub_start else None,
            "end_date": str(sub_end) if sub_end else None,
        },
        "days": days,
    }
