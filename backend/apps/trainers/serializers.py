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
