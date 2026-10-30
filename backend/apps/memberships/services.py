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
from apps.memberships.models import (
    Member,
    MemberFreeze,
    MembershipPlan,
    MemberSubscription,
)
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
            normalized_email = validate_email_address(
                raw_email,
                is_public_registration=is_self_service,
                is_lenient=(not is_self_service),
            )
            existing_user = User.all_objects.filter(email=normalized_email).first()
            if existing_user:
                is_expired_unverified = (
                    existing_user.role == User.ROLE_MEMBER
                    and existing_user.email_verified_at is None
                    and not existing_user.is_active
                )
                if not is_expired_unverified:
                    errors["email"] = ["A user with this email address already exists."]
        except ValidationError as e:
            if is_self_service:
                errors["email"] = list(e.messages)
            normalized_email = raw_email.strip().lower()
            existing_user = User.all_objects.filter(email=normalized_email).first()
            if existing_user:
                is_expired_unverified = (
                    existing_user.role == User.ROLE_MEMBER
                    and existing_user.email_verified_at is None
                    and not existing_user.is_active
                )
                if not is_expired_unverified:
                    errors["email"] = ["A user with this email address already exists."]

    raw_phone = data.get("phone")
    if not raw_phone:
        errors["phone"] = ["Phone number is required."]
        normalized_phone = ""
    else:
        try:
            normalized_phone = validate_and_normalize_phone(str(raw_phone))
            existing_member = Member.all_objects.filter(
                gym=gym, phone=normalized_phone
            ).first()
            if existing_member:
                is_expired_unverified = (
                    existing_member.user.role == User.ROLE_MEMBER
                    and existing_member.user.email_verified_at is None
                    and not existing_member.user.is_active
                )
                if not is_expired_unverified:
                    errors["phone"] = [
                        "A member with this phone number already exists in this gym."
                    ]
        except ValidationError as e:
            errors["phone"] = list(e.messages)
            normalized_phone = str(raw_phone).strip()

    raw_gender = (data.get("gender") or "").strip().lower()
    if raw_gender not in (Member.GENDER_FEMALE, Member.GENDER_MALE):
        errors["gender"] = ["Gender must be either Female or Male."]
    gender = raw_gender

    raw_emergency_contact = data.get("emergency_contact")
    normalized_emergency_contact = ""
    if raw_emergency_contact:
        try:
            normalized_emergency_contact = validate_and_normalize_phone(
                str(raw_emergency_contact)
            )
        except ValidationError as e:
            errors["emergency_contact"] = list(e.messages)

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
        "gender": gender,
        "emergency_contact": normalized_emergency_contact,
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
        # If an expired unverified member account already exists with this email, reuse and reactivate it
        stale_user = User.all_objects.filter(
            email=validated["email"],
            role=User.ROLE_MEMBER,
            email_verified_at__isnull=True,
            is_active=False,
        ).first()

        if stale_user:
            user = stale_user
            user.is_active = True
            user.full_name = validated["full_name"]
            user.phone = validated["phone"]
            user.set_password(raw_password)
            user.save()

            member = Member.all_objects.filter(user=user).first()
            if member:
                member.full_name = validated["full_name"]
                member.phone = validated["phone"]
                member.date_of_birth = validated["date_of_birth"]
                member.gender = validated["gender"]
                member.emergency_contact = validated["emergency_contact"]
                member.referral_source = validated["referral_source"]
                member.photo_url = validated["photo_url"]
                member.status = Member.STATUS_PENDING
                member.waiver_accepted_at = timezone.now()
                member._status_update_allowed = True
                try:
                    member.save()
                finally:
                    member._status_update_allowed = False
            else:
                member = Member.objects.create(
                    gym=gym,
                    user=user,
                    full_name=validated["full_name"],
                    phone=validated["phone"],
                    date_of_birth=validated["date_of_birth"],
                    gender=validated["gender"],
                    emergency_contact=validated["emergency_contact"],
                    referral_source=validated["referral_source"],
                    photo_url=validated["photo_url"],
                    status=Member.STATUS_PENDING,
                    waiver_accepted_at=timezone.now(),
                )
        else:
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
                photo_url=validated["photo_url"],
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
            photo_url=validated["photo_url"],
            status=Member.STATUS_PENDING,
            waiver_accepted_at=timezone.now(),
        )

        payment_method = str(data.get("payment_method") or "none").strip().lower()
        receipt = None
        if payment_method in ("cash", "bank_transfer"):
            plan_id = data.get("plan_id")
            if not plan_id:
                raise ValidationError(
                    {"plan_id": ["Plan is required when recording payment."]}
                )

            plan = MembershipPlan.objects.filter(
                gym=gym, id=plan_id, is_active=True
            ).first()
            if not plan:
                raise ValidationError(
                    {"plan_id": ["Membership plan not found or inactive for this gym."]}
                )

            idempotency_key = data.get("idempotency_key") or None
            notes = str(data.get("notes") or "").strip()

            if payment_method == "cash":
                from apps.payments.services import record_cash_payment

                _, receipt, _ = record_cash_payment(
                    gym=gym,
                    member=member,
                    plan=plan,
                    recorded_by=acting_user,
                    notes=notes,
                    idempotency_key=idempotency_key,
                )
            elif payment_method == "bank_transfer":
                from apps.payments.services import record_bank_transfer_payment
                from apps.tenants.storage import save_bank_transfer_screenshot

                bank_reference = str(data.get("bank_reference") or "").strip()
                if not bank_reference:
                    raise ValidationError(
                        {
                            "bank_reference": [
                                "Bank reference is required for bank transfer."
                            ]
                        }
                    )

                transfer_date = data.get("transfer_date")
                if not transfer_date:
                    raise ValidationError(
                        {
                            "transfer_date": [
                                "Transfer date is required for bank transfer."
                            ]
                        }
                    )

                screenshot_file = data.get("screenshot_file") or data.get("screenshot")
                if not screenshot_file:
                    raise ValidationError(
                        {
                            "screenshot": [
                                "A transfer screenshot image is required for bank transfer payments."
                            ]
                        }
                    )

                transfer_screenshot = save_bank_transfer_screenshot(
                    gym.id, screenshot_file
                )
                channel = str(data.get("channel") or "").strip()

                _, receipt, _ = record_bank_transfer_payment(
                    gym=gym,
                    member=member,
                    plan=plan,
                    recorded_by=acting_user,
                    bank_reference=bank_reference,
                    transfer_date=transfer_date,
                    channel=channel,
                    notes=notes,
                    idempotency_key=idempotency_key,
                    transfer_screenshot=transfer_screenshot,
                )

        if receipt:
            member._created_receipt = receipt

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
    allow_deactivated_plan: bool = False,
) -> MemberSubscription:
    """
    Create or renew a member subscription for an active plan.
    Deactivated plans are rejected for new checkouts, but allowed when confirming a payment
    that was initiated before the plan was deactivated (allow_deactivated_plan=True).
    Calculates end_date via calculate_plan_end_date and calls update_member_status in the same transaction.
    """
    if plan.gym_id != member.gym_id:
        raise ValidationError(
            "Cannot create or renew a subscription with a plan from another gym."
        )

    if not plan.is_active and not allow_deactivated_plan:
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

        if plan.trainer_inclusive:
            try:
                from apps.trainers.services import auto_assign_trainer_for_subscription

                auto_assign_trainer_for_subscription(subscription)
            except Exception as exc:
                import logging

                logging.getLogger(__name__).exception(
                    "Automatic trainer assignment error during subscription creation: %s",
                    exc,
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


def get_member_freeze_allowance(member: Member) -> Dict[str, Any]:
    """
    Returns gym freeze allowance and member's remaining freeze days.
    Server-enforced: checks GymConfig.freeze_days_allowed.
    """
    from apps.tenants.models import GymConfig

    config = GymConfig.objects.filter(gym=member.gym).first()
    total_allowed = config.freeze_days_allowed if config else 0

    sub = (
        MemberSubscription.all_objects.filter(gym=member.gym, member=member)
        .order_by("-end_date", "-created_at")
        .first()
    )

    if not sub:
        return {
            "total_allowed": total_allowed,
            "used_days": 0,
            "remaining_days": total_allowed,
            "has_active_subscription": False,
            "freeze_allowed": total_allowed > 0,
        }

    used_days = sum(
        f.days
        for f in MemberFreeze.all_objects.filter(
            gym=member.gym,
            member=member,
            subscription=sub,
            status__in=[MemberFreeze.STATUS_APPROVED, MemberFreeze.STATUS_COMPLETED],
        )
    )
    remaining_days = max(0, total_allowed - used_days)
    return {
        "total_allowed": total_allowed,
        "used_days": used_days,
        "remaining_days": remaining_days,
        "has_active_subscription": sub.status
        in [MemberSubscription.STATUS_ACTIVE, MemberSubscription.STATUS_FROZEN],
        "freeze_allowed": total_allowed > 0,
        "subscription_id": str(sub.id),
    }


def request_membership_freeze(
    member: Member,
    start_date: date,
    end_date: date,
    reason: str,
) -> MemberFreeze:
    """
    Member submits a freeze request for their active subscription.
    Enforces freeze allowance and gym freeze entitlement on the SERVER.
    """
    from apps.tenants.models import GymConfig

    config = GymConfig.objects.filter(gym=member.gym).first()
    total_allowed = config.freeze_days_allowed if config else 0
    if total_allowed <= 0:
        raise ValidationError({"detail": "This gym does not allow membership freezes."})

    today = timezone.localdate()
    if start_date < today:
        raise ValidationError(
            {"start_date": "Freeze start date cannot be in the past."}
        )
    if end_date < start_date:
        raise ValidationError(
            {"end_date": "Freeze end date must be on or after start date."}
        )

    days = (end_date - start_date).days + 1
    if days <= 0:
        raise ValidationError({"days": "Freeze duration must be at least 1 day."})

    trimmed_reason = (reason or "").strip()
    if len(trimmed_reason) < 5 or len(trimmed_reason) > 500:
        raise ValidationError(
            {"reason": "Reason must be between 5 and 500 characters."}
        )

    sub = (
        MemberSubscription.all_objects.filter(
            gym=member.gym,
            member=member,
            status__in=[
                MemberSubscription.STATUS_ACTIVE,
                MemberSubscription.STATUS_FROZEN,
            ],
        )
        .order_by("-end_date", "-created_at")
        .first()
    )

    if not sub:
        raise ValidationError(
            {"detail": "You do not have an active membership subscription to freeze."}
        )

    if start_date > sub.end_date:
        raise ValidationError(
            {"start_date": "Freeze cannot start after your subscription end date."}
        )

    used_days = sum(
        f.days
        for f in MemberFreeze.all_objects.filter(
            gym=member.gym,
            member=member,
            subscription=sub,
            status__in=[MemberFreeze.STATUS_APPROVED, MemberFreeze.STATUS_COMPLETED],
        )
    )
    remaining = total_allowed - used_days
    if days > remaining:
        raise ValidationError(
            {
                "detail": f"Requested freeze of {days} days exceeds your remaining allowance of {remaining} days."
            }
        )

    overlapping = MemberFreeze.all_objects.filter(
        gym=member.gym,
        member=member,
        status__in=[MemberFreeze.STATUS_PENDING, MemberFreeze.STATUS_APPROVED],
        start_date__lte=end_date,
        end_date__gte=start_date,
    ).exists()
    if overlapping:
        raise ValidationError(
            {
                "detail": "An overlapping pending or approved freeze request already exists."
            }
        )

    freeze = MemberFreeze.all_objects.create(
        gym=member.gym,
        member=member,
        subscription=sub,
        start_date=start_date,
        end_date=end_date,
        days=days,
        reason=trimmed_reason,
        status=MemberFreeze.STATUS_PENDING,
    )
    return freeze


def approve_membership_freeze(
    freeze_id: str,
    reviewer: User,
    gym: GymTenant,
) -> MemberFreeze:
    """
    Approve a pending member freeze request.
    Owner or Manager of that gym only.
    Concurrency protected: locks member record to prevent allowance races.
    Approving extends subscription end date by exactly frozen days, once.
    Updates member status strictly via shared update_member_status().
    Records audit entry and notification.
    """
    from apps.accounts.notifications import create_notification
    from apps.accounts.services import record_audit_log
    from apps.tenants.models import GymConfig

    if (
        reviewer.role not in (User.ROLE_OWNER, User.ROLE_MANAGER)
        or reviewer.gym_id != gym.id
    ):
        raise PermissionDenied("Only gym owner or manager can approve freeze requests.")

    with transaction.atomic():
        freeze = (
            MemberFreeze.all_objects.select_for_update()
            .filter(id=freeze_id, gym=gym)
            .first()
        )
        if not freeze:
            raise ValidationError({"detail": "Freeze request not found."})

        if freeze.status != MemberFreeze.STATUS_PENDING:
            raise ValidationError(
                {
                    "detail": f"Cannot approve freeze request with status '{freeze.status}'."
                }
            )

        # Lock member row for concurrency control
        member = Member.all_objects.select_for_update().get(id=freeze.member_id)

        config = GymConfig.objects.filter(gym=gym).first()
        total_allowed = config.freeze_days_allowed if config else 0
        if total_allowed <= 0:
            raise ValidationError(
                {"detail": "This gym does not allow membership freezes."}
            )

        sub = MemberSubscription.all_objects.select_for_update().get(
            id=freeze.subscription_id
        )

        used_days = sum(
            f.days
            for f in MemberFreeze.all_objects.filter(
                gym=gym,
                member=member,
                subscription=sub,
                status__in=[
                    MemberFreeze.STATUS_APPROVED,
                    MemberFreeze.STATUS_COMPLETED,
                ],
            )
        )
        remaining = total_allowed - used_days
        if freeze.days > remaining:
            raise ValidationError(
                {
                    "detail": f"Freeze approval refused: requested {freeze.days} days exceeds remaining allowance of {remaining} days."
                }
            )

        if not freeze.extension_applied:
            sub.end_date = sub.end_date + timedelta(days=freeze.days)
            sub.frozen_days_total += freeze.days
            today = timezone.localdate()
            if freeze.start_date <= today <= freeze.end_date:
                sub.status = MemberSubscription.STATUS_FROZEN
                sub.freeze_start_date = freeze.start_date
            sub.save(
                update_fields=[
                    "end_date",
                    "frozen_days_total",
                    "status",
                    "freeze_start_date",
                ]
            )
            freeze.extension_applied = True

        freeze.status = MemberFreeze.STATUS_APPROVED
        freeze.approved_by = reviewer
        freeze.reviewed_at = timezone.now()
        freeze.save()

        # Update member status strictly through shared status function
        update_member_status(member)

        record_audit_log(
            action_type="freeze_approved",
            affected_record_type="MemberFreeze",
            affected_record_id=str(freeze.id),
            actor=reviewer,
            gym=gym,
            metadata={
                "member_id": str(member.id),
                "member_name": member.full_name,
                "days": freeze.days,
                "start_date": str(freeze.start_date),
                "end_date": str(freeze.end_date),
                "new_subscription_end_date": str(sub.end_date),
            },
        )

        create_notification(
            recipient=member.user,
            notification_type="freeze_approved",
            message=f"Your freeze request for {freeze.days} day(s) was approved. Your subscription has been extended to {sub.end_date}.",
            gym=gym,
        )

        return freeze


def reject_membership_freeze(
    freeze_id: str,
    reviewer: User,
    rejection_reason: str,
    gym: GymTenant,
) -> MemberFreeze:
    """
    Reject a pending member freeze request with explanation.
    Leaves subscription active, writes audit log, and notifies member.
    """
    from apps.accounts.notifications import create_notification
    from apps.accounts.services import record_audit_log

    if (
        reviewer.role not in (User.ROLE_OWNER, User.ROLE_MANAGER)
        or reviewer.gym_id != gym.id
    ):
        raise PermissionDenied("Only gym owner or manager can reject freeze requests.")

    trimmed_reason = (rejection_reason or "").strip()
    if len(trimmed_reason) < 5 or len(trimmed_reason) > 500:
        raise ValidationError(
            {
                "rejection_reason": "Rejection explanation must be between 5 and 500 characters."
            }
        )

    with transaction.atomic():
        freeze = (
            MemberFreeze.all_objects.select_for_update()
            .filter(id=freeze_id, gym=gym)
            .first()
        )
        if not freeze:
            raise ValidationError({"detail": "Freeze request not found."})

        if freeze.status != MemberFreeze.STATUS_PENDING:
            raise ValidationError(
                {
                    "detail": f"Cannot reject freeze request with status '{freeze.status}'."
                }
            )

        member = Member.all_objects.get(id=freeze.member_id)
        freeze.status = MemberFreeze.STATUS_REJECTED
        freeze.approved_by = reviewer
        freeze.reviewed_at = timezone.now()
        freeze.rejection_reason = trimmed_reason
        freeze.save()

        record_audit_log(
            action_type="freeze_rejected",
            affected_record_type="MemberFreeze",
            affected_record_id=str(freeze.id),
            actor=reviewer,
            gym=gym,
            metadata={
                "member_id": str(member.id),
                "member_name": member.full_name,
                "rejection_reason": trimmed_reason,
            },
        )

        create_notification(
            recipient=member.user,
            notification_type="freeze_rejected",
            message=f"Your membership freeze request was rejected. Reason: {trimmed_reason}",
            gym=gym,
        )

        return freeze


def process_unfreezes(today: Optional[date] = None) -> int:
    """
    Scheduled task (runs every 5 minutes).
    Finds approved freezes whose end date has passed, completes them,
    returns subscriptions to active status, updates member status via
    shared update_member_status(), records audit logs, and notifies members.
    Also activates freezes whose start_date has arrived.
    """
    from apps.accounts.notifications import create_notification
    from apps.accounts.services import record_audit_log

    if today is None:
        today = timezone.localdate()

    # 1. Complete ended freezes
    ended_freezes = list(
        MemberFreeze.all_objects.filter(
            status=MemberFreeze.STATUS_APPROVED,
            end_date__lt=today,
        )
    )

    completed_count = 0
    for freeze in ended_freezes:
        with transaction.atomic():
            f = MemberFreeze.all_objects.select_for_update().get(id=freeze.id)
            if f.status != MemberFreeze.STATUS_APPROVED or f.end_date >= today:
                continue

            f.status = MemberFreeze.STATUS_COMPLETED
            f.unfrozen_at = timezone.now()
            f.save(update_fields=["status", "unfrozen_at", "updated_at"])

            sub = MemberSubscription.all_objects.select_for_update().get(
                id=f.subscription_id
            )

            # Check if any other approved freeze covers today
            other_active = MemberFreeze.all_objects.filter(
                subscription=sub,
                status=MemberFreeze.STATUS_APPROVED,
                start_date__lte=today,
                end_date__gte=today,
            ).exists()

            if not other_active and sub.status == MemberSubscription.STATUS_FROZEN:
                sub.status = (
                    MemberSubscription.STATUS_ACTIVE
                    if sub.end_date >= today
                    else MemberSubscription.STATUS_EXPIRED
                )
                sub.freeze_start_date = None
                sub.save(update_fields=["status", "freeze_start_date"])

            member = Member.all_objects.get(id=f.member_id)
            update_member_status(member, today=today)

            record_audit_log(
                action_type="freeze_unfrozen",
                affected_record_type="MemberFreeze",
                affected_record_id=str(f.id),
                actor=None,
                gym=f.gym,
                metadata={
                    "member_id": str(member.id),
                    "member_name": member.full_name,
                    "days": f.days,
                    "unfrozen_date": str(today),
                },
            )

            create_notification(
                recipient=member.user,
                notification_type="freeze_unfrozen",
                message="Your membership freeze has ended. Your check-in pass is now active.",
                gym=f.gym,
            )
            completed_count += 1

    # 2. Activate freezes starting today or earlier
    starting_freezes = list(
        MemberFreeze.all_objects.filter(
            status=MemberFreeze.STATUS_APPROVED,
            start_date__lte=today,
            end_date__gte=today,
        )
    )
    for freeze in starting_freezes:
        with transaction.atomic():
            sub = MemberSubscription.all_objects.select_for_update().get(
                id=freeze.subscription_id
            )
            if sub.status != MemberSubscription.STATUS_FROZEN:
                sub.status = MemberSubscription.STATUS_FROZEN
                sub.freeze_start_date = freeze.start_date
                sub.save(update_fields=["status", "freeze_start_date"])
                member = Member.all_objects.get(id=freeze.member_id)
                update_member_status(member, today=today)

    return completed_count
