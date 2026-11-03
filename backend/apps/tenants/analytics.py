"""Analytics and overview dashboard queries for Gym Owners and Managers (Sprint 27)."""

from datetime import datetime, time, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from django.db.models import Count, Q, Sum
from django.utils import timezone

from apps.attendance.models import Attendance
from apps.memberships.models import Member, MemberSubscription
from apps.payments.models import Payment
from apps.tenants.models import GymTenant


def get_gym_analytics_overview(tenant: GymTenant) -> Dict[str, Any]:
    """
    Computes dashboard analytics for Owner and Manager:
    1. Active members count (derived status active; frozen count returned separately).
    2. Today's check-ins count in Africa/Addis_Ababa timezone.
    3. Monthly net revenue: confirmed net cash received this calendar month
       (upgrade payments count their net amount, reversed payments excluded).
    4. Memberships expiring within 7 days: active subscriptions ending within 7 days
       that have NO queued following subscription (superseded subscriptions excluded).
    5. Premium analytics (revenue by plan): Growth/Pro only (has_analytics=True).
       Starter tier gets upgrade prompt.
    """
    tz_addis = ZoneInfo("Africa/Addis_Ababa")
    now_addis = timezone.now().astimezone(tz_addis)
    today_addis = now_addis.date()

    # 1. Member counts (active and frozen; derived status)
    member_counts = Member.all_objects.filter(gym=tenant).aggregate(
        active_count=Count("id", filter=Q(status=Member.STATUS_ACTIVE)),
        frozen_count=Count("id", filter=Q(status=Member.STATUS_FROZEN)),
        total_count=Count("id"),
    )
    active_members = member_counts["active_count"] or 0
    frozen_members = member_counts["frozen_count"] or 0

    # 2. Today's check-ins in Addis Ababa timezone
    today_checkins = Attendance.all_objects.filter(
        gym=tenant,
        date=today_addis,
    ).count()

    # 3. Monthly net revenue in current calendar month (Addis Ababa)
    # Confirmed net cash received this calendar month.
    # Reversed payments (STATUS_REVERSED) are excluded by filtering STATUS_CONFIRMED.
    # Upgrade payments record net cash received in amount_etb.
    start_of_month = today_addis.replace(day=1)
    start_dt = timezone.make_aware(datetime.combine(start_of_month, time.min), tz_addis)

    payments_month_qs = Payment.all_objects.filter(
        gym=tenant,
        status=Payment.STATUS_CONFIRMED,
        payer_type=Payment.PAYER_TYPE_MEMBER,
        created_at__gte=start_dt,
    )

    monthly_rev_total = payments_month_qs.aggregate(total=Sum("amount_etb"))["total"]
    monthly_net_revenue = monthly_rev_total or Decimal("0.00")

    # 4. Memberships expiring in 7 days without queued renewal
    seven_days_out = today_addis + timedelta(days=7)

    # Find members who have queued/future subscriptions starting after today
    # (superseded subscriptions are strictly excluded)
    queued_member_ids = (
        MemberSubscription.all_objects.filter(
            gym=tenant,
            start_date__gt=today_addis,
            status__in=[
                MemberSubscription.STATUS_PENDING,
                MemberSubscription.STATUS_ACTIVE,
            ],
        )
        .exclude(status=MemberSubscription.STATUS_SUPERSEDED)
        .values_list("member_id", flat=True)
    )

    expiring_subs_qs = (
        MemberSubscription.all_objects.filter(
            gym=tenant,
            status=MemberSubscription.STATUS_ACTIVE,
            end_date__gte=today_addis,
            end_date__lte=seven_days_out,
        )
        .exclude(status=MemberSubscription.STATUS_SUPERSEDED)
        .exclude(member_id__in=queued_member_ids)
        .select_related("member", "plan")
        .order_by("end_date")
    )

    expiring_members: List[Dict[str, Any]] = []
    for sub in expiring_subs_qs:
        expiring_members.append(
            {
                "member_id": str(sub.member.id),
                "member_name": sub.member.full_name,
                "member_phone": sub.member.phone,
                "plan_name": sub.plan.name if sub.plan else "Unknown",
                "end_date": str(sub.end_date),
                "days_remaining": (sub.end_date - today_addis).days,
            }
        )

    # 5. Premium analytics (Revenue by plan) - Gated by has_analytics
    config = getattr(tenant, "config", None)
    has_analytics = bool(config and getattr(config, "has_analytics", False))

    revenue_by_plan: Optional[List[Dict[str, Any]]] = None
    upgrade_prompt: Optional[str] = None

    if not has_analytics:
        upgrade_prompt = (
            "Upgrade to Growth or Pro to unlock revenue by plan breakdowns."
        )
    else:
        plan_stats = (
            Payment.all_objects.filter(
                gym=tenant,
                status=Payment.STATUS_CONFIRMED,
                payer_type=Payment.PAYER_TYPE_MEMBER,
                plan__isnull=False,
            )
            .values("plan_id", "plan__name")
            .annotate(
                total_revenue=Sum("amount_etb"),
                payment_count=Count("id"),
            )
            .order_by("-total_revenue")
        )

        revenue_by_plan = [
            {
                "plan_id": str(item["plan_id"]),
                "plan_name": item["plan__name"] or "Unknown",
                "revenue": str(item["total_revenue"] or Decimal("0.00")),
                "payment_count": item["payment_count"],
            }
            for item in plan_stats
        ]

    return {
        "active_members": active_members,
        "frozen_members": frozen_members,
        "today_checkins": today_checkins,
        "monthly_net_revenue": str(monthly_net_revenue),
        "currency": tenant.currency or "ETB",
        "expiring_memberships_count": len(expiring_members),
        "expiring_memberships": expiring_members,
        "has_analytics": has_analytics,
        "upgrade_prompt": upgrade_prompt,
        "revenue_by_plan": revenue_by_plan,
        "server_date": str(today_addis),
    }
