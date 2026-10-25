# Generated manually for Sprint 10

from django.db import migrations
from django.utils import timezone


def backfill_member_status(apps, schema_editor):
    Member = apps.get_model("memberships", "Member")
    MemberSubscription = apps.get_model("memberships", "MemberSubscription")
    today = timezone.localdate()

    for member in Member.objects.all():
        subs = list(
            MemberSubscription.objects.filter(member=member).order_by(
                "-end_date", "-created_at"
            )
        )
        if not subs:
            computed_status = "pending"
        elif any(s.status == "suspended" for s in subs):
            computed_status = "suspended"
        elif any(s.status == "frozen" for s in subs):
            computed_status = "frozen"
        elif any(
            s.status == "active" and s.start_date <= today <= s.end_date for s in subs
        ):
            computed_status = "active"
        elif all(
            s.status == "expired" or s.end_date < today
            for s in subs
            if s.status != "pending"
        ):
            computed_status = "expired"
        else:
            computed_status = "pending"

        if member.status != computed_status:
            member.status = computed_status
            member.save(update_fields=["status"])


def reverse_backfill(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("memberships", "0004_membershipplan_and_member_status_pending"),
    ]

    operations = [
        migrations.RunPython(backfill_member_status, reverse_backfill),
    ]
