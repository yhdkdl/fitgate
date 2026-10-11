"""Data models for payments and transactions."""

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.tenants.models import TenantAwareModel


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

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_CONFIRMED, "Confirmed"),
        (STATUS_FAILED, "Failed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payer_type = models.CharField(
        max_length=30,
        choices=PAYER_TYPE_CHOICES,
        default=PAYER_TYPE_MEMBER,
    )
    member_id = models.UUIDField(null=True, blank=True)
    subscription_id = models.UUIDField(null=True, blank=True)
    method = models.CharField(max_length=30, choices=METHOD_CHOICES)
    amount_etb = models.DecimalField(max_digits=12, decimal_places=2)
    chapa_ref = models.CharField(max_length=100, null=True, blank=True)
    bank_reference = models.CharField(max_length=100, null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="confirmed_payments",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Payment"
        verbose_name_plural = "Payments"

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
            if self.method not in (self.METHOD_CHAPA, self.METHOD_CASH):
                raise ValidationError(
                    {"method": ["Member payments must use chapa or cash."]}
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
