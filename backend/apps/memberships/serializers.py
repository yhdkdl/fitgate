"""Serializers for member profiles, registration, body composition metrics, and email verification."""

from rest_framework import serializers

from apps.memberships.models import BodyMetrics, Member


class BodyMetricsSerializer(serializers.ModelSerializer):
    """
    Serializer for member body composition metrics.
    Exposes BMI and US Navy body-fat estimates, explicitly labeled as estimates.
    """

    estimated_bmi = serializers.FloatField(read_only=True)
    estimated_body_fat_percentage = serializers.FloatField(read_only=True)
    bmi_label = serializers.SerializerMethodField()
    body_fat_label = serializers.SerializerMethodField()

    class Meta:
        model = BodyMetrics
        fields = [
            "id",
            "weight_kg",
            "height_cm",
            "measurements",
            "recorded_at",
            "estimated_bmi",
            "estimated_body_fat_percentage",
            "bmi_label",
            "body_fat_label",
        ]
        read_only_fields = [
            "id",
            "recorded_at",
            "estimated_bmi",
            "estimated_body_fat_percentage",
            "bmi_label",
            "body_fat_label",
        ]

    def get_bmi_label(self, obj: BodyMetrics) -> str:
        return "estimate"

    def get_body_fat_label(self, obj: BodyMetrics) -> str:
        return "estimate"


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


class PublicMemberRegistrationSerializer(serializers.Serializer):
    """
    Serializer for public self-service registration on gym subdomains.
    Requires health waiver acceptance and password.
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
    # Optional body metrics at registration
    weight_kg = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        required=False,
        allow_null=True,
    )
    height_cm = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        required=False,
        allow_null=True,
    )
    measurements = serializers.DictField(
        required=False,
        allow_null=True,
    )


class StaffMemberRegistrationSerializer(serializers.Serializer):
    """
    Serializer for staff-assisted member registration (Owner, Manager, Reception).
    Does not require a password; generates set-password invite link instead.
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
    # Optional body metrics at registration
    weight_kg = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        required=False,
        allow_null=True,
    )
    height_cm = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        required=False,
        allow_null=True,
    )
    measurements = serializers.DictField(
        required=False,
        allow_null=True,
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
    """Serializer for recording a new body metrics entry."""

    weight_kg = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        required=False,
        allow_null=True,
    )
    height_cm = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        required=False,
        allow_null=True,
    )
    measurements = serializers.DictField(
        required=False,
        allow_null=True,
    )
