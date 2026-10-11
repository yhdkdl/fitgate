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

    # Send welcome email containing set-password link (never a password)
    scheme = getattr(settings, "PUBLIC_URL_SCHEME", "https")
    domain = getattr(settings, "DOMAIN", "localhost")
    invite_link = f"{scheme}://{normalized_subdomain}.{domain}/set-password?token={raw_invite_token}"

    try:
        send_owner_welcome_email(owner, gym, invite_link)
    except Exception:
        logger.exception(
            "Failed to send welcome email to owner %s for gym %s",
            owner.email,
            gym.subdomain,
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

    gym.save(update_fields=update_fields)
    return gym
