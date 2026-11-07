"""Serializers for gym tenant management and Super Admin provisioning."""

from django.conf import settings
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied

from apps.accounts.serializers import UserSummarySerializer
from apps.core.validators import (
    validate_and_normalize_phone,
    validate_email_address,
    validate_name,
    validate_payment_amount,
    validate_text_length,
)
from apps.tenants.models import (
    DemoRequest,
    GymConfig,
    GymTenant,
    PlatformNotice,
    SupportMessage,
    SupportRequest,
    validate_hex_color,
    validate_subdomain,
)


class GymTenantSummarySerializer(serializers.ModelSerializer):
    """Summary of a gym tenant."""

    url = serializers.SerializerMethodField()
    owner_email = serializers.SerializerMethodField()

    class Meta:
        model = GymTenant
        fields = [
            "id",
            "name",
            "subdomain",
            "url",
            "status",
            "tier",
            "is_demo",
            "currency",
            "location",
            "public_contact_phone",
            "contact_name",
            "contact_phone",
            "contact_email",
            "owner_email",
            "subscription_expires_at",
            "tls_confirmed_at",
            "suspended_at",
            "lapse_flagged_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_url(self, obj) -> str:
        scheme = getattr(settings, "PUBLIC_URL_SCHEME", "https")
        domain = getattr(settings, "DOMAIN", "fitgate.tebebtech.com")
        port = getattr(settings, "PUBLIC_PORT", "")
        port_suffix = f":{port}" if port else ""
        return f"{scheme}://{obj.subdomain}.{domain}{port_suffix}/"

    def get_owner_email(self, obj) -> str:
        owner = obj.users.filter(role="owner").first()
        return owner.email if owner else (obj.contact_email or "")


class GymConfigSerializer(serializers.ModelSerializer):
    """Feature gating and configuration settings of a gym."""

    tier = serializers.CharField(source="gym.tier", read_only=True)

    class Meta:
        model = GymConfig
        fields = [
            "tier",
            "has_trainer_module",
            "has_ai_plans",
            "has_analytics",
            "has_group_classes",
            "has_notices",
            "has_expenses",
            "has_multi_branch",
            "freeze_days_allowed",
            "freeze_days_cap",
            "payment_grace_days",
            "subscription_reminder_days",
            "member_reminder_days",
            "brand_color",
            "logo",
            "show_unavailable_equipment",
            "is_equipment_list_complete",
            "telegram_channel",
            "disabled_roles",
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
    public_contact_phone = serializers.CharField(
        max_length=50, required=False, allow_blank=True, default=""
    )
    contact_name = serializers.CharField(
        max_length=150, required=False, allow_blank=True, default=""
    )
    contact_phone = serializers.CharField(
        max_length=50, required=False, allow_blank=True, default=""
    )
    contact_email = serializers.EmailField(required=False, allow_blank=True, default="")
    owner_name = serializers.CharField(
        max_length=150, required=False, allow_blank=True, default=""
    )
    owner_email = serializers.EmailField(required=True)
    owner_email_confirm = serializers.EmailField(
        required=False, allow_blank=True, default=""
    )
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

    def validate_public_contact_phone(self, value):
        if not value:
            return ""
        from apps.core.validators import validate_and_normalize_phone

        return validate_and_normalize_phone(value)

    def validate_contact_phone(self, value):
        if not value:
            return ""
        from apps.core.validators import validate_and_normalize_phone

        return validate_and_normalize_phone(value)

    def validate_location(self, value):
        from apps.core.validators import validate_address

        return validate_address(value)

    def validate(self, attrs):
        pub_phone = attrs.get("public_contact_phone") or attrs.get("contact_phone")
        if not pub_phone:
            raise serializers.ValidationError(
                {"public_contact_phone": ["Public contact phone is required."]}
            )
        attrs["public_contact_phone"] = pub_phone
        owner_email = attrs.get("owner_email")
        owner_email_confirm = attrs.get("owner_email_confirm")
        if owner_email_confirm and owner_email != owner_email_confirm:
            raise serializers.ValidationError(
                {"owner_email_confirm": ["Owner email addresses do not match."]}
            )
        return attrs

    def validate_name(self, value):
        return validate_name(value, "Gym name")

    def validate_subdomain(self, value):
        validate_subdomain(value)
        return value.lower()

    def validate_contact_name(self, value):
        if value:
            return validate_name(value, "Contact name")
        return ""

    def validate_contact_email(self, value):
        if value:
            return validate_email_address(value)
        return ""

    def validate_owner_name(self, value):
        if value:
            return validate_name(value, "Owner name")
        return ""

    def validate_owner_email(self, value):
        return validate_email_address(value)

    def validate_payment_amount(self, value):
        return validate_payment_amount(value)

    def validate_payment_reference(self, value):
        return validate_text_length(value, 3, 100, "Payment reference")


class CreateGymResponseSerializer(serializers.Serializer):
    """Response returned upon successful gym tenant creation."""

    gym = GymTenantSummarySerializer()
    config = GymConfigSerializer()
    owner = UserSummarySerializer()
    payment_id = serializers.UUIDField()
    gym_url = serializers.CharField(required=False)


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

    def validate_gym_name(self, value):
        return validate_name(value, "Gym name")

    def validate_contact_name(self, value):
        return validate_name(value, "Contact name")

    def validate_phone(self, value):
        return validate_and_normalize_phone(value)

    def validate_email(self, value):
        if value:
            return validate_email_address(value)
        return ""

    def validate_message(self, value):
        if value:
            return validate_text_length(value, 0, 1000, "Message")
        return ""


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

    def validate_notes(self, value):
        if value:
            return validate_text_length(value, 0, 1000, "Notes")
        return ""


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
        "show_unavailable_equipment",
        "is_equipment_list_complete",
        "telegram_channel",
        "member_reminder_days",
        "freeze_days_allowed",
    }
    ENTITLEMENT_FIELDS = {
        "tier",
        "has_trainer_module",
        "has_ai_plans",
        "has_analytics",
        "has_group_classes",
        "has_notices",
        "has_expenses",
        "has_multi_branch",
        "payment_grace_days",
        "subscription_reminder_days",
        "freeze_days_cap",
    }

    brand_color = serializers.CharField(
        max_length=7, required=False, allow_null=True, allow_blank=True
    )
    show_unavailable_equipment = serializers.BooleanField(required=False)
    is_equipment_list_complete = serializers.BooleanField(required=False)
    telegram_channel = serializers.CharField(
        max_length=33, required=False, allow_blank=True, allow_null=True
    )
    member_reminder_days = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
    )
    freeze_days_allowed = serializers.IntegerField(min_value=0, required=False)

    def validate_member_reminder_days(self, value):
        from django.core.exceptions import ValidationError as DjangoValidationError

        from apps.core.validators import validate_reminder_days

        try:
            return validate_reminder_days(value)
        except DjangoValidationError as exc:
            msg = exc.message if hasattr(exc, "message") else str(exc)
            raise serializers.ValidationError(msg)

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

    def validate_telegram_channel(self, value):
        from apps.core.validators import validate_telegram_channel

        cleaned = validate_telegram_channel(value)
        if cleaned:
            from apps.tenants.models import GymConfig

            tenant = (
                self.context.get("tenant")
                or getattr(self.context.get("request"), "tenant", None)
                or getattr(self.instance, "gym", None)
            )
            qs = GymConfig.objects.filter(telegram_channel__iexact=cleaned)
            if tenant:
                qs = qs.exclude(gym=tenant)
            elif self.instance and getattr(self.instance, "pk", None):
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    "This Telegram channel is already connected to another gym."
                )
        return cleaned


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
    online_payment_verified = serializers.BooleanField(default=False)
    has_group_classes = serializers.BooleanField(default=False)
    tier = serializers.CharField(required=False)
    capabilities = serializers.DictField(required=False)


class GymNoticeSerializer(serializers.ModelSerializer):
    posted_by_name = serializers.SerializerMethodField(read_only=True)
    is_platform_wide = serializers.SerializerMethodField(read_only=True)

    class Meta:
        from apps.tenants.models import GymNotice

        model = GymNotice
        fields = [
            "id",
            "title",
            "body",
            "posted_by",
            "posted_by_name",
            "is_platform_wide",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "posted_by",
            "posted_by_name",
            "is_platform_wide",
            "created_at",
            "updated_at",
        ]

    def get_posted_by_name(self, obj) -> str:
        if not obj.posted_by:
            return "FitGate Platform" if not obj.gym_id else "Gym Staff"
        if getattr(obj.posted_by, "role", None) == "super_admin":
            return "FitGate Platform"
        return getattr(obj.posted_by, "full_name", "") or obj.posted_by.email

    def get_is_platform_wide(self, obj) -> bool:
        return obj.gym_id is None

    def validate_title(self, value):
        from apps.core.validators import validate_notice_title

        return validate_notice_title(value)

    def validate_body(self, value):
        from apps.core.validators import validate_notice_body

        return validate_notice_body(value)


class PlatformNoticeSerializer(serializers.ModelSerializer):
    posted_by_name = serializers.SerializerMethodField(read_only=True)
    target_gym_names = serializers.SerializerMethodField(read_only=True)
    target_gym_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=GymTenant.objects.all(),
        source="target_gyms",
        required=False,
    )

    class Meta:
        model = PlatformNotice
        fields = [
            "id",
            "title",
            "message",
            "posted_by",
            "posted_by_name",
            "audience_type",
            "target_gym_ids",
            "target_gym_names",
            "show_until",
            "is_withdrawn",
            "withdrawn_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "posted_by",
            "posted_by_name",
            "target_gym_names",
            "is_withdrawn",
            "withdrawn_at",
            "created_at",
            "updated_at",
        ]

    def get_posted_by_name(self, obj) -> str:
        return "FitGate Platform"

    def get_target_gym_names(self, obj) -> list[str]:
        if obj.audience_type == PlatformNotice.AUDIENCE_ALL:
            return ["All gyms"]
        return [g.name for g in obj.target_gyms.all()]

    def validate_title(self, value):
        from apps.core.validators import validate_platform_notice_title

        return validate_platform_notice_title(value)

    def validate_message(self, value):
        from apps.core.validators import validate_platform_notice_message

        return validate_platform_notice_message(value)

    def validate(self, attrs):
        audience_type = attrs.get("audience_type", PlatformNotice.AUDIENCE_ALL)
        target_gyms = attrs.get("target_gyms", [])
        if audience_type == PlatformNotice.AUDIENCE_SELECTED and not target_gyms:
            raise serializers.ValidationError(
                {"target_gym_ids": ["Please select at least one gym for this notice."]}
            )
        show_until = attrs.get("show_until")
        if show_until:
            today = timezone.localdate()
            if show_until < today:
                raise serializers.ValidationError(
                    {"show_until": ["Show-until date cannot be in the past."]}
                )
        return attrs


class SupportMessageSerializer(serializers.ModelSerializer):
    sender_name = serializers.SerializerMethodField(read_only=True)
    sender_type = serializers.SerializerMethodField(read_only=True)
    sender_label = serializers.SerializerMethodField(read_only=True)
    body = serializers.CharField(source="message", read_only=True)

    class Meta:
        model = SupportMessage
        fields = [
            "id",
            "request_id",
            "sender_id",
            "sender_name",
            "sender_role",
            "sender_type",
            "sender_label",
            "message",
            "body",
            "created_at",
        ]
        read_only_fields = fields

    def get_sender_type(self, obj) -> str:
        return "platform" if obj.sender_role == "super_admin" else "gym"

    def get_sender_name(self, obj) -> str:
        if obj.sender_role == "super_admin":
            return "FitGate Support"
        return getattr(obj.sender, "full_name", "") or obj.sender.email

    def get_sender_label(self, obj) -> str:
        if obj.sender_role == "super_admin":
            return "FitGate Support"
        name = getattr(obj.sender, "full_name", "") or obj.sender.email
        role = (obj.sender_role or "Staff").replace("_", " ").title()
        return f"{name} ({role})"


class SupportRequestSerializer(serializers.ModelSerializer):
    gym_name = serializers.CharField(source="gym.name", read_only=True)
    gym_subdomain = serializers.CharField(source="gym.subdomain", read_only=True)
    created_by_name = serializers.SerializerMethodField(read_only=True)
    request_type_display = serializers.CharField(
        source="get_request_type_display", read_only=True
    )
    category = serializers.CharField(source="request_type", read_only=True)
    messages = SupportMessageSerializer(many=True, read_only=True)
    message_count = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = SupportRequest
        fields = [
            "id",
            "gym_id",
            "gym_name",
            "gym_subdomain",
            "created_by_id",
            "created_by_name",
            "request_type",
            "category",
            "request_type_display",
            "subject",
            "status",
            "message_count",
            "messages",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_created_by_name(self, obj) -> str:
        return getattr(obj.created_by, "full_name", "") or obj.created_by.email

    def get_message_count(self, obj) -> int:
        return obj.messages.count()


class SupportRequestCreateSerializer(serializers.Serializer):
    request_type = serializers.CharField(required=False)
    category = serializers.CharField(required=False)
    subject = serializers.CharField(max_length=100)
    message = serializers.CharField(max_length=1000)

    def validate(self, attrs):
        req_type = attrs.get("request_type") or attrs.get("category")
        if not req_type:
            raise serializers.ValidationError(
                {"request_type": "This field is required."}
            )
        valid_types = [c[0] for c in SupportRequest.TYPE_CHOICES]
        if req_type not in valid_types:
            raise serializers.ValidationError(
                {"request_type": f"Must be one of {valid_types}."}
            )
        attrs["request_type"] = req_type
        return attrs

    def validate_subject(self, value):
        from apps.core.validators import validate_support_subject

        return validate_support_subject(value)

    def validate_message(self, value):
        from apps.core.validators import validate_support_message

        return validate_support_message(value)


class SupportReplySerializer(serializers.Serializer):
    message = serializers.CharField(required=False, max_length=1000)
    body = serializers.CharField(required=False, max_length=1000)

    def validate(self, attrs):
        msg = attrs.get("message") or attrs.get("body")
        if not msg:
            raise serializers.ValidationError({"message": "This field is required."})
        from apps.core.validators import validate_support_reply

        attrs["message"] = validate_support_reply(msg)
        return attrs


class OwnerGymDetailsUpdateSerializer(serializers.Serializer):
    public_contact_phone = serializers.CharField(max_length=50, required=False)
    location = serializers.CharField(max_length=200, required=False, allow_blank=True)

    def validate_public_contact_phone(self, value):
        if not value:
            return ""
        from apps.core.validators import validate_and_normalize_phone

        return validate_and_normalize_phone(value)

    def validate_location(self, value):
        from apps.core.validators import validate_address

        return validate_address(value)


class PlatformGymDetailsUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150, required=False)
    location = serializers.CharField(max_length=200, required=False, allow_blank=True)
    public_contact_phone = serializers.CharField(max_length=50, required=False)
    contact_name = serializers.CharField(
        max_length=150, required=False, allow_blank=True
    )
    contact_phone = serializers.CharField(
        max_length=50, required=False, allow_blank=True
    )
    contact_email = serializers.EmailField(required=False, allow_blank=True)

    def validate_name(self, value):
        from apps.core.validators import validate_name

        return validate_name(value, field_name="Gym name")

    def validate_location(self, value):
        from apps.core.validators import validate_address

        return validate_address(value)

    def validate_public_contact_phone(self, value):
        if not value:
            return ""
        from apps.core.validators import validate_and_normalize_phone

        return validate_and_normalize_phone(value)

    def validate_contact_phone(self, value):
        if not value:
            return ""
        from apps.core.validators import validate_and_normalize_phone

        return validate_and_normalize_phone(value)
