"""Serializers for member profiles, registration, body composition metrics, and email verification."""

from rest_framework import serializers

from apps.accounts.models import User
from apps.memberships.models import BodyMetrics, Member


class BodyMetricsSerializer(serializers.ModelSerializer):
    """
    Serializer for member body composition metrics.
    Exposes BMI and US Navy body-fat estimates, explicitly labeled as estimates,
    along with recording trainer information.
    """

    estimated_bmi = serializers.FloatField(read_only=True)
    estimated_body_fat_percentage = serializers.FloatField(read_only=True)
    bmi_label = serializers.SerializerMethodField()
    body_fat_label = serializers.SerializerMethodField()
    trainer_name = serializers.SerializerMethodField()
    recorded_by_name = serializers.SerializerMethodField()

    class Meta:
        model = BodyMetrics
        fields = [
            "id",
            "weight_kg",
            "height_cm",
            "measurements",
            "recorded_at",
            "recorded_by",
            "trainer_name",
            "recorded_by_name",
            "estimated_bmi",
            "estimated_body_fat_percentage",
            "bmi_label",
            "body_fat_label",
        ]
        read_only_fields = [
            "id",
            "recorded_at",
            "recorded_by",
            "trainer_name",
            "recorded_by_name",
            "estimated_bmi",
            "estimated_body_fat_percentage",
            "bmi_label",
            "body_fat_label",
        ]

    def get_bmi_label(self, obj: BodyMetrics) -> str:
        return "estimate"

    def get_body_fat_label(self, obj: BodyMetrics) -> str:
        return "estimate"

    def get_trainer_name(self, obj: BodyMetrics) -> str:
        if obj.recorded_by:
            return obj.recorded_by.full_name
        return ""

    def get_recorded_by_name(self, obj: BodyMetrics) -> str:
        return self.get_trainer_name(obj)


class MemberSerializer(serializers.ModelSerializer):
    """Summary serializer for gym members."""

    email = serializers.EmailField(source="user.email", read_only=True)
    latest_metrics = BodyMetricsSerializer(read_only=True)

    class Meta:
        model = Member
        fields = [
            "id",
            "email",
            "full_name",
            "phone",
            "date_of_birth",
            "gender",
            "emergency_contact",
            "referral_source",
            "photo_url",
            "status",
            "joined_at",
            "waiver_accepted_at",
            "latest_metrics",
        ]
        read_only_fields = [
            "id",
            "email",
            "joined_at",
            "waiver_accepted_at",
            "latest_metrics",
        ]

    def to_representation(self, instance):
        request = self.context.get("request")
        user = getattr(request, "user", None) if request else None
        role = getattr(user, "role", None) if user and user.is_authenticated else None

        # Trainer search: minimal version returning only name, email and phone (no photo, etc.)
        if role == User.ROLE_TRAINER:
            return {
                "id": str(instance.id),
                "full_name": instance.full_name,
                "email": instance.user.email if instance.user else "",
                "phone": instance.phone,
            }

        data = super().to_representation(instance)
        # Reception and Super Admin see no measurements anywhere
        if role in (User.ROLE_RECEPTION, User.ROLE_SUPER_ADMIN):
            data["latest_metrics"] = None

        return data


class MemberDetailSerializer(serializers.ModelSerializer):
    """Detailed member profile including historical body metrics and calculations."""

    email = serializers.EmailField(source="user.email", read_only=True)
    latest_metrics = BodyMetricsSerializer(read_only=True)
    body_metrics = BodyMetricsSerializer(many=True, read_only=True)

    class Meta:
        model = Member
        fields = [
            "id",
            "email",
            "full_name",
            "phone",
            "date_of_birth",
            "gender",
            "emergency_contact",
            "referral_source",
            "photo_url",
            "status",
            "joined_at",
            "waiver_accepted_at",
            "latest_metrics",
            "body_metrics",
        ]
        read_only_fields = [
            "id",
            "email",
            "joined_at",
            "waiver_accepted_at",
            "latest_metrics",
            "body_metrics",
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get("request")
        user = getattr(request, "user", None) if request else None
        role = getattr(user, "role", None) if user and user.is_authenticated else None

        # Reception and Super Admin see no measurements anywhere
        if role in (User.ROLE_RECEPTION, User.ROLE_SUPER_ADMIN):
            data["latest_metrics"] = None
            data["body_metrics"] = []

        return data


class PublicMemberRegistrationSerializer(serializers.Serializer):
    """
    Serializer for public self-service registration on gym subdomains.
    Requires health waiver acceptance and password. Registration captures no body measurements.
    """

    full_name = serializers.CharField(max_length=150, required=True)
    email = serializers.EmailField(max_length=255, required=True)
    phone = serializers.CharField(max_length=20, required=True)
    password = serializers.CharField(
        max_length=128,
        write_only=True,
        required=True,
    )
    waiver_accepted = serializers.BooleanField(required=True)
    date_of_birth = serializers.DateField(required=False, allow_null=True)
    gender = serializers.ChoiceField(
        choices=Member.GENDER_CHOICES,
        required=False,
        allow_blank=True,
    )
    emergency_contact = serializers.CharField(
        max_length=255,
        required=False,
        allow_blank=True,
    )
    referral_source = serializers.CharField(
        max_length=100,
        required=False,
        allow_blank=True,
    )
    photo_url = serializers.CharField(
        max_length=255,
        required=False,
        allow_blank=True,
    )


class StaffMemberRegistrationSerializer(serializers.Serializer):
    """
    Serializer for staff-assisted member registration (Owner, Manager, Reception).
    Does not require a password; generates set-password invite link instead.
    Registration captures no body measurements.
    """

    full_name = serializers.CharField(max_length=150, required=True)
    email = serializers.EmailField(max_length=255, required=True)
    phone = serializers.CharField(max_length=20, required=True)
    waiver_accepted = serializers.BooleanField(required=True)
    date_of_birth = serializers.DateField(required=False, allow_null=True)
    gender = serializers.ChoiceField(
        choices=Member.GENDER_CHOICES,
        required=False,
        allow_blank=True,
    )
    emergency_contact = serializers.CharField(
        max_length=255,
        required=False,
        allow_blank=True,
    )
    referral_source = serializers.CharField(
        max_length=100,
        required=False,
        allow_blank=True,
    )
    photo_url = serializers.CharField(
        max_length=255,
        required=False,
        allow_blank=True,
    )


class VerifyEmailRequestSerializer(serializers.Serializer):
    """Serializer for email verification request."""

    token = serializers.CharField(max_length=128, required=True)


class MemberUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating member profile details."""

    class Meta:
        model = Member
        fields = [
            "full_name",
            "phone",
            "date_of_birth",
            "gender",
            "emergency_contact",
            "referral_source",
            "photo_url",
            "status",
        ]


class RecordBodyMetricsSerializer(serializers.Serializer):
    """
    Serializer for recording a new body metrics entry by a Trainer.
    Weight (kg) and height (cm) are required; waist, neck and hip are optional.
    """

    weight_kg = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        required=True,
    )
    height_cm = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        required=True,
    )
    waist_cm = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        required=False,
        allow_null=True,
    )
    neck_cm = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        required=False,
        allow_null=True,
    )
    hip_cm = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        required=False,
        allow_null=True,
    )
    measurements = serializers.DictField(
        required=False,
        allow_null=True,
    )
