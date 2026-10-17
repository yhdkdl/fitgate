"""Service functions for member registration, email verification, and body metrics."""

import hashlib
import logging
import secrets
from datetime import timedelta
from typing import Any, Dict, Optional, Tuple

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
from apps.memberships.models import Member
from apps.tenants.models import GymTenant

logger = logging.getLogger(__name__)


def validate_registration_payload(
    gym: GymTenant,
    data: Dict[str, Any],
    is_self_service: bool = True,
) -> Dict[str, Any]:
    """
    Validate registration input for both self-service and staff-assisted workflows.
    Ensures identical Member + BodyMetrics validation and duplicate rejection.
    """
    errors: Dict[str, list[str]] = {}

    full_name = str(data.get("full_name") or "").strip()
    if not full_name:
        errors["full_name"] = ["Full name is required."]

    raw_email = data.get("email")
    if not raw_email or not isinstance(raw_email, str):
        errors["email"] = ["Email address is required."]
    else:
        normalized_email = raw_email.strip().lower()
        if User.all_objects.filter(email=normalized_email).exists():
            errors["email"] = ["A user with this email address already exists."]

    phone = str(data.get("phone") or "").strip()
    if not phone:
        errors["phone"] = ["Phone number is required."]
    else:
        # Check duplicate phone within this gym tenant
        if Member.all_objects.filter(gym=gym, phone=phone).exists():
            errors["phone"] = [
                "A member with this phone number already exists in this gym."
            ]

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
                email=raw_email.strip().lower() if raw_email else "member@fitgate.org",
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
        "email": raw_email.strip().lower(),
        "phone": phone,
        "date_of_birth": data.get("date_of_birth"),
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
            photo_url=validated["photo_url"],
            status=Member.STATUS_ACTIVE,
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
            status=Member.STATUS_ACTIVE,
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
