"""Serializers for gym tenant management and Super Admin provisioning."""

from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied

from apps.accounts.serializers import UserSummarySerializer
from apps.tenants.models import DemoRequest, GymConfig, GymTenant, validate_hex_color


class GymTenantSummarySerializer(serializers.ModelSerializer):
    """Summary of a gym tenant."""

    class Meta:
        model = GymTenant
        fields = [
            "id",
            "name",
            "subdomain",
            "status",
            "tier",
            "currency",
            "location",
            "contact_name",
            "contact_phone",
            "contact_email",
            "subscription_expires_at",
            "tls_confirmed_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class GymConfigSerializer(serializers.ModelSerializer):
    """Feature gating and configuration settings of a gym."""

    class Meta:
        model = GymConfig
        fields = [
            "has_trainer_module",
            "has_ai_plans",
            "has_analytics",
            "has_group_classes",
            "has_multi_branch",
            "freeze_days_allowed",
            "payment_grace_days",
            "subscription_reminder_days",
            "member_reminder_days",
            "brand_color",
            "logo",
            "show_unavailable_equipment",
            "first_run_dismissed_at",
        ]
        read_only_fields = fields


class CreateGymRequestSerializer(serializers.Serializer):
    """Payload for Super Admin gym creation."""

    name = serializers.CharField(max_length=150, required=True)
    subdomain = serializers.CharField(max_length=63, required=True)
    tier = serializers.ChoiceField(choices=GymTenant.TIER_CHOICES, required=True)
    location = serializers.CharField(
        max_length=255, required=False, allow_blank=True, default=""
    )
    contact_name = serializers.CharField(
        max_length=150, required=False, allow_blank=True, default=""
    )
    contact_phone = serializers.CharField(
        max_length=20, required=False, allow_blank=True, default=""
    )
    contact_email = serializers.EmailField(required=False, allow_blank=True, default="")
    owner_name = serializers.CharField(
        max_length=150, required=False, allow_blank=True, default=""
    )
    owner_email = serializers.EmailField(required=True)
    payment_amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=True
    )
    payment_reference = serializers.CharField(max_length=100, required=True)
    payment_method = serializers.CharField(
        max_length=30, required=False, default="bank_transfer"
    )
    demo_request_id = serializers.CharField(
        max_length=100, required=False, allow_null=True, allow_blank=True, default=None
    )


class CreateGymResponseSerializer(serializers.Serializer):
    """Response returned upon successful gym tenant creation."""

    gym = GymTenantSummarySerializer()
    config = GymConfigSerializer()
    owner = UserSummarySerializer()
    payment_id = serializers.UUIDField()
    invite_link = serializers.CharField()


class ProposeSubdomainResponseSerializer(serializers.Serializer):
    """Response containing proposed candidate subdomain."""

    subdomain = serializers.CharField()


class ConfirmTLSResponseSerializer(serializers.Serializer):
    """Response returned upon TLS certificate confirmation."""

    gym = GymTenantSummarySerializer()
    message = serializers.CharField()


class PublicDemoRequestSerializer(serializers.Serializer):
    """Public serializer for lead demo request submissions with honeypot field."""

    gym_name = serializers.CharField(max_length=150, required=True)
    contact_name = serializers.CharField(max_length=150, required=True)
    phone = serializers.CharField(max_length=50, required=True)
    city = serializers.CharField(
        max_length=100, required=False, allow_blank=True, default=""
    )
    email = serializers.EmailField(required=False, allow_blank=True, default="")
    message = serializers.CharField(required=False, allow_blank=True, default="")
    website = serializers.CharField(
        required=False, allow_blank=True, default="", write_only=True
    )


class DemoRequestSerializer(serializers.ModelSerializer):
    """Serializer for Super Admin lead management."""

    handled_by_email = serializers.SerializerMethodField()
    converted_gym_subdomain = serializers.SerializerMethodField()

    class Meta:
        model = DemoRequest
        fields = [
            "id",
            "gym_name",
            "contact_name",
            "phone",
            "city",
            "email",
            "message",
            "status",
            "notes",
            "handled_by",
            "handled_by_email",
            "converted_gym",
            "converted_gym_subdomain",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "gym_name",
            "contact_name",
            "phone",
            "city",
            "email",
            "message",
            "handled_by",
            "handled_by_email",
            "converted_gym",
            "converted_gym_subdomain",
            "created_at",
            "updated_at",
        ]

    def get_handled_by_email(self, obj) -> str | None:
        return obj.handled_by.email if obj.handled_by else None

    def get_converted_gym_subdomain(self, obj) -> str | None:
        return obj.converted_gym.subdomain if obj.converted_gym else None


class DemoRequestUpdateSerializer(serializers.Serializer):
    """Serializer for updating status and internal notes on a demo request."""

    status = serializers.ChoiceField(choices=DemoRequest.STATUS_CHOICES, required=False)
    notes = serializers.CharField(required=False, allow_blank=True)


class DemoRequestConvertResponseSerializer(serializers.Serializer):
    """Data returned to pre-fill the Create Gym form from a demo request."""

    demo_request_id = serializers.UUIDField()
    name = serializers.CharField()
    contact_name = serializers.CharField()
    contact_phone = serializers.CharField()
    contact_email = serializers.EmailField()
    location = serializers.CharField()


class UploadMemberPhotoSerializer(serializers.Serializer):
    """Upload serializer for member photos."""

    photo = serializers.FileField(required=True)


class UploadMemberPhotoResponseSerializer(serializers.Serializer):
    """Response returned upon member photo upload."""

    file_path = serializers.CharField()
    filename = serializers.CharField()
    url = serializers.CharField()


class UploadGymLogoSerializer(serializers.Serializer):
    """Upload serializer for gym logo."""

    logo = serializers.FileField(required=True)


class UploadGymLogoResponseSerializer(serializers.Serializer):
    """Response returned upon gym logo upload."""

    url = serializers.CharField()


class GymSettingsUpdateSerializer(serializers.Serializer):
    """
    Serializer for Owner-editable gym settings with strict allow-list enforcement.
    Any attempt to modify entitlement fields is rejected with 403 PermissionDenied.
    Any other unallowed or unknown field is rejected with 400 ValidationError.
    """

    ALLOWED_FIELDS = {
        "brand_color",
        "logo",
        "show_unavailable_equipment",
        "member_reminder_days",
    }
    ENTITLEMENT_FIELDS = {
        "tier",
        "has_trainer_module",
        "has_ai_plans",
        "has_analytics",
        "has_group_classes",
        "has_multi_branch",
        "freeze_days_allowed",
        "payment_grace_days",
        "subscription_reminder_days",
    }

    brand_color = serializers.CharField(
        max_length=7, required=False, allow_null=True, allow_blank=True
    )
    logo = serializers.CharField(
        max_length=500, required=False, allow_null=True, allow_blank=True
    )
    show_unavailable_equipment = serializers.BooleanField(required=False)
    member_reminder_days = serializers.ListField(
        child=serializers.IntegerField(min_value=0), required=False
    )

    def to_internal_value(self, data):
        if not isinstance(data, dict):
            raise serializers.ValidationError("Expected a dictionary of settings.")

        # Check for entitlement fields first: fail-closed with 403 PermissionDenied
        forbidden_entitlements = set(data.keys()).intersection(self.ENTITLEMENT_FIELDS)
        if forbidden_entitlements:
            raise PermissionDenied("Only Super Admin can modify gym entitlements.")

        # Check for unallowed / unknown fields: fail-closed with 400 ValidationError
        unknown_fields = set(data.keys()) - self.ALLOWED_FIELDS
        if unknown_fields:
            raise serializers.ValidationError(
                {
                    field: "Field is read-only or not recognized."
                    for field in sorted(unknown_fields)
                }
            )

        return super().to_internal_value(data)

    def validate_brand_color(self, value):
        if value:
            validate_hex_color(value)
        return value


class ChecklistItemSerializer(serializers.Serializer):
    """Item in first-run onboarding checklist."""

    label = serializers.CharField()
    completed = serializers.BooleanField()


class FirstRunChecklistResponseSerializer(serializers.Serializer):
    """First-run onboarding checklist progress for gym Owner."""

    is_dismissed = serializers.BooleanField()
    dismissed_at = serializers.DateTimeField(allow_null=True)
    all_completed = serializers.BooleanField()
    items = serializers.DictField(child=ChecklistItemSerializer())


class GymPublicEntryResponseSerializer(serializers.Serializer):
    """Public details returned on the gym subdomain entry page."""

    still_securing = serializers.BooleanField()
    gym_id = serializers.UUIDField(required=False)
    name = serializers.CharField()
    subdomain = serializers.CharField(required=False)
    brand_color = serializers.CharField(allow_null=True, required=False)
    logo = serializers.CharField(allow_null=True, required=False)
    phone = serializers.CharField(required=False, allow_blank=True)
    location = serializers.CharField(required=False, allow_blank=True)
    currency = serializers.CharField(required=False)
    message = serializers.CharField(required=False)
