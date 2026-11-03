from rest_framework import serializers

from apps.core.validators import (
    validate_equipment_category,
    validate_equipment_issue_reason,
    validate_equipment_min_quantity,
    validate_equipment_name,
    validate_equipment_purchase_date,
    validate_equipment_quantity,
)
from apps.equipment.constants import CONDITION_CHOICES
from apps.equipment.models import Equipment, MaintenanceLog


class MaintenanceLogSerializer(serializers.ModelSerializer):
    reported_by_name = serializers.SerializerMethodField()
    resolved_by_name = serializers.SerializerMethodField()

    class Meta:
        model = MaintenanceLog
        fields = [
            "id",
            "equipment",
            "reported_by",
            "reported_by_name",
            "issue_reason",
            "other_details",
            "reported_at",
            "resolved_at",
            "resolved_by",
            "resolved_by_name",
            "resolution_notes",
        ]
        read_only_fields = [
            "id",
            "reported_by",
            "reported_by_name",
            "reported_at",
            "resolved_at",
            "resolved_by",
            "resolved_by_name",
        ]

    def get_reported_by_name(self, obj) -> str:
        if obj.reported_by:
            return getattr(obj.reported_by, "full_name", "") or obj.reported_by.email
        return "Unknown"

    def get_resolved_by_name(self, obj) -> str:
        if obj.resolved_by:
            return getattr(obj.resolved_by, "full_name", "") or obj.resolved_by.email
        return ""


class EquipmentSerializer(serializers.ModelSerializer):
    is_low_quantity = serializers.BooleanField(read_only=True)
    maintenance_logs = MaintenanceLogSerializer(many=True, read_only=True)

    class Meta:
        model = Equipment
        fields = [
            "id",
            "name",
            "category",
            "serial_number",
            "quantity",
            "min_qty_threshold",
            "condition",
            "purchase_date",
            "unit_purchase_price_etb",
            "branch_id",
            "is_low_quantity",
            "maintenance_logs",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "is_low_quantity", "created_at", "updated_at"]

    def validate_name(self, value):
        return validate_equipment_name(value)

    def validate_category(self, value):
        return validate_equipment_category(value)

    def validate_quantity(self, value):
        return validate_equipment_quantity(value)

    def validate_min_qty_threshold(self, value):
        return validate_equipment_min_quantity(value)

    def validate_purchase_date(self, value):
        return validate_equipment_purchase_date(value)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        from apps.accounts.models import User

        request = self.context.get("request")
        user = getattr(request, "user", None) if request else None
        role = getattr(user, "role", None) if user and user.is_authenticated else None

        # Price visibility: strictly Owner and Manager only
        if role not in (User.ROLE_OWNER, User.ROLE_MANAGER):
            data.pop("unit_purchase_price_etb", None)

        # Member privacy: never see maintenance notes, serial numbers, or prices
        if role == User.ROLE_MEMBER:
            data.pop("serial_number", None)
            data.pop("maintenance_logs", None)
            data.pop("min_qty_threshold", None)
            data.pop("unit_purchase_price_etb", None)

        return data


class EquipmentCreateUpdateSerializer(serializers.ModelSerializer):
    record_as_expense = serializers.BooleanField(
        required=False, default=False, write_only=True
    )

    class Meta:
        model = Equipment
        fields = [
            "name",
            "category",
            "serial_number",
            "quantity",
            "min_qty_threshold",
            "condition",
            "purchase_date",
            "unit_purchase_price_etb",
            "branch_id",
            "record_as_expense",
        ]

    def validate_name(self, value):
        return validate_equipment_name(value)

    def validate_category(self, value):
        return validate_equipment_category(value)

    def validate_quantity(self, value):
        return validate_equipment_quantity(value)

    def validate_min_qty_threshold(self, value):
        return validate_equipment_min_quantity(value)

    def validate_purchase_date(self, value):
        return validate_equipment_purchase_date(value)

    def validate_unit_purchase_price_etb(self, value):
        if value is not None:
            if value <= 0:
                raise serializers.ValidationError(
                    "Unit purchase price must be strictly greater than 0."
                )
            if value > 10000000:
                raise serializers.ValidationError(
                    "Unit purchase price cannot exceed 10,000,000.00 ETB."
                )
        return value


class ReportIssueSerializer(serializers.Serializer):
    issue_reason = serializers.CharField(required=True)
    other_details = serializers.CharField(
        required=False, allow_blank=True, default="", max_length=200
    )

    def validate(self, attrs):
        reason, details = validate_equipment_issue_reason(
            attrs.get("issue_reason"), attrs.get("other_details")
        )
        return {"issue_reason": reason, "other_details": details}


class UpdateConditionSerializer(serializers.Serializer):
    condition = serializers.ChoiceField(choices=CONDITION_CHOICES, required=True)
    resolution_notes = serializers.CharField(
        required=False, allow_blank=True, default="", max_length=500
    )
