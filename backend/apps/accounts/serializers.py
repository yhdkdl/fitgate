from typing import Optional

from rest_framework import serializers

from apps.accounts.models import AuditLog, Notification, User
from apps.core.validators import (
    validate_and_normalize_phone,
    validate_email_address,
    validate_name,
)

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
    phone = serializers.CharField(max_length=50, required=False, allow_blank=True)

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
        if value:
            return validate_name(value, "Full name")
        return ""

    def validate_phone(self, value):
        if value:
            return validate_and_normalize_phone(value)
        return ""


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

    def validate_email(self, value):
        return validate_email_address(value)


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


class PasswordResetRequestSerializer(serializers.Serializer):
    """Payload for requesting a password reset email."""

    email = serializers.EmailField(required=True)

    def validate_email(self, value):
        return validate_email_address(value)


class PasswordResetResponseSerializer(serializers.Serializer):
    """Uniform response for password reset requests."""

    detail = serializers.CharField()


class PasswordResetConfirmRequestSerializer(serializers.Serializer):
    """Payload for confirming a password reset."""

    token = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, write_only=True)


class PasswordResetConfirmResponseSerializer(serializers.Serializer):
    """Response returned upon successful password reset completion."""

    detail = serializers.CharField()


class SetPasswordFromInviteRequestSerializer(serializers.Serializer):
    """Payload for setting initial password from an invite token."""

    token = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, write_only=True)


class SetPasswordFromInviteResponseSerializer(serializers.Serializer):
    """Response returned upon successful invite password completion."""

    detail = serializers.CharField()


class StaffMemberSerializer(serializers.ModelSerializer):
    """Serializer representing a staff member in the gym tenant."""

    invitation_status = serializers.SerializerMethodField()
    email_delivery_message = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "role",
            "gym_id",
            "full_name",
            "phone",
            "is_active",
            "email_verified_at",
            "created_at",
            "invitation_status",
            "email_delivery_message",
        ]
        read_only_fields = fields

    def get_invitation_status(self, obj) -> str:
        if obj.has_usable_password():
            return "activated"

        request = self.context.get("request")
        user = getattr(request, "user", None) if request else None

        # Tenancy check: Item 12 - "Email not delivered" is visible only to staff of the same gym (Super Admin for owners)
        is_same_gym_staff = bool(
            user
            and user.is_authenticated
            and (
                (
                    user.role == User.ROLE_SUPER_ADMIN
                    and (obj.gym_id is None or obj.role == User.ROLE_OWNER)
                )
                or (
                    user.gym_id
                    and obj.gym_id
                    and user.gym_id == obj.gym_id
                    and user.role
                    in (User.ROLE_OWNER, User.ROLE_MANAGER, User.ROLE_RECEPTION)
                )
            )
        )
        if not is_same_gym_staff:
            return "sent"

        from apps.accounts.models import EmailDeliveryStatus

        record = EmailDeliveryStatus.all_objects.filter(
            email=obj.email.strip().lower(),
            gym_id=obj.gym_id,
        ).first()
        if not record and (obj.gym_id is None or obj.role == User.ROLE_OWNER):
            record = EmailDeliveryStatus.all_objects.filter(
                email=obj.email.strip().lower(),
                gym__isnull=True,
            ).first()

        if record and record.status in (
            EmailDeliveryStatus.STATUS_NOT_DELIVERED,
            EmailDeliveryStatus.STATUS_SUPPRESSED,
        ):
            return "not_delivered"

        return "sent"

    def get_email_delivery_message(self, obj) -> Optional[str]:
        if self.get_invitation_status(obj) == "not_delivered":
            return "Fix the address and resend"
        return None


class InviteStaffRequestSerializer(serializers.Serializer):
    """Payload for inviting a staff member (Manager, Trainer, or Reception)."""

    email = serializers.EmailField(required=True)
    role = serializers.ChoiceField(
        choices=[
            (User.ROLE_MANAGER, "Manager"),
            (User.ROLE_TRAINER, "Trainer"),
            (User.ROLE_RECEPTION, "Reception"),
        ],
        required=True,
    )
    full_name = serializers.CharField(
        max_length=150, required=False, allow_blank=True, default=""
    )
    phone = serializers.CharField(
        max_length=50, required=False, allow_blank=True, default=""
    )

    def validate_email(self, value):
        return validate_email_address(value)

    def validate_full_name(self, value):
        if value:
            return validate_name(value, "Full name")
        return ""

    def validate_phone(self, value):
        if value:
            return validate_and_normalize_phone(value)
        return ""


class InviteStaffResponseSerializer(serializers.Serializer):
    """Response returned upon successful staff invitation."""

    detail = serializers.CharField()
    user = StaffMemberSerializer()


class StaffActionResponseSerializer(serializers.Serializer):
    """Response returned upon staff deactivation or reactivation."""

    detail = serializers.CharField()
    user = StaffMemberSerializer()


class AuditLogActorSerializer(serializers.ModelSerializer):
    """Summary of the actor associated with an audit log entry."""

    class Meta:
        model = User
        fields = ["id", "email", "full_name", "role"]
        read_only_fields = fields


class AuditLogSerializer(serializers.ModelSerializer):
    """Read-only representation of an AuditLog entry."""

    actor = AuditLogActorSerializer(read_only=True)
    gym_id = serializers.UUIDField(allow_null=True, source="gym.id", read_only=True)
    gym_name = serializers.CharField(
        source="gym.name", read_only=True, allow_null=True, default=None
    )

    class Meta:
        model = AuditLog
        fields = [
            "id",
            "gym_id",
            "gym_name",
            "actor",
            "action_type",
            "affected_record_type",
            "affected_record_id",
            "timestamp",
            "metadata",
        ]
        read_only_fields = fields


class NotificationSerializer(serializers.ModelSerializer):
    """Read-only representation of an in-app user notification."""

    class Meta:
        model = Notification
        fields = [
            "id",
            "type",
            "message",
            "is_read",
            "created_at",
        ]
        read_only_fields = fields
