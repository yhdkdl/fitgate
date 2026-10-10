"""Serializers for authentication and user endpoints."""

from rest_framework import serializers

from apps.accounts.models import User


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
            "must_change_password",
        ]
        read_only_fields = fields


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
