"""Serializers for gym tenant management and Super Admin provisioning."""

from rest_framework import serializers

from apps.accounts.serializers import UserSummarySerializer
from apps.tenants.models import GymConfig, GymTenant


class GymTenantSummarySerializer(serializers.ModelSerializer):
    """Summary of a gym tenant."""

    class Meta:
        model = GymTenant
        fields = [
            "id",
            "name",
            "subdomain",
            "status",
            "tier",
            "currency",
            "location",
            "contact_name",
            "contact_phone",
            "contact_email",
            "subscription_expires_at",
            "tls_confirmed_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class GymConfigSerializer(serializers.ModelSerializer):
    """Feature gating and configuration settings of a gym."""

    class Meta:
        model = GymConfig
        fields = [
            "has_trainer_module",
            "has_ai_plans",
            "has_analytics",
            "has_group_classes",
            "has_multi_branch",
            "freeze_days_allowed",
            "payment_grace_days",
            "subscription_reminder_days",
            "member_reminder_days",
        ]
        read_only_fields = fields


class CreateGymRequestSerializer(serializers.Serializer):
    """Payload for Super Admin gym creation."""

    name = serializers.CharField(max_length=150, required=True)
    subdomain = serializers.CharField(max_length=63, required=True)
    tier = serializers.ChoiceField(choices=GymTenant.TIER_CHOICES, required=True)
    location = serializers.CharField(
        max_length=255, required=False, allow_blank=True, default=""
    )
    contact_name = serializers.CharField(
        max_length=150, required=False, allow_blank=True, default=""
    )
    contact_phone = serializers.CharField(
        max_length=20, required=False, allow_blank=True, default=""
    )
    contact_email = serializers.EmailField(required=False, allow_blank=True, default="")
    owner_name = serializers.CharField(
        max_length=150, required=False, allow_blank=True, default=""
    )
    owner_email = serializers.EmailField(required=True)
    payment_amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=True
    )
    payment_reference = serializers.CharField(max_length=100, required=True)
    payment_method = serializers.CharField(
        max_length=30, required=False, default="bank_transfer"
    )
    demo_request_id = serializers.CharField(
        max_length=100, required=False, allow_null=True, allow_blank=True, default=None
    )


class CreateGymResponseSerializer(serializers.Serializer):
    """Response returned upon successful gym tenant creation."""

    gym = GymTenantSummarySerializer()
    config = GymConfigSerializer()
    owner = UserSummarySerializer()
    payment_id = serializers.UUIDField()
    invite_link = serializers.CharField()


class ProposeSubdomainResponseSerializer(serializers.Serializer):
    """Response containing proposed candidate subdomain."""

    subdomain = serializers.CharField()


class ConfirmTLSResponseSerializer(serializers.Serializer):
    """Response returned upon TLS certificate confirmation."""

    gym = GymTenantSummarySerializer()
    message = serializers.CharField()
