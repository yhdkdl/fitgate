"""Notification helper functions for accounts."""

import logging

from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


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
        send_mail(
            subject=f"FitGate Alert: Account locked for {user.email}",
            message=(
                f"Hello,\n\n"
                f"The account for {user.email} in gym '{user.gym.name}' has been temporarily "
                f"locked following {user.failed_login_count} consecutive failed login attempts.\n"
                f"The lockout will expire at {user.locked_until}.\n"
            ),
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@fitgate.org"),
            recipient_list=[owner.email],
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
    send_mail(
        subject=subject,
        message=message,
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@fitgate.org"),
        recipient_list=[user.email],
        fail_silently=False,
    )
