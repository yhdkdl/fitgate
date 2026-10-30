from django.db import migrations


def backfill_trainer_profiles(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    Trainer = apps.get_model("trainers", "Trainer")

    for user in User.objects.filter(role="trainer"):
        if not user.gym_id:
            continue
        if not Trainer.objects.filter(user_id=user.id).exists():
            Trainer.objects.create(
                user_id=user.id,
                gym_id=user.gym_id,
                max_clients=20,
            )


def reverse_backfill(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("trainers", "0001_initial"),
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(backfill_trainer_profiles, reverse_backfill),
    ]
