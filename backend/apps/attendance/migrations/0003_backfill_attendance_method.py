# Generated manually for Sprint 10 ordered migration step 2

from django.db import migrations


def backfill_attendance_method(apps, schema_editor):
    Attendance = apps.get_model("attendance", "Attendance")
    Attendance.objects.filter(is_override=True).update(method="manual_override")
    Attendance.objects.filter(is_override=False).update(method="qr")


def reverse_backfill(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("attendance", "0002_attendance_method_optional"),
    ]

    operations = [
        migrations.RunPython(backfill_attendance_method, reverse_backfill),
    ]
