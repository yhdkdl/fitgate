"""Serializers for payment configurations, checkout sessions, and status reporting."""

from decimal import Decimal

from django.utils import timezone
from rest_framework import serializers

from apps.payments.models import Expense, GymPaymentConfig


class GymPaymentConfigSerializer(serializers.ModelSerializer):
    """Safe read-only representation of gym payment configuration."""

    is_configured = serializers.BooleanField(read_only=True)
    masked_public_key = serializers.CharField(read_only=True)
    has_secret_key = serializers.BooleanField(read_only=True)
    has_webhook_secret = serializers.BooleanField(read_only=True)
    use_mock = serializers.SerializerMethodField()
    detected_mode = serializers.SerializerMethodField()
    is_enabled = serializers.BooleanField(read_only=True)
    unfinished_online_payments = serializers.SerializerMethodField()

    class Meta:
        model = GymPaymentConfig
        fields = [
            "is_configured",
            "is_test_mode",
            "is_verified",
            "is_enabled",
            "verified_at",
            "masked_public_key",
            "has_secret_key",
            "has_webhook_secret",
            "use_mock",
            "detected_mode",
            "unfinished_online_payments",
        ]
        read_only_fields = fields

    def get_unfinished_online_payments(self, obj) -> int:
        from apps.payments.models import Payment

        return Payment.objects.filter(
            gym=obj.gym,
            method=Payment.METHOD_CHAPA,
            status=Payment.STATUS_PENDING,
        ).count()

    def get_use_mock(self, obj) -> bool:
        from django.conf import settings

        return getattr(settings, "CHAPA_USE_MOCK", False)

    def get_detected_mode(self, obj) -> str:
        sec = obj.secret_key or ""
        pub = obj.public_key or ""
        if "TEST" in sec.upper() or "TEST" in pub.upper():
            return "Test"
        if sec or pub:
            return "Live"
        return "Unknown"


class GymPaymentConfigUpdateSerializer(serializers.Serializer):
    """Input serializer for gym owner configuring Chapa credentials."""

    is_enabled = serializers.BooleanField(required=False)

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
    bank_reference = serializers.CharField(read_only=True, allow_null=True)
    transfer_channel = serializers.CharField(read_only=True, allow_null=True)
    is_reversed = serializers.BooleanField(read_only=True)
    reversed_at = serializers.SerializerMethodField()
    reversal_reason = serializers.SerializerMethodField()
    is_upgrade = serializers.SerializerMethodField()

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
            "gross_amount_etb",
            "credit_amount_etb",
            "is_upgrade",
            "currency",
            "payment_method",
            "bank_reference",
            "transfer_channel",
            "is_reversed",
            "reversed_at",
            "reversal_reason",
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

    def get_reversed_at(self, obj):
        if (
            hasattr(obj, "payment")
            and obj.payment
            and hasattr(obj.payment, "reversal")
            and obj.payment.reversal
        ):
            return obj.payment.reversal.reversed_at
        return None

    def get_reversal_reason(self, obj):
        if (
            hasattr(obj, "payment")
            and obj.payment
            and hasattr(obj.payment, "reversal")
            and obj.payment.reversal
        ):
            return obj.payment.reversal.reason
        return None

    def get_is_upgrade(self, obj) -> bool:
        if hasattr(obj, "payment") and obj.payment:
            return bool(getattr(obj.payment, "is_upgrade", False))
        return bool(obj.gross_amount_etb or obj.credit_amount_etb)


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
    gross_amount_etb = serializers.DecimalField(
        max_digits=12, decimal_places=2, allow_null=True, required=False
    )
    credit_amount_etb = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False
    )
    is_upgrade = serializers.BooleanField(default=False)
    currency = serializers.CharField()
    status = serializers.CharField()
    confirmed_by_id = serializers.UUIDField(allow_null=True)
    confirmed_by_name = serializers.CharField(allow_blank=True)
    receipt_number = serializers.CharField(allow_blank=True)
    notes = serializers.CharField(allow_blank=True)
    bank_reference = serializers.CharField(allow_blank=True, default="")
    transfer_date = serializers.DateField(allow_null=True, required=False)
    channel = serializers.CharField(allow_blank=True, default="")
    is_reconciled = serializers.BooleanField(default=False)
    reconciled_at = serializers.DateTimeField(allow_null=True, required=False)
    is_reversed = serializers.BooleanField(default=False)
    reversed_at = serializers.DateTimeField(allow_null=True, required=False)


class MemberPaymentHistoryItemSerializer(serializers.Serializer):
    """Member self-service view of their own payment history."""

    id = serializers.UUIDField()
    created_at = serializers.DateTimeField()
    plan_name = serializers.CharField(allow_blank=True)
    method = serializers.CharField()
    amount_etb = serializers.DecimalField(max_digits=12, decimal_places=2)
    gross_amount_etb = serializers.DecimalField(
        max_digits=12, decimal_places=2, allow_null=True, required=False
    )
    credit_amount_etb = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False
    )
    is_upgrade = serializers.BooleanField(default=False)
    currency = serializers.CharField()
    status = serializers.CharField()
    receipt_number = serializers.CharField(allow_blank=True)
    bank_reference = serializers.CharField(allow_blank=True, default="")
    is_reversed = serializers.BooleanField(default=False)
    reversed_at = serializers.DateTimeField(allow_null=True, required=False)
    subscription_start_date = serializers.DateField(allow_null=True)
    subscription_end_date = serializers.DateField(allow_null=True)


class RecordCashPaymentResponseSerializer(serializers.Serializer):
    """Output serializer for cash payment confirmation."""

    payment_id = serializers.UUIDField()
    receipt = ReceiptSerializer()
    status = serializers.CharField()
    amount_etb = serializers.DecimalField(max_digits=12, decimal_places=2)
    detail = serializers.CharField()


class RecordBankTransferPaymentRequestSerializer(serializers.Serializer):
    """Input serializer to record a bank-transfer payment."""

    member_id = serializers.UUIDField(required=True)
    plan_id = serializers.UUIDField(required=True)
    bank_reference = serializers.CharField(required=True, min_length=3, max_length=100)
    transfer_date = serializers.DateField(required=True)
    channel = serializers.CharField(
        required=False, allow_blank=True, default="", max_length=50
    )
    notes = serializers.CharField(
        required=False, allow_blank=True, default="", max_length=1000
    )
    idempotency_key = serializers.CharField(
        required=False, allow_blank=True, default="", max_length=64
    )


class RecordBankTransferResponseSerializer(serializers.Serializer):
    """Output serializer for bank-transfer payment confirmation."""

    payment_id = serializers.UUIDField()
    receipt = ReceiptSerializer()
    status = serializers.CharField()
    amount_etb = serializers.DecimalField(max_digits=12, decimal_places=2)
    bank_reference = serializers.CharField()
    is_reconciled = serializers.BooleanField()
    detail = serializers.CharField()


class UnreconciledBankTransferItemSerializer(serializers.Serializer):
    """Owner view of an unreconciled bank transfer."""

    id = serializers.UUIDField()
    transfer_date = serializers.DateField(allow_null=True)
    created_at = serializers.DateTimeField()
    bank_reference = serializers.CharField()
    channel = serializers.CharField(allow_blank=True)
    amount_etb = serializers.DecimalField(max_digits=12, decimal_places=2)
    member_id = serializers.UUIDField(allow_null=True)
    member_name = serializers.CharField()
    member_phone = serializers.CharField(allow_blank=True)
    confirmed_by_id = serializers.UUIDField(allow_null=True)
    confirmed_by_name = serializers.CharField()
    receipt_number = serializers.CharField()
    has_screenshot = serializers.BooleanField(default=False)
    screenshot_url = serializers.CharField(allow_null=True, required=False)


class ReconcileBankTransfersSerializer(serializers.Serializer):
    """Owner bulk or single reconciliation request."""

    payment_ids = serializers.ListField(
        child=serializers.UUIDField(), allow_empty=False
    )


class ReverseBankTransferSerializer(serializers.Serializer):
    """Owner reversal request with mandatory reason."""

    reason = serializers.CharField(min_length=5, max_length=500)


class MemberPaymentStatusSerializer(serializers.Serializer):
    """Read-only payment status for member self-service return page."""

    status = serializers.CharField()
    receipt_id = serializers.CharField(allow_null=True)
    plan_name = serializers.CharField(allow_blank=True)


class PlanUpgradeQuoteSerializer(serializers.Serializer):
    current_subscription_id = serializers.UUIDField()
    current_plan_id = serializers.UUIDField()
    current_plan_name = serializers.CharField()
    current_plan_price_etb = serializers.CharField()
    current_start_date = serializers.DateField()
    current_end_date = serializers.DateField()
    new_plan_id = serializers.UUIDField()
    new_plan_name = serializers.CharField()
    new_plan_price_etb = serializers.CharField()
    total_days = serializers.IntegerField()
    used_days = serializers.IntegerField()
    remaining_days = serializers.IntegerField()
    net_paid_etb = serializers.CharField()
    credit_amount_etb = serializers.CharField()
    gross_amount_etb = serializers.CharField()
    net_amount_etb = serializers.CharField()
    new_start_date = serializers.DateField()
    new_end_date = serializers.DateField()


class ExpenseSerializer(serializers.ModelSerializer):
    category_display = serializers.CharField(
        source="get_category_display", read_only=True
    )
    logged_by_name = serializers.SerializerMethodField()
    voided_by_name = serializers.SerializerMethodField()
    equipment_name = serializers.SerializerMethodField()
    is_voided = serializers.BooleanField(source="is_void", read_only=True)

    class Meta:
        model = Expense
        fields = [
            "id",
            "amount_etb",
            "category",
            "category_display",
            "note",
            "incurred_on",
            "logged_by",
            "logged_by_name",
            "equipment",
            "equipment_name",
            "is_void",
            "is_voided",
            "voided_at",
            "voided_by",
            "voided_by_name",
            "void_reason",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "logged_by",
            "logged_by_name",
            "is_void",
            "voided_at",
            "voided_by",
            "voided_by_name",
            "void_reason",
            "created_at",
            "updated_at",
        ]

    def get_logged_by_name(self, obj) -> str:
        if obj.logged_by:
            return obj.logged_by.full_name or obj.logged_by.email
        return ""

    def get_voided_by_name(self, obj) -> str:
        if obj.voided_by:
            return obj.voided_by.full_name or obj.voided_by.email
        return ""

    def get_equipment_name(self, obj) -> str:
        if obj.equipment:
            return obj.equipment.name
        return ""


class ExpenseCreateSerializer(serializers.ModelSerializer):
    amount_etb = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=Decimal("0.01"),
        max_value=Decimal("10000000.00"),
        error_messages={
            "min_value": "Expense amount must be greater than 0 and at most 10,000,000 ETB.",
            "max_value": "Expense amount must be greater than 0 and at most 10,000,000 ETB.",
        },
    )
    category = serializers.ChoiceField(
        choices=Expense.CATEGORY_CHOICES,
        error_messages={"invalid_choice": "Please select an expense category."},
    )
    note = serializers.CharField(
        max_length=500,
        required=False,
        allow_blank=True,
        default="",
        error_messages={"max_length": "Expense note cannot exceed 500 characters."},
    )
    incurred_on = serializers.DateField(
        required=False,
        default=timezone.localdate,
    )

    class Meta:
        model = Expense
        fields = [
            "amount_etb",
            "category",
            "note",
            "incurred_on",
            "equipment",
        ]

    def validate_incurred_on(self, value):
        if value and value > timezone.localdate():
            raise serializers.ValidationError("Expense date cannot be in the future.")
        return value


class ExpenseVoidSerializer(serializers.Serializer):
    void_reason = serializers.CharField(
        min_length=2,
        max_length=255,
        required=True,
        error_messages={
            "required": "Void reason is required.",
            "min_length": "Void reason must be at least 2 characters.",
            "max_length": "Void reason cannot exceed 255 characters.",
        },
    )
