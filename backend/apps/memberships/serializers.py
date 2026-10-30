from typing import Optional

from rest_framework import serializers

from apps.accounts.models import User
from apps.core.validators import (
    validate_and_normalize_phone,
    validate_bicep,
    validate_body_fat_percentage,
    validate_calf,
    validate_chest,
    validate_date_of_birth,
    validate_email_address,
    validate_height,
    validate_hip,
    validate_name,
    validate_neck,
    validate_resting_heart_rate,
    validate_text_length,
    validate_thigh,
    validate_waist,
    validate_weight,
)
from apps.memberships.models import (
    BodyMetrics,
    Member,
    MemberFreeze,
    MembershipPlan,
)


class BodyMetricsSerializer(serializers.ModelSerializer):
    """
    Serializer for member body composition metrics.
    Exposes BMI, US Navy body-fat estimates, waist-to-hip ratio, and lean body mass,
    along with recording trainer information and correction status.
    """

    estimated_bmi = serializers.FloatField(read_only=True)
    estimated_body_fat_percentage = serializers.FloatField(read_only=True)
    waist_to_hip_ratio = serializers.FloatField(read_only=True)
    lean_body_mass = serializers.FloatField(read_only=True)
    lean_body_mass_label = serializers.CharField(read_only=True)
    is_corrected = serializers.SerializerMethodField()
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
            "waist_to_hip_ratio",
            "lean_body_mass",
            "lean_body_mass_label",
            "is_corrected",
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
            "waist_to_hip_ratio",
            "lean_body_mass",
            "lean_body_mass_label",
            "is_corrected",
        ]

    def get_is_corrected(self, obj: BodyMetrics) -> bool:
        if not obj.measurements or not isinstance(obj.measurements, dict):
            return False
        return bool(
            obj.measurements.get("is_corrected") or obj.measurements.get("corrected")
        )

    def get_bmi_label(self, obj: BodyMetrics) -> str:
        return "estimate"

    def get_body_fat_label(self, obj: BodyMetrics) -> str:
        if (
            obj.measurements
            and isinstance(obj.measurements, dict)
            and obj.measurements.get("body_fat_percentage") is not None
        ):
            return "measured"
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
    invitation_status = serializers.SerializerMethodField()
    email_delivery_message = serializers.SerializerMethodField()
    assigned_trainer = serializers.SerializerMethodField(read_only=True)
    is_on_trainer_plan = serializers.SerializerMethodField(read_only=True)
    is_on_trainer_plan = serializers.SerializerMethodField(read_only=True)

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
            "invitation_status",
            "email_delivery_message",
            "assigned_trainer",
            "is_on_trainer_plan",
        ]
        read_only_fields = [
            "id",
            "email",
            "status",
            "joined_at",
            "waiver_accepted_at",
            "latest_metrics",
            "invitation_status",
            "email_delivery_message",
            "assigned_trainer",
        ]

    def get_invitation_status(self, obj) -> Optional[str]:
        request = self.context.get("request")
        user = getattr(request, "user", None) if request else None

        # Tenancy check: Item 12 - "Email not delivered" is visible only to staff of the same gym
        is_same_gym_staff = bool(
            user
            and user.is_authenticated
            and (
                user.role == User.ROLE_SUPER_ADMIN
                or (
                    user.gym_id
                    and obj.gym_id
                    and user.gym_id == obj.gym_id
                    and user.role
                    in (User.ROLE_OWNER, User.ROLE_MANAGER, User.ROLE_RECEPTION)
                )
            )
        )
        if not is_same_gym_staff:
            return None

        member_user = getattr(obj, "user", None)
        if member_user and member_user.has_usable_password():
            return "activated"

        if member_user and member_user.email:
            from apps.accounts.models import EmailDeliveryStatus

            record = EmailDeliveryStatus.all_objects.filter(
                email=member_user.email.strip().lower(),
                gym_id=obj.gym_id,
            ).first()
            if record and record.status in (
                EmailDeliveryStatus.STATUS_NOT_DELIVERED,
                EmailDeliveryStatus.STATUS_SUPPRESSED,
            ):
                return "not_delivered"

        return "sent"

    def get_email_delivery_message(self, obj) -> Optional[str]:
        if self.get_invitation_status(obj) == "not_delivered":
            return "Fix the address and resend"
        return None

    def get_assigned_trainer(self, obj):
        active_assignment = (
            obj.trainer_assignments.filter(ended_at__isnull=True)
            .select_related("trainer__user")
            .first()
        )
        if active_assignment and active_assignment.trainer:
            t_user = active_assignment.trainer.user
            return {
                "id": str(active_assignment.trainer.id),
                "name": t_user.full_name or t_user.email,
                "specialization": active_assignment.trainer.specialization or "",
                "photo_url": active_assignment.trainer.photo_url or "",
            }
        return None

    def get_is_on_trainer_plan(self, obj) -> bool:
        sub = obj.active_subscription
        return bool(sub and sub.plan and sub.plan.has_trainer)

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

        active_assignment = (
            instance.trainer_assignments.filter(ended_at__isnull=True)
            .select_related("trainer__user")
            .first()
        )
        if active_assignment and active_assignment.trainer:
            t_user = active_assignment.trainer.user
            data["assigned_trainer"] = {
                "id": str(active_assignment.trainer.id),
                "name": t_user.full_name or t_user.email,
                "specialization": active_assignment.trainer.specialization or "",
                "photo_url": active_assignment.trainer.photo_url or "",
            }
        else:
            data["assigned_trainer"] = None

        active_sub = instance.active_subscription
        data["is_on_trainer_plan"] = bool(
            active_sub and active_sub.plan and active_sub.plan.has_trainer
        )

        return data


class MemberDetailSerializer(serializers.ModelSerializer):
    """Detailed member profile including historical body metrics and calculations."""

    email = serializers.EmailField(source="user.email", read_only=True)
    latest_metrics = BodyMetricsSerializer(read_only=True)
    body_metrics = BodyMetricsSerializer(many=True, read_only=True)
    assigned_trainer = serializers.SerializerMethodField(read_only=True)
    is_on_trainer_plan = serializers.SerializerMethodField(read_only=True)

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
            "assigned_trainer",
            "is_on_trainer_plan",
        ]
        read_only_fields = [
            "id",
            "email",
            "status",
            "joined_at",
            "waiver_accepted_at",
            "latest_metrics",
            "body_metrics",
            "assigned_trainer",
        ]

    def get_assigned_trainer(self, obj):
        active_assignment = (
            obj.trainer_assignments.filter(ended_at__isnull=True)
            .select_related("trainer__user")
            .first()
        )
        if active_assignment and active_assignment.trainer:
            t_user = active_assignment.trainer.user
            return {
                "id": str(active_assignment.trainer.id),
                "name": t_user.full_name or t_user.email,
                "specialization": active_assignment.trainer.specialization or "",
                "photo_url": active_assignment.trainer.photo_url or "",
            }
        return None

    def get_is_on_trainer_plan(self, obj) -> bool:
        sub = obj.active_subscription
        return bool(sub and sub.plan and sub.plan.has_trainer)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get("request")
        user = getattr(request, "user", None) if request else None
        role = getattr(user, "role", None) if user and user.is_authenticated else None

        # Reception and Super Admin see no measurements anywhere
        if role in (User.ROLE_RECEPTION, User.ROLE_SUPER_ADMIN):
            data["latest_metrics"] = None
            data["body_metrics"] = []

        active_assignment = (
            instance.trainer_assignments.filter(ended_at__isnull=True)
            .select_related("trainer__user")
            .first()
        )
        if active_assignment and active_assignment.trainer:
            t_user = active_assignment.trainer.user
            data["assigned_trainer"] = {
                "id": str(active_assignment.trainer.id),
                "name": t_user.full_name or t_user.email,
                "specialization": active_assignment.trainer.specialization,
            }
        else:
            data["assigned_trainer"] = None

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
        required=True,
    )
    emergency_contact = serializers.CharField(
        max_length=50,
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
            return validate_and_normalize_phone(value)
        return ""


class StaffMemberRegistrationSerializer(serializers.Serializer):
    """
    Serializer for staff-assisted member registration (Owner, Manager, Reception).
    Does not require a password; generates set-password invite link instead.
    Integrates optional upfront payment (Cash, Bank transfer, or None).
    """

    full_name = serializers.CharField(max_length=150, required=True)
    email = serializers.EmailField(max_length=255, required=True)
    phone = serializers.CharField(max_length=50, required=True)
    waiver_accepted = serializers.BooleanField(required=True)
    date_of_birth = serializers.DateField(required=False, allow_null=True)
    gender = serializers.ChoiceField(
        choices=Member.GENDER_CHOICES,
        required=True,
    )
    emergency_contact = serializers.CharField(
        max_length=50,
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
    payment_method = serializers.ChoiceField(
        choices=["cash", "bank_transfer", "none", "no_payment"],
        required=False,
        default="none",
    )
    plan_id = serializers.UUIDField(required=False, allow_null=True)
    idempotency_key = serializers.CharField(
        max_length=255, required=False, allow_blank=True
    )
    notes = serializers.CharField(max_length=500, required=False, allow_blank=True)
    bank_reference = serializers.CharField(
        max_length=100, required=False, allow_blank=True
    )
    transfer_date = serializers.DateField(required=False, allow_null=True)
    channel = serializers.CharField(max_length=50, required=False, allow_blank=True)
    screenshot = serializers.FileField(required=False, allow_null=True)

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
            return validate_and_normalize_phone(value)
        return ""

    def validate(self, attrs):
        method = attrs.get("payment_method") or "none"
        if method in ("cash", "bank_transfer"):
            if not attrs.get("plan_id"):
                raise serializers.ValidationError(
                    {
                        "plan_id": [
                            "Active membership plan is required when recording payment."
                        ]
                    }
                )
        if method == "bank_transfer":
            if not attrs.get("bank_reference"):
                raise serializers.ValidationError(
                    {
                        "bank_reference": [
                            "Bank reference is required for bank transfer."
                        ]
                    }
                )
            if not attrs.get("transfer_date"):
                raise serializers.ValidationError(
                    {"transfer_date": ["Transfer date is required for bank transfer."]}
                )
        return attrs


class VerifyEmailRequestSerializer(serializers.Serializer):
    """Serializer for email verification request."""

    token = serializers.CharField(max_length=128, required=True)


class MemberUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating member profile details by gym staff."""

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
            return validate_and_normalize_phone(value)
        return ""

    def validate_gender(self, value):
        if value and value not in (Member.GENDER_FEMALE, Member.GENDER_MALE):
            raise serializers.ValidationError("Gender must be either Female or Male.")
        return value


class RecordBodyMetricsSerializer(serializers.Serializer):
    """
    Serializer for recording or correcting body metrics entries by a Trainer.
    Weight (kg) and height (cm) are required on new records; all circumference
    and vitals measurements are optional.
    """

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
    chest_cm = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        required=False,
        allow_null=True,
    )
    bicep_left_cm = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        required=False,
        allow_null=True,
    )
    bicep_right_cm = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        required=False,
        allow_null=True,
    )
    thigh_left_cm = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        required=False,
        allow_null=True,
    )
    thigh_right_cm = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        required=False,
        allow_null=True,
    )
    calf_left_cm = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        required=False,
        allow_null=True,
    )
    calf_right_cm = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        required=False,
        allow_null=True,
    )
    resting_heart_rate = serializers.IntegerField(
        required=False,
        allow_null=True,
    )
    body_fat_percentage = serializers.DecimalField(
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
        if value is not None:
            return validate_weight(value)
        return value

    def validate_height_cm(self, value):
        if value is not None:
            return validate_height(value)
        return value

    def validate_waist_cm(self, value):
        return validate_waist(value)

    def validate_neck_cm(self, value):
        return validate_neck(value)

    def validate_hip_cm(self, value):
        return validate_hip(value)

    def validate_chest_cm(self, value):
        return validate_chest(value)

    def validate_bicep_left_cm(self, value):
        return validate_bicep(value)

    def validate_bicep_right_cm(self, value):
        return validate_bicep(value)

    def validate_thigh_left_cm(self, value):
        return validate_thigh(value)

    def validate_thigh_right_cm(self, value):
        return validate_thigh(value)

    def validate_calf_left_cm(self, value):
        return validate_calf(value)

    def validate_calf_right_cm(self, value):
        return validate_calf(value)

    def validate_resting_heart_rate(self, value):
        return validate_resting_heart_rate(value)

    def validate_body_fat_percentage(self, value):
        return validate_body_fat_percentage(value)

    def validate(self, attrs):
        # Also validate fields passed within measurements dict if provided
        meas = attrs.get("measurements")
        if meas and isinstance(meas, dict):
            if "chest_cm" in meas and attrs.get("chest_cm") is None:
                attrs["chest_cm"] = validate_chest(meas["chest_cm"])
            if "bicep_left_cm" in meas and attrs.get("bicep_left_cm") is None:
                attrs["bicep_left_cm"] = validate_bicep(meas["bicep_left_cm"])
            if "bicep_right_cm" in meas and attrs.get("bicep_right_cm") is None:
                attrs["bicep_right_cm"] = validate_bicep(meas["bicep_right_cm"])
            if "thigh_left_cm" in meas and attrs.get("thigh_left_cm") is None:
                attrs["thigh_left_cm"] = validate_thigh(meas["thigh_left_cm"])
            if "thigh_right_cm" in meas and attrs.get("thigh_right_cm") is None:
                attrs["thigh_right_cm"] = validate_thigh(meas["thigh_right_cm"])
            if "calf_left_cm" in meas and attrs.get("calf_left_cm") is None:
                attrs["calf_left_cm"] = validate_calf(meas["calf_left_cm"])
            if "calf_right_cm" in meas and attrs.get("calf_right_cm") is None:
                attrs["calf_right_cm"] = validate_calf(meas["calf_right_cm"])
            if "resting_heart_rate" in meas and attrs.get("resting_heart_rate") is None:
                attrs["resting_heart_rate"] = validate_resting_heart_rate(
                    meas["resting_heart_rate"]
                )
            if (
                "body_fat_percentage" in meas
                and attrs.get("body_fat_percentage") is None
            ):
                attrs["body_fat_percentage"] = validate_body_fat_percentage(
                    meas["body_fat_percentage"]
                )
        return attrs


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


class MemberFreezeRequestSerializer(serializers.Serializer):
    """Request serializer for submitting a membership freeze."""

    start_date = serializers.DateField(
        required=True,
        help_text="First day of membership freeze.",
    )
    end_date = serializers.DateField(
        required=True,
        help_text="Last day of membership freeze.",
    )
    reason = serializers.CharField(
        required=True,
        min_length=5,
        max_length=500,
        help_text="Reason for the freeze request (5 to 500 characters).",
    )


class MemberFreezeRejectSerializer(serializers.Serializer):
    """Request serializer for rejecting a membership freeze."""

    rejection_reason = serializers.CharField(
        required=True,
        min_length=5,
        max_length=500,
        help_text="Explanation for rejecting the freeze request (5 to 500 characters).",
    )


class MemberFreezeSerializer(serializers.ModelSerializer):
    """Detailed read serializer for MemberFreeze records."""

    member = serializers.SerializerMethodField()
    member_name = serializers.CharField(source="member.full_name", read_only=True)
    member_phone = serializers.CharField(source="member.phone", read_only=True)
    approved_by_name = serializers.SerializerMethodField()

    class Meta:
        model = MemberFreeze
        fields = [
            "id",
            "member",
            "member_id",
            "member_name",
            "member_phone",
            "subscription_id",
            "start_date",
            "end_date",
            "days",
            "reason",
            "status",
            "approved_by_id",
            "approved_by_name",
            "reviewed_at",
            "rejection_reason",
            "extension_applied",
            "unfrozen_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_member(self, obj):
        if obj.member:
            return {
                "id": str(obj.member.id),
                "full_name": obj.member.full_name or "",
                "phone": obj.member.phone or "",
            }
        return None

    def get_approved_by_name(self, obj) -> str:
        if obj.approved_by:
            return obj.approved_by.full_name or obj.approved_by.email
        return ""


class MemberFreezeAllowanceSerializer(serializers.Serializer):
    """Read serializer for member freeze allowance."""

    total_allowed = serializers.IntegerField()
    used_days = serializers.IntegerField()
    remaining_days = serializers.IntegerField()
    has_active_subscription = serializers.BooleanField()
    freeze_allowed = serializers.BooleanField()
    subscription_id = serializers.CharField(required=False, allow_null=True)
