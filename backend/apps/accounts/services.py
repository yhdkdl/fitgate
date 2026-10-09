"""Business logic and service functions for accounts app."""

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from rest_framework.exceptions import PermissionDenied

from apps.accounts.models import User


def create_additional_super_admin(
    actor: User, email: str, password: str, current_password: str
) -> User:
    """
    Create a new Super Admin account.

    Preconditions:
    - actor must be an active Super Admin.
    - actor's current password must be verified.
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
