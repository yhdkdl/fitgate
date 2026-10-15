"""API views for QR check-in, attendance recording, manual override, and attendance logs."""

import uuid
from datetime import datetime, timedelta

from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import (
    CanManageAttendance,
    IsMember,
    RequirePasswordChanged,
)
from apps.attendance.crypto import get_rsa_public_key_pem
from apps.attendance.serializers import (
    AttendanceLogResponseSerializer,
    AttendanceManualOverrideRequestSerializer,
    AttendanceManualOverrideResponseSerializer,
    AttendancePublicKeyResponseSerializer,
    AttendanceScanRequestSerializer,
    AttendanceScanResponseSerializer,
    AttendanceScanResultMemberSerializer,
    MemberQrTokenResponseSerializer,
)
from apps.attendance.services import (
    ScanValidationError,
    get_member_attendance_log,
    issue_member_qr_token,
    process_manual_override,
    verify_and_process_scan,
)
from apps.memberships.models import Member

ScanErrorResponseSerializer = inline_serializer(
    name="AttendanceScanErrorResponse",
    fields={
        "detail": serializers.CharField(),
        "reason": serializers.CharField(),
        "member": AttendanceScanResultMemberSerializer(required=False),
    },
)

QrTokenErrorResponseSerializer = inline_serializer(
    name="MemberQrTokenErrorResponse",
    fields={
        "detail": serializers.CharField(),
        "reason": serializers.CharField(),
    },
)


class AttendancePublicKeyView(APIView):
    """
    Export RSA public key for offline QR signature verification.

    Allows offline scanners (PWA, mobile, hardware) to verify tokens offline.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        summary="Get QR Verification Public Key",
        description="Returns the RSA public key used to verify asymmetric QR check-in tokens offline.",
        responses={200: AttendancePublicKeyResponseSerializer},
    )
    def get(self, request):
        public_key = get_rsa_public_key_pem()
        serializer = AttendancePublicKeyResponseSerializer(
            {"public_key": public_key, "algorithm": "RS256"}
        )
        return Response(serializer.data, status=status.HTTP_200_OK)


class MemberQrTokenView(APIView):
    """
    Generate / rotate asymmetric RS256 JWT QR token for active member.

    Valid for 90 seconds. Refreshes token on valid scan or periodic fetch.
    """

    permission_classes = [RequirePasswordChanged, IsMember]

    def _get_member(self, request) -> Member:
        tenant = getattr(request, "tenant", None)
        if not tenant:
            raise PermissionDenied("Gym tenant context required.")
        member = (
            Member.all_objects.filter(gym=tenant, user=request.user)
            .select_related("gym")
            .first()
        )
        if not member:
            raise NotFound("Member record not found.")
        return member

    @extend_schema(
        summary="Get Active Member QR Token",
        description="Generates a signed RS256 QR check-in token (90s window) for the authenticated member.",
        responses={
            200: MemberQrTokenResponseSerializer,
            400: QrTokenErrorResponseSerializer,
        },
    )
    def get(self, request):
        member = self._get_member(request)
        try:
            token_str, qr_record = issue_member_qr_token(member)
            return Response(
                {
                    "token": token_str,
                    "expires_at": qr_record.expires_at.isoformat(),
                    "valid_seconds": 90,
                    "member_id": str(member.id),
                },
                status=status.HTTP_200_OK,
            )
        except ScanValidationError as e:
            return Response(
                {"detail": e.message, "reason": e.reason},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @extend_schema(
        summary="Rotate Member QR Token",
        description="Explicitly issues a rotated QR check-in token for the member.",
        request=None,
        responses={
            200: MemberQrTokenResponseSerializer,
            400: QrTokenErrorResponseSerializer,
        },
    )
    def post(self, request):
        return self.get(request)


class AttendanceScanView(APIView):
    """
    Validate QR check-in token and record attendance.

    Enforces asymmetric RS256 signature, 90s window, single-use, active subscription,
    and single daily check-in per member.
    """

    permission_classes = [RequirePasswordChanged, CanManageAttendance]

    @extend_schema(
        summary="Scan QR Check-in Token",
        description="Validates a member QR token, records attendance, and issues replacement token.",
        request=AttendanceScanRequestSerializer,
        responses={
            200: AttendanceScanResponseSerializer,
            400: ScanErrorResponseSerializer,
        },
    )
    def post(self, request):
        tenant = getattr(request, "tenant", None)
        if not tenant:
            raise PermissionDenied("Gym tenant context required.")

        serializer = AttendanceScanRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        token_str = serializer.validated_data["token"]
        branch_id = serializer.validated_data.get("branch_id")

        try:
            result = verify_and_process_scan(
                token_str=token_str,
                gym=tenant,
                recorded_by=request.user,
                branch_id=branch_id,
            )
            return Response(result, status=status.HTTP_200_OK)
        except ScanValidationError as e:
            data = {
                "detail": e.message,
                "reason": e.reason,
            }
            if e.member:
                data["member"] = {
                    "id": str(e.member.id),
                    "full_name": e.member.full_name,
                    "photo_url": e.member.photo_url or "",
                    "status": e.member.status,
                    "phone": e.member.phone,
                }
            return Response(data, status=status.HTTP_400_BAD_REQUEST)


class AttendanceManualOverrideView(APIView):
    """
    Perform manual attendance check-in override by Reception / staff.

    Requires an active subscription and non-empty reason. Refused for expired,
    frozen, or suspended members. Produces an Attendance row and an AuditLog entry.
    """

    permission_classes = [RequirePasswordChanged, CanManageAttendance]

    @extend_schema(
        summary="Manual Check-in Override",
        description="Records a manual attendance check-in when QR cannot be used. Audit-logged.",
        request=AttendanceManualOverrideRequestSerializer,
        responses={
            201: AttendanceManualOverrideResponseSerializer,
            400: ScanErrorResponseSerializer,
        },
    )
    def post(self, request):
        tenant = getattr(request, "tenant", None)
        if not tenant:
            raise PermissionDenied("Gym tenant context required.")

        serializer = AttendanceManualOverrideRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        member_id = serializer.validated_data["member_id"]
        reason = serializer.validated_data["reason"]
        branch_id = serializer.validated_data.get("branch_id")

        try:
            result = process_manual_override(
                member_id=member_id,
                gym=tenant,
                reason=reason,
                recorded_by=request.user,
                branch_id=branch_id,
            )
            return Response(result, status=status.HTTP_201_CREATED)
        except ScanValidationError as e:
            data = {
                "detail": e.message,
                "reason": e.reason,
            }
            if e.member:
                data["member"] = {
                    "id": str(e.member.id),
                    "full_name": e.member.full_name,
                    "photo_url": e.member.photo_url or "",
                    "status": e.member.status,
                    "phone": e.member.phone,
                }
            return Response(data, status=status.HTTP_400_BAD_REQUEST)


def _parse_date_range(request):
    """Helper to parse start_date and end_date query parameters."""
    today = timezone.localdate()
    start_str = request.query_params.get("start_date")
    end_str = request.query_params.get("end_date")

    if start_str:
        try:
            start_date = datetime.strptime(start_str, "%Y-%m-%d").date()
        except ValueError:
            start_date = today - timedelta(days=30)
    else:
        start_date = today - timedelta(days=30)

    if end_str:
        try:
            end_date = datetime.strptime(end_str, "%Y-%m-%d").date()
        except ValueError:
            end_date = today
    else:
        end_date = today

    if start_date > end_date:
        start_date, end_date = end_date, start_date

    return start_date, end_date


class GymMemberAttendanceLogView(APIView):
    """
    Staff view for daily member attendance log.

    Returns ✓/✗ per day for date range, derived from check-ins and subscription period.
    """

    permission_classes = [RequirePasswordChanged, CanManageAttendance]

    @extend_schema(
        summary="Get Member Attendance Calendar Log",
        description="Returns daily attendance status (✓ present, ✗ absent, blank outside subscription) for a date range.",
        parameters=[
            OpenApiParameter(
                name="start_date",
                type=str,
                location=OpenApiParameter.QUERY,
                description="Start date (YYYY-MM-DD). Defaults to 30 days ago.",
            ),
            OpenApiParameter(
                name="end_date",
                type=str,
                location=OpenApiParameter.QUERY,
                description="End date (YYYY-MM-DD). Defaults to today.",
            ),
        ],
        responses={200: AttendanceLogResponseSerializer},
    )
    def get(self, request, pk: uuid.UUID):
        tenant = getattr(request, "tenant", None)
        if not tenant:
            raise PermissionDenied("Gym tenant context required.")

        member = (
            Member.all_objects.filter(gym=tenant, id=pk).select_related("gym").first()
        )
        if not member:
            raise NotFound("Member not found.")

        start_date, end_date = _parse_date_range(request)
        log_data = get_member_attendance_log(member, start_date, end_date)
        return Response(log_data, status=status.HTTP_200_OK)


class MemberSelfAttendanceLogView(APIView):
    """
    Member self-service view for daily attendance log.

    Returns ✓/✗ per day for date range, derived from check-ins and subscription period.
    """

    permission_classes = [RequirePasswordChanged, IsMember]

    @extend_schema(
        summary="Get Self Attendance Calendar Log",
        description="Returns member's daily attendance status for a date range.",
        parameters=[
            OpenApiParameter(
                name="start_date",
                type=str,
                location=OpenApiParameter.QUERY,
                description="Start date (YYYY-MM-DD). Defaults to 30 days ago.",
            ),
            OpenApiParameter(
                name="end_date",
                type=str,
                location=OpenApiParameter.QUERY,
                description="End date (YYYY-MM-DD). Defaults to today.",
            ),
        ],
        responses={200: AttendanceLogResponseSerializer},
    )
    def get(self, request):
        tenant = getattr(request, "tenant", None)
        if not tenant:
            raise PermissionDenied("Gym tenant context required.")

        member = (
            Member.all_objects.filter(gym=tenant, user=request.user)
            .select_related("gym")
            .first()
        )
        if not member:
            raise NotFound("Member record not found.")

        start_date, end_date = _parse_date_range(request)
        log_data = get_member_attendance_log(member, start_date, end_date)
        return Response(log_data, status=status.HTTP_200_OK)
