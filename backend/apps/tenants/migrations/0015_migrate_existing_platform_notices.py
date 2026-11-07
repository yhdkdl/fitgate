from django.db import migrations


def migrate_existing_platform_notices(apps, schema_editor):
    GymNotice = apps.get_model("tenants", "GymNotice")
    PlatformNotice = apps.get_model("tenants", "PlatformNotice")

    notices = GymNotice.objects.filter(gym__isnull=True)
    for gn in notices:
        PlatformNotice.objects.create(
            id=gn.id,
            title=gn.title,
            message=gn.body,
            posted_by=gn.posted_by,
            audience_type="all",
            created_at=gn.created_at,
            updated_at=gn.updated_at,
        )
    notices.delete()


def reverse_migration(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("tenants", "0014_platformnotice_supportrequest_supportmessage"),
    ]

    operations = [
        migrations.RunPython(migrate_existing_platform_notices, reverse_migration),
    ]
