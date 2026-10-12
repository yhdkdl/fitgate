import os

from django.core.exceptions import ValidationError
from django.http import FileResponse
from drf_spectacular.utils import OpenApiResponse, extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.accounts.notifications import notify_demo_request_received
from apps.accounts.permissions import (
    CanEditGymEntitlements,
    CanEditGymSettings,
    IsGymOwner,
    IsSuperAdmin,
    RequirePasswordChanged,
)
from apps.accounts.serializers import UserSummarySerializer
from apps.tenants.models import DemoRequest, GymConfig, GymTenant
from apps.tenants.serializers import (
    ConfirmTLSResponseSerializer,
    CreateGymRequestSerializer,
    CreateGymResponseSerializer,
    DemoRequestConvertResponseSerializer,
    DemoRequestSerializer,
    DemoRequestUpdateSerializer,
    FirstRunChecklistResponseSerializer,
    GymConfigSerializer,
    GymPublicEntryResponseSerializer,
    GymSettingsUpdateSerializer,
    GymTenantSummarySerializer,
    ProposeSubdomainResponseSerializer,
    PublicDemoRequestSerializer,
    UploadGymLogoResponseSerializer,
    UploadGymLogoSerializer,
    UploadMemberPhotoResponseSerializer,
    UploadMemberPhotoSerializer,
)
from apps.tenants.services import (
    confirm_gym_tls,
    create_gym,
    dismiss_first_run_checklist,
    get_first_run_checklist,
    propose_subdomain,
    update_gym_settings,
)
from apps.tenants.storage import (
    get_authenticated_photo_stream,
    save_gym_logo,
    save_member_photo,
)
from apps.tenants.throttling import DemoRequestRateThrottle


class CreateGymView(APIView):
    """
    Super Admin endpoint to atomically create a new gym tenant, payment record,
    owner account, and provision the subdomain via cPanel UAPI.
    """

    permission_classes = [IsAuthenticated, RequirePasswordChanged, IsSuperAdmin]

    @extend_schema(
        summary="Create gym tenant",
        description="Super Admin creates an active gym tenant, records bank transfer payment, and provisions subdomain.",
        request=CreateGymRequestSerializer,
        responses={
            201: CreateGymResponseSerializer,
            400: OpenApiResponse(description="Validation error"),
            403: OpenApiResponse(description="Forbidden"),
        },
    )
    def post(self, request, *args, **kwargs):
        # Must be invoked at the apex platform domain
        if getattr(request, "tenant", None) is not None:
            raise PermissionDenied(
                "Super Admin operations must be performed at the apex platform domain."
            )

        serializer = CreateGymRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data

        try:
            result = create_gym(
                name=data["name"],
                subdomain=data["subdomain"],
                tier=data["tier"],
                owner_email=data["owner_email"],
                payment_amount=data["payment_amount"],
                payment_reference=data["payment_reference"],
                acting_super_admin=request.user,
                location=data.get("location", ""),
                contact_name=data.get("contact_name", ""),
                contact_phone=data.get("contact_phone", ""),
                contact_email=data.get("contact_email", ""),
                owner_name=data.get("owner_name", ""),
                payment_method=data.get("payment_method", "bank_transfer"),
                demo_request_id=data.get("demo_request_id"),
            )
        except ValidationError as exc:
            error_dict = (
                exc.message_dict
                if hasattr(exc, "message_dict")
                else {"detail": exc.messages}
            )
            return Response(error_dict, status=status.HTTP_400_BAD_REQUEST)

        response_data = {
            "gym": GymTenantSummarySerializer(result["gym"]).data,
            "config": GymConfigSerializer(result["config"]).data,
            "owner": UserSummarySerializer(result["owner"]).data,
            "payment_id": str(result["payment"].id),
            "invite_link": result["invite_link"],
        }
        return Response(response_data, status=status.HTTP_201_CREATED)

    @extend_schema(
        summary="List gym tenants",
        description="Lists all gym tenants on the platform for Super Admin.",
        responses={200: GymTenantSummarySerializer(many=True)},
    )
    def get(self, request, *args, **kwargs):
        if getattr(request, "tenant", None) is not None:
            raise PermissionDenied(
                "Super Admin operations must be performed at the apex platform domain."
            )
        gyms = GymTenant.objects.all().order_by("-created_at")
        serializer = GymTenantSummarySerializer(gyms, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ProposeSubdomainView(APIView):
    """Suggest an available, DNS-compliant subdomain candidate from a gym name."""

    permission_classes = [IsAuthenticated, RequirePasswordChanged, IsSuperAdmin]

    @extend_schema(
        summary="Propose candidate subdomain",
        description="Generates a sanitized DNS label candidate for a proposed gym name.",
        responses={200: ProposeSubdomainResponseSerializer},
    )
    def get(self, request, *args, **kwargs):
        name = request.query_params.get("name", "")
        candidate = propose_subdomain(name)
        return Response({"subdomain": candidate}, status=status.HTTP_200_OK)


class ConfirmGymTLSView(APIView):
    """
    Super Admin endpoint to confirm that a gym's TLS certificate has been issued.

    Unlocks login and registration on the gym's subdomain and sets the initial 1-year subscription window.
    """

    permission_classes = [IsAuthenticated, RequirePasswordChanged, IsSuperAdmin]

    @extend_schema(
        summary="Confirm gym TLS certificate",
        description="Confirms subdomain TLS certificate, activating login access and establishing subscription expiry.",
        request=None,
        responses={
            200: ConfirmTLSResponseSerializer,
            400: OpenApiResponse(description="Gym not found"),
            403: OpenApiResponse(description="Forbidden"),
        },
    )
    def post(self, request, gym_id, *args, **kwargs):
        try:
            gym = confirm_gym_tls(gym_id=gym_id, acting_super_admin=request.user)
        except ValidationError as exc:
            error_dict = (
                exc.message_dict
                if hasattr(exc, "message_dict")
                else {"detail": exc.messages}
            )
            return Response(error_dict, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                "gym": GymTenantSummarySerializer(gym).data,
                "message": "TLS certificate confirmed. Login access is now active.",
            },
            status=status.HTTP_200_OK,
        )


class ListGymsView(APIView):
    """Super Admin endpoint to list all gym tenants."""

    permission_classes = [IsAuthenticated, RequirePasswordChanged, IsSuperAdmin]

    @extend_schema(
        summary="List gym tenants",
        description="Lists all gym tenants on the platform.",
        responses={200: GymTenantSummarySerializer(many=True)},
    )
    def get(self, request, *args, **kwargs):
        gyms = GymTenant.objects.all().order_by("-created_at")
        serializer = GymTenantSummarySerializer(gyms, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class GymDetailView(APIView):
    """Super Admin endpoint to retrieve gym tenant details and config."""

    permission_classes = [IsAuthenticated, RequirePasswordChanged, IsSuperAdmin]

    @extend_schema(
        summary="Get gym tenant details",
        description="Retrieves a specific gym tenant and its configuration.",
        responses={
            200: inline_serializer(
                name="GymDetailResponse",
                fields={
                    "gym": GymTenantSummarySerializer(),
                    "config": GymConfigSerializer(),
                },
            ),
            404: OpenApiResponse(description="Not found"),
        },
    )
    def get(self, request, gym_id, *args, **kwargs):
        try:
            gym = GymTenant.objects.select_related("config").get(id=gym_id)
        except GymTenant.DoesNotExist:
            return Response(
                {"detail": "Gym tenant not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        config = getattr(gym, "config", None)
        return Response(
            {
                "gym": GymTenantSummarySerializer(gym).data,
                "config": GymConfigSerializer(config).data if config else None,
            },
            status=status.HTTP_200_OK,
        )


class PublicDemoRequestView(APIView):
    """
    Public endpoint on the apex platform domain for prospective gyms to request a demo.

    Rejected on gym subdomains. Rate-limited and includes honeypot protection.
    """

    permission_classes = (AllowAny,)
    authentication_classes = ()
    throttle_classes = (DemoRequestRateThrottle,)

    @extend_schema(
        summary="Submit demo request",
        description="Public endpoint to request a demo for a gym. Only accepted on the apex domain.",
        request=PublicDemoRequestSerializer,
        responses={
            201: inline_serializer(
                name="PublicDemoRequestResponse",
                fields={
                    "detail": serializers.CharField(),
                    "id": serializers.CharField(required=False),
                },
            ),
            400: OpenApiResponse(description="Bad request or rejected on subdomain"),
            429: OpenApiResponse(description="Too many requests"),
        },
    )
    def post(self, request, *args, **kwargs):
        if getattr(request, "tenant", None) is not None:
            return Response(
                {
                    "detail": "Demo requests are only accepted on the apex platform domain."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = PublicDemoRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        honeypot = data.get("website", "").strip()
        if honeypot:
            # Honeypot filled by bot: silently return success without persisting
            return Response(
                {"detail": "demo_request_received"},
                status=status.HTTP_201_CREATED,
            )

        demo = DemoRequest.objects.create(
            gym_name=data["gym_name"].strip(),
            contact_name=data["contact_name"].strip(),
            phone=data["phone"].strip(),
            city=data.get("city", "").strip(),
            email=data.get("email", "").strip().lower(),
            message=data.get("message", "").strip(),
            status=DemoRequest.STATUS_NEW,
        )

        notify_demo_request_received(demo)

        return Response(
            {"detail": "demo_request_received", "id": str(demo.id)},
            status=status.HTTP_201_CREATED,
        )


class DemoRequestListView(APIView):
    """Super Admin endpoint to list all prospective gym demo requests."""

    permission_classes = [IsAuthenticated, RequirePasswordChanged, IsSuperAdmin]

    @extend_schema(
        summary="List demo requests",
        description="Super Admin endpoint to view and filter demo request leads.",
        responses={200: DemoRequestSerializer(many=True)},
    )
    def get(self, request, *args, **kwargs):
        qs = DemoRequest.objects.all().select_related("handled_by", "converted_gym")
        status_filter = request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)

        serializer = DemoRequestSerializer(qs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class DemoRequestDetailView(APIView):
    """Super Admin endpoint to retrieve and update demo request status/notes."""

    permission_classes = [IsAuthenticated, RequirePasswordChanged, IsSuperAdmin]

    @extend_schema(
        summary="Get demo request detail",
        responses={
            200: DemoRequestSerializer,
            404: OpenApiResponse(description="Not found"),
        },
    )
    def get(self, request, pk, *args, **kwargs):
        try:
            demo = DemoRequest.objects.select_related(
                "handled_by", "converted_gym"
            ).get(pk=pk)
        except DemoRequest.DoesNotExist:
            return Response(
                {"detail": "Demo request not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(DemoRequestSerializer(demo).data, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Update demo request status or notes",
        request=DemoRequestUpdateSerializer,
        responses={
            200: DemoRequestSerializer,
            400: OpenApiResponse(description="Bad request"),
            404: OpenApiResponse(description="Not found"),
        },
    )
    def patch(self, request, pk, *args, **kwargs):
        try:
            demo = DemoRequest.objects.select_related(
                "handled_by", "converted_gym"
            ).get(pk=pk)
        except DemoRequest.DoesNotExist:
            return Response(
                {"detail": "Demo request not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = DemoRequestUpdateSerializer(data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        if "status" in serializer.validated_data:
            demo.status = serializer.validated_data["status"]
        if "notes" in serializer.validated_data:
            demo.notes = serializer.validated_data["notes"]
        demo.handled_by = request.user
        demo.save()

        return Response(DemoRequestSerializer(demo).data, status=status.HTTP_200_OK)


class DemoRequestConvertView(APIView):
    """Super Admin endpoint returning pre-filled data to convert a lead to a gym."""

    permission_classes = [IsAuthenticated, RequirePasswordChanged, IsSuperAdmin]

    @extend_schema(
        summary="Convert demo request to gym form data",
        responses={
            200: DemoRequestConvertResponseSerializer,
            404: OpenApiResponse(description="Not found"),
        },
    )
    def get(self, request, pk, *args, **kwargs):
        try:
            demo = DemoRequest.objects.get(pk=pk)
        except DemoRequest.DoesNotExist:
            return Response(
                {"detail": "Demo request not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        data = {
            "demo_request_id": str(demo.id),
            "name": demo.gym_name,
            "contact_name": demo.contact_name,
            "contact_phone": demo.phone,
            "contact_email": demo.email,
            "location": demo.city,
        }
        return Response(data, status=status.HTTP_200_OK)


class ServeMemberPhotoView(APIView):
    """
    Serve authenticated member photos with strict per-gym scoping.
    Browser never receives direct Cloudinary URL.
    Returns 403 on tenant mismatch, 404 when file does not exist.
    """

    permission_classes = [IsAuthenticated, RequirePasswordChanged]

    @extend_schema(
        summary="Serve authenticated member photo",
        description="Serves member photo stream only to users belonging to the specified gym or Super Admin.",
        responses={
            200: OpenApiResponse(description="Image WebP stream"),
            400: OpenApiResponse(description="Invalid request or filename format"),
            401: OpenApiResponse(description="Authentication credentials required"),
            403: OpenApiResponse(
                description="Forbidden - user belongs to different gym"
            ),
            404: OpenApiResponse(description="Photo not found"),
        },
    )
    def get(self, request, gym_id, filename, *args, **kwargs):
        if not request.user or not request.user.is_authenticated:
            return Response(
                {"detail": "Authentication credentials were not provided."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # Enforce tenant isolation: Super Admin or user belonging to gym_id
        is_super_admin = getattr(
            request.user, "role", None
        ) == User.ROLE_SUPER_ADMIN or getattr(request.user, "is_superuser", False)
        if not is_super_admin:
            user_gym_id = getattr(request.user, "gym_id", None)
            if user_gym_id != gym_id:
                raise PermissionDenied(
                    "You do not have permission to access photos for another gym."
                )

        try:
            stream, content_type = get_authenticated_photo_stream(gym_id, filename)
        except ValidationError as exc:
            msg = (
                exc.messages[0]
                if hasattr(exc, "messages") and len(exc.messages) == 1
                else (exc.messages if hasattr(exc, "messages") else str(exc))
            )
            return Response({"detail": msg}, status=status.HTTP_400_BAD_REQUEST)
        except FileNotFoundError:
            return Response(
                {"detail": "Photo not found."}, status=status.HTTP_404_NOT_FOUND
            )

        response = FileResponse(stream, content_type=content_type)
        response["Cache-Control"] = "private, no-transform, max-age=3600"
        return response


class UploadMemberPhotoView(APIView):
    """
    Upload and process a member photo into gym-scoped authenticated storage.
    """

    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [IsAuthenticated, RequirePasswordChanged]

    @extend_schema(
        summary="Upload member photo",
        description="Validates image format and size (<= 2 MB), strips EXIF, resizes, and saves to gym-scoped authenticated storage.",
        request=UploadMemberPhotoSerializer,
        responses={
            201: UploadMemberPhotoResponseSerializer,
            400: OpenApiResponse(description="Validation error or missing file"),
            403: OpenApiResponse(description="Forbidden - cross-tenant access denied"),
        },
    )
    def post(self, request, gym_id, *args, **kwargs):
        if not request.user or not request.user.is_authenticated:
            return Response(
                {"detail": "Authentication credentials were not provided."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        is_super_admin = getattr(
            request.user, "role", None
        ) == User.ROLE_SUPER_ADMIN or getattr(request.user, "is_superuser", False)
        if not is_super_admin:
            user_gym_id = getattr(request.user, "gym_id", None)
            if user_gym_id != gym_id:
                raise PermissionDenied(
                    "You cannot upload member photos for another gym."
                )

        uploaded_file = request.FILES.get("photo") or request.FILES.get("file")
        if not uploaded_file:
            return Response(
                {"detail": "No photo file provided."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            relative_path = save_member_photo(gym_id, uploaded_file)
        except ValidationError as exc:
            msg = (
                exc.messages[0]
                if hasattr(exc, "messages") and len(exc.messages) == 1
                else (exc.messages if hasattr(exc, "messages") else str(exc))
            )
            return Response({"detail": msg}, status=status.HTTP_400_BAD_REQUEST)

        filename = os.path.basename(relative_path)
        url = f"/api/media/member-photos/{gym_id}/{filename}/"
        return Response(
            {
                "file_path": relative_path,
                "filename": filename,
                "url": url,
            },
            status=status.HTTP_201_CREATED,
        )


class UploadGymLogoView(APIView):
    """
    Upload and process a public gym logo.
    Only Owner of the gym on the active tenant can upload.
    """

    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [IsAuthenticated, RequirePasswordChanged, IsGymOwner]

    @extend_schema(
        summary="Upload gym logo",
        description="Uploads and optimizes gym logo (public asset). Only accessible by gym Owner.",
        request=UploadGymLogoSerializer,
        responses={
            200: UploadGymLogoResponseSerializer,
            400: OpenApiResponse(description="Validation error or missing file"),
            403: OpenApiResponse(description="Forbidden - only Owner permitted"),
        },
    )
    def post(self, request, gym_id, *args, **kwargs):
        is_owner = getattr(request.user, "role", None) == User.ROLE_OWNER and str(
            getattr(request.user, "gym_id", None)
        ) == str(gym_id)
        if not is_owner:
            raise PermissionDenied("Only the gym owner can upload a gym logo.")

        uploaded_file = request.FILES.get("logo") or request.FILES.get("file")
        if not uploaded_file:
            return Response(
                {"detail": "No logo file provided."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            url = save_gym_logo(gym_id, uploaded_file)
        except ValidationError as exc:
            msg = (
                exc.messages[0]
                if hasattr(exc, "messages") and len(exc.messages) == 1
                else (exc.messages if hasattr(exc, "messages") else str(exc))
            )
            return Response({"detail": msg}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"url": url}, status=status.HTTP_200_OK)


class GymSettingsView(APIView):
    """
    View and update gym configuration and branding settings.
    - Owner can update brand_color, logo, show_unavailable_equipment, member_reminder_days.
    - Owner attempting to update entitlement fields receives 403 Forbidden.
    - Manager and other staff roles receive 403 Forbidden.
    - Super Admin receives 403 Forbidden on gym subdomain (SPEC §2 indicates '-' for Super Admin).
    """

    permission_classes = [IsAuthenticated, RequirePasswordChanged, CanEditGymSettings]

    @extend_schema(
        summary="Get gym settings",
        description="Returns gym configuration and branding settings for Owner.",
        responses={200: GymConfigSerializer},
    )
    def get(self, request, *args, **kwargs):
        gym = request.tenant
        config = getattr(gym, "config", None)
        if config is None:
            config, _ = GymConfig.objects.get_or_create(gym=gym)

        return Response(GymConfigSerializer(config).data, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Update gym settings",
        description="Updates Owner-editable gym settings (branding, reminders). Entitlement modifications by Owner return 403.",
        request=GymSettingsUpdateSerializer,
        responses={
            200: GymConfigSerializer,
            400: OpenApiResponse(description="Validation error"),
            403: OpenApiResponse(
                description="Forbidden - entitlements restricted to Super Admin or non-Owner access"
            ),
        },
    )
    def patch(self, request, *args, **kwargs):
        gym = request.tenant
        serializer = GymSettingsUpdateSerializer(data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            config = update_gym_settings(gym, request.user, serializer.validated_data)
        except ValidationError as exc:
            msg = (
                exc.messages[0]
                if hasattr(exc, "messages") and len(exc.messages) == 1
                else (exc.messages if hasattr(exc, "messages") else str(exc))
            )
            return Response({"detail": msg}, status=status.HTTP_400_BAD_REQUEST)

        return Response(GymConfigSerializer(config).data, status=status.HTTP_200_OK)


class PlatformGymConfigView(APIView):
    """
    Super Admin endpoint on apex domain to inspect and update gym entitlements.
    """

    permission_classes = [
        IsAuthenticated,
        RequirePasswordChanged,
        CanEditGymEntitlements,
    ]

    @extend_schema(
        summary="Get gym config (platform)",
        description="Super Admin views configuration and entitlements of a gym tenant at apex platform.",
        responses={
            200: GymConfigSerializer,
            404: OpenApiResponse(description="Gym not found"),
        },
    )
    def get(self, request, gym_id, *args, **kwargs):
        try:
            gym = GymTenant.objects.get(id=gym_id)
        except GymTenant.DoesNotExist:
            return Response(
                {"detail": "Gym tenant not found."}, status=status.HTTP_404_NOT_FOUND
            )
        config = getattr(gym, "config", None)
        if config is None:
            config, _ = GymConfig.objects.get_or_create(gym=gym)
        return Response(GymConfigSerializer(config).data, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Update gym entitlements (platform)",
        description="Super Admin updates gym tier and feature entitlements at apex platform.",
        request=GymConfigSerializer,
        responses={
            200: GymConfigSerializer,
            400: OpenApiResponse(description="Validation error"),
            404: OpenApiResponse(description="Gym not found"),
        },
    )
    def patch(self, request, gym_id, *args, **kwargs):
        try:
            gym = GymTenant.objects.get(id=gym_id)
        except GymTenant.DoesNotExist:
            return Response(
                {"detail": "Gym tenant not found."}, status=status.HTTP_404_NOT_FOUND
            )

        try:
            config = update_gym_settings(gym, request.user, request.data)
        except ValidationError as exc:
            msg = (
                exc.messages[0]
                if hasattr(exc, "messages") and len(exc.messages) == 1
                else (exc.messages if hasattr(exc, "messages") else str(exc))
            )
            return Response({"detail": msg}, status=status.HTTP_400_BAD_REQUEST)

        return Response(GymConfigSerializer(config).data, status=status.HTTP_200_OK)


class FirstRunChecklistView(APIView):
    """
    Onboarding checklist progress for gym Owner.
    Derived automatically from database rows (branding, plan, staff, member).
    """

    permission_classes = [IsAuthenticated, RequirePasswordChanged, IsGymOwner]

    @extend_schema(
        summary="Get first-run onboarding checklist",
        description="Returns first-run checklist progress for the gym Owner.",
        responses={
            200: FirstRunChecklistResponseSerializer,
            403: OpenApiResponse(description="Forbidden - only Owner permitted"),
        },
    )
    def get(self, request, *args, **kwargs):
        gym = request.tenant
        data = get_first_run_checklist(gym)
        return Response(data, status=status.HTTP_200_OK)


class DismissFirstRunChecklistView(APIView):
    """
    Dismiss the first-run onboarding checklist for the gym Owner.
    Dismissal persists in GymConfig.first_run_dismissed_at.
    """

    permission_classes = [IsAuthenticated, RequirePasswordChanged, IsGymOwner]

    @extend_schema(
        summary="Dismiss first-run onboarding checklist",
        description="Persists dismissal of onboarding checklist for the gym.",
        request=None,
        responses={
            200: inline_serializer(
                name="DismissChecklistResponse",
                fields={
                    "is_dismissed": serializers.BooleanField(),
                    "dismissed_at": serializers.DateTimeField(),
                },
            ),
            403: OpenApiResponse(description="Forbidden - only Owner permitted"),
        },
    )
    def post(self, request, *args, **kwargs):
        gym = request.tenant
        config = dismiss_first_run_checklist(gym)
        return Response(
            {
                "is_dismissed": True,
                "dismissed_at": config.first_run_dismissed_at,
            },
            status=status.HTTP_200_OK,
        )


class GymPublicEntryView(APIView):
    """
    Public entry endpoint on gym subdomain.
    Returns gym name, brand color, logo, phone, location, currency.
    If certificate is not confirmed, returns 503 'still being secured'.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        summary="Public gym entry page",
        description="Public endpoint returning gym branding, details, and active plans on the gym subdomain. Shows 503 if TLS is pending.",
        responses={
            200: GymPublicEntryResponseSerializer,
            503: OpenApiResponse(description="Subdomain is still being secured"),
        },
    )
    def get(self, request, *args, **kwargs):
        gym = getattr(request, "tenant", None)

        if gym is None:
            subdomain = request.query_params.get("subdomain")
            if subdomain:
                gym = GymTenant.objects.filter(
                    subdomain=subdomain.strip().lower()
                ).first()

        if gym is None:
            return Response(
                {"detail": "Gym tenant context required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check TLS confirmation status
        if gym.tls_confirmed_at is None:
            return Response(
                {
                    "still_securing": True,
                    "name": gym.name,
                    "message": "This gym portal is still being secured. Please check back shortly.",
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        config = getattr(gym, "config", None)
        data = {
            "still_securing": False,
            "gym_id": gym.id,
            "name": gym.name,
            "subdomain": gym.subdomain,
            "brand_color": getattr(config, "brand_color", None) if config else None,
            "logo": getattr(config, "logo", None) if config else None,
            "phone": gym.contact_phone,
            "location": gym.location,
            "currency": gym.currency,
            "plans": [],
        }
        return Response(data, status=status.HTTP_200_OK)
