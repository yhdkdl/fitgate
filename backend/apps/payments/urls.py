"""URL routing for payments, Chapa checkout, webhooks, and gateway configuration."""

from django.urls import path

from apps.payments.views import (
    BankTransferScreenshotView,
    ChapaCheckoutView,
    ChapaWebhookView,
    GymPaymentConfigTestView,
    GymPaymentConfigView,
    GymPaymentListView,
    GymPaymentPublicStatusView,
    MemberPaymentHistoryView,
    MemberPaymentStatusView,
    ReceiptDetailView,
    ReconcileBankTransfersView,
    RecordBankTransferPaymentView,
    RecordCashPaymentView,
    ReverseBankTransferView,
    SuperAdminGymPaymentStatusView,
    UnreconciledBankTransfersView,
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
    # Member Self-Service Payment Status by Reference
    path(
        "api/payments/status/<str:reference>/",
        MemberPaymentStatusView.as_view(),
        name="member-payment-status",
    ),
    # Staff Cash Payment Recording (Owner, Manager, Reception)
    path(
        "api/gym/payments/cash/",
        RecordCashPaymentView.as_view(),
        name="gym-record-cash-payment",
    ),
    # Staff Bank Transfer Recording (Owner, Manager, Reception)
    path(
        "api/gym/payments/bank-transfer/",
        RecordBankTransferPaymentView.as_view(),
        name="gym-record-bank-transfer",
    ),
    # Owner Bank Transfer Reconciliation (Owner only)
    path(
        "api/gym/payments/bank-transfers/unreconciled/",
        UnreconciledBankTransfersView.as_view(),
        name="gym-unreconciled-bank-transfers",
    ),
    path(
        "api/gym/payments/bank-transfers/reconcile/",
        ReconcileBankTransfersView.as_view(),
        name="gym-reconcile-bank-transfers",
    ),
    # Owner Bank Transfer Reversal (Owner only)
    path(
        "api/gym/payments/<uuid:payment_id>/reverse/",
        ReverseBankTransferView.as_view(),
        name="gym-reverse-bank-transfer",
    ),
    # Staff Gym Payment History & Revenue Summary (Owner, Manager)
    path(
        "api/gym/payments/",
        GymPaymentListView.as_view(),
        name="gym-payments-list",
    ),
    # Digital Receipt Details (Staff or owning member)
    path(
        "api/gym/receipts/<str:receipt_id>/",
        ReceiptDetailView.as_view(),
        name="gym-receipt-detail",
    ),
    # Bank Transfer Screenshot View (Staff Owner/Manager/Recorder only)
    path(
        "api/gym/payments/bank-transfers/<uuid:payment_id>/screenshot/",
        BankTransferScreenshotView.as_view(),
        name="gym-bank-transfer-screenshot",
    ),
    # Gym Payment Public Status
    path(
        "api/gym/payments/public-status/",
        GymPaymentPublicStatusView.as_view(),
        name="gym-payment-public-status",
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
