# Generated manually for Sprint 10 ordered migration step 1

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("attendance", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="attendance",
            name="method",
            field=models.CharField(
                blank=True,
                choices=[
                    ("qr", "QR Code Scan"),
                    ("manual_override", "Manual Staff Override"),
                ],
                max_length=20,
                null=True,
            ),
        ),
    ]
