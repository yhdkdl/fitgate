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


class RecordCashPaymentRequestSerializer(serializers.Serializer):
    """Input serializer for gym staff recording a cash payment."""

    member_id = serializers.UUIDField(required=True)
    plan_id = serializers.UUIDField(required=True)
    notes = serializers.CharField(
        required=False, allow_blank=True, default="", max_length=1000
    )
    idempotency_key = serializers.CharField(
        required=False, allow_blank=True, default="", max_length=64
    )


class ReceiptSerializer(serializers.ModelSerializer):
    """Read-only digital receipt representation."""

    issued_by_name = serializers.SerializerMethodField()
    gym_name = serializers.CharField(source="gym.name", read_only=True)
    gym_subdomain = serializers.CharField(source="gym.subdomain", read_only=True)

    class Meta:
        from apps.payments.models import Receipt

        model = Receipt
        fields = [
            "id",
            "receipt_number",
            "sequence_number",
            "issued_at",
            "issued_by_id",
            "issued_by_name",
            "amount_etb",
            "currency",
            "payment_method",
            "member_name",
            "member_phone",
            "plan_name",
            "plan_duration",
            "notes",
            "gym_name",
            "gym_subdomain",
        ]
        read_only_fields = fields

    def get_issued_by_name(self, obj) -> str:
        if obj.issued_by:
            return (
                obj.issued_by.full_name or obj.issued_by.email or str(obj.issued_by.id)
            )
        return "System"


class PaymentListItemSerializer(serializers.Serializer):
    """Staff view of a payment record with receipt reference."""

    id = serializers.UUIDField()
    created_at = serializers.DateTimeField()
    payer_type = serializers.CharField()
    member_id = serializers.UUIDField(allow_null=True)
    member_name = serializers.CharField(allow_blank=True)
    plan_id = serializers.UUIDField(allow_null=True)
    plan_name = serializers.CharField(allow_blank=True)
    method = serializers.CharField()
    amount_etb = serializers.DecimalField(max_digits=12, decimal_places=2)
    currency = serializers.CharField()
    status = serializers.CharField()
    confirmed_by_id = serializers.UUIDField(allow_null=True)
    confirmed_by_name = serializers.CharField(allow_blank=True)
    receipt_number = serializers.CharField(allow_blank=True)
    notes = serializers.CharField(allow_blank=True)


class MemberPaymentHistoryItemSerializer(serializers.Serializer):
    """Member self-service view of their own payment history."""

    id = serializers.UUIDField()
    created_at = serializers.DateTimeField()
    plan_name = serializers.CharField(allow_blank=True)
    method = serializers.CharField()
    amount_etb = serializers.DecimalField(max_digits=12, decimal_places=2)
    currency = serializers.CharField()
    status = serializers.CharField()
    receipt_number = serializers.CharField(allow_blank=True)
    subscription_start_date = serializers.DateField(allow_null=True)
    subscription_end_date = serializers.DateField(allow_null=True)


class RecordCashPaymentResponseSerializer(serializers.Serializer):
    """Output serializer for cash payment confirmation."""

    payment_id = serializers.UUIDField()
    receipt = ReceiptSerializer()
    status = serializers.CharField()
    amount_etb = serializers.DecimalField(max_digits=12, decimal_places=2)
    detail = serializers.CharField()
