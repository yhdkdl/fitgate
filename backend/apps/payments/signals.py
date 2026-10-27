"""Signals for payments app."""

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.payments.models import GymReceiptCounter
from apps.tenants.models import GymTenant


@receiver(post_save, sender=GymTenant)
def create_gym_receipt_counter(sender, instance, created, **kwargs):
    """Automatically create a GymReceiptCounter when a GymTenant is created."""
    if created:
        GymReceiptCounter.all_objects.get_or_create(gym=instance)
