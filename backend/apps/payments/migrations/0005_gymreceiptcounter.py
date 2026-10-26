import uuid

import django.db.models.deletion
from django.db import migrations, models


def populate_gym_receipt_counters(apps, schema_editor):
    GymTenant = apps.get_model("tenants", "GymTenant")
    Receipt = apps.get_model("payments", "Receipt")
    GymReceiptCounter = apps.get_model("payments", "GymReceiptCounter")

    for tenant in GymTenant.objects.all():
        max_seq = (
            Receipt.objects.filter(gym=tenant).aggregate(models.Max("sequence_number"))[
                "sequence_number__max"
            ]
            or 0
        )
        GymReceiptCounter.objects.get_or_create(
            gym=tenant,
            defaults={"last_receipt_number": max_seq},
        )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("payments", "0004_bank_transfer_and_reversals"),
        ("tenants", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="GymReceiptCounter",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("last_receipt_number", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "gym",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="%(app_label)s_%(class)ss",
                        to="tenants.gymtenant",
                    ),
                ),
            ],
            options={
                "verbose_name": "Gym Receipt Counter",
                "verbose_name_plural": "Gym Receipt Counters",
            },
        ),
        migrations.AddConstraint(
            model_name="gymreceiptcounter",
            constraint=models.UniqueConstraint(
                fields=("gym",),
                name="unique_gym_receipt_counter",
            ),
        ),
        migrations.RunPython(
            populate_gym_receipt_counters,
            reverse_code=noop_reverse,
        ),
    ]
