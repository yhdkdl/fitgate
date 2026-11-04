from django.db import migrations


def sync_group_classes_entitlements(apps, schema_editor):
    GymTenant = apps.get_model("tenants", "GymTenant")
    GymConfig = apps.get_model("tenants", "GymConfig")

    for tenant in GymTenant.objects.all():
        config = GymConfig.objects.filter(gym=tenant).first()
        if config:
            is_growth_or_pro = tenant.tier in ("growth", "pro")
            if config.has_group_classes != is_growth_or_pro:
                config.has_group_classes = is_growth_or_pro
                config.save(update_fields=["has_group_classes"])


def reverse_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("tenants", "0009_gymconfig_telegram_channel_gymnotice"),
    ]

    operations = [
        migrations.RunPython(sync_group_classes_entitlements, reverse_noop),
    ]
