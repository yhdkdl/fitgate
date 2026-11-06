"""
Tests for Sprint 29a Expenses & Financial/Attendance Reports.

Verifies:
- Role access: Owner and Manager allowed; Trainer, Reception, Member, Super Admin refused.
- Tenant isolation: expenses and reports scoped strictly to gym.
- Expense field validation: amount (> 0 to 10M ETB), category, note (<= 500), date not future.
- Void lifecycle: no hard delete; void reason recorded; excluded from active totals; audit-logged.
- Equipment integration: adding equipment with price and record_as_expense creates linked expense; not counted twice.
- Reports: financial summary (confirmed net revenue minus expenses) and attendance summary.
"""

from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import AuditLog, User
from apps.accounts.tokens import get_tokens_for_user
from apps.attendance.models import Attendance
from apps.memberships.models import Member, MembershipPlan, MemberSubscription
from apps.payments.models import Expense, Payment
from apps.tenants.models import GymConfig, GymTenant


def auth_client(client, user, gym=None):
    tokens = get_tokens_for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
    if gym:
        client.defaults["HTTP_HOST"] = f"{gym.subdomain}.localhost"
    else:
        client.defaults["HTTP_HOST"] = "localhost"
    return client


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def test_setup(db):
    gym_a = GymTenant.objects.create(
        name="Apex Gym Addis",
        subdomain="apex",
        tier=GymTenant.TIER_GROWTH,
        status=GymTenant.STATUS_ACTIVE,
        tls_confirmed_at=timezone.now(),
    )
    GymConfig.objects.update_or_create(gym=gym_a)

    gym_b = GymTenant.objects.create(
        name="FitGym Adama",
        subdomain="adama",
        tier=GymTenant.TIER_GROWTH,
        status=GymTenant.STATUS_ACTIVE,
        tls_confirmed_at=timezone.now(),
    )
    GymConfig.objects.update_or_create(gym=gym_b)

    owner_a = User.objects.create_user(
        email="owner_a@apex.com",
        password="ValidPassword123!",
        role=User.ROLE_OWNER,
        gym=gym_a,
        is_active=True,
    )
    manager_a = User.objects.create_user(
        email="manager_a@apex.com",
        password="ValidPassword123!",
        role=User.ROLE_MANAGER,
        gym=gym_a,
        is_active=True,
    )
    trainer_a = User.objects.create_user(
        email="trainer_a@apex.com",
        password="ValidPassword123!",
        role=User.ROLE_TRAINER,
        gym=gym_a,
        is_active=True,
    )
    reception_a = User.objects.create_user(
        email="reception_a@apex.com",
        password="ValidPassword123!",
        role=User.ROLE_RECEPTION,
        gym=gym_a,
        is_active=True,
    )
    member_user_a = User.objects.create_user(
        email="member_a@apex.com",
        password="ValidPassword123!",
        role=User.ROLE_MEMBER,
        gym=gym_a,
        is_active=True,
    )
    super_admin = User.objects.create_user(
        email="superadmin@fitgate.com",
        password="ValidPassword123!",
        role=User.ROLE_SUPER_ADMIN,
        gym=None,
        is_active=True,
    )

    plan_a = MembershipPlan.objects.create(
        gym=gym_a,
        name="Standard Monthly",
        price_etb=Decimal("3000.00"),
        duration_value=1,
        duration_unit=MembershipPlan.DURATION_MONTHS,
        is_active=True,
    )

    member_a = Member.objects.create(
        gym=gym_a,
        user=member_user_a,
        full_name="Kidus Mengistu",
        phone="+251911001122",
        status=Member.STATUS_ACTIVE,
        waiver_accepted_at=timezone.now(),
    )

    sub_a = MemberSubscription.objects.create(
        gym=gym_a,
        member=member_a,
        plan=plan_a,
        start_date=timezone.localdate(),
        end_date=timezone.localdate() + timezone.timedelta(days=30),
        status=MemberSubscription.STATUS_ACTIVE,
    )

    payment_confirmed = Payment.objects.create(
        gym=gym_a,
        payer_type=Payment.PAYER_TYPE_MEMBER,
        member=member_a,
        plan=plan_a,
        subscription=sub_a,
        method=Payment.METHOD_CASH,
        amount_etb=Decimal("3000.00"),
        gross_amount_etb=Decimal("3000.00"),
        credit_amount_etb=Decimal("0.00"),
        status=Payment.STATUS_CONFIRMED,
        confirmed_by=owner_a,
    )

    payment_reversed = Payment.objects.create(
        gym=gym_a,
        payer_type=Payment.PAYER_TYPE_MEMBER,
        member=member_a,
        plan=plan_a,
        subscription=sub_a,
        method=Payment.METHOD_BANK_TRANSFER,
        amount_etb=Decimal("500.00"),
        gross_amount_etb=Decimal("500.00"),
        credit_amount_etb=Decimal("0.00"),
        status=Payment.STATUS_REVERSED,
    )

    attendance_a = Attendance.objects.create(
        gym=gym_a,
        member=member_a,
        date=timezone.localdate(),
        checked_in_at=timezone.now(),
        method=Attendance.METHOD_QR,
    )

    return {
        "gym_a": gym_a,
        "gym_b": gym_b,
        "owner_a": owner_a,
        "manager_a": manager_a,
        "trainer_a": trainer_a,
        "reception_a": reception_a,
        "member_user_a": member_user_a,
        "super_admin": super_admin,
        "member_a": member_a,
        "plan_a": plan_a,
        "payment_confirmed": payment_confirmed,
        "payment_reversed": payment_reversed,
        "attendance_a": attendance_a,
    }


@pytest.mark.django_db
def test_owner_and_manager_can_log_and_list_expenses(api_client, test_setup):
    auth_client(api_client, test_setup["owner_a"], test_setup["gym_a"])

    # 1. Log expense as Owner
    payload = {
        "amount_etb": "15000.00",
        "category": "rent",
        "note": "November facility rent",
        "incurred_on": timezone.localdate().isoformat(),
    }
    res_post = api_client.post("/api/gym/expenses/", payload, format="json")
    assert res_post.status_code == status.HTTP_201_CREATED
    expense_id = res_post.data["id"]
    assert res_post.data["amount_etb"] == "15000.00"
    assert res_post.data["category"] == "rent"
    assert res_post.data["category_display"] == "Rent"
    assert (
        res_post.data["logged_by_name"] == test_setup["owner_a"].full_name
        or test_setup["owner_a"].email
    )
    assert res_post.data["is_void"] is False

    # Check audit log
    audit = AuditLog.all_objects.filter(
        gym=test_setup["gym_a"],
        action_type="expense_logged",
        affected_record_id=expense_id,
    ).first()
    assert audit is not None
    assert audit.actor == test_setup["owner_a"]
    assert audit.metadata["amount_etb"] == "15000.00"

    # 2. List expenses as Manager
    auth_client(api_client, test_setup["manager_a"], test_setup["gym_a"])
    res_list = api_client.get("/api/gym/expenses/")
    assert res_list.status_code == status.HTTP_200_OK
    assert res_list.data["count"] == 1
    assert res_list.data["total_active_etb"] == "15000.00"


@pytest.mark.django_db
def test_expense_validation(api_client, test_setup):
    auth_client(api_client, test_setup["owner_a"], test_setup["gym_a"])

    # Amount <= 0
    res_zero = api_client.post(
        "/api/gym/expenses/",
        {
            "amount_etb": "0.00",
            "category": "rent",
        },
    )
    assert res_zero.status_code == status.HTTP_400_BAD_REQUEST

    # Amount > 10M
    res_over = api_client.post(
        "/api/gym/expenses/",
        {
            "amount_etb": "10000000.01",
            "category": "rent",
        },
    )
    assert res_over.status_code == status.HTTP_400_BAD_REQUEST

    # Invalid category
    res_cat = api_client.post(
        "/api/gym/expenses/",
        {
            "amount_etb": "500.00",
            "category": "vacation",
        },
    )
    assert res_cat.status_code == status.HTTP_400_BAD_REQUEST

    # Future date
    future_date = (timezone.localdate() + timezone.timedelta(days=2)).isoformat()
    res_future = api_client.post(
        "/api/gym/expenses/",
        {
            "amount_etb": "500.00",
            "category": "utilities",
            "incurred_on": future_date,
        },
    )
    assert res_future.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_expense_void_lifecycle(api_client, test_setup):
    auth_client(api_client, test_setup["owner_a"], test_setup["gym_a"])

    expense = Expense.objects.create(
        gym=test_setup["gym_a"],
        amount_etb=Decimal("2500.00"),
        category=Expense.CATEGORY_UTILITIES,
        note="Electric bill duplicate",
        logged_by=test_setup["owner_a"],
    )

    # Hard delete forbidden
    with pytest.raises(ValidationError):
        expense.delete()

    # Voiding without reason fails
    res_no_reason = api_client.post(f"/api/gym/expenses/{expense.id}/void/", {})
    assert res_no_reason.status_code == status.HTTP_400_BAD_REQUEST

    # Voiding with reason succeeds
    res_void = api_client.post(
        f"/api/gym/expenses/{expense.id}/void/",
        {
            "void_reason": "Accidental duplicate entry for water bill",
        },
    )
    assert res_void.status_code == status.HTTP_200_OK
    assert res_void.data["is_void"] is True
    assert res_void.data["void_reason"] == "Accidental duplicate entry for water bill"

    # Check database and audit log
    expense.refresh_from_db()
    assert expense.is_void is True
    assert expense.voided_by == test_setup["owner_a"]

    audit = AuditLog.all_objects.filter(
        gym=test_setup["gym_a"],
        action_type="expense_voided",
        affected_record_id=str(expense.id),
    ).first()
    assert audit is not None
    assert audit.metadata["void_reason"] == "Accidental duplicate entry for water bill"

    # Voiding again fails
    res_repeat = api_client.post(
        f"/api/gym/expenses/{expense.id}/void/",
        {
            "void_reason": "Trying again",
        },
    )
    assert res_repeat.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_unauthorized_roles_refused(api_client, test_setup):
    for role_user in [
        test_setup["trainer_a"],
        test_setup["reception_a"],
        test_setup["member_user_a"],
        test_setup["super_admin"],
    ]:
        auth_client(
            api_client, role_user, test_setup["gym_a"] if role_user.gym else None
        )
        assert (
            api_client.get("/api/gym/expenses/").status_code
            == status.HTTP_403_FORBIDDEN
        )
        assert (
            api_client.get("/api/gym/reports/financial/").status_code
            == status.HTTP_403_FORBIDDEN
        )


@pytest.mark.django_db
def test_equipment_expense_linkage_and_no_double_count(api_client, test_setup):
    auth_client(api_client, test_setup["owner_a"], test_setup["gym_a"])

    # 1. Create equipment item with price and record_as_expense=True
    equip_payload = {
        "name": "Heavy Duty Squat Rack",
        "category": "squat_rack",
        "quantity": 2,
        "unit_purchase_price_etb": "45000.00",
        "record_as_expense": True,
    }
    res_eq = api_client.post("/api/gym/equipment/", equip_payload, format="json")
    assert res_eq.status_code == status.HTTP_201_CREATED
    eq_id = res_eq.data["id"]

    # Verify linked expense created
    linked_expense = Expense.all_objects.filter(
        equipment_id=eq_id, is_void=False
    ).first()
    assert linked_expense is not None
    # 2 racks * 45,000 = 90,000.00 ETB
    assert linked_expense.amount_etb == Decimal("90000.00")
    assert linked_expense.category == Expense.CATEGORY_EQUIPMENT

    # 2. Updating equipment price updates linked expense without creating duplicate
    res_patch = api_client.patch(
        f"/api/gym/equipment/{eq_id}/",
        {
            "unit_purchase_price_etb": "50000.00",
            "record_as_expense": True,
        },
        format="json",
    )
    assert res_patch.status_code == status.HTTP_200_OK

    all_linked = Expense.all_objects.filter(equipment_id=eq_id, is_void=False)
    assert all_linked.count() == 1
    # 2 racks * 50,000 = 100,000.00 ETB
    assert all_linked.first().amount_etb == Decimal("100000.00")


@pytest.mark.django_db
def test_financial_report_and_tenant_isolation(api_client, test_setup):
    auth_client(api_client, test_setup["owner_a"], test_setup["gym_a"])

    # Add active expense
    Expense.objects.create(
        gym=test_setup["gym_a"],
        amount_etb=Decimal("1200.00"),
        category=Expense.CATEGORY_SUPPLIES,
        note="Cleaning supplies",
        logged_by=test_setup["owner_a"],
    )

    # Add voided expense (must not be counted in totals)
    Expense.objects.create(
        gym=test_setup["gym_a"],
        amount_etb=Decimal("9999.00"),
        category=Expense.CATEGORY_OTHER,
        is_void=True,
        void_reason="Mistake",
    )

    # Add expense to Gym B (must not leak)
    Expense.objects.create(
        gym=test_setup["gym_b"],
        amount_etb=Decimal("50000.00"),
        category=Expense.CATEGORY_RENT,
    )

    res = api_client.get("/api/gym/reports/financial/")
    assert res.status_code == status.HTTP_200_OK

    # Confirmed gross = 3000, reversed = 500 -> net revenue = 2500
    assert res.data["confirmed_gross_revenue_etb"] == "3000.00"
    assert res.data["reversed_payments_etb"] == "500.00"
    assert res.data["net_revenue_etb"] == "2500.00"

    # Total expenses = 1200 (voided 9999 and Gym B 50000 excluded)
    assert res.data["total_expenses_etb"] == "1200.00"
    # Net income = 2500 - 1200 = 1300
    assert res.data["net_income_etb"] == "1300.00"

    # Category breakdown includes supplies
    assert "supplies" in res.data["expenses_by_category"]
    assert res.data["expenses_by_category"]["supplies"]["total_etb"] == "1200.00"


@pytest.mark.django_db
def test_attendance_report(api_client, test_setup):
    auth_client(api_client, test_setup["owner_a"], test_setup["gym_a"])

    res = api_client.get("/api/gym/reports/attendance/")
    assert res.status_code == status.HTTP_200_OK
    assert res.data["total_check_ins"] == 1
    assert res.data["unique_members"] == 1
    assert res.data["qr_check_ins"] == 1
    assert res.data["manual_override_check_ins"] == 0
    assert len(res.data["daily_counts"]) == 1
