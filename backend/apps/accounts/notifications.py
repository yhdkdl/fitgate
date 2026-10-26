"""Notification helper functions for accounts."""

import email.utils
import logging
import re
from typing import Any, List, Optional, Union

from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


def sanitize_email_display_name(raw_name: Optional[str]) -> str:
    """
    Sanitize display name for email sender:
    - Strip control characters (including newlines \\r, \\n)
    - Strip quotes (' and ") and angle brackets (< and >)
    - Collapse consecutive whitespace into single spaces
    - Trim whitespace
    - Limit length to at most 60 characters
    - Fallback to 'FitGate' if empty or whitespace-only
    Guarantees no email header injection is possible.
    """
    if not raw_name:
        return "FitGate"

    # Strip control characters (ASCII 0-31 and 127)
    cleaned = re.sub(r"[\x00-\x1f\x7f]", " ", str(raw_name))
    # Strip quotes and angle brackets
    cleaned = re.sub(r"[\'\"<>]", "", cleaned)
    # Collapse multiple whitespace characters into a single space
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    if not cleaned:
        return "FitGate"

    # Limit to at most 60 characters
    cleaned = cleaned[:60].strip()
    return cleaned or "FitGate"


def build_from_email(gym_or_name: Optional[Union[str, Any]] = None) -> str:
    """
    Build sender header "<display_name> <DEFAULT_FROM_EMAIL>" using email.utils.formataddr.
    If gym_or_name is provided:
      - If it has an attribute 'name', use gym.name
      - Else use str(gym_or_name)
    If gym_or_name is None, use "FitGate".
    """
    if gym_or_name is None:
        display_name = "FitGate"
    elif hasattr(gym_or_name, "name"):
        display_name = gym_or_name.name
    else:
        display_name = str(gym_or_name)

    safe_name = sanitize_email_display_name(display_name)
    default_from = settings.DEFAULT_FROM_EMAIL

    # Extract bare email address if DEFAULT_FROM_EMAIL is already "Name <addr>"
    _, parsed_email = email.utils.parseaddr(default_from)
    from_addr = parsed_email or default_from

    return email.utils.formataddr((safe_name, from_addr))


def is_recipient_allowed_by_staging_allowlist(email_addr: str) -> bool:
    """Check staging recipient allowlist (EMAIL_ALLOWED_RECIPIENTS)."""
    allowed_list = getattr(settings, "EMAIL_ALLOWED_RECIPIENTS", [])
    if not allowed_list:
        return True
    e = email_addr.strip().lower()
    for allowed in allowed_list:
        a = allowed.strip().lower()
        if a.startswith("@") and e.endswith(a):
            return True
        if e == a:
            return True
    return False


def check_and_increment_email_rate_caps(gym: Optional[Any] = None) -> bool:
    """
    Check hourly email dispatch rate caps per gym and platform-wide.
    Raises ValidationError("email limit reached") if cap is exceeded.
    """
    from django.core.cache import cache
    from django.core.exceptions import ValidationError
    from django.utils import timezone

    current_hour_str = timezone.now().strftime("%Y%m%d%H")

    # Platform hourly cap
    platform_cap = getattr(settings, "EMAIL_HOURLY_CAP_PLATFORM", 500)
    platform_key = f"email_rate_cap:platform:{current_hour_str}"
    try:
        current_platform = cache.get(platform_key, 0)
        if current_platform >= platform_cap:
            logger.warning(
                "Platform email rate cap exceeded (%d >= %d).",
                current_platform,
                platform_cap,
            )
            raise ValidationError("email limit reached")
    except ValidationError:
        raise
    except Exception as e:
        logger.warning("Cache access error checking platform email cap: %s", e)

    # Gym hourly cap
    gym_id = None
    if gym:
        gym_id = gym.id if hasattr(gym, "id") else str(gym)
    if gym_id:
        gym_cap = getattr(settings, "EMAIL_HOURLY_CAP_PER_GYM", 100)
        gym_key = f"email_rate_cap:gym:{gym_id}:{current_hour_str}"
        try:
            current_gym = cache.get(gym_key, 0)
            if current_gym >= gym_cap:
                logger.warning(
                    "Gym %s email rate cap exceeded (%d >= %d).",
                    gym_id,
                    current_gym,
                    gym_cap,
                )
                raise ValidationError("email limit reached")
        except ValidationError:
            raise
        except Exception as e:
            logger.warning("Cache access error checking gym email cap: %s", e)

    return True


def record_email_rate_cap_dispatch(gym: Optional[Any] = None, count: int = 1) -> None:
    """Increment hourly email dispatch counters in cache."""
    from django.core.cache import cache
    from django.utils import timezone

    current_hour_str = timezone.now().strftime("%Y%m%d%H")
    platform_key = f"email_rate_cap:platform:{current_hour_str}"
    try:
        cache.set(platform_key, cache.get(platform_key, 0) + count, timeout=3700)
    except Exception:
        pass

    gym_id = None
    if gym:
        gym_id = gym.id if hasattr(gym, "id") else str(gym)
    if gym_id:
        gym_key = f"email_rate_cap:gym:{gym_id}:{current_hour_str}"
        try:
            cache.set(gym_key, cache.get(gym_key, 0) + count, timeout=3700)
        except Exception:
            pass


def send_fitgate_email(
    subject: str,
    message: str,
    recipient_list: List[str],
    gym: Optional[Any] = None,
    fail_silently: bool = False,
    **kwargs,
) -> int:
    """
    Central helper for routing all FitGate transactional emails with safety gates:
    1. Local dev uses console/mocked backend; fake addresses keep working.
    2. Suppression table check: addresses on the suppression list are never emailed again.
    3. Strict mode (staging/production with EMAIL_STRICT_MODE=True):
       - Skips reserved test domains (example.com, .test, .invalid, .localhost, .local) and logs warning.
       - Validates DNS domain existence (short timeout); definite NXDOMAIN skips and logs.
    4. Staging allow-list: restricts real sending to approved recipients/domains (EMAIL_ALLOWED_RECIPIENTS).
    5. Rate caps: hourly per-gym and platform-wide limits; beyond it mails are skipped with ValidationError("email limit reached").
    6. Tracks delivery status in EmailDeliveryStatus table.
    """
    from apps.accounts.models import EmailDeliveryStatus
    from apps.core.validators import (
        check_domain_dns_accepts_mail,
        is_reserved_test_domain,
    )
    from apps.tenants.models import GymTenant

    gym_obj = gym if isinstance(gym, GymTenant) else None
    strict_mode = getattr(settings, "EMAIL_STRICT_MODE", False)

    effective_recipients = []
    for raw_email in recipient_list:
        clean_email = str(raw_email).strip().lower()
        if not clean_email:
            continue

        # 1. Suppression check
        suppression = EmailDeliveryStatus.all_objects.filter(
            email=clean_email,
            status=EmailDeliveryStatus.STATUS_SUPPRESSED,
        ).first()
        if suppression:
            logger.warning(
                "Skipping email to %s: address is on suppression list (reason: %s).",
                clean_email,
                suppression.reason,
            )
            continue

        domain = clean_email.split("@")[-1].strip()

        # 2. Strict mode checks (staging / production)
        if strict_mode:
            if is_reserved_test_domain(domain):
                logger.warning(
                    "Skipping email to %s: domain '%s' is a reserved test domain in strict mode.",
                    clean_email,
                    domain,
                )
                EmailDeliveryStatus.all_objects.update_or_create(
                    email=clean_email,
                    defaults={
                        "status": EmailDeliveryStatus.STATUS_NOT_DELIVERED,
                        "reason": "reserved_domain",
                        "gym": gym_obj,
                    },
                )
                continue

            try:
                check_domain_dns_accepts_mail(domain)
            except Exception as e:
                logger.warning(
                    "Skipping email to %s: domain '%s' DNS lookup rejected: %s",
                    clean_email,
                    domain,
                    e,
                )
                EmailDeliveryStatus.all_objects.update_or_create(
                    email=clean_email,
                    defaults={
                        "status": EmailDeliveryStatus.STATUS_NOT_DELIVERED,
                        "reason": "dns_lookup_failed",
                        "gym": gym_obj,
                    },
                )
                continue

        # 3. Optional staging allow-list check
        if not is_recipient_allowed_by_staging_allowlist(clean_email):
            logger.info(
                "Skipping email to %s: not in staging EMAIL_ALLOWED_RECIPIENTS allow-list.",
                clean_email,
            )
            continue

        effective_recipients.append(clean_email)

    if not effective_recipients:
        return 0

    # 4. Rate caps check
    check_and_increment_email_rate_caps(gym=gym)

    from_email = build_from_email(gym)
    sent_count = send_mail(
        subject=subject,
        message=message,
        from_email=from_email,
        recipient_list=effective_recipients,
        fail_silently=fail_silently,
        **kwargs,
    )

    if sent_count > 0:
        record_email_rate_cap_dispatch(gym=gym, count=len(effective_recipients))
        for clean_email in effective_recipients:
            EmailDeliveryStatus.all_objects.update_or_create(
                email=clean_email,
                defaults={
                    "status": EmailDeliveryStatus.STATUS_SENT,
                    "reason": "",
                    "gym": gym_obj,
                },
            )

    return sent_count


def notify_account_locked(user) -> None:
    """
    Handle lockout notification:
    - Super Admin lockouts are logged only (no email).
    - Gym users: send an email to the gym's active Owner.
    """
    from apps.accounts.models import User

    if user.role == User.ROLE_SUPER_ADMIN or user.gym is None:
        logger.warning(
            "Security alert: Super Admin account locked due to consecutive failed logins: %s",
            user.email,
        )
        return

    # Find active Owner of the user's gym
    owner = User.all_objects.filter(
        gym=user.gym,
        role=User.ROLE_OWNER,
        is_active=True,
    ).first()

    if owner and owner.email:
        send_fitgate_email(
            subject=f"FitGate Alert: Account locked for {user.email}",
            message=(
                f"Hello,\n\n"
                f"The account for {user.email} in gym '{user.gym.name}' has been temporarily "
                f"locked following {user.failed_login_count} consecutive failed login attempts.\n"
                f"The lockout will expire at {user.locked_until}.\n"
            ),
            recipient_list=[owner.email],
            gym=user.gym,
            fail_silently=False,
        )
    else:
        logger.warning(
            "Account locked for %s in gym %s, but no active Owner found to notify.",
            user.email,
            user.gym.name,
        )


def send_password_reset_email(user, link: str) -> None:
    """
    Send password reset email to user.

    Plain text email containing:
    - the reset link
    - expiry duration (PASSWORD_RESET_TOKEN_MINUTES)
    - notice to ignore if not requested
    """
    minutes = getattr(settings, "PASSWORD_RESET_TOKEN_MINUTES", 60)
    subject = "FitGate: Reset your password"
    message = (
        f"Hello,\n\n"
        f"We received a request to reset the password for your FitGate account ({user.email}).\n\n"
        f"You can reset your password using the following link:\n"
        f"{link}\n\n"
        f"This link will expire in {minutes} minutes.\n\n"
        f"If you did not request a password reset, you can safely ignore this email.\n"
    )
    send_fitgate_email(
        subject=subject,
        message=message,
        recipient_list=[user.email],
        gym=user.gym,
        fail_silently=False,
    )


def send_owner_welcome_email(owner, gym, invite_link: str) -> None:
    """
    Send welcome email to newly created Gym Owner containing set-password link.

    Crucial: Must never contain any password.
    """
    subject = f"Welcome to FitGate — Set up your account for {gym.name}"
    message = (
        f"Hello {owner.full_name or 'there'},\n\n"
        f"Your gym '{gym.name}' has been created on the FitGate platform.\n\n"
        f"To get started, please set your password using the secure link below:\n"
        f"{invite_link}\n\n"
        f"This link is valid for 7 days. Once your password is set and your domain's security certificate is verified, you can log in to manage your gym.\n\n"
        f"Welcome aboard,\nThe FitGate Team\n"
    )
    send_fitgate_email(
        subject=subject,
        message=message,
        recipient_list=[owner.email],
        gym=gym,
        fail_silently=False,
    )


def send_staff_invite_email(user, gym, invite_link: str) -> None:
    """
    Send invitation email to newly invited staff member (Manager, Trainer, or Reception)
    containing single-use set-password link. Never contains a password.
    """
    from apps.accounts.models import User

    role_display = dict(User.ROLE_CHOICES).get(user.role, user.role.capitalize())
    subject = f"Invitation to join {gym.name} as {role_display}"
    message = (
        f"Hello {user.full_name or 'there'},\n\n"
        f"You have been invited to join '{gym.name}' on FitGate as a {role_display}.\n\n"
        f"To set up your account and choose your password, please use the secure link below:\n"
        f"{invite_link}\n\n"
        f"This link is valid for 7 days. Once your password is set, you can sign in to the staff portal.\n\n"
        f"Welcome aboard,\nThe FitGate Team\n"
    )
    send_fitgate_email(
        subject=subject,
        message=message,
        recipient_list=[user.email],
        gym=gym,
        fail_silently=False,
    )


def send_member_verification_email(user, gym, verify_link: str) -> None:
    """
    Send email verification link to newly self-registered gym member.
    """
    subject = f"Verify your email address for {gym.name}"
    message = (
        f"Hello {user.full_name or 'there'},\n\n"
        f"Thank you for registering at '{gym.name}'.\n\n"
        f"To complete your registration and activate your account, please verify your email "
        f"using the link below:\n"
        f"{verify_link}\n\n"
        f"This verification link is valid for 24 hours.\n\n"
        f"Best regards,\nThe {gym.name} Team\n"
    )
    send_fitgate_email(
        subject=subject,
        message=message,
        recipient_list=[user.email],
        gym=gym,
        fail_silently=False,
    )


def send_member_invite_email(user, gym, invite_link: str) -> None:
    """
    Send invitation email with set-password link to staff-registered member.
    """
    subject = f"Welcome to {gym.name} — Set up your member account"
    message = (
        f"Hello {user.full_name or 'there'},\n\n"
        f"You have been registered as a member at '{gym.name}'.\n\n"
        f"To activate your account and choose your password, please use the secure link below:\n"
        f"{invite_link}\n\n"
        f"This link is valid for 7 days. Once your password is set, you can log in to view your profile, "
        f"subscription, and check-in QR codes.\n\n"
        f"Welcome aboard,\nThe {gym.name} Team\n"
    )
    send_fitgate_email(
        subject=subject,
        message=message,
        recipient_list=[user.email],
        gym=gym,
        fail_silently=False,
    )


def create_notification(
    recipient,
    notification_type: str,
    message: str,
    gym=None,
):
    """
    ONE shared helper function that creates an in-app notification record.
    Stored only, no email, tenant-scoped to the gym (or platform-level if gym is None).
    """
    from apps.accounts.models import Notification

    if gym is None and getattr(recipient, "gym", None):
        gym = recipient.gym

    return Notification.objects.create(
        recipient=recipient,
        type=notification_type,
        message=message,
        gym=gym,
    )


def notify_demo_request_received(demo_request) -> None:
    """
    Create a platform-level notification for all active Super Admins upon receiving a new demo request.
    """
    from apps.accounts.models import User

    super_admins = User.all_objects.filter(
        role=User.ROLE_SUPER_ADMIN,
        is_active=True,
    )
    for admin_user in super_admins:
        create_notification(
            recipient=admin_user,
            notification_type="demo_request",
            message=(
                f"New demo request from '{demo_request.gym_name}' "
                f"(Contact: {demo_request.contact_name}, Phone: {demo_request.phone})"
            ),
            gym=None,
        )

    logger.info(
        "Platform notification created for demo request from gym '%s' (%s)",
        demo_request.gym_name,
        demo_request.phone,
    )
