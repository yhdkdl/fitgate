"""Serializers for authentication and user endpoints."""

import re

from rest_framework import serializers

from apps.accounts.models import User

PRIVILEGED_FIELDS = (
    "role",
    "gym",
    "gym_id",
    "is_active",
    "status",
    "max_clients",
    "email",
    "must_change_password",
    "password_changed_at",
    "failed_login_count",
    "locked_until",
    "is_staff",
    "is_superuser",
)


class UserSummarySerializer(serializers.ModelSerializer):
    """Minimal representation of authenticated user."""

    gym_id = serializers.UUIDField(allow_null=True, source="gym.id", read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "role",
            "gym_id",
            "full_name",
            "phone",
            "must_change_password",
        ]
        read_only_fields = fields


class UserProfileSerializer(serializers.ModelSerializer):
    """Profile representation of authenticated user."""

    gym_id = serializers.UUIDField(allow_null=True, source="gym.id", read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "role",
            "gym_id",
            "full_name",
            "phone",
            "must_change_password",
        ]
        read_only_fields = fields


class UserProfileUpdateSerializer(serializers.ModelSerializer):
    """Payload for updating user profile (full_name and phone only)."""

    full_name = serializers.CharField(
        max_length=150, required=False, allow_blank=True, trim_whitespace=False
    )
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True)

    class Meta:
        model = User
        fields = ["full_name", "phone"]

    def to_internal_value(self, data):
        for field in PRIVILEGED_FIELDS:
            if field in data:
                raise serializers.ValidationError(
                    {field: [f"Field '{field}' is privileged and cannot be modified."]}
                )
        return super().to_internal_value(data)

    def validate_full_name(self, value):
        if value is not None and value != "" and not value.strip():
            raise serializers.ValidationError("Full name cannot be whitespace-only.")
        return value.strip() if value else ""

    def validate_phone(self, value):
        if not value:
            return ""
        if len(value) < 7 or len(value) > 20:
            raise serializers.ValidationError(
                "Phone number must be between 7 and 20 characters."
            )
        check_val = value[1:] if value.startswith("+") else value
        if not re.match(r"^[0-9 -]+$", check_val):
            raise serializers.ValidationError(
                "Phone number can only contain digits, spaces, hyphens, and an optional leading '+'."
            )
        if not any(c.isdigit() for c in check_val):
            raise serializers.ValidationError(
                "Phone number must contain at least one digit."
            )
        return value


class ChangePasswordRequestSerializer(serializers.Serializer):
    """Payload for changing user password."""

    current_password = serializers.CharField(required=True, write_only=True)
    new_password = serializers.CharField(required=True, write_only=True)


class ChangePasswordResponseSerializer(serializers.Serializer):
    """Response containing refreshed JWT pair and user summary."""

    access = serializers.CharField()
    refresh = serializers.CharField()
    user = UserSummarySerializer()


class LoginRequestSerializer(serializers.Serializer):
    """Payload for user authentication."""

    email = serializers.EmailField(required=True)
    password = serializers.CharField(required=True, write_only=True)


class LoginResponseSerializer(serializers.Serializer):
    """Response containing JWT tokens, user summary, and role dashboard."""

    access = serializers.CharField()
    refresh = serializers.CharField()
    user = UserSummarySerializer()
    dashboard = serializers.DictField()


class TokenRefreshRequestSerializer(serializers.Serializer):
    """Payload for token refresh."""

    refresh = serializers.CharField(required=True)


class TokenRefreshResponseSerializer(serializers.Serializer):
    """Response containing refreshed access token."""

    access = serializers.CharField()


class LogoutRequestSerializer(serializers.Serializer):
    """Payload for user logout."""

    refresh = serializers.CharField(required=True)


class CreateSuperAdminRequestSerializer(serializers.Serializer):
    """Payload for creating an additional Super Admin account."""

    email = serializers.EmailField(required=True)
    password = serializers.CharField(required=True, write_only=True)
    current_password = serializers.CharField(required=True, write_only=True)


class SuperAdminResponseSerializer(serializers.ModelSerializer):
    """Response for created Super Admin."""

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "role",
            "must_change_password",
            "created_at",
        ]
        read_only_fields = fields
