"""Application configuration for payments."""

from django.apps import AppConfig


class PaymentsConfig(AppConfig):
    """Configuration for payments app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.payments"
    verbose_name = "Payments"
