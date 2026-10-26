import os
import secrets
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
    compact_id_to_uuid,
    hash_token,
    sign_qr_payload,
    uuid_to_compact_id,
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
    from apps.accounts.notifications import create_notification

    for staff in staff_users:
        create_notification(
            recipient=staff,
            notification_type="duplicate_checkin_alert",
            message=(
                f"Duplicate check-in attempted today ({checkin_date}) by member "
                f"{member.full_name} ({member.phone})."
            ),
            gym=gym,
        )


def issue_member_qr_token(
    member: Member, valid_seconds: Optional[int] = None
) -> Tuple[str, QRToken]:
    """
    Issue a fresh signed asymmetric JWT QR token for an active member.

    SPEC §8 / SPRINTS.md:
    - 90-second expiration window
    - Single-use consumption tracking
    - Refused if member lacks an active subscription (pending/expired/frozen/suspended)
    """
    if valid_seconds is None:
        valid_seconds = getattr(settings, "QR_TOKEN_WINDOW_SECONDS", 90)

    today = timezone.localdate()
    subs = list(
        MemberSubscription.all_objects.filter(gym=member.gym, member=member).order_by(
            "-end_date", "-created_at"
        )
    )
    if not subs:
        if member.status == Member.STATUS_PENDING:
            raise ScanValidationError(
                reason="pending",
                message="No active plan yet.",
                member=member,
            )
        raise ScanValidationError(
            reason="expired",
            message="Member has no active subscription.",
            member=member,
        )
    if any(s.status == MemberSubscription.STATUS_SUSPENDED for s in subs):
        raise ScanValidationError(
            reason="suspended",
            message="Member subscription is suspended.",
            member=member,
        )
    if any(s.status == MemberSubscription.STATUS_FROZEN for s in subs):
        raise ScanValidationError(
            reason="frozen",
            message="Member subscription is frozen.",
            member=member,
        )
    active_sub = next(
        (
            s
            for s in subs
            if s.status == MemberSubscription.STATUS_ACTIVE
            and s.start_date <= today <= s.end_date
        ),
        None,
    )
    if not active_sub:
        if any(
            s.status == MemberSubscription.STATUS_ACTIVE and s.start_date > today
            for s in subs
        ):
            raise ScanValidationError(
                reason="pending",
                message="No active plan yet.",
                member=member,
            )
        raise ScanValidationError(
            reason="expired",
            message="Member subscription has expired.",
            member=member,
        )

    now = timezone.now()
    expires_at = now + timedelta(seconds=valid_seconds)
    token_id = secrets.token_urlsafe(8)

    payload = {
        "m": uuid_to_compact_id(member.id),
        "g": uuid_to_compact_id(member.gym_id),
        "j": token_id,
        "exp": int(expires_at.timestamp()),
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


def execute_check_in(
    member: Member,
    gym: GymTenant,
    method: str,
    recorded_by: Optional[User] = None,
    override_reason: str = "",
    branch_id: Optional[uuid.UUID] = None,
    qr_record: Optional[QRToken] = None,
) -> dict:
    """
    Unified check-in execution engine for all member check-in methods.
    QR scans, manual overrides, and future credentials (NFC, biometric) all route here.

    Enforces:
    1. Method validation ('qr', 'manual_override', etc.).
    2. Overrides require non-empty reason and staff user.
    3. Member account status:
       - Suspended / frozen member accounts are refused immediately.
    4. Subscription validity checked directly from MemberSubscription (never trusts Member.status):
       - Refuses pending members with 'No active plan yet.' (reason='pending')
       - Refuses suspended members with 'Member subscription is suspended.' (reason='suspended')
       - Refuses frozen members with 'Member subscription is frozen.' (reason='frozen')
       - Refuses expired members with 'Member subscription has expired.' (reason='expired')
    5. QR token validity (checked after member/subscription status):
       - Refuses inactive or already-used token with 'This QR token has already been used.' (reason='token_consumed')
    6. Duplicate check-in on the same day is refused, produces NO second row, and notifies staff.
    7. Atomically consumes QR token (if QR), creates Attendance record with method and is_override,
       issues replacement QR token (if QR), and writes audit log.
    8. Ensures DB constraint attendance_override_matches_method is satisfied.
    """
    if method not in [Attendance.METHOD_QR, Attendance.METHOD_MANUAL_OVERRIDE]:
        raise ScanValidationError(
            reason="invalid_method",
            message=f"Unsupported check-in method: {method}",
            member=member,
        )

    is_override = method == Attendance.METHOD_MANUAL_OVERRIDE
    clean_override_reason = override_reason.strip() if override_reason else ""

    if is_override:
        if not recorded_by:
            raise ValueError(
                "A staff user (recorded_by) is required for manual override."
            )
        if not clean_override_reason:
            raise ScanValidationError(
                reason="reason_required",
                message="A non-empty reason is required for manual override.",
                member=member,
            )

    # 1. Check member account status
    if member.status == Member.STATUS_SUSPENDED:
        msg = (
            "Member account is suspended."
            if not is_override
            else "Manual override refused: member subscription is suspended."
        )
        raise ScanValidationError(
            reason="suspended",
            message=msg,
            member=member,
        )
    if member.status == Member.STATUS_FROZEN:
        msg = (
            "Member membership is frozen."
            if not is_override
            else "Manual override refused: member membership is frozen."
        )
        raise ScanValidationError(
            reason="frozen",
            message=msg,
            member=member,
        )

    # 2. Validate subscription directly (NEVER trust Member.status)
    today = timezone.localdate()
    subs = list(
        MemberSubscription.all_objects.filter(gym=gym, member=member).order_by(
            "-end_date", "-created_at"
        )
    )

    if not subs:
        if member.status == Member.STATUS_PENDING:
            raise ScanValidationError(
                reason="pending",
                message="No active plan yet.",
                member=member,
            )
        msg = (
            "Member subscription has expired."
            if not is_override
            else "Manual override refused: member subscription has expired."
        )
        raise ScanValidationError(
            reason="expired",
            message=msg,
            member=member,
        )

    if any(s.status == MemberSubscription.STATUS_SUSPENDED for s in subs):
        msg = (
            "Member subscription is suspended."
            if not is_override
            else "Manual override refused: member subscription is suspended."
        )
        raise ScanValidationError(
            reason="suspended",
            message=msg,
            member=member,
        )

    if any(s.status == MemberSubscription.STATUS_FROZEN for s in subs):
        msg = (
            "Member subscription is frozen."
            if not is_override
            else "Manual override refused: member subscription is frozen."
        )
        raise ScanValidationError(
            reason="frozen",
            message=msg,
            member=member,
        )

    active_sub = next(
        (
            s
            for s in subs
            if s.status == MemberSubscription.STATUS_ACTIVE
            and s.start_date <= today <= s.end_date
        ),
        None,
    )

    if not active_sub:
        if any(
            s.status == MemberSubscription.STATUS_ACTIVE and s.start_date > today
            for s in subs
        ):
            raise ScanValidationError(
                reason="pending",
                message="No active plan yet.",
                member=member,
            )
        msg = (
            "Member subscription has expired."
            if not is_override
            else "Manual override refused: member subscription has expired."
        )
        raise ScanValidationError(
            reason="expired",
            message=msg,
            member=member,
        )

    # 3. Check token consumption and active status in database (AFTER subscription checks)
    if method == Attendance.METHOD_QR and qr_record is not None:
        if not qr_record.is_active or qr_record.used_at is not None:
            raise ScanValidationError(
                reason="token_consumed",
                message="This QR token has already been used.",
                member=member,
            )

    # 4. Check duplicate scan on the same calendar day
    existing_attendance = Attendance.all_objects.filter(
        gym=gym,
        member=member,
        date=today,
    ).first()

    if existing_attendance:
        notify_staff_duplicate_scan(gym, member, today)
        raise ScanValidationError(
            reason="already_checked_in",
            message=f"Member {member.full_name} has already checked in today.",
            member=member,
        )

    # 3. Atomically consume token (if QR), create Attendance row, issue replacement token, log audit
    try:
        with transaction.atomic():
            if qr_record:
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
                        member=member,
                    )

            attendance = Attendance.all_objects.create(
                gym=gym,
                member=member,
                branch_id=branch_id,
                date=today,
                status=Attendance.STATUS_CHECKED_IN,
                checked_in_at=timezone.now(),
                method=method,
                is_override=is_override,
                override_reason=clean_override_reason if is_override else "",
                recorded_by=recorded_by,
            )

            next_token = None
            if method == Attendance.METHOD_QR:
                next_token, _ = issue_member_qr_token(member)

            action_type = (
                "attendance_qr_scan"
                if method == Attendance.METHOD_QR
                else "attendance_manual_override"
            )
            metadata = {
                "member_id": str(member.id),
                "member_name": member.full_name,
                "method": method,
                "date": str(today),
            }
            if is_override:
                metadata["reason"] = clean_override_reason

            record_audit_log(
                action_type=action_type,
                affected_record_type="Attendance",
                affected_record_id=str(attendance.id),
                actor=recorded_by,
                gym=gym,
                metadata=metadata,
            )
    except IntegrityError as e:
        notify_staff_duplicate_scan(gym, member, today)
        raise ScanValidationError(
            reason="already_checked_in",
            message=f"Member {member.full_name} has already checked in today.",
            member=member,
        ) from e

    message = (
        f"Welcome, {member.full_name}!"
        if method == Attendance.METHOD_QR
        else f"Manual check-in recorded for {member.full_name}."
    )

    return {
        "status": "success",
        "message": message,
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
            "method": attendance.method,
            "is_override": attendance.is_override,
            "override_reason": attendance.override_reason,
        },
        "next_token": next_token,
    }


def verify_and_process_scan(
    token_str: str,
    gym: GymTenant,
    recorded_by: Optional[User] = None,
    branch_id: Optional[uuid.UUID] = None,
) -> dict:
    """
    Verify asymmetric QR token and record attendance via shared execute_check_in.
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
    if "type" in payload and payload.get("type") != "qr_checkin":
        raise ScanValidationError(reason="invalid_token", message="Invalid token type.")

    raw_gym = payload.get("g") or payload.get("gym_id")
    if not raw_gym:
        raise ScanValidationError(
            reason="invalid_token", message="QR token missing gym identity."
        )
    try:
        token_gym_uuid = compact_id_to_uuid(raw_gym)
    except Exception:
        raise ScanValidationError(
            reason="invalid_token", message="QR token has invalid gym identity."
        )

    if token_gym_uuid != gym.id:
        raise ScanValidationError(
            reason="gym_mismatch",
            message="QR token belongs to a different gym tenant.",
        )

    raw_member = payload.get("m") or payload.get("member_id") or payload.get("sub")
    if not raw_member:
        raise ScanValidationError(
            reason="invalid_token", message="QR token missing member identity."
        )
    try:
        member_id = compact_id_to_uuid(raw_member)
    except Exception:
        raise ScanValidationError(
            reason="invalid_token", message="QR token has invalid member identity."
        )

    # 3. Lookup member
    member = (
        Member.all_objects.filter(gym=gym, id=member_id).select_related("gym").first()
    )
    if not member:
        raise ScanValidationError(
            reason="member_not_found", message="Member record not found."
        )

    # 4. Find token record in database
    token_hex_hash = hash_token(token_str)
    qr_record = QRToken.all_objects.filter(gym=gym, token_hash=token_hex_hash).first()

    if not qr_record:
        raise ScanValidationError(
            reason="token_consumed",
            message="This QR token has already been used.",
        )

    # 5. Delegate check-in logic to unified function
    return execute_check_in(
        member=member,
        gym=gym,
        method=Attendance.METHOD_QR,
        recorded_by=recorded_by,
        branch_id=branch_id,
        qr_record=qr_record,
    )


def process_manual_override(
    member_id: uuid.UUID,
    gym: GymTenant,
    reason: str,
    recorded_by: Optional[User] = None,
    branch_id: Optional[uuid.UUID] = None,
    actor: Optional[User] = None,
) -> dict:
    """
    Perform manual attendance check-in override via shared execute_check_in.
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

    member = (
        Member.all_objects.filter(gym=gym, id=member_id).select_related("gym").first()
    )
    if not member:
        raise ScanValidationError(
            reason="member_not_found", message="Member record not found."
        )

    # Delegate check-in logic to unified function
    return execute_check_in(
        member=member,
        gym=gym,
        method=Attendance.METHOD_MANUAL_OVERRIDE,
        recorded_by=staff_user,
        override_reason=reason.strip(),
        branch_id=branch_id,
    )


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
                        "method": att.method,
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
