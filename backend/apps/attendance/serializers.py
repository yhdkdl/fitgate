"""Serializers for attendance endpoints, QR verification, and manual overrides."""

from rest_framework import serializers


class AttendancePublicKeyResponseSerializer(serializers.Serializer):
    """Response serializer for public key export."""

    public_key = serializers.CharField(
        help_text="PEM-encoded Ed25519 public key for offline QR signature verification."
    )
    algorithm = serializers.CharField(default="EdDSA")


class MemberQrTokenResponseSerializer(serializers.Serializer):
    """Response serializer for member QR token generation."""

    token = serializers.CharField(help_text="Signed EdDSA JWT QR token.")
    expires_at = serializers.DateTimeField(
        help_text="Timestamp when this token expires."
    )
    valid_seconds = serializers.IntegerField(
        default=90, help_text="Token validity window in seconds."
    )
    member_id = serializers.UUIDField()


class AttendanceScanRequestSerializer(serializers.Serializer):
    """Request serializer for QR attendance scan."""

    token = serializers.CharField(
        required=True,
        help_text="Scanned QR token string (EdDSA JWT).",
    )
    branch_id = serializers.UUIDField(
        required=False,
        allow_null=True,
        help_text="Optional branch UUID for multi-branch check-ins.",
    )


class AttendanceScanResultMemberSerializer(serializers.Serializer):
    """Member details returned upon scan."""

    id = serializers.UUIDField()
    full_name = serializers.CharField()
    photo_url = serializers.CharField(allow_blank=True)
    status = serializers.CharField()
    phone = serializers.CharField(allow_blank=True, required=False)


class AttendanceRecordSerializer(serializers.Serializer):
    """Attendance record details."""

    id = serializers.UUIDField()
    date = serializers.DateField()
    checked_in_at = serializers.DateTimeField()
    is_override = serializers.BooleanField()
    override_reason = serializers.CharField(allow_blank=True, required=False)


class AttendanceScanResponseSerializer(serializers.Serializer):
    """Success response serializer for QR scan."""

    status = serializers.CharField(default="success")
    message = serializers.CharField()
    member = AttendanceScanResultMemberSerializer()
    attendance = AttendanceRecordSerializer()
    next_token = serializers.CharField(
        help_text="Newly rotated token issued for the member."
    )


class AttendanceManualOverrideRequestSerializer(serializers.Serializer):
    """Request serializer for manual attendance override by reception."""

    member_id = serializers.UUIDField(
        required=True,
        help_text="UUID of the member to check in.",
    )
    reason = serializers.CharField(
        required=True,
        min_length=1,
        max_length=500,
        help_text="Non-empty explanation for manual override.",
    )
    branch_id = serializers.UUIDField(
        required=False,
        allow_null=True,
        help_text="Optional branch UUID.",
    )

    def validate_reason(self, value: str) -> str:
        clean = value.strip()
        if not clean:
            raise serializers.ValidationError("Reason cannot be blank.")
        return clean


class AttendanceManualOverrideResponseSerializer(serializers.Serializer):
    """Response serializer for manual attendance override."""

    status = serializers.CharField(default="success")
    message = serializers.CharField()
    member = AttendanceScanResultMemberSerializer()
    attendance = AttendanceRecordSerializer()


class DailyAttendanceItemSerializer(serializers.Serializer):
    """Daily check-in status within the calendar log."""

    date = serializers.DateField()
    status = serializers.CharField(help_text="'present', 'absent', or 'blank'")
    symbol = serializers.CharField(
        allow_blank=True, help_text="'✓', '✗', or empty for days outside subscription"
    )
    attended = serializers.BooleanField()
    checked_in_at = serializers.DateTimeField(required=False, allow_null=True)
    is_override = serializers.BooleanField(required=False)


class AttendanceLogResponseSerializer(serializers.Serializer):
    """Response serializer for attendance calendar log."""

    member_id = serializers.UUIDField()
    member_name = serializers.CharField()
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    subscription_period = serializers.DictField()
    days = DailyAttendanceItemSerializer(many=True)


class AttendanceTodayItemSerializer(serializers.Serializer):
    """Entry in Today's Check-ins list."""

    id = serializers.UUIDField()
    member_id = serializers.UUIDField()
    member_name = serializers.CharField()
    member_photo_url = serializers.CharField(allow_blank=True)
    checked_in_at = serializers.DateTimeField()
    is_override = serializers.BooleanField()
    override_reason = serializers.CharField(allow_blank=True, required=False)
    recorded_by_name = serializers.CharField(allow_null=True, required=False)


class AttendanceTodayListResponseSerializer(serializers.Serializer):
    """Response serializer for live Today's Check-ins list."""

    total_count = serializers.IntegerField(
        help_text="Total number of members checked in today."
    )
    results = AttendanceTodayItemSerializer(many=True)
