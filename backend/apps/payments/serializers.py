"""Serializers for payment configurations, checkout sessions, and status reporting."""

from rest_framework import serializers

from apps.payments.models import GymPaymentConfig


class GymPaymentConfigSerializer(serializers.ModelSerializer):
    """Safe read-only representation of gym payment configuration."""

    is_configured = serializers.BooleanField(read_only=True)
    masked_public_key = serializers.CharField(read_only=True)
    has_secret_key = serializers.BooleanField(read_only=True)
    has_webhook_secret = serializers.BooleanField(read_only=True)

    class Meta:
        model = GymPaymentConfig
        fields = [
            "is_configured",
            "is_test_mode",
            "is_verified",
            "verified_at",
            "masked_public_key",
            "has_secret_key",
            "has_webhook_secret",
        ]
        read_only_fields = fields


class GymPaymentConfigUpdateSerializer(serializers.Serializer):
    """Input serializer for gym owner configuring Chapa credentials."""

    public_key = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=255,
        write_only=True,
    )
    secret_key = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=255,
        write_only=True,
    )
    webhook_secret = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=255,
        write_only=True,
    )

    def validate_public_key(self, value: str) -> str:
        value = value.strip()
        if value and "CHAPUBK" not in value.upper():
            raise serializers.ValidationError(
                "Invalid Chapa public key format (must start with CHAPUBK or CHAPUBK_TEST)."
            )
        return value

    def validate_secret_key(self, value: str) -> str:
        value = value.strip()
        if value and "CHASECK" not in value.upper():
            raise serializers.ValidationError(
                "Invalid Chapa secret key format (must start with CHASECK or CHASECK_TEST)."
            )
        return value


class ChapaCheckoutRequestSerializer(serializers.Serializer):
    """Input serializer for initiating online subscription checkout."""

    plan_id = serializers.UUIDField(required=True)


class ChapaCheckoutResponseSerializer(serializers.Serializer):
    """Output serializer for online subscription checkout session."""

    checkout_url = serializers.URLField()
    tx_ref = serializers.CharField()
    payment_id = serializers.UUIDField()


class SuperAdminGymPaymentStatusSerializer(serializers.Serializer):
    """Platform administration view of gym payment mode (test vs live) without exposing keys."""

    gym_id = serializers.UUIDField()
    gym_name = serializers.CharField()
    subdomain = serializers.CharField()
    is_configured = serializers.BooleanField()
    is_test_mode = serializers.BooleanField()
    is_verified = serializers.BooleanField()
