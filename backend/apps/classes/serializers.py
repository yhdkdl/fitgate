from rest_framework import serializers

from apps.classes.constants import (
    CLASS_DURATION_CHOICES,
    CLASS_TITLE_CHOICES,
    CLASS_TITLE_OTHER,
)
from apps.classes.models import ClassBooking, ClassSession
from apps.memberships.models import Member


class ClassSessionSerializer(serializers.ModelSerializer):
    display_title = serializers.CharField(read_only=True)
    booked_count = serializers.IntegerField(read_only=True)
    spots_remaining = serializers.IntegerField(read_only=True)
    is_full = serializers.BooleanField(read_only=True)
    is_past = serializers.BooleanField(read_only=True)
    trainer_name = serializers.SerializerMethodField()
    trainer_photo_url = serializers.SerializerMethodField()
    user_booking = serializers.SerializerMethodField()

    class Meta:
        model = ClassSession
        fields = [
            "id",
            "title",
            "display_title",
            "other_title",
            "trainer",
            "trainer_name",
            "trainer_photo_url",
            "start_time",
            "duration_minutes",
            "end_time",
            "capacity",
            "status",
            "booked_count",
            "spots_remaining",
            "is_full",
            "is_past",
            "user_booking",
        ]
        read_only_fields = [
            "id",
            "end_time",
            "status",
            "booked_count",
            "spots_remaining",
            "is_full",
            "is_past",
            "user_booking",
        ]

    def get_trainer_name(self, obj) -> str:
        if obj.trainer and obj.trainer.user:
            return obj.trainer.user.full_name or obj.trainer.user.email
        return "Unknown Trainer"

    def get_trainer_photo_url(self, obj) -> str:
        if obj.trainer:
            return obj.trainer.photo_url or ""
        return ""

    def get_user_booking(self, obj):
        request = self.context.get("request")
        if not request or not request.user or not request.user.is_authenticated:
            return None
        # Check if user is a member
        member = getattr(request.user, "member_profile", None)
        if not member:
            return None
        booking = obj.bookings.filter(member=member, status="booked").first()
        if booking:
            return {
                "id": str(booking.id),
                "status": booking.status,
                "attended": booking.attended,
                "created_at": booking.created_at.isoformat(),
            }
        return None


class ClassSessionCreateSerializer(serializers.Serializer):
    title = serializers.ChoiceField(choices=CLASS_TITLE_CHOICES)
    other_title = serializers.CharField(
        max_length=50, required=False, allow_blank=True, default=""
    )
    trainer_id = serializers.UUIDField()
    start_time = serializers.DateTimeField()
    duration_minutes = serializers.ChoiceField(
        choices=CLASS_DURATION_CHOICES, default=60
    )
    capacity = serializers.IntegerField(min_value=1, max_value=200, default=20)
    repeat_weeks = serializers.IntegerField(min_value=1, max_value=12, default=1)

    def validate(self, attrs):
        title = attrs.get("title")
        other_title = attrs.get("other_title", "").strip()
        if title == CLASS_TITLE_OTHER and not other_title:
            raise serializers.ValidationError(
                {"other_title": "Custom title is required when title is Other."}
            )
        return attrs


class ClassSessionUpdateSerializer(serializers.Serializer):
    title = serializers.ChoiceField(choices=CLASS_TITLE_CHOICES, required=False)
    other_title = serializers.CharField(max_length=50, required=False, allow_blank=True)
    trainer_id = serializers.UUIDField(required=False)
    start_time = serializers.DateTimeField(required=False)
    duration_minutes = serializers.ChoiceField(
        choices=CLASS_DURATION_CHOICES, required=False
    )
    capacity = serializers.IntegerField(min_value=1, max_value=200, required=False)


class ClassRosterMemberSerializer(serializers.ModelSerializer):
    email = serializers.SerializerMethodField()
    photo_url = serializers.SerializerMethodField()

    class Meta:
        model = Member
        fields = [
            "id",
            "full_name",
            "phone",
            "email",
            "photo_url",
            "status",
        ]

    def get_email(self, obj) -> str:
        if obj.user:
            return obj.user.email
        return ""

    def get_photo_url(self, obj) -> str:
        return obj.photo_url or ""


class ClassBookingSerializer(serializers.ModelSerializer):
    member = ClassRosterMemberSerializer(read_only=True)
    session_title = serializers.CharField(
        source="session.display_title", read_only=True
    )
    session_start_time = serializers.DateTimeField(
        source="session.start_time", read_only=True
    )
    session_end_time = serializers.DateTimeField(
        source="session.end_time", read_only=True
    )
    session_duration_minutes = serializers.IntegerField(
        source="session.duration_minutes", read_only=True
    )
    session_status = serializers.CharField(source="session.status", read_only=True)
    trainer_name = serializers.SerializerMethodField()

    class Meta:
        model = ClassBooking
        fields = [
            "id",
            "session",
            "session_title",
            "session_start_time",
            "session_end_time",
            "session_duration_minutes",
            "session_status",
            "trainer_name",
            "member",
            "status",
            "attended",
            "marked_at",
            "created_at",
        ]
        read_only_fields = fields

    def get_trainer_name(self, obj) -> str:
        if obj.session and obj.session.trainer and obj.session.trainer.user:
            return obj.session.trainer.user.full_name or obj.session.trainer.user.email
        return "Unknown"


class BookClassSerializer(serializers.Serializer):
    member_id = serializers.UUIDField(required=False, allow_null=True)


class MarkAttendanceSerializer(serializers.Serializer):
    member_id = serializers.UUIDField()
    attended = serializers.BooleanField(default=True)
