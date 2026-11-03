"""
Views for gym expense tracking and financial/attendance reporting.

Sprint 29a:
- Accessible only to Owner and Manager roles.
- Scoped strictly to requesting gym tenant.
- Expenses: amount, category, note, incurred_on, equipment linkage.
- No hard delete: voiding with void_reason, voided_at, voided_by.
- Audit-logged: expense_logged, expense_voided.
- Financial report: net revenue vs active expenses, category breakdown, plan breakdown.
- Attendance report: total check-ins, unique members, check-in method breakdown.
"""

from decimal import Decimal

from django.db.models import Count, Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import AuditLog
from apps.accounts.permissions import IsOwnerOrManager
from apps.attendance.models import Attendance
from apps.core.validators import validate_export_date_range
from apps.payments.models import Expense, Payment
from apps.payments.serializers import (
    ExpenseCreateSerializer,
    ExpenseSerializer,
    ExpenseVoidSerializer,
)


class ExpenseListCreateView(APIView):
    """
    List and create expenses for the gym tenant.
    Restricted to Owner and Manager.
    """

    permission_classes = [IsOwnerOrManager]

    def get(self, request):
        tenant = request.tenant
        qs = Expense.objects.filter(gym=tenant).select_related(
            "logged_by", "voided_by", "equipment"
        )

        # Optional filters
        category = request.query_params.get("category")
        if category:
            qs = qs.filter(category=category.strip().lower())

        include_voided = request.query_params.get("include_voided", "true").lower() in (
            "true",
            "1",
            "yes",
        )
        if not include_voided:
            qs = qs.filter(is_void=False)

        start_date_param = request.query_params.get("start_date")
        end_date_param = request.query_params.get("end_date")
        if start_date_param or end_date_param:
            try:
                start_date, end_date = validate_export_date_range(
                    start_date_param, end_date_param
                )
                if start_date:
                    qs = qs.filter(incurred_on__gte=start_date)
                if end_date:
                    qs = qs.filter(incurred_on__lte=end_date)
            except Exception as e:
                return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        # Calculate active total
        active_total = qs.filter(is_void=False).aggregate(total=Sum("amount_etb"))[
            "total"
        ] or Decimal("0.00")

        serializer = ExpenseSerializer(qs, many=True)
        return Response(
            {
                "expenses": serializer.data,
                "total_active_etb": str(active_total),
                "count": qs.count(),
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        tenant = request.tenant
        serializer = ExpenseCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        expense = serializer.save(
            gym=tenant,
            logged_by=request.user,
        )

        # Audit log
        AuditLog.objects.create(
            gym=tenant,
            actor=request.user,
            action_type="expense_logged",
            affected_record_type="expense",
            affected_record_id=str(expense.id),
            metadata={
                "amount_etb": str(expense.amount_etb),
                "category": expense.category,
                "incurred_on": expense.incurred_on.isoformat(),
                "equipment_id": (
                    str(expense.equipment_id) if expense.equipment_id else None
                ),
            },
        )

        return Response(ExpenseSerializer(expense).data, status=status.HTTP_201_CREATED)


class ExpenseVoidView(APIView):
    """
    Void a mistaken expense.
    Never hard deletes: sets is_void=True, voided_at, voided_by, void_reason.
    Restricted to Owner and Manager.
    """

    permission_classes = [IsOwnerOrManager]

    def post(self, request, pk):
        tenant = request.tenant
        expense = get_object_or_404(Expense, pk=pk, gym=tenant)

        if expense.is_void:
            return Response(
                {"detail": "This expense has already been voided."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = ExpenseVoidSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        void_reason = serializer.validated_data["void_reason"]
        expense.is_void = True
        expense.voided_at = timezone.now()
        expense.voided_by = request.user
        expense.void_reason = void_reason
        expense.save()

        # Audit log
        AuditLog.objects.create(
            gym=tenant,
            actor=request.user,
            action_type="expense_voided",
            affected_record_type="expense",
            affected_record_id=str(expense.id),
            metadata={
                "amount_etb": str(expense.amount_etb),
                "category": expense.category,
                "void_reason": void_reason,
            },
        )

        return Response(ExpenseSerializer(expense).data, status=status.HTTP_200_OK)


class GymFinancialReportView(APIView):
    """
    Financial performance report:
    - Confirmed net revenue (confirmed member payments minus reversals)
    - Active expenses
    - Net income (revenue minus expenses)
    - Category breakdown
    - Revenue by plan breakdown
    Restricted to Owner and Manager.
    """

    permission_classes = [IsOwnerOrManager]

    def get(self, request):
        tenant = request.tenant
        start_date_param = request.query_params.get("start_date")
        end_date_param = request.query_params.get("end_date")

        start_date = None
        end_date = None
        if start_date_param or end_date_param:
            try:
                start_date, end_date = validate_export_date_range(
                    start_date_param, end_date_param
                )
            except Exception as e:
                return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        # Payments query
        payments_qs = Payment.objects.filter(
            gym=tenant, payer_type=Payment.PAYER_TYPE_MEMBER
        )
        if start_date:
            payments_qs = payments_qs.filter(created_at__date__gte=start_date)
        if end_date:
            payments_qs = payments_qs.filter(created_at__date__lte=end_date)

        confirmed_gross = payments_qs.filter(status=Payment.STATUS_CONFIRMED).aggregate(
            total=Sum("amount_etb")
        )["total"] or Decimal("0.00")
        reversed_total = payments_qs.filter(status=Payment.STATUS_REVERSED).aggregate(
            total=Sum("amount_etb")
        )["total"] or Decimal("0.00")
        net_revenue = confirmed_gross - reversed_total

        # Expenses query
        expenses_qs = Expense.objects.filter(gym=tenant, is_void=False)
        if start_date:
            expenses_qs = expenses_qs.filter(incurred_on__gte=start_date)
        if end_date:
            expenses_qs = expenses_qs.filter(incurred_on__lte=end_date)

        total_expenses = expenses_qs.aggregate(total=Sum("amount_etb"))[
            "total"
        ] or Decimal("0.00")
        net_income = net_revenue - total_expenses

        # Category breakdown
        category_rows = (
            expenses_qs.values("category")
            .annotate(total=Sum("amount_etb"), count=Count("id"))
            .order_by("-total")
        )
        category_breakdown = {
            row["category"]: {
                "total_etb": str(row["total"]),
                "count": row["count"],
            }
            for row in category_rows
        }

        # Revenue by plan breakdown
        plan_rows = (
            payments_qs.filter(status=Payment.STATUS_CONFIRMED, plan__isnull=False)
            .values("plan__id", "plan__name")
            .annotate(total=Sum("amount_etb"), payment_count=Count("id"))
            .order_by("-total")
        )
        plan_breakdown = [
            {
                "plan_id": str(row["plan__id"]),
                "plan_name": row["plan__name"],
                "total_etb": str(row["total"]),
                "payment_count": row["payment_count"],
            }
            for row in plan_rows
        ]

        return Response(
            {
                "period": {
                    "start_date": start_date.isoformat() if start_date else None,
                    "end_date": end_date.isoformat() if end_date else None,
                },
                "confirmed_gross_revenue_etb": str(confirmed_gross),
                "reversed_payments_etb": str(reversed_total),
                "net_revenue_etb": str(net_revenue),
                "total_expenses_etb": str(total_expenses),
                "net_income_etb": str(net_income),
                "expenses_by_category": category_breakdown,
                "revenue_by_plan": plan_breakdown,
            },
            status=status.HTTP_200_OK,
        )


class GymAttendanceReportView(APIView):
    """
    Attendance summary report:
    - Total check-ins
    - Unique members checked in
    - Method breakdown (QR code vs manual override)
    - Daily check-in counts
    Restricted to Owner and Manager.
    """

    permission_classes = [IsOwnerOrManager]

    def get(self, request):
        tenant = request.tenant
        start_date_param = request.query_params.get("start_date")
        end_date_param = request.query_params.get("end_date")

        start_date = None
        end_date = None
        if start_date_param or end_date_param:
            try:
                start_date, end_date = validate_export_date_range(
                    start_date_param, end_date_param
                )
            except Exception as e:
                return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        attendance_qs = Attendance.objects.filter(gym=tenant)
        if start_date:
            attendance_qs = attendance_qs.filter(date__gte=start_date)
        if end_date:
            attendance_qs = attendance_qs.filter(date__lte=end_date)

        total_check_ins = attendance_qs.count()
        unique_members = attendance_qs.values("member_id").distinct().count()

        qr_count = attendance_qs.filter(method=Attendance.METHOD_QR).count()
        manual_count = attendance_qs.filter(
            method=Attendance.METHOD_MANUAL_OVERRIDE
        ).count()

        daily_rows = (
            attendance_qs.values("date").annotate(count=Count("id")).order_by("-date")
        )
        daily_counts = [
            {"date": row["date"].isoformat(), "count": row["count"]}
            for row in daily_rows
        ]

        return Response(
            {
                "period": {
                    "start_date": start_date.isoformat() if start_date else None,
                    "end_date": end_date.isoformat() if end_date else None,
                },
                "total_check_ins": total_check_ins,
                "unique_members": unique_members,
                "qr_check_ins": qr_count,
                "manual_override_check_ins": manual_count,
                "daily_counts": daily_counts,
            },
            status=status.HTTP_200_OK,
        )
