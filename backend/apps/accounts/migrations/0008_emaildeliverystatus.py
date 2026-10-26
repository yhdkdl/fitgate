import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0007_strict_auditlog_immutability"),
        ("tenants", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="EmailDeliveryStatus",
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
                ("email", models.EmailField(db_index=True, max_length=254)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("sent", "Sent"),
                            ("not_delivered", "Not Delivered"),
                            ("suppressed", "Suppressed"),
                        ],
                        default="sent",
                        max_length=30,
                    ),
                ),
                ("reason", models.CharField(blank=True, default="", max_length=100)),
                ("event_payload", models.JSONField(blank=True, default=dict)),
                ("resend_count_today", models.PositiveIntegerField(default=0)),
                ("last_resend_date", models.DateField(blank=True, null=True)),
                ("last_sent_at", models.DateTimeField(auto_now=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "gym",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="email_delivery_statuses",
                        to="tenants.gymtenant",
                    ),
                ),
            ],
            options={
                "verbose_name": "Email Delivery Status",
                "verbose_name_plural": "Email Delivery Statuses",
            },
        ),
        migrations.AddIndex(
            model_name="emaildeliverystatus",
            index=models.Index(fields=["email"], name="accounts_em_email_001_idx"),
        ),
        migrations.AddIndex(
            model_name="emaildeliverystatus",
            index=models.Index(fields=["gym", "status"], name="accounts_em_gym_st_idx"),
        ),
        migrations.AddConstraint(
            model_name="emaildeliverystatus",
            constraint=models.UniqueConstraint(
                fields=("email",), name="unique_email_delivery_status"
            ),
        ),
    ]
