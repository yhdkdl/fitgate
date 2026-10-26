"""URL routing for payments, Chapa checkout, webhooks, and gateway configuration."""

from django.urls import path

from apps.payments.views import (
    ChapaCheckoutView,
    ChapaWebhookView,
    GymPaymentConfigTestView,
    GymPaymentConfigView,
    GymPaymentListView,
    MemberPaymentHistoryView,
    ReceiptDetailView,
    RecordCashPaymentView,
    SuperAdminGymPaymentStatusView,
)

app_name = "payments"

urlpatterns = [
    # Gym Owner Payment Gateway Configuration (strictly Owner only)
    path(
        "api/gym/payment-config/",
        GymPaymentConfigView.as_view(),
        name="gym-payment-config",
    ),
    path(
        "api/gym/payment-config/test/",
        GymPaymentConfigTestView.as_view(),
        name="gym-payment-config-test",
    ),
    # Member Online Checkout
    path(
        "api/payments/checkout/chapa/",
        ChapaCheckoutView.as_view(),
        name="chapa-checkout",
    ),
    # Member Self-Service Payment History
    path(
        "api/payments/history/",
        MemberPaymentHistoryView.as_view(),
        name="member-payment-history",
    ),
    # Staff Cash Payment Recording (Owner, Manager, Reception)
    path(
        "api/gym/payments/cash/",
        RecordCashPaymentView.as_view(),
        name="gym-record-cash-payment",
    ),
    # Staff Gym Payment History & Revenue Summary (Owner, Manager)
    path(
        "api/gym/payments/",
        GymPaymentListView.as_view(),
        name="gym-payments-list",
    ),
    # Digital Receipt Details (Staff or owning member)
    path(
        "api/gym/receipts/<uuid:receipt_id>/",
        ReceiptDetailView.as_view(),
        name="gym-receipt-detail",
    ),
    # Chapa Webhook Receiver (public, HMAC-verified)
    path(
        "api/webhooks/chapa/",
        ChapaWebhookView.as_view(),
        name="chapa-webhook",
    ),
    # Super Admin Gym Payment Status (platform administration, mode inspection only)
    path(
        "api/platform/gyms/<uuid:gym_id>/payment-status/",
        SuperAdminGymPaymentStatusView.as_view(),
        name="superadmin-gym-payment-status",
    ),
]
