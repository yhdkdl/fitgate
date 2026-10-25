"""Serializers for member profiles, registration, body composition metrics, and email verification."""

from rest_framework import serializers

from apps.accounts.models import User
from apps.core.validators import (
    validate_and_normalize_phone,
    validate_date_of_birth,
    validate_email_address,
    validate_height,
    validate_hip,
    validate_name,
    validate_neck,
    validate_text_length,
    validate_waist,
    validate_weight,
)
from apps.memberships.models import (
    BodyMetrics,
    Member,
    MembershipPlan,
    MemberSubscription,
)


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
            "status",
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
            "status",
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
    phone = serializers.CharField(max_length=50, required=True)
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

    def validate_full_name(self, value):
        return validate_name(value, "Full name")

    def validate_email(self, value):
        return validate_email_address(value)

    def validate_phone(self, value):
        return validate_and_normalize_phone(value)

    def validate_date_of_birth(self, value):
        if value:
            return validate_date_of_birth(value)
        return value

    def validate_emergency_contact(self, value):
        if value:
            return validate_text_length(value, 2, 255, "Emergency contact")
        return ""


class StaffMemberRegistrationSerializer(serializers.Serializer):
    """
    Serializer for staff-assisted member registration (Owner, Manager, Reception).
    Does not require a password; generates set-password invite link instead.
    Registration captures no body measurements.
    """

    full_name = serializers.CharField(max_length=150, required=True)
    email = serializers.EmailField(max_length=255, required=True)
    phone = serializers.CharField(max_length=50, required=True)
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

    def validate_full_name(self, value):
        return validate_name(value, "Full name")

    def validate_email(self, value):
        return validate_email_address(value)

    def validate_phone(self, value):
        return validate_and_normalize_phone(value)

    def validate_date_of_birth(self, value):
        if value:
            return validate_date_of_birth(value)
        return value

    def validate_emergency_contact(self, value):
        if value:
            return validate_text_length(value, 2, 255, "Emergency contact")
        return ""


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
        ]

    def validate_full_name(self, value):
        if value:
            return validate_name(value, "Full name")
        return ""

    def validate_phone(self, value):
        if value:
            return validate_and_normalize_phone(value)
        return ""

    def validate_date_of_birth(self, value):
        if value:
            return validate_date_of_birth(value)
        return value

    def validate_emergency_contact(self, value):
        if value:
            return validate_text_length(value, 2, 255, "Emergency contact")
        return ""


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

    def validate_weight_kg(self, value):
        return validate_weight(value)

    def validate_height_cm(self, value):
        return validate_height(value)

    def validate_waist_cm(self, value):
        return validate_waist(value)

    def validate_neck_cm(self, value):
        return validate_neck(value)

    def validate_hip_cm(self, value):
        return validate_hip(value)


class MembershipPlanSerializer(serializers.ModelSerializer):
    """Serializer for gym membership plans."""

    warning = serializers.CharField(read_only=True, required=False)
    has_no_trainers_warning = serializers.BooleanField(read_only=True, default=False)

    class Meta:
        model = MembershipPlan
        fields = [
            "id",
            "name",
            "description",
            "duration_value",
            "duration_unit",
            "price_etb",
            "trainer_inclusive",
            "is_active",
            "warning",
            "has_no_trainers_warning",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "warning",
            "has_no_trainers_warning",
            "created_at",
            "updated_at",
        ]

    def validate_name(self, value):
        if not value or not str(value).strip():
            raise serializers.ValidationError("Plan name cannot be blank.")
        return validate_text_length(value.strip(), 2, 100, "Plan name")

    def validate_duration_value(self, value):
        if value is None or int(value) <= 0:
            raise serializers.ValidationError(
                "Duration value must be a positive number greater than 0."
            )
        return int(value)

    def validate_duration_unit(self, value):
        if value not in (
            MembershipPlan.DURATION_DAYS,
            MembershipPlan.DURATION_MONTHS,
        ):
            raise serializers.ValidationError(
                "Duration unit must be either 'days' or 'months'."
            )
        return value

    def validate_price_etb(self, value):
        if value is None or value < 0:
            raise serializers.ValidationError("Price must be 0 or greater.")
        return value


class PublicPlanSerializer(serializers.ModelSerializer):
    """Public read-only serializer for active membership plans."""

    class Meta:
        model = MembershipPlan
        fields = [
            "id",
            "name",
            "description",
            "duration_value",
            "duration_unit",
            "price_etb",
            "trainer_inclusive",
        ]
        read_only_fields = fields


class MemberSuspendRequestSerializer(serializers.Serializer):
    """Request serializer for suspending a member."""

    reason = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=500,
        help_text="Optional reason for suspending member.",
    )


class MemberSubscriptionSerializer(serializers.ModelSerializer):
    """Serializer for member subscriptions."""

    plan_name = serializers.CharField(source="plan.name", read_only=True)

    class Meta:
        model = MemberSubscription
        fields = [
            "id",
            "member",
            "plan",
            "plan_name",
            "start_date",
            "end_date",
            "status",
            "freeze_start_date",
            "frozen_days_total",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "plan_name",
            "created_at",
        ]
