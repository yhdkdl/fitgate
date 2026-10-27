# Generated manually for Sprint 10 ordered migration step 3

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("attendance", "0003_backfill_attendance_method"),
    ]

    operations = [
        migrations.AlterField(
            model_name="attendance",
            name="method",
            field=models.CharField(
                choices=[
                    ("qr", "QR Code Scan"),
                    ("manual_override", "Manual Staff Override"),
                ],
                default="qr",
                max_length=20,
            ),
        ),
        migrations.AddConstraint(
            model_name="attendance",
            constraint=models.CheckConstraint(
                condition=(
                    (models.Q(is_override=True) & models.Q(method="manual_override"))
                    | (
                        models.Q(is_override=False)
                        & ~models.Q(method="manual_override")
                    )
                ),
                name="attendance_override_matches_method",
            ),
        ),
    ]
