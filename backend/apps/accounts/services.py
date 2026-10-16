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
from apps.accounts.notifications import (
    send_password_reset_email,
    send_staff_invite_email,
)
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

    with transaction.atomic():
        user.set_password(new_password)
        user.must_change_password = False
        user.save(
            update_fields=["password", "password_changed_at", "must_change_password"]
        )
        record_audit_log(
            action_type="password_changed",
            affected_record_type="User",
            affected_record_id=str(user.id),
            actor=user,
            gym=getattr(user, "gym", None),
            metadata={"email": user.email},
        )

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
        with transaction.atomic():
            new_super_admin = User.objects.create_superuser(
                email=normalized_email,
                password=password,
                must_change_password=True,
            )
            record_audit_log(
                action_type="super_admin_created",
                affected_record_type="User",
                affected_record_id=str(new_super_admin.id),
                actor=actor,
                gym=None,
                metadata={"created_email": normalized_email},
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
    scheme = settings.PUBLIC_URL_SCHEME
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


def set_password_from_invite(
    raw_token: str, new_password: str, tenant: Optional[GymTenant]
) -> Dict[str, str]:
    """
    Set initial password for an invited user (e.g. newly created Gym Owner) using AuthToken.PURPOSE_INVITE.

    Order of checks:
    (1) Find AuthToken by sha256(raw_token) and purpose 'invite'.
    (2) Validate user is active, matches host context (gym tenant).
    (3) Verify token has not expired and has not been used.
    (4) Validate password strength with Django AUTH_PASSWORD_VALIDATORS.
    (5) In transaction.atomic: consume token (used_at=now), set password,
        clear must_change_password, email_verified_at=now, failed_login_count=0.
    """
    if not raw_token or not isinstance(raw_token, str):
        raise ValidationError({"detail": "token_invalid"})

    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    auth_token = (
        AuthToken.objects.select_related("user", "user__gym")
        .filter(token_hash=token_hash, purpose=AuthToken.PURPOSE_INVITE)
        .first()
    )

    if auth_token is None:
        raise ValidationError({"detail": "token_invalid"})

    user = auth_token.user
    if not user.is_active:
        raise ValidationError({"detail": "token_invalid"})

    # Host context check: Gym users must match tenant subdomain; Super Admin at apex
    if tenant is None:
        if user.gym_id is not None or user.role != User.ROLE_SUPER_ADMIN:
            raise ValidationError({"detail": "token_invalid"})
    else:
        if user.gym_id is None or str(user.gym_id) != str(tenant.id):
            raise ValidationError({"detail": "token_invalid"})

    if auth_token.used_at is not None:
        raise ValidationError({"detail": "token_invalid"})

    now = timezone.now()
    if auth_token.expires_at <= now:
        raise ValidationError({"detail": "token_expired"})

    if not new_password or not isinstance(new_password, str):
        raise ValidationError({"new_password": ["This field may not be blank."]})

    try:
        validate_password(new_password, user=user)
    except ValidationError as exc:
        raise ValidationError({"new_password": list(exc.messages)})

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
        if not user.email_verified_at:
            user.email_verified_at = now_consume
        user.save(
            update_fields=[
                "password",
                "password_changed_at",
                "must_change_password",
                "failed_login_count",
                "locked_until",
                "email_verified_at",
            ]
        )

        # Mark all other unused invite tokens for this user as used
        AuthToken.objects.filter(
            user=user,
            purpose=AuthToken.PURPOSE_INVITE,
            used_at__isnull=True,
        ).exclude(pk=auth_token.pk).update(used_at=now_consume)

    return {"detail": "password_set_complete"}


def invite_staff_member(
    acting_user: User, gym: GymTenant, data: Dict[str, Any]
) -> tuple[User, AuthToken, str]:
    """
    Invite a staff member (Manager, Trainer, Reception) to the gym tenant.

    Permissions:
    - Owner can invite Managers, Trainers, Reception.
    - Manager can invite Trainers and Reception only.
    - Manager inviting a Manager raises 403 PermissionDenied.
    - Other roles raise 403 PermissionDenied.

    Behavior:
    - Verifies acting_user.gym_id == gym.id.
    - Verifies email is globally unique across all gyms (case-insensitive).
    - Creates User with unusable password, email_verified_at=now, is_active=True.
    - Creates AuthToken with purpose=invite, expires_at=now + 7 days.
    - Sends invitation email with set-password link via transaction.on_commit.
    """
    if getattr(acting_user, "gym_id", None) != gym.id:
        raise PermissionDenied(
            "You do not have permission to invite staff for another gym."
        )

    acting_role = getattr(acting_user, "role", None)
    if acting_role not in (User.ROLE_OWNER, User.ROLE_MANAGER):
        raise PermissionDenied("Only Gym Owner or Manager can invite staff members.")

    target_role = data.get("role")
    valid_roles = (User.ROLE_MANAGER, User.ROLE_TRAINER, User.ROLE_RECEPTION)
    if target_role not in valid_roles:
        raise ValidationError({"role": [f"Invalid staff role '{target_role}'."]})

    if acting_role == User.ROLE_MANAGER and target_role == User.ROLE_MANAGER:
        raise PermissionDenied("Managers cannot invite or manage Manager accounts.")

    raw_email = data.get("email", "")
    if not raw_email or not isinstance(raw_email, str):
        raise ValidationError({"email": ["This field may not be blank."]})

    normalized_email = raw_email.strip().lower()
    if User.all_objects.filter(email=normalized_email).exists():
        raise ValidationError({"email": ["A user with this email already exists."]})

    full_name = str(data.get("full_name") or "").strip()
    phone = str(data.get("phone") or "").strip()

    with transaction.atomic():
        user = User.objects.create(
            email=normalized_email,
            role=target_role,
            gym=gym,
            full_name=full_name,
            phone=phone,
            is_active=True,
            email_verified_at=timezone.now(),
            must_change_password=False,
        )
        user.set_unusable_password()
        user.save()

        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        expires_at = timezone.now() + timedelta(days=7)
        token_obj = AuthToken.objects.create(
            user=user,
            token_hash=token_hash,
            purpose=AuthToken.PURPOSE_INVITE,
            expires_at=expires_at,
        )

        scheme = settings.PUBLIC_URL_SCHEME
        domain = settings.DOMAIN
        invite_link = (
            f"{scheme}://{gym.subdomain}.{domain}/set-password?token={raw_token}"
        )

        record_audit_log(
            action_type="staff_provisioned",
            affected_record_type="User",
            affected_record_id=str(user.id),
            actor=acting_user,
            gym=gym,
            metadata={
                "email": normalized_email,
                "role": target_role,
                "full_name": full_name,
            },
        )

        def _send():
            try:
                send_staff_invite_email(user, gym, invite_link)
            except Exception:
                logger.exception(
                    "Failed to send staff invitation email to %s", user.email
                )

        transaction.on_commit(_send)

    return user, token_obj, raw_token


def deactivate_staff_member(acting_user: User, target_user: User) -> User:
    """
    Deactivate a staff member.
    Immediately blocks login and invalidates existing JWT tokens.
    Never hard-deletes; email remains reserved.
    """
    if acting_user.id == target_user.id:
        raise PermissionDenied("You cannot deactivate your own account.")

    if getattr(acting_user, "gym_id", None) != target_user.gym_id:
        raise PermissionDenied(
            "You do not have permission to manage staff for another gym."
        )

    acting_role = getattr(acting_user, "role", None)
    target_role = getattr(target_user, "role", None)

    if acting_role == User.ROLE_OWNER:
        if target_role not in (
            User.ROLE_MANAGER,
            User.ROLE_TRAINER,
            User.ROLE_RECEPTION,
        ):
            raise PermissionDenied("Cannot deactivate this account.")
    elif acting_role == User.ROLE_MANAGER:
        if target_role not in (User.ROLE_TRAINER, User.ROLE_RECEPTION):
            raise PermissionDenied(
                "Managers cannot deactivate Manager or Owner accounts."
            )
    else:
        raise PermissionDenied("Only Gym Owner or Manager can deactivate staff.")

    with transaction.atomic():
        target_user.is_active = False
        target_user.password_changed_at = timezone.now()
        target_user.save(update_fields=["is_active", "password_changed_at"])
        record_audit_log(
            action_type="staff_deactivated",
            affected_record_type="User",
            affected_record_id=str(target_user.id),
            actor=acting_user,
            gym=acting_user.gym,
            metadata={
                "email": target_user.email,
                "role": target_user.role,
            },
        )
    return target_user


def reactivate_staff_member(acting_user: User, target_user: User) -> User:
    """
    Reactivate a previously deactivated staff member.
    """
    if getattr(acting_user, "gym_id", None) != target_user.gym_id:
        raise PermissionDenied(
            "You do not have permission to manage staff for another gym."
        )

    acting_role = getattr(acting_user, "role", None)
    target_role = getattr(target_user, "role", None)

    if acting_role == User.ROLE_OWNER:
        if target_role not in (
            User.ROLE_MANAGER,
            User.ROLE_TRAINER,
            User.ROLE_RECEPTION,
        ):
            raise PermissionDenied("Cannot reactivate this account.")
    elif acting_role == User.ROLE_MANAGER:
        if target_role not in (User.ROLE_TRAINER, User.ROLE_RECEPTION):
            raise PermissionDenied(
                "Managers cannot reactivate Manager or Owner accounts."
            )
    else:
        raise PermissionDenied("Only Gym Owner or Manager can reactivate staff.")

    with transaction.atomic():
        target_user.is_active = True
        target_user.save(update_fields=["is_active"])
        record_audit_log(
            action_type="staff_reactivated",
            affected_record_type="User",
            affected_record_id=str(target_user.id),
            actor=acting_user,
            gym=acting_user.gym,
            metadata={
                "email": target_user.email,
                "role": target_user.role,
            },
        )
    return target_user


def record_audit_log(
    action_type: str,
    affected_record_type: str,
    affected_record_id: str,
    actor: Optional[User] = None,
    gym: Optional[GymTenant] = None,
    metadata: Optional[dict] = None,
):
    """
    Record an append-only audit trail event.
    Scopes to gym if provided (or derived from actor/record); platform-level if gym is None.
    Strips any sensitive keys (passwords, tokens, secrets) before saving.
    """
    from apps.accounts.models import AuditLog

    if (
        actor is not None
        and getattr(actor, "role", None) == User.ROLE_SUPER_ADMIN
        and gym is None
    ):
        gym = None
    elif gym is None and actor is not None and getattr(actor, "gym", None) is not None:
        gym = actor.gym

    safe_metadata = {}
    if metadata:
        FORBIDDEN_KEY_FRAGMENTS = (
            "password",
            "token",
            "secret",
            "key",
            "authorization",
            "credential",
        )
        for k, v in metadata.items():
            k_lower = str(k).lower()
            if any(frag in k_lower for frag in FORBIDDEN_KEY_FRAGMENTS):
                continue
            safe_metadata[k] = v

    return AuditLog.all_objects.create(
        actor=actor,
        gym=gym,
        action_type=action_type,
        affected_record_type=affected_record_type,
        affected_record_id=str(affected_record_id),
        metadata=safe_metadata,
    )
