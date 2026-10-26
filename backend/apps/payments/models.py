"""Data models for payments, payment configurations, and transactions."""

import uuid
from typing import Optional

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.tenants.models import TenantAwareModel


class GymPaymentConfig(TenantAwareModel):
    """
    Per-gym payment configuration for Chapa and external gateways.
    One config per gym tenant. Credentials are encrypted at rest with TENANT_CREDENTIALS_KEY.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    encrypted_public_key = models.TextField(blank=True, default="")
    encrypted_secret_key = models.TextField(blank=True, default="")
    encrypted_webhook_secret = models.TextField(blank=True, default="")
    is_test_mode = models.BooleanField(default=True)
    is_verified = models.BooleanField(default=False)
    verified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Gym Payment Configuration"
        verbose_name_plural = "Gym Payment Configurations"
        constraints = [
            models.UniqueConstraint(fields=["gym"], name="unique_gym_payment_config")
        ]

    @property
    def public_key(self) -> str:
        from apps.payments.encryption import decrypt_credential

        return decrypt_credential(self.encrypted_public_key)

    @public_key.setter
    def public_key(self, value: str):
        from apps.payments.encryption import encrypt_credential

        self.encrypted_public_key = encrypt_credential(value)
        if value:
            self.is_test_mode = "test" in value.lower()

    @property
    def secret_key(self) -> str:
        from apps.payments.encryption import decrypt_credential

        return decrypt_credential(self.encrypted_secret_key)

    @secret_key.setter
    def secret_key(self, value: str):
        from apps.payments.encryption import encrypt_credential

        self.encrypted_secret_key = encrypt_credential(value)
        if value and not self.encrypted_public_key:
            self.is_test_mode = "test" in value.lower()

    @property
    def webhook_secret(self) -> str:
        from apps.payments.encryption import decrypt_credential

        return decrypt_credential(self.encrypted_webhook_secret)

    @webhook_secret.setter
    def webhook_secret(self, value: str):
        from apps.payments.encryption import encrypt_credential

        self.encrypted_webhook_secret = encrypt_credential(value)

    @property
    def masked_public_key(self) -> str:
        from apps.payments.encryption import mask_credential

        return mask_credential(self.public_key)

    @property
    def has_secret_key(self) -> bool:
        return bool(self.encrypted_secret_key)

    @property
    def has_webhook_secret(self) -> bool:
        return bool(self.encrypted_webhook_secret)

    @property
    def is_configured(self) -> bool:
        return bool(self.encrypted_public_key and self.encrypted_secret_key)

    def __str__(self):
        mode = "Test" if self.is_test_mode else "Live"
        status = "Verified" if self.is_verified else "Unverified"
        return f"GymPaymentConfig({self.gym.subdomain} - {mode} [{status}])"


class Payment(TenantAwareModel):
    """
    Records payments for gym platform subscriptions and member plans.

    Tenant-scoped to the paying gym tenant.
    """

    PAYER_TYPE_GYM_SUBSCRIPTION = "gym_subscription"
    PAYER_TYPE_MEMBER = "member"

    PAYER_TYPE_CHOICES = [
        (PAYER_TYPE_GYM_SUBSCRIPTION, "Gym Subscription"),
        (PAYER_TYPE_MEMBER, "Member"),
    ]

    METHOD_CHAPA = "chapa"
    METHOD_CASH = "cash"
    METHOD_BANK_TRANSFER = "bank_transfer"

    METHOD_CHOICES = [
        (METHOD_CHAPA, "Chapa"),
        (METHOD_CASH, "Cash"),
        (METHOD_BANK_TRANSFER, "Bank Transfer"),
    ]

    STATUS_PENDING = "pending"
    STATUS_CONFIRMED = "confirmed"
    STATUS_FAILED = "failed"
    STATUS_ABANDONED = "abandoned"
    STATUS_REVERSED = "reversed"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_CONFIRMED, "Confirmed"),
        (STATUS_FAILED, "Failed"),
        (STATUS_ABANDONED, "Abandoned"),
        (STATUS_REVERSED, "Reversed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payer_type = models.CharField(
        max_length=30,
        choices=PAYER_TYPE_CHOICES,
        default=PAYER_TYPE_MEMBER,
    )
    member = models.ForeignKey(
        "memberships.Member",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="payments",
        db_column="member_id",
    )
    plan = models.ForeignKey(
        "memberships.MembershipPlan",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="payments",
    )
    subscription = models.ForeignKey(
        "memberships.MemberSubscription",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="payments",
        db_column="subscription_id",
    )
    method = models.CharField(max_length=30, choices=METHOD_CHOICES)
    amount_etb = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=10, default="ETB")
    chapa_ref = models.CharField(max_length=100, null=True, blank=True, unique=True)
    bank_reference = models.CharField(max_length=100, null=True, blank=True)
    bank_reference_normalized = models.CharField(
        max_length=100, null=True, blank=True, db_index=True
    )
    transfer_date = models.DateField(null=True, blank=True)
    channel = models.CharField(max_length=50, blank=True, default="")
    is_reconciled = models.BooleanField(default=False)
    reconciled_at = models.DateTimeField(null=True, blank=True)
    reconciled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reconciled_payments",
    )
    flagged_unreconciled_at = models.DateTimeField(null=True, blank=True)
    previous_subscription_state = models.JSONField(default=dict, blank=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )
    metadata = models.JSONField(default=dict, blank=True)
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="confirmed_payments",
    )
    idempotency_key = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Payment"
        verbose_name_plural = "Payments"
        constraints = [
            models.UniqueConstraint(
                fields=["gym", "idempotency_key"],
                condition=models.Q(idempotency_key__isnull=False),
                name="unique_gym_payment_idempotency_key",
            ),
            models.UniqueConstraint(
                fields=["gym", "bank_reference_normalized"],
                condition=models.Q(bank_reference_normalized__isnull=False),
                name="unique_gym_bank_reference_normalized",
            ),
        ]

    def clean(self):
        super().clean()
        if self.amount_etb is not None and self.amount_etb <= 0:
            raise ValidationError({"amount_etb": ["Amount must be greater than zero."]})

        if self.payer_type == self.PAYER_TYPE_GYM_SUBSCRIPTION:
            if self.method != self.METHOD_BANK_TRANSFER:
                raise ValidationError(
                    {
                        "method": [
                            "Gym subscription payments must use bank_transfer. Chapa is rejected."
                        ]
                    }
                )
        elif self.payer_type == self.PAYER_TYPE_MEMBER:
            if self.method not in (
                self.METHOD_CHAPA,
                self.METHOD_CASH,
                self.METHOD_BANK_TRANSFER,
            ):
                raise ValidationError(
                    {
                        "method": [
                            "Member payments must use chapa, cash, or bank_transfer."
                        ]
                    }
                )

        if self.bank_reference:
            cleaned_ref = self.bank_reference.strip()
            if len(cleaned_ref) < 3 or len(cleaned_ref) > 100:
                raise ValidationError(
                    {
                        "bank_reference": [
                            "Bank reference must be between 3 and 100 characters."
                        ]
                    }
                )
            self.bank_reference = cleaned_ref
            self.bank_reference_normalized = cleaned_ref.lower()

        if self.transfer_date:
            from django.utils import timezone

            if self.transfer_date > timezone.localdate():
                raise ValidationError(
                    {"transfer_date": ["Transfer date cannot be in the future."]}
                )

        if self.status == self.STATUS_CONFIRMED and self.method in (
            self.METHOD_CASH,
            self.METHOD_BANK_TRANSFER,
        ):
            if not self.confirmed_by_id:
                raise ValidationError(
                    {
                        "confirmed_by": [
                            "Confirmed cash and bank transfer payments require confirmed_by."
                        ]
                    }
                )

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Payment {self.id} ({self.payer_type} - {self.amount_etb} ETB [{self.status}])"


class PaymentReversal(TenantAwareModel):
    """
    Immutable record of a reversed bank-transfer payment.
    Protected against update and deletion at application and database trigger level.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payment = models.OneToOneField(
        "payments.Payment",
        on_delete=models.PROTECT,
        related_name="reversal",
    )
    reversed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="executed_reversals",
    )
    reversed_at = models.DateTimeField(editable=False)
    reason = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-reversed_at"]
        verbose_name = "Payment Reversal"
        verbose_name_plural = "Payment Reversals"

    def clean(self):
        super().clean()
        if self.reason:
            cleaned_reason = self.reason.strip()
            if len(cleaned_reason) < 5 or len(cleaned_reason) > 500:
                raise ValidationError(
                    {
                        "reason": [
                            "Reversal reason must be between 5 and 500 characters."
                        ]
                    }
                )
            self.reason = cleaned_reason
        else:
            raise ValidationError({"reason": ["Reversal reason is required."]})

    def save(self, *args, **kwargs):
        if not self._state.adding and self.pk:
            if PaymentReversal.all_objects.filter(pk=self.pk).exists():
                raise ValidationError(
                    "Payment reversals are immutable and cannot be updated."
                )
        if not self.reversed_at:
            from django.utils import timezone

            self.reversed_at = timezone.now()
        self.clean()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Payment reversals are immutable and cannot be deleted.")

    def __str__(self):
        return f"PaymentReversal({self.payment_id} by {self.reversed_by_id})"


class Receipt(TenantAwareModel):
    """
    Official digital receipt for confirmed payments.
    Receipt numbers are sequential and unique per gym.
    Receipts are immutable: cannot be edited or deleted once issued.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payment = models.OneToOneField(
        "payments.Payment",
        on_delete=models.PROTECT,
        related_name="receipt",
    )
    receipt_number = models.CharField(max_length=64, editable=False)
    sequence_number = models.PositiveIntegerField(editable=False)
    issued_at = models.DateTimeField(auto_now_add=True)
    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="issued_receipts",
    )
    amount_etb = models.DecimalField(max_digits=12, decimal_places=2, editable=False)
    currency = models.CharField(max_length=10, default="ETB", editable=False)
    payment_method = models.CharField(max_length=30, editable=False)
    member_name = models.CharField(max_length=255, editable=False)
    member_phone = models.CharField(
        max_length=30, blank=True, default="", editable=False
    )
    plan_name = models.CharField(max_length=255, editable=False)
    plan_duration = models.CharField(
        max_length=100, blank=True, default="", editable=False
    )
    notes = models.TextField(blank=True, default="", editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-issued_at"]
        verbose_name = "Receipt"
        verbose_name_plural = "Receipts"
        constraints = [
            models.UniqueConstraint(
                fields=["gym", "receipt_number"],
                name="unique_gym_receipt_number",
            ),
            models.UniqueConstraint(
                fields=["gym", "sequence_number"],
                name="unique_gym_receipt_sequence",
            ),
        ]

    def clean(self):
        super().clean()
        if (
            self.payment
            and self.payment.method
            in (Payment.METHOD_CASH, Payment.METHOD_BANK_TRANSFER)
            and not self.issued_by_id
        ):
            raise ValidationError(
                {
                    "issued_by": [
                        "Cash and bank transfer receipts must record which staff member issued them."
                    ]
                }
            )

    @property
    def is_reversed(self) -> bool:
        return (
            self.payment.status == Payment.STATUS_REVERSED if self.payment_id else False
        )

    @property
    def bank_reference(self) -> Optional[str]:
        return self.payment.bank_reference if self.payment_id else None

    @property
    def transfer_channel(self) -> Optional[str]:
        return self.payment.channel if self.payment_id else None

    def save(self, *args, **kwargs):
        if not self._state.adding and self.pk:
            if Receipt.all_objects.filter(pk=self.pk).exists():
                raise ValidationError("Receipts are immutable and cannot be updated.")
        self.clean()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Receipts cannot be deleted.")

    def __str__(self):
        return f"Receipt {self.receipt_number} ({self.amount_etb} ETB)"


class GymReceiptCounter(TenantAwareModel):
    """
    Dedicated per-gym counter for sequential, gapless receipt numbering.
    Locked with select_for_update inside payment transactions.
    Rolls back automatically if the payment transaction fails.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    last_receipt_number = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Gym Receipt Counter"
        verbose_name_plural = "Gym Receipt Counters"
        constraints = [
            models.UniqueConstraint(
                fields=["gym"],
                name="unique_gym_receipt_counter",
            )
        ]

    def __str__(self):
        return f"ReceiptCounter ({self.gym_id}): {self.last_receipt_number}"
