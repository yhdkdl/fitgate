"""
Views for gym tenant data export in CSV format.

Sprint 29:
- Scoped to requesting gym tenant.
- Accessible only to Owner and Manager roles.
- Formula injection protection (leading apostrophe for =, +, -, @).
- UTF-8 BOM (\ufeff) for Excel Amharic compatibility.
- Optional date range filtering (at most 1 year / 366 days).
- Audit-logged with export type and row count.
"""

import csv

from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import AuditLog
from apps.accounts.permissions import IsOwnerOrManager, RequirePasswordChanged
from apps.attendance.models import Attendance
from apps.core.validators import sanitize_csv_cell, validate_export_date_range
from apps.memberships.models import Member, MemberSubscription
from apps.payments.models import Payment


class GymDataExportView(APIView):
    """
    Export gym tenant data as a CSV download.

    Supported export types:
    - members: Name, Phone, Email, Status, Plan, Start Date, End Date (no health, photos, or measurements)
    - payments: Receipt Number, Date, Method, Plan, Gross, Credit, Net Received, Upgrade, Status, Bank Ref, Confirmed By
    - attendance: Date and Time, Member Name, Check-in Method
    """

    permission_classes = [IsAuthenticated, RequirePasswordChanged, IsOwnerOrManager]

    VALID_EXPORT_TYPES = ("members", "payments", "attendance")

    def get(self, request, export_type: str):
        export_type = (export_type or "").strip().lower()
        if export_type not in self.VALID_EXPORT_TYPES:
            return Response(
                {
                    "detail": f"Invalid export type '{export_type}'. Must be one of: {', '.join(self.VALID_EXPORT_TYPES)}."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        start_date_param = request.query_params.get("start_date")
        end_date_param = request.query_params.get("end_date")

        try:
            start_date, end_date = validate_export_date_range(
                start_date_param, end_date_param
            )
        except ValidationError as e:
            return Response(
                {"detail": str(e.message if hasattr(e, "message") else e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        tenant = request.tenant
        timestamp_str = timezone.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{tenant.subdomain}_{export_type}_{timestamp_str}.csv"

        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        response.write("\ufeff")  # Excel-friendly UTF-8 BOM

        writer = csv.writer(response)
        row_count = 0

        if export_type == "members":
            headers = [
                "Name",
                "Phone",
                "Email",
                "Status",
                "Plan",
                "Start Date",
                "End Date",
            ]
            writer.writerow(headers)

            members_qs = (
                Member.objects.filter(gym=tenant)
                .select_related("user")
                .prefetch_related("subscriptions__plan")
                .order_by("-joined_at")
            )
            if start_date:
                members_qs = members_qs.filter(joined_at__date__gte=start_date)
            if end_date:
                members_qs = members_qs.filter(joined_at__date__lte=end_date)

            for member in members_qs:
                active_subs = [
                    s
                    for s in member.subscriptions.all()
                    if s.status != MemberSubscription.STATUS_SUPERSEDED
                ]
                # Pick the latest active/valid subscription
                latest_sub = active_subs[0] if active_subs else None

                plan_name = (
                    latest_sub.plan.name if latest_sub and latest_sub.plan else "None"
                )
                start_date_str = latest_sub.start_date.isoformat() if latest_sub else ""
                end_date_str = latest_sub.end_date.isoformat() if latest_sub else ""

                row = [
                    member.full_name,
                    member.phone,
                    member.user.email if member.user else "",
                    member.status,
                    plan_name,
                    start_date_str,
                    end_date_str,
                ]
                writer.writerow([sanitize_csv_cell(val) for val in row])
                row_count += 1

        elif export_type == "payments":
            headers = [
                "Receipt Number",
                "Date",
                "Payment Method",
                "Plan",
                "Gross Amount (ETB)",
                "Credit Amount (ETB)",
                "Net Received (ETB)",
                "Is Upgrade",
                "Status",
                "Bank Reference",
                "Confirmed By",
            ]
            writer.writerow(headers)

            payments_qs = (
                Payment.objects.filter(
                    gym=tenant,
                    payer_type=Payment.PAYER_TYPE_MEMBER,
                )
                .exclude(
                    status__in=[
                        Payment.STATUS_PENDING_REVIEW,
                        Payment.STATUS_DECLINED,
                    ]
                )
                .select_related("receipt", "plan", "confirmed_by", "member")
                .order_by("-created_at")
            )
            if start_date:
                payments_qs = payments_qs.filter(created_at__date__gte=start_date)
            if end_date:
                payments_qs = payments_qs.filter(created_at__date__lte=end_date)

            for payment in payments_qs:
                receipt_number = (
                    payment.receipt.receipt_number
                    if hasattr(payment, "receipt") and payment.receipt
                    else ""
                )
                created_date_str = payment.created_at.strftime("%Y-%m-%d %H:%M:%S")
                method_display = payment.get_method_display()
                plan_name = payment.plan.name if payment.plan else ""
                gross_str = str(
                    payment.gross_amount_etb
                    if payment.gross_amount_etb is not None
                    else payment.amount_etb
                )
                credit_str = str(payment.credit_amount_etb)
                net_str = str(payment.amount_etb)
                is_upgrade_str = "Yes" if payment.is_upgrade else "No"
                status_display = payment.get_status_display()
                bank_ref = payment.bank_reference or ""
                confirmed_by_str = (
                    payment.confirmed_by.full_name or payment.confirmed_by.email
                    if payment.confirmed_by
                    else ""
                )

                row = [
                    receipt_number,
                    created_date_str,
                    method_display,
                    plan_name,
                    gross_str,
                    credit_str,
                    net_str,
                    is_upgrade_str,
                    status_display,
                    bank_ref,
                    confirmed_by_str,
                ]
                writer.writerow([sanitize_csv_cell(val) for val in row])
                row_count += 1

        elif export_type == "attendance":
            headers = ["Date and Time", "Member Name", "Check-in Method"]
            writer.writerow(headers)

            attendance_qs = (
                Attendance.objects.filter(gym=tenant)
                .select_related("member")
                .order_by("-checked_in_at")
            )
            if start_date:
                attendance_qs = attendance_qs.filter(date__gte=start_date)
            if end_date:
                attendance_qs = attendance_qs.filter(date__lte=end_date)

            for att in attendance_qs:
                dt_str = att.checked_in_at.strftime("%Y-%m-%d %H:%M:%S")
                member_name = att.member.full_name if att.member else ""
                method_display = att.get_method_display()

                row = [dt_str, member_name, method_display]
                writer.writerow([sanitize_csv_cell(val) for val in row])
                row_count += 1

        # Record audit log entry
        AuditLog.objects.create(
            gym=tenant,
            actor=request.user,
            action_type="data_exported",
            affected_record_type="export",
            affected_record_id=export_type,
            metadata={
                "export_type": export_type,
                "row_count": row_count,
                "start_date": start_date.isoformat() if start_date else None,
                "end_date": end_date.isoformat() if end_date else None,
            },
        )

        return response
