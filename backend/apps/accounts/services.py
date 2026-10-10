import hashlib
import logging
import secrets
from datetime import timedelta
from typing import Any, Dict, Optional

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from apps.accounts.models import AuthToken, User
from apps.accounts.notifications import send_password_reset_email
from apps.accounts.serializers import UserSummarySerializer
from apps.accounts.tokens import get_tokens_for_user
from apps.tenants.models import GymTenant

logger = logging.getLogger(__name__)


def change_password(
    user: User, current_password: str, new_password: str
) -> Dict[str, Any]:
    """
    Change user's password, clear must_change_password, and issue fresh JWT pair.

    Validation rules:
    - current_password must be correct.
    - new_password cannot be identical to current_password.
    - new_password must satisfy Django AUTH_PASSWORD_VALIDATORS.
    """
    if not current_password or not user.check_password(current_password):
        raise ValidationError({"current_password": ["Current password is incorrect."]})

    if current_password == new_password:
        raise ValidationError(
            {
                "new_password": [
                    "New password cannot be the same as the current password."
                ]
            }
        )

    try:
        validate_password(new_password, user=user)
    except ValidationError as exc:
        raise ValidationError({"new_password": list(exc.messages)})

    user.set_password(new_password)
    user.must_change_password = False
    user.save(update_fields=["password", "password_changed_at", "must_change_password"])

    tokens = get_tokens_for_user(user)
    return {
        "access": tokens["access"],
        "refresh": tokens["refresh"],
        "user": UserSummarySerializer(user).data,
    }


def create_additional_super_admin(
    actor: User, email: str, password: str, current_password: str
) -> User:
    """
    Create a new Super Admin account.

    Preconditions:
    - actor must be an active Super Admin.
    - actor's current password must be verified.
    - password must satisfy Django password validators.
    - New super admin must have must_change_password = True.
    - Sprint 9 will wire audit logging into this service function.
    """
    if not actor or not actor.is_authenticated or actor.role != User.ROLE_SUPER_ADMIN:
        raise PermissionDenied(
            "Only active Super Admins can create additional Super Admins."
        )

    if not current_password or not actor.check_password(current_password):
        raise ValidationError({"current_password": ["Invalid current password."]})

    if not email:
        raise ValidationError({"email": ["Email is required."]})

    if not password:
        raise ValidationError({"password": ["Password is required."]})

    try:
        validate_password(password, user=None)
    except ValidationError as exc:
        raise ValidationError({"password": list(exc.messages)})

    normalized_email = email.strip().lower()

    if User.all_objects.filter(email__iexact=normalized_email).exists():
        raise ValidationError({"email": ["A user with this email already exists."]})

    try:
        new_super_admin = User.objects.create_superuser(
            email=normalized_email,
            password=password,
            must_change_password=True,
        )
    except IntegrityError:
        raise ValidationError({"email": ["A user with this email already exists."]})

    return new_super_admin


def request_password_reset(
    email: Optional[str], tenant: Optional[GymTenant]
) -> Optional[str]:
    """
    Request password reset for email on the current tenant host.

    Enforces:
    - Safe handling of malformed input (never raises).
    - Host-scoping: apex sees only platform Super Admin (gym is null); gym host sees only its users.
    - Only active users on this host receive a reset token and email.
    - Respects PASSWORD_RESET_COOLDOWN_SECONDS: if an unused/recent reset token was created
      within the cooldown, does nothing silently.
    - Invalidates older unused reset tokens for the user before creating a new one.
    - Never stores raw token in DB: stores sha256 hex digest.
    - Token expires in PASSWORD_RESET_TOKEN_MINUTES.
    - Link is built from user's gym subdomain + settings.DOMAIN (apex = settings.DOMAIN),
      never from request headers. Scheme from settings.PUBLIC_URL_SCHEME.
    - Email sent via notifications.send_password_reset_email(user, link).
    - Email exceptions are caught and logged without sensitive tokens/links.
    - Returns the raw token for convenience (or None).
    """
    if not email or not isinstance(email, str):
        return None

    normalized_email = email.strip().lower()

    if tenant is None:
        user = User.all_objects.filter(
            email=normalized_email, gym__isnull=True, role=User.ROLE_SUPER_ADMIN
        ).first()
    else:
        user = User.all_objects.filter(email=normalized_email, gym=tenant).first()

    if user is None or not user.is_active:
        return None

    # Check cooldown
    cooldown_seconds = getattr(settings, "PASSWORD_RESET_COOLDOWN_SECONDS", 120)
    cooldown_cutoff = timezone.now() - timedelta(seconds=cooldown_seconds)
    recent_token_exists = AuthToken.objects.filter(
        user=user,
        purpose=AuthToken.PURPOSE_PASSWORD_RESET,
        created_at__gte=cooldown_cutoff,
    ).exists()

    if recent_token_exists:
        return None

    now = timezone.now()

    # Invalidate older unused reset tokens for this user
    AuthToken.objects.filter(
        user=user,
        purpose=AuthToken.PURPOSE_PASSWORD_RESET,
        used_at__isnull=True,
    ).update(used_at=now)

    # Generate new raw token and store its sha256 hex digest
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    expiry_minutes = getattr(settings, "PASSWORD_RESET_TOKEN_MINUTES", 60)
    expires_at = now + timedelta(minutes=expiry_minutes)

    AuthToken.objects.create(
        user=user,
        purpose=AuthToken.PURPOSE_PASSWORD_RESET,
        token_hash=token_hash,
        expires_at=expires_at,
    )

    # Construct reset link
    scheme = getattr(settings, "PUBLIC_URL_SCHEME", "https")
    if user.gym:
        host = f"{user.gym.subdomain}.{settings.DOMAIN}"
    else:
        host = settings.DOMAIN

    link = f"{scheme}://{host}/reset-password?token={raw_token}"

    try:
        send_password_reset_email(user, link)
    except Exception:
        logger.exception("Failed to send password reset email to user %s", user.id)

    return raw_token


def confirm_password_reset(
    raw_token: str, new_password: str, tenant: Optional[GymTenant]
) -> Dict[str, str]:
    """
    Confirm password reset with raw_token and new_password.

    Order of checks:
    (1) Find AuthToken by sha256(token) and purpose password_reset.
        User must be active and visible on this host, otherwise token_invalid.
    (2) Expired -> token_expired; used or unknown or wrong host -> token_invalid.
    (3) validate_password(new_password, user) BEFORE consuming token,
        so a weak password returns 400 and the link stays usable.
    (4) In transaction.atomic: consume token with ONE conditional update
        (filter pk, used_at is null, expires_at > now -> update(used_at=now)).
        If 0 rows updated, treat as token_invalid (single-use under double submit).
        Then user.set_password(new_password), must_change_password=False,
        failed_login_count=0, locked_until=None, save;
        mark all other unused reset tokens of that user as used.
        Do NOT issue tokens.
        Return {"detail": "password_reset_complete"}.
    """
    # (1) Find AuthToken by sha256(token) and purpose password_reset
    if not raw_token or not isinstance(raw_token, str):
        raise ValidationError({"detail": "token_invalid"})

    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    auth_token = (
        AuthToken.objects.select_related("user", "user__gym")
        .filter(token_hash=token_hash, purpose=AuthToken.PURPOSE_PASSWORD_RESET)
        .first()
    )

    if auth_token is None:
        raise ValidationError({"detail": "token_invalid"})

    user = auth_token.user
    if not user.is_active:
        raise ValidationError({"detail": "token_invalid"})

    # Host visibility check
    if tenant is None:
        if user.gym_id is not None or user.role != User.ROLE_SUPER_ADMIN:
            raise ValidationError({"detail": "token_invalid"})
    else:
        if user.gym_id is None or str(user.gym_id) != str(tenant.id):
            raise ValidationError({"detail": "token_invalid"})

    # (2) Expired vs used checks
    if auth_token.used_at is not None:
        raise ValidationError({"detail": "token_invalid"})

    now = timezone.now()
    if auth_token.expires_at <= now:
        raise ValidationError({"detail": "token_expired"})

    # (3) Validate password BEFORE consuming token
    if not new_password or not isinstance(new_password, str):
        raise ValidationError({"new_password": ["This field may not be blank."]})

    try:
        validate_password(new_password, user=user)
    except ValidationError as exc:
        raise ValidationError({"new_password": list(exc.messages)})

    # (4) In transaction.atomic: consume token with ONE conditional update
    with transaction.atomic():
        now_consume = timezone.now()
        rows_updated = AuthToken.objects.filter(
            pk=auth_token.pk,
            used_at__isnull=True,
            expires_at__gt=now_consume,
        ).update(used_at=now_consume)

        if rows_updated == 0:
            raise ValidationError({"detail": "token_invalid"})

        user.set_password(new_password)
        user.must_change_password = False
        user.failed_login_count = 0
        user.locked_until = None
        user.save(
            update_fields=[
                "password",
                "password_changed_at",
                "must_change_password",
                "failed_login_count",
                "locked_until",
            ]
        )

        # Mark all other unused reset tokens of that user as used
        AuthToken.objects.filter(
            user=user,
            purpose=AuthToken.PURPOSE_PASSWORD_RESET,
            used_at__isnull=True,
        ).exclude(pk=auth_token.pk).update(used_at=now_consume)

    return {"detail": "password_reset_complete"}
