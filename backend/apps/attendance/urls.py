"""URL routing for attendance, QR token, and check-in endpoints."""

from django.urls import path

from apps.attendance.views import (
    AttendanceManualOverrideView,
    AttendancePublicKeyView,
    AttendanceScanView,
    GymMemberAttendanceLogView,
    MemberQrTokenView,
    MemberSelfAttendanceLogView,
)

urlpatterns = [
    # Public key for offline signature verification
    path(
        "api/attendance/public-key/",
        AttendancePublicKeyView.as_view(),
        name="attendance-public-key",
    ),
    # Member QR token issuance & rotation
    path(
        "api/members/me/qr-token/",
        MemberQrTokenView.as_view(),
        name="member-me-qr-token",
    ),
    # Staff scan and manual override
    path(
        "api/gym/attendance/scan/",
        AttendanceScanView.as_view(),
        name="gym-attendance-scan",
    ),
    path(
        "api/gym/attendance/manual-override/",
        AttendanceManualOverrideView.as_view(),
        name="gym-attendance-manual-override",
    ),
    # Daily attendance calendar logs
    path(
        "api/gym/members/<uuid:pk>/attendance/",
        GymMemberAttendanceLogView.as_view(),
        name="gym-member-attendance-log",
    ),
    path(
        "api/members/me/attendance/",
        MemberSelfAttendanceLogView.as_view(),
        name="member-me-attendance-log",
    ),
]
