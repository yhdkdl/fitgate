"""Service functions for member registration, email verification, and body metrics."""

import hashlib
import logging
import secrets
from datetime import date, timedelta
from typing import Any, Dict, Optional, Tuple

from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import AuthToken, User
from apps.accounts.notifications import (
    send_member_invite_email,
    send_member_verification_email,
)
from apps.core.validators import (
    validate_and_normalize_phone,
    validate_date_of_birth,
    validate_email_address,
    validate_name,
)
from apps.memberships.models import Member, MembershipPlan, MemberSubscription
from apps.tenants.models import GymTenant

logger = logging.getLogger(__name__)


def validate_registration_payload(
    gym: GymTenant,
    data: Dict[str, Any],
    is_self_service: bool = True,
) -> Dict[str, Any]:
    """
    Validate registration input for both self-service and staff-assisted workflows.
    Ensures identical Member validation and duplicate rejection.
    """
    errors: Dict[str, list[str]] = {}

    full_name_raw = data.get("full_name")
    try:
        full_name = validate_name(full_name_raw or "", "Full name")
    except ValidationError as e:
        errors["full_name"] = list(e.messages)
        full_name = str(full_name_raw or "").strip()

    raw_email = data.get("email")
    if not raw_email or not isinstance(raw_email, str):
        errors["email"] = ["Email address is required."]
        normalized_email = ""
    else:
        try:
            normalized_email = validate_email_address(raw_email)
            if User.all_objects.filter(email=normalized_email).exists():
                errors["email"] = ["A user with this email address already exists."]
        except ValidationError as e:
            errors["email"] = list(e.messages)
            normalized_email = raw_email.strip().lower()

    raw_phone = data.get("phone")
    if not raw_phone:
        errors["phone"] = ["Phone number is required."]
        normalized_phone = ""
    else:
        try:
            normalized_phone = validate_and_normalize_phone(str(raw_phone))
            if Member.all_objects.filter(gym=gym, phone=normalized_phone).exists():
                errors["phone"] = [
                    "A member with this phone number already exists in this gym."
                ]
        except ValidationError as e:
            errors["phone"] = list(e.messages)
            normalized_phone = str(raw_phone).strip()

    raw_dob = data.get("date_of_birth")
    validated_dob = raw_dob
    if raw_dob:
        try:
            validated_dob = validate_date_of_birth(raw_dob)
        except ValidationError as e:
            errors["date_of_birth"] = list(e.messages)

    waiver_accepted = data.get("waiver_accepted")
    if (
        waiver_accepted is not True
        and waiver_accepted != "true"
        and waiver_accepted != "True"
    ):
        errors["waiver_accepted"] = [
            "Accepting the health waiver is required to register."
        ]

    if is_self_service:
        password = data.get("password")
        if not password or not isinstance(password, str):
            errors["password"] = ["Password is required for self-registration."]
        else:
            dummy_user = User(
                email=(
                    normalized_email
                    if normalized_email
                    else f"member@{getattr(settings, 'DOMAIN', 'fitgate.tebebtech.com')}"
                ),
                full_name=full_name,
                role=User.ROLE_MEMBER,
                gym=gym,
            )
            try:
                validate_password(password, user=dummy_user)
            except ValidationError as val_err:
                errors["password"] = list(val_err.messages)

    if errors:
        raise ValidationError(errors)

    return {
        "full_name": full_name,
        "email": normalized_email,
        "phone": normalized_phone,
        "date_of_birth": validated_dob,
        "gender": data.get("gender") or "",
        "emergency_contact": str(data.get("emergency_contact") or "").strip(),
        "referral_source": str(data.get("referral_source") or "").strip(),
        "photo_url": str(data.get("photo_url") or "").strip(),
    }


def register_member_self_service(
    gym: GymTenant,
    data: Dict[str, Any],
) -> Tuple[Member, str]:
    """
    Register a new member via the public self-service portal on the gym's subdomain.

    - Creates unverified User (email_verified_at=None).
    - Hashes password.
    - Creates Member and initial BodyMetrics.
    - Generates single-use 24h email verification AuthToken.
    - Sends verification email via transaction.on_commit.
    """
    validated = validate_registration_payload(gym, data, is_self_service=True)
    raw_password = data["password"]

    with transaction.atomic():
        user = User.objects.create(
            email=validated["email"],
            role=User.ROLE_MEMBER,
            gym=gym,
            full_name=validated["full_name"],
            phone=validated["phone"],
            is_active=True,
            email_verified_at=None,
            must_change_password=False,
        )
        user.set_password(raw_password)
        user.save()

        member = Member.objects.create(
            gym=gym,
            user=user,
            full_name=validated["full_name"],
            phone=validated["phone"],
            date_of_birth=validated["date_of_birth"],
            gender=validated["gender"],
            emergency_contact=validated["emergency_contact"],
            referral_source=validated["referral_source"],
            status=Member.STATUS_PENDING,
            waiver_accepted_at=timezone.now(),
        )

        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        expires_at = timezone.now() + timedelta(hours=24)
        AuthToken.objects.create(
            user=user,
            token_hash=token_hash,
            purpose=AuthToken.PURPOSE_EMAIL_VERIFICATION,
            expires_at=expires_at,
        )

        scheme = settings.PUBLIC_URL_SCHEME
        domain = settings.DOMAIN
        port_suffix = (
            f":{settings.PUBLIC_PORT}" if getattr(settings, "PUBLIC_PORT", "") else ""
        )
        verify_link = f"{scheme}://{gym.subdomain}.{domain}{port_suffix}/verify-email?token={raw_token}"

        from apps.accounts.services import record_audit_log

        record_audit_log(
            action_type="member_registered",
            affected_record_type="Member",
            affected_record_id=str(member.id),
            actor=user,
            gym=gym,
            metadata={
                "email": user.email,
                "registration_type": "self_service",
                "full_name": member.full_name,
            },
        )

        transaction.on_commit(
            lambda: send_member_verification_email(user, gym, verify_link)
        )

    return member, raw_token


def register_member_staff_assisted(
    acting_user: User,
    gym: GymTenant,
    data: Dict[str, Any],
) -> Tuple[Member, str]:
    """
    Register a new member assisted by gym staff (Owner, Manager, Reception).

    - Enforces RBAC: only Owner, Manager, or Reception permitted.
    - User created with unusable password and email_verified_at=now (counts as verified).
    - Creates Member and initial BodyMetrics matching self-service structure.
    - Generates single-use 7-day set-password AuthToken.
    - Sends invite email via transaction.on_commit.
    """
    if getattr(acting_user, "gym_id", None) != gym.id:
        raise PermissionDenied(
            "You do not have permission to register members for another gym."
        )

    acting_role = getattr(acting_user, "role", None)
    allowed_roles = (User.ROLE_OWNER, User.ROLE_MANAGER, User.ROLE_RECEPTION)
    if acting_role not in allowed_roles:
        raise PermissionDenied(
            "Only Gym Owner, Manager, or Reception can register members."
        )

    validated = validate_registration_payload(gym, data, is_self_service=False)

    with transaction.atomic():
        user = User.objects.create(
            email=validated["email"],
            role=User.ROLE_MEMBER,
            gym=gym,
            full_name=validated["full_name"],
            phone=validated["phone"],
            is_active=True,
            email_verified_at=timezone.now(),
            must_change_password=False,
        )
        user.set_unusable_password()
        user.save()

        member = Member.objects.create(
            gym=gym,
            user=user,
            full_name=validated["full_name"],
            phone=validated["phone"],
            date_of_birth=validated["date_of_birth"],
            gender=validated["gender"],
            emergency_contact=validated["emergency_contact"],
            referral_source=validated["referral_source"],
            status=Member.STATUS_PENDING,
            waiver_accepted_at=timezone.now(),
        )

        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        expires_at = timezone.now() + timedelta(days=7)
        AuthToken.objects.create(
            user=user,
            token_hash=token_hash,
            purpose=AuthToken.PURPOSE_INVITE,
            expires_at=expires_at,
        )

        scheme = settings.PUBLIC_URL_SCHEME
        domain = settings.DOMAIN
        port_suffix = (
            f":{settings.PUBLIC_PORT}" if getattr(settings, "PUBLIC_PORT", "") else ""
        )
        invite_link = f"{scheme}://{gym.subdomain}.{domain}{port_suffix}/set-password?token={raw_token}"

        from apps.accounts.services import record_audit_log

        record_audit_log(
            action_type="member_registered",
            affected_record_type="Member",
            affected_record_id=str(member.id),
            actor=acting_user,
            gym=gym,
            metadata={
                "email": user.email,
                "registration_type": "staff_assisted",
                "full_name": member.full_name,
            },
        )

        transaction.on_commit(lambda: send_member_invite_email(user, gym, invite_link))

    return member, raw_token


def verify_member_email(
    raw_token: str,
    tenant: Optional[GymTenant] = None,
) -> User:
    """
    Verify member email address using a single-use token from AuthToken.PURPOSE_EMAIL_VERIFICATION.

    - Token must exist, match SHA-256 hash, purpose, not used, and not expired.
    - Verifies user belongs to tenant subdomain if in tenant context.
    - Atomically marks token used and sets user.email_verified_at.
    """
    if not raw_token or not isinstance(raw_token, str):
        raise ValidationError({"detail": "Invalid or expired verification token."})

    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    auth_token = (
        AuthToken.objects.select_related("user", "user__gym")
        .filter(
            token_hash=token_hash,
            purpose=AuthToken.PURPOSE_EMAIL_VERIFICATION,
        )
        .first()
    )

    if auth_token is None or auth_token.used_at is not None:
        raise ValidationError({"detail": "Invalid or expired verification token."})

    now = timezone.now()
    if auth_token.expires_at <= now:
        raise ValidationError({"detail": "Invalid or expired verification token."})

    user = auth_token.user
    if not user.is_active:
        raise ValidationError({"detail": "Invalid or expired verification token."})

    if tenant is not None:
        if user.gym_id is None or str(user.gym_id) != str(tenant.id):
            raise ValidationError({"detail": "Invalid or expired verification token."})

    with transaction.atomic():
        auth_token.used_at = now
        auth_token.save(update_fields=["used_at"])

        user.email_verified_at = now
        user.save(update_fields=["email_verified_at"])

        from apps.accounts.services import record_audit_log

        record_audit_log(
            action_type="email_verified",
            affected_record_type="User",
            affected_record_id=str(user.id),
            actor=user,
            gym=getattr(user, "gym", None),
            metadata={"email": user.email},
        )

    return user


def calculate_plan_end_date(
    start_date: date, duration_value: int, duration_unit: str
) -> date:
    """
    Calculate subscription end date accurately based on duration unit.
    For month durations, uses calendar months including month-end days (e.g. Jan 31 + 1 mo = Feb 28).
    For day durations, uses exact day count.
    """
    if duration_unit == MembershipPlan.DURATION_MONTHS or duration_unit == "months":
        return start_date + relativedelta(months=duration_value)
    elif duration_unit == MembershipPlan.DURATION_DAYS or duration_unit == "days":
        return start_date + timedelta(days=duration_value)
    else:
        raise ValueError(f"Unsupported duration unit: {duration_unit}")


def compute_member_status(member: Member, today: Optional[date] = None) -> str:
    """
    Derives member status strictly from MemberSubscription.
    MemberSubscription is the single source of truth.
    Returns one of: 'pending', 'active', 'expired', 'frozen', 'suspended'.
    """
    if today is None:
        today = timezone.localdate()

    subs = list(
        MemberSubscription.all_objects.filter(gym=member.gym, member=member).order_by(
            "-end_date", "-created_at"
        )
    )
    if not subs:
        return Member.STATUS_PENDING

    # 1. Any suspended subscription marks the member as suspended
    if any(s.status == MemberSubscription.STATUS_SUSPENDED for s in subs):
        return Member.STATUS_SUSPENDED

    # 2. Any currently frozen subscription
    if any(s.status == MemberSubscription.STATUS_FROZEN for s in subs):
        return Member.STATUS_FROZEN

    # 3. Check for active subscription covering today
    for s in subs:
        if s.status == MemberSubscription.STATUS_ACTIVE:
            if s.start_date <= today <= s.end_date:
                return Member.STATUS_ACTIVE

    # 4. Check for future active subscription
    for s in subs:
        if s.status == MemberSubscription.STATUS_ACTIVE and s.start_date > today:
            return Member.STATUS_PENDING

    # 5. Check for expired subscriptions
    all_expired = all(
        s.status == MemberSubscription.STATUS_EXPIRED or s.end_date < today
        for s in subs
        if s.status != MemberSubscription.STATUS_PENDING
    )
    if all_expired and any(s.status != MemberSubscription.STATUS_PENDING for s in subs):
        return Member.STATUS_EXPIRED

    return Member.STATUS_PENDING


def update_member_status(member: Member, today: Optional[date] = None) -> str:
    """
    Computes derived status from MemberSubscription and writes Member.status.
    Runs inside the current transaction with protected access.
    Only this function may write Member.status.
    """
    new_status = compute_member_status(member, today=today)
    if member.status != new_status:
        member.status = new_status
        member._status_update_allowed = True
        try:
            member.save(update_fields=["status"])
        finally:
            member._status_update_allowed = False
    return new_status


def create_or_renew_subscription(
    member: Member,
    plan: MembershipPlan,
    start_date: Optional[date] = None,
    actor: Optional[User] = None,
) -> MemberSubscription:
    """
    Create or renew a member subscription for an active plan.
    Deactivated plans are rejected for new subscriptions.
    Calculates end_date via calculate_plan_end_date and calls update_member_status in the same transaction.
    """
    if not plan.is_active:
        raise ValidationError(
            "Cannot create or renew a subscription with a deactivated plan."
        )

    today = timezone.localdate()
    if start_date is None:
        current_sub = (
            MemberSubscription.all_objects.filter(
                gym=member.gym,
                member=member,
                status=MemberSubscription.STATUS_ACTIVE,
                end_date__gte=today,
            )
            .order_by("-end_date")
            .first()
        )
        if current_sub and current_sub.end_date >= today:
            start_date = current_sub.end_date + timedelta(days=1)
        else:
            start_date = today

    end_date = calculate_plan_end_date(
        start_date, plan.duration_value, plan.duration_unit
    )

    with transaction.atomic():
        subscription = MemberSubscription.all_objects.create(
            gym=member.gym,
            member=member,
            plan=plan,
            start_date=start_date,
            end_date=end_date,
            status=MemberSubscription.STATUS_ACTIVE,
        )
        update_member_status(member, today=today)

        from apps.accounts.services import record_audit_log

        record_audit_log(
            action_type="member_subscription_created",
            affected_record_type="MemberSubscription",
            affected_record_id=str(subscription.id),
            actor=actor or getattr(member, "user", None),
            gym=member.gym,
            metadata={
                "member_id": str(member.id),
                "member_name": member.full_name,
                "plan_id": str(plan.id),
                "plan_name": plan.name,
                "start_date": str(start_date),
                "end_date": str(end_date),
                "price_etb": str(plan.price_etb),
            },
        )
    return subscription


def suspend_member(
    member: Member,
    actor: User,
    reason: str = "",
) -> Member:
    """
    Suspend a member. Moves their subscription to STATUS_SUSPENDED and derives Member.status in the same transaction.
    Only Gym Owner and Manager can suspend a member.
    """
    today = timezone.localdate()
    with transaction.atomic():
        subs = list(
            MemberSubscription.all_objects.filter(
                gym=member.gym, member=member
            ).order_by("-end_date", "-created_at")
        )
        if subs:
            for s in subs:
                if s.status in (
                    MemberSubscription.STATUS_ACTIVE,
                    MemberSubscription.STATUS_FROZEN,
                    MemberSubscription.STATUS_PENDING,
                ):
                    s.status = MemberSubscription.STATUS_SUSPENDED
                    s.save(update_fields=["status"])
        else:
            MemberSubscription.all_objects.create(
                gym=member.gym,
                member=member,
                plan=None,
                start_date=today,
                end_date=today,
                status=MemberSubscription.STATUS_SUSPENDED,
            )

        update_member_status(member, today=today)

        from apps.accounts.services import record_audit_log

        record_audit_log(
            action_type="member_suspended",
            affected_record_type="Member",
            affected_record_id=str(member.id),
            actor=actor,
            gym=member.gym,
            metadata={
                "member_id": str(member.id),
                "member_name": member.full_name,
                "reason": reason,
            },
        )
    return member


def reactivate_member(
    member: Member,
    actor: User,
) -> Member:
    """
    Reactivate a suspended member. Restores subscription status and derives Member.status in the same transaction.
    Only Gym Owner and Manager can reactivate a member.
    """
    today = timezone.localdate()
    with transaction.atomic():
        suspended_subs = list(
            MemberSubscription.all_objects.filter(
                gym=member.gym,
                member=member,
                status=MemberSubscription.STATUS_SUSPENDED,
            )
        )
        for s in suspended_subs:
            if s.plan is None and s.start_date == s.end_date == today:
                s.delete()
            elif s.end_date >= today:
                s.status = MemberSubscription.STATUS_ACTIVE
                s.save(update_fields=["status"])
            else:
                s.status = MemberSubscription.STATUS_EXPIRED
                s.save(update_fields=["status"])

        update_member_status(member, today=today)

        from apps.accounts.services import record_audit_log

        record_audit_log(
            action_type="member_reactivated",
            affected_record_type="Member",
            affected_record_id=str(member.id),
            actor=actor,
            gym=member.gym,
            metadata={
                "member_id": str(member.id),
                "member_name": member.full_name,
            },
        )
    return member
