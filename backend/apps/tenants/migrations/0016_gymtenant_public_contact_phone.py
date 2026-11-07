from django.db import migrations, models


def copy_old_contact_phone_to_public(apps, schema_editor):
    GymTenant = apps.get_model("tenants", "GymTenant")
    for gym in GymTenant.objects.all():
        if not gym.public_contact_phone and gym.contact_phone:
            gym.public_contact_phone = gym.contact_phone
            gym.save(update_fields=["public_contact_phone"])


def reverse_copy(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("tenants", "0015_migrate_existing_platform_notices"),
    ]

    operations = [
        migrations.AddField(
            model_name="gymtenant",
            name="public_contact_phone",
            field=models.CharField(blank=True, default="", max_length=20),
        ),
        migrations.RunPython(copy_old_contact_phone_to_public, reverse_copy),
    ]
