from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.accounts.models import User


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def ensure_trainer_profile_on_user_save(sender, instance, created, **kwargs):
    """
    Ensure every User with role='trainer' has an associated Trainer profile
    belonging to the same gym.
    """
    if getattr(instance, "role", None) == User.ROLE_TRAINER and instance.gym_id:
        from apps.trainers.models import Trainer

        # Use all_objects to bypass thread-local tenant filtering during creation/signal handling
        if not Trainer.all_objects.filter(user=instance).exists():
            Trainer.all_objects.create(
                user=instance,
                gym=instance.gym,
                max_clients=20,
            )
