from django.core.management import call_command
from django.db import migrations


def create_cache_table(apps, schema_editor):
    try:
        call_command("createcachetable", "fitgate_cache_table")
    except Exception:
        pass


def reverse_cache_table(apps, schema_editor):
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("DROP TABLE IF EXISTS fitgate_cache_table")


class Migration(migrations.Migration):
    dependencies = [
        ("tenants", "0004_gymconfig_brand_color_and_more"),
    ]

    operations = [
        migrations.RunPython(create_cache_table, reverse_cache_table),
    ]
