"""Signals for tenants app."""

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.tenants.models import GymConfig, GymTenant


@receiver(post_save, sender=GymTenant)
def create_gym_config(sender, instance, created, **kwargs):
    """Automatically create a default GymConfig when a GymTenant is created."""
    if created:
        GymConfig.objects.get_or_create(gym=instance)
