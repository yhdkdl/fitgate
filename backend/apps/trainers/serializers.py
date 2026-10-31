from rest_framework import serializers

from apps.accounts.models import User
from apps.trainers.models import Trainer, TrainerAssignment


class TrainerUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "full_name", "phone", "is_active"]
        read_only_fields = fields


class TrainerSerializer(serializers.ModelSerializer):
    user = TrainerUserSerializer(read_only=True)
    max_clients = serializers.IntegerField(min_value=1, max_value=100, required=True)
    client_count = serializers.IntegerField(read_only=True)
    photo_url = serializers.CharField(read_only=True, required=False, allow_blank=True)

    class Meta:
        model = Trainer
        fields = [
            "id",
            "user",
            "photo_url",
            "specialization",
            "max_clients",
            "client_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "user",
            "client_count",
            "created_at",
            "updated_at",
        ]


class TrainerCapacityUpdateSerializer(serializers.Serializer):
    max_clients = serializers.IntegerField(
        min_value=1,
        max_value=100,
        required=True,
        error_messages={
            "min_value": "Maximum clients must be between 1 and 100.",
            "max_value": "Maximum clients must be between 1 and 100.",
            "invalid": "A valid integer is required.",
        },
    )
    specialization = serializers.CharField(
        max_length=255,
        required=False,
        allow_blank=True,
        allow_null=True,
    )


class TrainerCapacityUpdateResponseSerializer(serializers.Serializer):
    detail = serializers.CharField()
    warning = serializers.CharField(allow_null=True, required=False)
    trainer = TrainerSerializer()


class AssignmentMemberSummarySerializer(serializers.Serializer):
    id = serializers.UUIDField()
    full_name = serializers.CharField()
    phone = serializers.CharField()
    status = serializers.CharField()
    plan_name = serializers.CharField(allow_null=True)


class TrainerAssignmentDetailSerializer(serializers.ModelSerializer):
    member = serializers.SerializerMethodField()
    trainer = TrainerSerializer(read_only=True)
    assigned_by = TrainerUserSerializer(read_only=True)

    class Meta:
        model = TrainerAssignment
        fields = [
            "id",
            "member",
            "trainer",
            "assigned_at",
            "ended_at",
            "assigned_by",
        ]

    def get_member(self, obj):
        active_sub = (
            obj.member.gym.memberships_membersubscriptions.filter(
                member=obj.member,
                status="active",
            )
            .order_by("-end_date")
            .first()
        )
        return {
            "id": str(obj.member.id),
            "full_name": obj.member.full_name,
            "phone": obj.member.phone,
            "status": obj.member.status,
            "plan_name": active_sub.plan.name if active_sub else "—",
        }


class TrainerMyClientSerializer(serializers.Serializer):
    assignment_id = serializers.UUIDField()
    member_id = serializers.UUIDField()
    member_name = serializers.CharField()
    member_phone = serializers.CharField()
    photo_url = serializers.CharField(allow_blank=True, default="")
    plan_name = serializers.CharField()
    assigned_at = serializers.DateTimeField()
    has_measurements = serializers.BooleanField(default=False)


class UnassignedMemberSerializer(serializers.Serializer):
    member_id = serializers.UUIDField()
    full_name = serializers.CharField()
    phone = serializers.CharField()
    status = serializers.CharField()
    plan_name = serializers.CharField()
    subscription_id = serializers.UUIDField()
    start_date = serializers.DateField()
    end_date = serializers.DateField()


class ManualReassignRequestSerializer(serializers.Serializer):
    member_id = serializers.UUIDField(required=True)
    trainer_id = serializers.UUIDField(required=True)
    confirm_over_capacity = serializers.BooleanField(default=False, required=False)


class ManualReassignResponseSerializer(serializers.Serializer):
    detail = serializers.CharField()
    assignment = TrainerAssignmentDetailSerializer()


class LatestMeasurementsSummarySerializer(serializers.Serializer):
    weight_kg = serializers.DecimalField(
        max_digits=5, decimal_places=2, allow_null=True
    )
    height_cm = serializers.DecimalField(
        max_digits=5, decimal_places=2, allow_null=True
    )
    waist_cm = serializers.DecimalField(
        max_digits=5, decimal_places=2, allow_null=True, required=False
    )
    neck_cm = serializers.DecimalField(
        max_digits=5, decimal_places=2, allow_null=True, required=False
    )
    hip_cm = serializers.DecimalField(
        max_digits=5, decimal_places=2, allow_null=True, required=False
    )
    chest_cm = serializers.DecimalField(
        max_digits=5, decimal_places=2, allow_null=True, required=False
    )
    bicep_left_cm = serializers.DecimalField(
        max_digits=5, decimal_places=2, allow_null=True, required=False
    )
    bicep_right_cm = serializers.DecimalField(
        max_digits=5, decimal_places=2, allow_null=True, required=False
    )
    thigh_left_cm = serializers.DecimalField(
        max_digits=5, decimal_places=2, allow_null=True, required=False
    )
    thigh_right_cm = serializers.DecimalField(
        max_digits=5, decimal_places=2, allow_null=True, required=False
    )
    calf_left_cm = serializers.DecimalField(
        max_digits=5, decimal_places=2, allow_null=True, required=False
    )
    calf_right_cm = serializers.DecimalField(
        max_digits=5, decimal_places=2, allow_null=True, required=False
    )
    resting_heart_rate = serializers.IntegerField(allow_null=True, required=False)
    body_fat_percentage = serializers.DecimalField(
        max_digits=4, decimal_places=2, allow_null=True, required=False
    )
    lean_body_mass_kg = serializers.DecimalField(
        max_digits=5, decimal_places=2, allow_null=True, required=False
    )
    bmi = serializers.DecimalField(
        max_digits=4, decimal_places=2, allow_null=True, required=False
    )
    recorded_at = serializers.DateTimeField(allow_null=True)


class FitnessProfileSerializer(serializers.ModelSerializer):
    member_id = serializers.UUIDField(source="member.id", read_only=True)
    goal = serializers.CharField(required=True)
    fitness_level = serializers.CharField(required=True)
    health_limitations = serializers.ListField(
        child=serializers.CharField(), required=True
    )
    other_limitations = serializers.CharField(
        required=False, allow_blank=True, max_length=200, default=""
    )
    equipment_access = serializers.ListField(
        child=serializers.CharField(), required=True
    )
    other_equipment = serializers.CharField(
        required=False, allow_blank=True, max_length=200, default=""
    )
    training_days_per_week = serializers.IntegerField(required=True)
    session_length_minutes = serializers.IntegerField(required=True)
    dietary_notes = serializers.ListField(child=serializers.CharField(), required=True)
    other_dietary = serializers.CharField(
        required=False, allow_blank=True, max_length=200, default=""
    )
    has_medical_caution = serializers.BooleanField(read_only=True)
    latest_measurements = serializers.SerializerMethodField()

    class Meta:
        from apps.trainers.models import FitnessProfile

        model = FitnessProfile
        fields = [
            "member_id",
            "goal",
            "fitness_level",
            "health_limitations",
            "other_limitations",
            "equipment_access",
            "other_equipment",
            "training_days_per_week",
            "session_length_minutes",
            "dietary_notes",
            "other_dietary",
            "has_medical_caution",
            "latest_measurements",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "member_id",
            "has_medical_caution",
            "created_at",
            "updated_at",
            "latest_measurements",
        ]

    def validate(self, attrs):
        from apps.core.validators import (
            validate_dietary_choices,
            validate_equipment_access,
            validate_health_limitations,
        )

        try:
            limits, other_limits = validate_health_limitations(
                attrs.get("health_limitations"), attrs.get("other_limitations")
            )
            attrs["health_limitations"] = limits
            attrs["other_limitations"] = other_limits
        except Exception as e:
            msg = getattr(e, "message", getattr(e, "messages", str(e)))
            if isinstance(msg, list):
                msg = msg[0]
            raise serializers.ValidationError({"health_limitations": msg})

        try:
            equip, other_equip = validate_equipment_access(
                attrs.get("equipment_access"), attrs.get("other_equipment")
            )
            attrs["equipment_access"] = equip
            attrs["other_equipment"] = other_equip
        except Exception as e:
            msg = getattr(e, "message", getattr(e, "messages", str(e)))
            if isinstance(msg, list):
                msg = msg[0]
            raise serializers.ValidationError({"equipment_access": msg})

        try:
            diet, other_diet = validate_dietary_choices(
                attrs.get("dietary_notes"), attrs.get("other_dietary")
            )
            attrs["dietary_notes"] = diet
            attrs["other_dietary"] = other_diet
        except Exception as e:
            msg = getattr(e, "message", getattr(e, "messages", str(e)))
            if isinstance(msg, list):
                msg = msg[0]
            raise serializers.ValidationError({"dietary_notes": msg})

        return attrs

    def validate_goal(self, value):
        from apps.core.validators import validate_goal

        try:
            return validate_goal(value)
        except Exception as e:
            detail = getattr(e, "detail", getattr(e, "messages", str(e)))
            if isinstance(detail, list):
                detail = detail[0]
            raise serializers.ValidationError(detail)

    def validate_fitness_level(self, value):
        from apps.core.validators import validate_fitness_level

        try:
            return validate_fitness_level(value)
        except Exception as e:
            detail = getattr(e, "detail", getattr(e, "messages", str(e)))
            if isinstance(detail, list):
                detail = detail[0]
            raise serializers.ValidationError(detail)

    def validate_training_days_per_week(self, value):
        from apps.core.validators import validate_training_days_per_week

        try:
            return validate_training_days_per_week(value)
        except Exception as e:
            detail = getattr(e, "detail", getattr(e, "messages", str(e)))
            if isinstance(detail, list):
                detail = detail[0]
            raise serializers.ValidationError(detail)

    def validate_session_length_minutes(self, value):
        from apps.core.validators import validate_session_length

        try:
            return validate_session_length(value)
        except Exception as e:
            detail = getattr(e, "detail", getattr(e, "messages", str(e)))
            if isinstance(detail, list):
                detail = detail[0]
            raise serializers.ValidationError(detail)

    def get_latest_measurements(self, obj):
        from apps.memberships.models import BodyMetrics

        member = obj.member
        latest = (
            BodyMetrics.objects.filter(member=member, gym_id=obj.gym_id)
            .order_by("-recorded_at")
            .first()
        )
        if not latest:
            return None
        measurements = latest.measurements or {}
        weight_kg = latest.weight_kg
        height_cm = latest.height_cm
        body_fat = measurements.get("body_fat_percentage")
        lean_mass = None
        if weight_kg is not None and body_fat is not None:
            try:
                lean_mass = round(float(weight_kg) * (1 - float(body_fat) / 100), 2)
            except (ValueError, TypeError):
                lean_mass = None
        bmi = None
        if weight_kg and height_cm:
            try:
                height_m = float(height_cm) / 100
                bmi = round(float(weight_kg) / (height_m * height_m), 2)
            except (ValueError, TypeError, ZeroDivisionError):
                bmi = None

        return {
            "weight_kg": weight_kg,
            "height_cm": height_cm,
            "waist_cm": measurements.get("waist_cm"),
            "neck_cm": measurements.get("neck_cm"),
            "hip_cm": measurements.get("hip_cm"),
            "chest_cm": measurements.get("chest_cm"),
            "bicep_left_cm": measurements.get("bicep_left_cm"),
            "bicep_right_cm": measurements.get("bicep_right_cm"),
            "thigh_left_cm": measurements.get("thigh_left_cm"),
            "thigh_right_cm": measurements.get("thigh_right_cm"),
            "calf_left_cm": measurements.get("calf_left_cm"),
            "calf_right_cm": measurements.get("calf_right_cm"),
            "resting_heart_rate": measurements.get("resting_heart_rate"),
            "body_fat_percentage": body_fat,
            "lean_body_mass_kg": lean_mass,
            "bmi": bmi,
            "recorded_at": latest.recorded_at,
        }
