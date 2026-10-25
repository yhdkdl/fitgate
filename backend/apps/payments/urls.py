"""URL routing for payments, Chapa checkout, webhooks, and gateway configuration."""

from django.urls import path

from apps.payments.views import (
    ChapaCheckoutView,
    ChapaWebhookView,
    GymPaymentConfigTestView,
    GymPaymentConfigView,
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
