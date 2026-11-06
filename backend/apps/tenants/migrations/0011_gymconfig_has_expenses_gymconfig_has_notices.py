from django.db import migrations, models


def sync_notices_and_expenses_entitlements(apps, schema_editor):
    GymTenant = apps.get_model("tenants", "GymTenant")
    GymConfig = apps.get_model("tenants", "GymConfig")

    for tenant in GymTenant.objects.all():
        config = GymConfig.objects.filter(gym=tenant).first()
        if config:
            is_growth_or_pro = tenant.tier in ("growth", "pro")
            config.has_notices = is_growth_or_pro
            config.has_expenses = is_growth_or_pro
            config.save(update_fields=["has_notices", "has_expenses"])


def reverse_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("tenants", "0010_populate_group_classes_entitlement"),
    ]

    operations = [
        migrations.AddField(
            model_name="gymconfig",
            name="has_expenses",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="gymconfig",
            name="has_notices",
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(sync_notices_and_expenses_entitlements, reverse_noop),
    ]
