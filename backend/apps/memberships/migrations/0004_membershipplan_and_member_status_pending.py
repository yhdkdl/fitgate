# Generated manually for Sprint 10

import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("memberships", "0003_bodymetrics_recorded_by"),
        ("tenants", "0004_gymconfig_brand_color_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="member",
            name="status",
            field=models.CharField(
                choices=[
                    ("pending", "Pending"),
                    ("active", "Active"),
                    ("expired", "Expired"),
                    ("frozen", "Frozen"),
                    ("suspended", "Suspended"),
                ],
                db_index=True,
                default="pending",
                max_length=20,
            ),
        ),
        migrations.CreateModel(
            name="MembershipPlan",
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
                ("name", models.CharField(max_length=100)),
                ("description", models.TextField(blank=True, default="")),
                ("duration_value", models.PositiveIntegerField()),
                (
                    "duration_unit",
                    models.CharField(
                        choices=[("days", "Days"), ("months", "Months")],
                        default="months",
                        max_length=10,
                    ),
                ),
                ("price_etb", models.DecimalField(decimal_places=2, max_digits=10)),
                ("trainer_inclusive", models.BooleanField(default=False)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
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
                "verbose_name": "Membership Plan",
                "verbose_name_plural": "Membership Plans",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddConstraint(
            model_name="membershipplan",
            constraint=models.UniqueConstraint(
                fields=("gym", "name"), name="membershipplan_gym_name_unique"
            ),
        ),
        migrations.AlterField(
            model_name="membersubscription",
            name="plan_id",
            field=models.ForeignKey(
                blank=True,
                db_column="plan_id",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="subscriptions",
                to="memberships.membershipplan",
            ),
        ),
        migrations.RenameField(
            model_name="membersubscription",
            old_name="plan_id",
            new_name="plan",
        ),
    ]
