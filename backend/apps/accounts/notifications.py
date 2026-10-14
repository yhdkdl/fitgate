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
            from_email=settings.DEFAULT_FROM_EMAIL,
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
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
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
    send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[owner.email],
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
    send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )


def notify_demo_request_received(demo_request) -> None:
    """
    Create a platform-level notification for all active Super Admins upon receiving a new demo request.

    Also logs the new request for platform visibility.
    """
    from apps.accounts.models import Notification, User

    super_admins = User.all_objects.filter(
        role=User.ROLE_SUPER_ADMIN,
        is_active=True,
    )
    for admin_user in super_admins:
        Notification.objects.create(
            recipient=admin_user,
            gym=None,
            type="demo_request",
            message=(
                f"New demo request from '{demo_request.gym_name}' "
                f"(Contact: {demo_request.contact_name}, Phone: {demo_request.phone})"
            ),
        )

    logger.info(
        "Platform notification created for demo request from gym '%s' (%s)",
        demo_request.gym_name,
        demo_request.phone,
    )
