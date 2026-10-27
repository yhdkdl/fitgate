"""Domain services for gym tenant lifecycle, provisioning, and TLS confirmation."""

import hashlib
import logging
import re
import secrets
from datetime import timedelta
from decimal import Decimal
from typing import Any, Dict, Optional
from uuid import UUID

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from apps.accounts.models import AuthToken, User
from apps.accounts.notifications import send_owner_welcome_email
from apps.payments.models import Payment
from apps.tenants.models import (
    RESERVED_SUBDOMAINS,
    GymConfig,
    GymTenant,
    get_tier_defaults,
    validate_subdomain,
)
from apps.tenants.uapi import BaseUAPIClient, get_uapi_client

logger = logging.getLogger(__name__)


def propose_subdomain(name: str) -> str:
    """
    Generate an editable, DNS-compliant subdomain candidate from a gym name.

    Normalizes to lowercase alphanumeric characters separated by single hyphens,
    ensures it is not reserved, and appends a numeric suffix if already registered.
    """
    if not name or not isinstance(name, str):
        candidate = "gym"
    else:
        # Convert non-alphanumeric chars to hyphens
        candidate = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
        if not candidate:
            candidate = "gym"

    # Truncate to maximum 60 chars to allow numeric suffix if needed
    candidate = candidate[:60].rstrip("-")

    if candidate in RESERVED_SUBDOMAINS:
        candidate = f"{candidate}-gym"

    # Ensure uniqueness against existing GymTenant records
    base_candidate = candidate
    suffix = 1
    while GymTenant.objects.filter(subdomain=candidate).exists():
        candidate = f"{base_candidate}-{suffix}"
        suffix += 1

    return candidate


@transaction.atomic
def create_gym(
    *,
    name: str,
    subdomain: str,
    tier: str,
    owner_email: str,
    payment_amount: Decimal | float | int | str,
    payment_reference: str,
    acting_super_admin: User,
    location: str = "",
    contact_name: str = "",
    contact_phone: str = "",
    contact_email: str = "",
    owner_name: str = "",
    payment_method: str = "bank_transfer",
    demo_request_id: Optional[str] = None,
    uapi_client: Optional[BaseUAPIClient] = None,
) -> Dict[str, Any]:
    """
    Atomically create a new gym tenant, configuration, payment, owner user,
    and provision subdomain via cPanel UAPI.

    Preconditions:
    - acting_super_admin must have role super_admin.
    - payment_method must be bank_transfer (chapa is rejected).
    - subdomain must be a valid, unreserved, unique DNS label.
    - owner_email must not already exist across the platform.

    Atomicity:
    - If any step fails (including UAPI provisioning), all database changes
      are rolled back leaving nothing half-created.
    """
    # 1. Authorization check
    if (
        not acting_super_admin
        or getattr(acting_super_admin, "role", None) != User.ROLE_SUPER_ADMIN
    ):
        raise PermissionDenied("Only Super Admin can create a gym tenant.")

    # 2. Payment method validation
    if payment_method != Payment.METHOD_BANK_TRANSFER:
        raise ValidationError(
            {
                "payment_method": [
                    "Gym subscription payments must use bank_transfer. Chapa is rejected."
                ]
            }
        )

    # 3. Subdomain normalization and validation
    if not subdomain or not isinstance(subdomain, str):
        raise ValidationError({"subdomain": ["Subdomain is required."]})
    normalized_subdomain = subdomain.strip().lower()
    validate_subdomain(normalized_subdomain)

    if GymTenant.objects.filter(subdomain=normalized_subdomain).exists():
        raise ValidationError({"subdomain": ["Subdomain already exists."]})

    # 4. Tier validation
    if tier not in (
        GymTenant.TIER_STARTER,
        GymTenant.TIER_GROWTH,
        GymTenant.TIER_PRO,
    ):
        raise ValidationError({"tier": [f"Invalid subscription tier: {tier}"]})

    # 5. Owner email validation and uniqueness
    if not owner_email or not isinstance(owner_email, str):
        raise ValidationError({"owner_email": ["Owner email is required."]})
    normalized_owner_email = owner_email.strip().lower()

    if User.all_objects.filter(email=normalized_owner_email).exists():
        raise ValidationError(
            {"owner_email": ["A user with this email address already exists."]}
        )

    # 6. Payment amount validation
    try:
        amount_decimal = Decimal(str(payment_amount))
        if amount_decimal <= 0:
            raise ValueError
    except Exception:
        raise ValidationError(
            {"payment_amount": ["Payment amount must be a positive number."]}
        )

    if not payment_reference:
        raise ValidationError(
            {"payment_reference": ["Bank transfer reference note is required."]}
        )

    # 7. Atomic creation
    # Create GymTenant as active (no pending gym in this version)
    gym = GymTenant.objects.create(
        name=name.strip(),
        subdomain=normalized_subdomain,
        status=GymTenant.STATUS_ACTIVE,
        tier=tier,
        currency="ETB",
        location=location.strip(),
        contact_name=contact_name.strip(),
        contact_phone=contact_phone.strip(),
        contact_email=(
            contact_email.strip().lower() if contact_email else normalized_owner_email
        ),
        tls_confirmed_at=None,
        subscription_expires_at=None,
    )

    # Create GymConfig with tier defaults
    tier_defaults = get_tier_defaults(tier)
    gym_config, _ = GymConfig.objects.update_or_create(gym=gym, defaults=tier_defaults)

    # Record confirmed payment
    payment = Payment.objects.create(
        gym=gym,
        payer_type=Payment.PAYER_TYPE_GYM_SUBSCRIPTION,
        method=Payment.METHOD_BANK_TRANSFER,
        amount_etb=amount_decimal,
        bank_reference=payment_reference.strip(),
        status=Payment.STATUS_CONFIRMED,
        confirmed_by=acting_super_admin,
    )

    # Create Owner user (pre-verified email, no password set)
    now = timezone.now()
    owner = User(
        gym=gym,
        email=normalized_owner_email,
        full_name=owner_name.strip() if owner_name else contact_name.strip(),
        phone=contact_phone.strip(),
        role=User.ROLE_OWNER,
        is_active=True,
        email_verified_at=now,
        must_change_password=True,
    )
    owner.set_unusable_password()
    owner.save()

    # Create single-use expiring invite token
    raw_invite_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_invite_token.encode("utf-8")).hexdigest()
    invite_token = AuthToken.objects.create(
        user=owner,
        purpose=AuthToken.PURPOSE_INVITE,
        token_hash=token_hash,
        expires_at=now + timedelta(days=7),
    )

    # Provision subdomain via cPanel UAPI
    client = uapi_client or get_uapi_client()
    client.provision_subdomain(normalized_subdomain)

    # Send welcome email containing set-password link (never a password) via transaction.on_commit
    scheme = settings.PUBLIC_URL_SCHEME
    domain = settings.DOMAIN
    port_suffix = (
        f":{settings.PUBLIC_PORT}" if getattr(settings, "PUBLIC_PORT", "") else ""
    )
    invite_link = f"{scheme}://{normalized_subdomain}.{domain}{port_suffix}/set-password?token={raw_invite_token}"

    def _send_welcome():
        try:
            send_owner_welcome_email(owner, gym, invite_link)
        except Exception:
            logger.exception(
                "Failed to send welcome email to owner %s for gym %s",
                owner.email,
                gym.subdomain,
            )

    transaction.on_commit(_send_welcome)

    # Link demo request if provided (Sprint 4a)
    if demo_request_id:
        from apps.tenants.models import DemoRequest

        demo_req = DemoRequest.objects.filter(id=demo_request_id).first()
        if demo_req:
            demo_req.status = DemoRequest.STATUS_CONVERTED
            demo_req.converted_gym = gym
            demo_req.handled_by = acting_super_admin
            demo_req.save()

    from apps.accounts.services import record_audit_log

    record_audit_log(
        action_type="gym_created",
        affected_record_type="GymTenant",
        affected_record_id=str(gym.id),
        actor=acting_super_admin,
        gym=None,
        metadata={
            "name": gym.name,
            "subdomain": gym.subdomain,
            "tier": gym.tier,
            "owner_email": owner.email,
            "payment_amount": str(amount_decimal),
        },
    )

    return {
        "gym": gym,
        "config": gym_config,
        "payment": payment,
        "owner": owner,
        "invite_token": invite_token,
        "invite_link": invite_link,
        "raw_invite_token": raw_invite_token,
    }


def confirm_gym_tls(gym_id: UUID | str, acting_super_admin: User) -> GymTenant:
    """
    Confirm TLS certificate validity for a gym tenant.

    - Super Admin only.
    - Sets tls_confirmed_at to current timestamp.
    - If set for the first time, sets subscription_expires_at to one year later.
    """
    if (
        not acting_super_admin
        or getattr(acting_super_admin, "role", None) != User.ROLE_SUPER_ADMIN
    ):
        raise PermissionDenied("Only Super Admin can confirm TLS certificates.")

    try:
        gym = GymTenant.objects.get(id=gym_id)
    except GymTenant.DoesNotExist:
        raise ValidationError({"gym_id": ["Gym tenant not found."]})

    now = timezone.now()
    update_fields = ["tls_confirmed_at", "updated_at"]

    if gym.tls_confirmed_at is None:
        gym.tls_confirmed_at = now
        gym.subscription_expires_at = now + timedelta(days=365)
        update_fields.append("subscription_expires_at")
    else:
        gym.tls_confirmed_at = now

    with transaction.atomic():
        gym.save(update_fields=update_fields)
        from apps.accounts.services import record_audit_log

        record_audit_log(
            action_type="gym_tls_confirmed",
            affected_record_type="GymTenant",
            affected_record_id=str(gym.id),
            actor=acting_super_admin,
            gym=gym,
            metadata={
                "subdomain": gym.subdomain,
                "tls_confirmed_at": gym.tls_confirmed_at.isoformat(),
            },
        )
    return gym


ENTITLEMENT_FIELDS = frozenset(
    {
        "tier",
        "has_trainer_module",
        "has_ai_plans",
        "has_analytics",
        "has_group_classes",
        "has_multi_branch",
        "freeze_days_allowed",
        "payment_grace_days",
        "subscription_reminder_days",
    }
)


def get_first_run_checklist(gym: GymTenant) -> dict:
    """
    Compute onboarding checklist progress from real application records.

    Items:
    1. add_branding: brand_color or logo configured.
    2. create_first_plan: first membership plan created (Sprint 10).
    3. add_staff: manager, trainer, or reception account created.
    4. register_first_member: member account registered.
    """
    config = GymConfig.objects.filter(gym_id=gym.id).first()
    if config is None:
        config, _ = GymConfig.objects.get_or_create(gym=gym)

    branding_completed = bool(config.brand_color or config.logo)

    first_plan_completed = False
    try:
        from apps.memberships.models import MembershipPlan

        first_plan_completed = MembershipPlan.objects.filter(gym=gym).exists()
    except (ImportError, Exception):
        first_plan_completed = False

    staff_completed = User.all_objects.filter(
        gym=gym,
        role__in=[User.ROLE_MANAGER, User.ROLE_TRAINER, User.ROLE_RECEPTION],
    ).exists()

    member_completed = User.all_objects.filter(
        gym=gym,
        role=User.ROLE_MEMBER,
    ).exists()

    items = {
        "add_branding": {
            "label": "Add gym branding & logo",
            "completed": branding_completed,
        },
        "create_first_plan": {
            "label": "Create your first membership plan",
            "completed": first_plan_completed,
        },
        "add_staff": {
            "label": "Add a staff account",
            "completed": staff_completed,
        },
        "register_first_member": {
            "label": "Register your first member",
            "completed": member_completed,
        },
    }

    all_completed = all(item["completed"] for item in items.values())
    is_dismissed = bool(config.first_run_dismissed_at is not None)

    return {
        "is_dismissed": is_dismissed,
        "dismissed_at": config.first_run_dismissed_at,
        "all_completed": all_completed,
        "items": items,
    }


def dismiss_first_run_checklist(
    gym: GymTenant, acting_user: Optional[User] = None
) -> GymConfig:
    """Mark first-run checklist as dismissed for the gym."""
    config = getattr(gym, "config", None)
    if config is None:
        config, _ = GymConfig.objects.get_or_create(gym=gym)

    if config.first_run_dismissed_at is None:
        with transaction.atomic():
            config.first_run_dismissed_at = timezone.now()
            config.save(update_fields=["first_run_dismissed_at"])
            from apps.accounts.services import record_audit_log

            record_audit_log(
                action_type="checklist_dismissed",
                affected_record_type="GymConfig",
                affected_record_id=str(config.pk),
                actor=acting_user,
                gym=gym,
                metadata={"dismissed_at": config.first_run_dismissed_at.isoformat()},
            )
    return config


def update_gym_settings(
    gym: GymTenant,
    acting_user: User,
    data: dict,
) -> GymConfig:
    """
    Update Owner-editable gym settings with strict RBAC enforcement:
    - Super Admin can update all settings.
    - Owner can update brand_color, logo, show_unavailable_equipment, member_reminder_days.
    - Any attempt by an Owner to modify entitlement fields returns 403 Forbidden.
    - Manager or other roles attempting any modification receive 403 Forbidden.
    """
    is_super_admin = getattr(
        acting_user, "role", None
    ) == User.ROLE_SUPER_ADMIN or getattr(acting_user, "is_superuser", False)
    is_owner = (
        getattr(acting_user, "role", None) == User.ROLE_OWNER
        and getattr(acting_user, "gym_id", None) == gym.id
    )

    if not (is_super_admin or is_owner):
        raise PermissionDenied(
            "Only the gym owner or Super Admin can edit gym settings."
        )

    # Entitlement protection against Owner edits
    if not is_super_admin:
        unauthorized_fields = ENTITLEMENT_FIELDS.intersection(data.keys())
        if unauthorized_fields:
            raise PermissionDenied("Only Super Admin can modify gym entitlements.")

    config = getattr(gym, "config", None)
    if config is None:
        config, _ = GymConfig.objects.get_or_create(gym=gym)

    update_fields = []
    if "brand_color" in data:
        config.brand_color = data["brand_color"]
        update_fields.append("brand_color")
    if "logo" in data:
        config.logo = data["logo"]
        update_fields.append("logo")
    if "show_unavailable_equipment" in data:
        config.show_unavailable_equipment = data["show_unavailable_equipment"]
        update_fields.append("show_unavailable_equipment")
    if "member_reminder_days" in data:
        config.member_reminder_days = data["member_reminder_days"]
        update_fields.append("member_reminder_days")

    if is_super_admin:
        # Entitlements editable by Super Admin
        for field in [
            "has_trainer_module",
            "has_ai_plans",
            "has_analytics",
            "has_group_classes",
            "has_multi_branch",
            "freeze_days_allowed",
            "payment_grace_days",
            "subscription_reminder_days",
        ]:
            if field in data:
                setattr(config, field, data[field])
                update_fields.append(field)

    if update_fields:
        with transaction.atomic():
            config.save(update_fields=update_fields)
            from apps.accounts.services import record_audit_log

            record_audit_log(
                action_type="gym_settings_updated",
                affected_record_type="GymConfig",
                affected_record_id=str(config.pk),
                actor=acting_user,
                gym=gym,
                metadata={"updated_fields": update_fields},
            )

    return config
