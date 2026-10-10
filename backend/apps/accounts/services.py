"""Business logic and service functions for accounts app."""

from typing import Any, Dict

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from rest_framework.exceptions import PermissionDenied

from apps.accounts.models import User
from apps.accounts.serializers import UserSummarySerializer
from apps.accounts.tokens import get_tokens_for_user


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
