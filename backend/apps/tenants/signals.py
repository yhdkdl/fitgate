"""Signals for tenants app."""

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.tenants.models import GymConfig, GymTenant, get_tier_defaults


@receiver(post_save, sender=GymTenant)
def create_gym_config(sender, instance, created, **kwargs):
    """Automatically create a default GymConfig matching the tenant's tier when created."""
    if created:
        defaults = get_tier_defaults(instance.tier or GymTenant.TIER_STARTER)
        GymConfig.objects.get_or_create(gym=instance, defaults=defaults)
