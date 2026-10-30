from rest_framework import serializers

from apps.accounts.models import User
from apps.trainers.models import Trainer


class TrainerUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "full_name", "phone", "is_active"]
        read_only_fields = fields


class TrainerSerializer(serializers.ModelSerializer):
    user = TrainerUserSerializer(read_only=True)
    client_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Trainer
        fields = [
            "id",
            "user",
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
        max_value=200,
        required=True,
        error_messages={
            "min_value": "Maximum clients must be between 1 and 200.",
            "max_value": "Maximum clients must be between 1 and 200.",
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
