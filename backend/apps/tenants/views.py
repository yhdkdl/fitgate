import os
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.http import FileResponse, Http404
from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.authentication import FitGateJWTAuthentication
from apps.accounts.models import User
from apps.accounts.notifications import notify_demo_request_received
from apps.accounts.permissions import (
    CanEditGymEntitlements,
    CanEditGymSettings,
    IsGymOwner,
    IsOwnerOrManager,
    IsSuperAdmin,
    RequirePasswordChanged,
)
from apps.accounts.serializers import UserSummarySerializer
from apps.accounts.services import record_audit_log
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
from apps.tenants.uapi import CPanelUAPIError


class CreateGymView(APIView):
    """
    Super Admin endpoint to atomically create a new gym tenant, payment record,
    owner account, and provision the subdomain via cPanel UAPI.
    """

    required_flag = None  # Tier-exempt (available on Starter)

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
        except IntegrityError:
            return Response(
                {"subdomain": ["Subdomain already exists."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except CPanelUAPIError:
            return Response(
                {"detail": "subdomain_provisioning_failed"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        scheme = getattr(settings, "PUBLIC_URL_SCHEME", "https")
        domain = getattr(settings, "DOMAIN", "fitgate.tebebtech.com")
        port = getattr(settings, "PUBLIC_PORT", "")
        port_suffix = f":{port}" if port else ""
        gym_url = f"{scheme}://{result['gym'].subdomain}.{domain}{port_suffix}/"

        response_data = {
            "gym": GymTenantSummarySerializer(result["gym"]).data,
            "config": GymConfigSerializer(result["config"]).data,
            "owner": UserSummarySerializer(result["owner"]).data,
            "payment_id": str(result["payment"].id),
            "gym_url": gym_url,
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
        status_param = request.query_params.get("status")
        if status_param and status_param != "all":
            if status_param == "awaiting_certificate":
                gyms = gyms.filter(status=GymTenant.STATUS_PENDING)
            else:
                gyms = gyms.filter(status=status_param)

        tier_param = request.query_params.get("tier")
        if tier_param and tier_param != "all":
            gyms = gyms.filter(tier=tier_param)

        search_param = request.query_params.get("search")
        if search_param:
            search_param = search_param.strip()
            gyms = gyms.filter(
                Q(name__icontains=search_param) | Q(subdomain__icontains=search_param)
            )

        serializer = GymTenantSummarySerializer(gyms, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ProposeSubdomainView(APIView):
    """Suggest an available, DNS-compliant subdomain candidate from a gym name."""

    required_flag = None  # Tier-exempt (available on Starter)

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

    required_flag = None  # Tier-exempt (available on Starter)

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

    required_flag = None
    permission_classes = [IsAuthenticated, RequirePasswordChanged, IsSuperAdmin]

    @extend_schema(
        summary="List gym tenants",
        description="Lists all gym tenants on the platform.",
        responses={200: GymTenantSummarySerializer(many=True)},
    )
    def get(self, request, *args, **kwargs):
        gyms = GymTenant.objects.all().order_by("-created_at")
        status_param = request.query_params.get("status")
        if status_param and status_param != "all":
            if status_param == "awaiting_certificate":
                gyms = gyms.filter(status=GymTenant.STATUS_PENDING)
            else:
                gyms = gyms.filter(status=status_param)

        tier_param = request.query_params.get("tier")
        if tier_param and tier_param != "all":
            gyms = gyms.filter(tier=tier_param)

        search_param = request.query_params.get("search")
        if search_param:
            search_param = search_param.strip()
            gyms = gyms.filter(
                Q(name__icontains=search_param) | Q(subdomain__icontains=search_param)
            )

        serializer = GymTenantSummarySerializer(gyms, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class GymDetailView(APIView):
    """Super Admin endpoint to retrieve gym tenant details and config."""

    required_flag = None  # Tier-exempt (available on Starter)

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

    required_flag = None  # Tier-exempt (available on Starter)

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

    required_flag = None  # Tier-exempt (available on Starter)

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

    required_flag = None  # Tier-exempt (available on Starter)

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

        with transaction.atomic():
            if "status" in serializer.validated_data:
                demo.status = serializer.validated_data["status"]
            if "notes" in serializer.validated_data:
                demo.notes = serializer.validated_data["notes"]
            demo.handled_by = request.user
            demo.save()

            record_audit_log(
                action_type="demo_request_updated",
                affected_record_type="DemoRequest",
                affected_record_id=str(demo.id),
                actor=request.user,
                gym=None,
                metadata={"status": demo.status},
            )

        return Response(DemoRequestSerializer(demo).data, status=status.HTTP_200_OK)


class DemoRequestConvertView(APIView):
    """Super Admin endpoint returning pre-filled data to convert a lead to a gym."""

    required_flag = None  # Tier-exempt (available on Starter)

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
    Returns 404 on tenant mismatch (cross-gym IDOR protection) or when file does not exist.
    """

    required_flag = None  # Tier-exempt (available on Starter)

    permission_classes = [IsAuthenticated, RequirePasswordChanged]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        gym_id = kwargs.get("gym_id")
        tenant = getattr(request, "tenant", None)
        if not tenant or str(gym_id) != str(tenant.id):
            raise Http404("Gym tenant not found.")

    @extend_schema(
        summary="Serve authenticated member photo",
        description="Serves member photo stream only to users belonging to the specified gym.",
        responses={
            200: OpenApiResponse(description="Image WebP stream"),
            400: OpenApiResponse(description="Invalid request or filename format"),
            401: OpenApiResponse(description="Authentication credentials required"),
            403: OpenApiResponse(
                description="Forbidden - user belongs to different gym or unauthorized role"
            ),
            404: OpenApiResponse(description="Photo not found or tenant mismatch"),
        },
    )
    def get(self, request, gym_id, filename, *args, **kwargs):
        if getattr(request.user, "gym_id", None) != request.tenant.id:
            raise PermissionDenied(
                "You do not have permission to access photos for another gym."
            )

        role = getattr(request.user, "role", None)
        if role not in (
            User.ROLE_OWNER,
            User.ROLE_MANAGER,
            User.ROLE_TRAINER,
            User.ROLE_RECEPTION,
            User.ROLE_MEMBER,
        ):
            raise PermissionDenied("Only gym staff or members may view member photos.")

        if role == User.ROLE_MEMBER:
            member = getattr(request.user, "member_profile", None)
            if not member:
                raise PermissionDenied(
                    "Members may only view their own photo or assigned trainer photo."
                )

            stored_filename = (
                os.path.basename(member.photo_url.rstrip("/"))
                if member.photo_url
                else None
            )
            is_own_photo = bool(stored_filename and filename == stored_filename)

            is_current_trainer_photo = False
            from apps.trainers.models import TrainerAssignment

            current_assignment = (
                TrainerAssignment.objects.filter(
                    member=member,
                    ended_at__isnull=True,
                    gym=request.tenant,
                )
                .select_related("trainer")
                .first()
            )

            if (
                current_assignment
                and current_assignment.trainer
                and current_assignment.trainer.photo_url
            ):
                trainer_filename = os.path.basename(
                    current_assignment.trainer.photo_url.rstrip("/")
                )
                if filename == trainer_filename:
                    is_current_trainer_photo = True

            if not is_own_photo and not is_current_trainer_photo:
                raise PermissionDenied(
                    "Members may only view their own photo or their current assigned trainer's photo."
                )

        elif role == User.ROLE_TRAINER:
            # Trainers can view their own trainer photo or photos of their currently assigned members
            trainer = getattr(request.user, "trainer_profile", None)
            stored_trainer_filename = (
                os.path.basename(trainer.photo_url.rstrip("/"))
                if (trainer and trainer.photo_url)
                else None
            )

            if stored_trainer_filename and filename == stored_trainer_filename:
                # Trainer's own photo
                pass
            else:
                from django.db.models import Q

                from apps.memberships.models import Member
                from apps.trainers.models import TrainerAssignment

                member = Member.objects.filter(
                    Q(photo_url__endswith=f"/{filename}/")
                    | Q(photo_url__endswith=f"/{filename}")
                    | Q(photo_url=filename),
                    gym=request.tenant,
                ).first()
                if not member:
                    return Response(
                        {"detail": "Photo not found."}, status=status.HTTP_404_NOT_FOUND
                    )

                is_assigned = TrainerAssignment.objects.filter(
                    trainer__user=request.user,
                    member=member,
                    ended_at__isnull=True,
                    gym=request.tenant,
                ).exists()

                if not is_assigned:
                    raise PermissionDenied(
                        "Trainers may only view photos of their assigned members."
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
    Also handles member photo listing for gym staff.
    """

    required_flag = None  # Tier-exempt (available on Starter)

    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [IsAuthenticated, RequirePasswordChanged]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        gym_id = kwargs.get("gym_id")
        tenant = getattr(request, "tenant", None)
        if not tenant or str(gym_id) != str(tenant.id):
            raise Http404("Gym tenant not found.")

    def get(self, request, gym_id, *args, **kwargs):
        """Photo list endpoint: only gym staff permitted."""
        if getattr(request.user, "gym_id", None) != request.tenant.id:
            raise PermissionDenied("You cannot list member photos for another gym.")

        role = getattr(request.user, "role", None)
        if role not in (
            User.ROLE_OWNER,
            User.ROLE_MANAGER,
            User.ROLE_TRAINER,
            User.ROLE_RECEPTION,
        ):
            raise PermissionDenied("Only gym staff may list member photos.")

        return Response([], status=status.HTTP_200_OK)

    @extend_schema(
        summary="Upload member photo",
        description="Validates image format and size (<= 2 MB), strips EXIF, resizes, and saves to gym-scoped authenticated storage.",
        request=UploadMemberPhotoSerializer,
        responses={
            201: UploadMemberPhotoResponseSerializer,
            400: OpenApiResponse(description="Validation error or missing file"),
            403: OpenApiResponse(description="Forbidden - cross-tenant access denied"),
            404: OpenApiResponse(description="Tenant mismatch"),
        },
    )
    def post(self, request, gym_id, *args, **kwargs):
        if getattr(request.user, "gym_id", None) != request.tenant.id:
            raise PermissionDenied("You cannot upload member photos for another gym.")

        role = getattr(request.user, "role", None)
        if role == User.ROLE_MEMBER:
            raise PermissionDenied("Members cannot upload or change photos.")

        if role not in (
            User.ROLE_OWNER,
            User.ROLE_MANAGER,
            User.ROLE_RECEPTION,
            User.ROLE_TRAINER,
        ):
            raise PermissionDenied("Only gym staff may upload member photos.")

        if role == User.ROLE_TRAINER and (
            request.data.get("member_id") or request.query_params.get("member_id")
        ):
            raise PermissionDenied("Trainers cannot upload or change member photos.")

        member_id = request.data.get("member_id") or request.query_params.get(
            "member_id"
        )
        if member_id:
            from apps.memberships.models import Member

            if (
                Member.all_objects.filter(id=member_id)
                .exclude(gym=request.tenant)
                .exists()
            ):
                raise PermissionDenied(
                    "You cannot upload or change photos for members of another gym."
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
        except Exception as exc:
            return Response(
                {"detail": f"Failed to save member photo: {str(exc)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        filename = os.path.basename(relative_path)
        url = f"/api/media/member-photos/{gym_id}/{filename}/"

        target_member = None
        with transaction.atomic():
            if role == User.ROLE_TRAINER:
                trainer = getattr(request.user, "trainer_profile", None)
                if not trainer:
                    raise Http404("Trainer profile not found.")
                trainer.photo_url = url
                trainer.save(update_fields=["photo_url"])
                record_audit_log(
                    action_type="trainer_photo_uploaded",
                    affected_record_type="Trainer",
                    affected_record_id=str(trainer.id),
                    actor=request.user,
                    gym=request.tenant,
                    metadata={"trainer_id": str(trainer.id), "filename": filename},
                )
            elif role == User.ROLE_MEMBER:
                target_member = getattr(request.user, "member_profile", None)
                if target_member:
                    target_member.photo_url = url
                    target_member.save(update_fields=["photo_url"])
            else:
                member_id = request.data.get("member_id") or request.query_params.get(
                    "member_id"
                )
                if member_id:
                    from apps.memberships.models import Member

                    target_member = Member.objects.filter(
                        gym=request.tenant, id=member_id
                    ).first()
                    if not target_member:
                        raise Http404("Member not found.")
                    target_member.photo_url = url
                    target_member.save(update_fields=["photo_url"])

            if role != User.ROLE_TRAINER:
                record_audit_log(
                    action_type="member_photo_uploaded",
                    affected_record_type="Member",
                    affected_record_id=(
                        str(target_member.id) if target_member else str(request.user.id)
                    ),
                    actor=request.user,
                    gym=request.tenant,
                    metadata={"filename": filename},
                )

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

    required_flag = None  # Tier-exempt (available on Starter)

    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [IsAuthenticated, RequirePasswordChanged, IsGymOwner]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        gym_id = kwargs.get("gym_id")
        tenant = getattr(request, "tenant", None)
        if not tenant or str(gym_id) != str(tenant.id):
            raise Http404("Gym tenant not found.")

    @extend_schema(
        summary="Upload gym logo",
        description="Uploads and optimizes gym logo (public asset). Only accessible by gym Owner.",
        request=UploadGymLogoSerializer,
        responses={
            200: UploadGymLogoResponseSerializer,
            400: OpenApiResponse(description="Validation error or missing file"),
            403: OpenApiResponse(description="Forbidden - only Owner permitted"),
            404: OpenApiResponse(description="Tenant mismatch"),
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

        config = getattr(request.tenant, "config", None)
        if config:
            with transaction.atomic():
                config.logo = url
                config.save(update_fields=["logo"])
                record_audit_log(
                    action_type="gym_logo_uploaded",
                    affected_record_type="GymConfig",
                    affected_record_id=str(config.pk),
                    actor=request.user,
                    gym=request.tenant,
                    metadata={"url": url},
                )

        return Response({"url": url}, status=status.HTTP_200_OK)


class GymSettingsView(APIView):
    """
    View and update gym configuration and branding settings.
    - Owner can update brand_color, logo, show_unavailable_equipment, member_reminder_days.
    - Owner attempting to update entitlement fields receives 403 Forbidden.
    - Manager and other staff roles receive 403 Forbidden.
    - Super Admin receives 403 Forbidden on gym subdomain (SPEC §2 indicates '-' for Super Admin).
    """

    required_flag = None  # Tier-exempt (available on Starter)

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

        from apps.payments.models import Payment

        past_payments = Payment.all_objects.filter(
            gym=gym,
            payer_type=Payment.PAYER_TYPE_GYM_SUBSCRIPTION,
        ).order_by("-created_at")
        data = GymConfigSerializer(config).data
        data["subscription"] = {
            "tier": gym.tier,
            "status": gym.status,
            "subscription_expires_at": (
                gym.subscription_expires_at.isoformat()
                if gym.subscription_expires_at
                else None
            ),
            "past_payments": [
                {
                    "id": str(p.id),
                    "date": p.created_at.date().isoformat() if p.created_at else None,
                    "amount": str(p.amount_etb),
                    "method": p.method,
                    "reference": p.bank_reference or p.bank_reference_normalized or "-",
                    "status": p.status,
                }
                for p in past_payments
            ],
        }
        return Response(data, status=status.HTTP_200_OK)

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
        config = getattr(gym, "config", None)
        if config is None:
            config, _ = GymConfig.objects.get_or_create(gym=gym)
        serializer = GymSettingsUpdateSerializer(
            instance=config,
            data=request.data,
            context={"request": request, "tenant": gym},
            partial=True,
        )
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

        from apps.payments.models import Payment

        past_payments = Payment.all_objects.filter(
            gym=gym,
            payer_type=Payment.PAYER_TYPE_GYM_SUBSCRIPTION,
        ).order_by("-created_at")
        data = GymConfigSerializer(config).data
        data["subscription"] = {
            "tier": gym.tier,
            "status": gym.status,
            "subscription_expires_at": (
                gym.subscription_expires_at.isoformat()
                if gym.subscription_expires_at
                else None
            ),
            "past_payments": [
                {
                    "id": str(p.id),
                    "date": p.created_at.date().isoformat() if p.created_at else None,
                    "amount": str(p.amount_etb),
                    "method": p.method,
                    "reference": p.bank_reference or p.bank_reference_normalized or "-",
                    "status": p.status,
                }
                for p in past_payments
            ],
        }
        return Response(data, status=status.HTTP_200_OK)


class PlatformGymConfigView(APIView):
    """
    Super Admin endpoint on apex domain to inspect and update gym entitlements.
    """

    required_flag = None  # Tier-exempt (available on Starter)

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
        from apps.payments.models import Payment

        past_payments = Payment.all_objects.filter(
            gym=gym,
            payer_type=Payment.PAYER_TYPE_GYM_SUBSCRIPTION,
        ).order_by("-created_at")
        data = GymConfigSerializer(config).data
        data["subscription"] = {
            "tier": gym.tier,
            "status": gym.status,
            "subscription_expires_at": (
                gym.subscription_expires_at.isoformat()
                if gym.subscription_expires_at
                else None
            ),
            "past_payments": [
                {
                    "id": str(p.id),
                    "date": p.created_at.date().isoformat() if p.created_at else None,
                    "amount": str(p.amount_etb),
                    "method": p.method,
                    "reference": p.bank_reference or p.bank_reference_normalized or "-",
                    "status": p.status,
                }
                for p in past_payments
            ],
        }
        return Response(data, status=status.HTTP_200_OK)

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
            if "tier" in request.data:
                tier_val = str(request.data["tier"]).lower()
                if tier_val in [GymTenant.TIER_STARTER, GymTenant.TIER_GROWTH]:
                    gym.tier = tier_val
                    gym.save(update_fields=["tier"])
            config = update_gym_settings(gym, request.user, request.data)
        except ValidationError as exc:
            msg = (
                exc.messages[0]
                if hasattr(exc, "messages") and len(exc.messages) == 1
                else (exc.messages if hasattr(exc, "messages") else str(exc))
            )
            return Response({"detail": msg}, status=status.HTTP_400_BAD_REQUEST)

        from apps.payments.models import Payment

        past_payments = Payment.all_objects.filter(
            gym=gym,
            payer_type=Payment.PAYER_TYPE_GYM_SUBSCRIPTION,
        ).order_by("-created_at")
        data = GymConfigSerializer(config).data
        data["subscription"] = {
            "tier": gym.tier,
            "status": gym.status,
            "subscription_expires_at": (
                gym.subscription_expires_at.isoformat()
                if gym.subscription_expires_at
                else None
            ),
            "past_payments": [
                {
                    "id": str(p.id),
                    "date": p.created_at.date().isoformat() if p.created_at else None,
                    "amount": str(p.amount_etb),
                    "method": p.method,
                    "reference": p.bank_reference or p.bank_reference_normalized or "-",
                    "status": p.status,
                }
                for p in past_payments
            ],
        }
        return Response(data, status=status.HTTP_200_OK)


class FirstRunChecklistView(APIView):
    """
    Onboarding checklist progress for gym Owner.
    Derived automatically from database rows (branding, plan, staff, member).
    """

    required_flag = None  # Tier-exempt (available on Starter)

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

    required_flag = None  # Tier-exempt (available on Starter)

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
        config = dismiss_first_run_checklist(gym, acting_user=request.user)
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

    required_flag = None  # Tier-exempt (available on Starter)

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
            config = getattr(gym, "config", None)
            from apps.memberships.models import MembershipPlan
            from apps.memberships.serializers import PublicPlanSerializer

            active_plans = MembershipPlan.all_objects.filter(
                gym=gym, is_active=True
            ).order_by("-created_at")

            from apps.tenants.models import get_gym_capabilities

            caps = get_gym_capabilities(gym)
            if not caps.get("has_trainer_module", False):
                active_plans = active_plans.exclude(trainer_inclusive=True)

            return Response(
                {
                    "still_securing": True,
                    "gym_id": gym.id,
                    "name": gym.name,
                    "subdomain": gym.subdomain,
                    "tier": gym.tier,
                    "capabilities": caps,
                    "brand_color": (
                        getattr(config, "brand_color", None) if config else None
                    ),
                    "logo": getattr(config, "logo", None) if config else None,
                    "phone": gym.contact_phone,
                    "location": gym.location,
                    "currency": gym.currency,
                    "message": "This gym portal is still being secured. Please check back shortly.",
                    "plans": PublicPlanSerializer(active_plans, many=True).data,
                    "online_payment_verified": False,
                    "has_group_classes": (
                        getattr(config, "has_group_classes", False) if config else False
                    ),
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        config = getattr(gym, "config", None)
        from apps.memberships.models import MembershipPlan
        from apps.memberships.serializers import PublicPlanSerializer
        from apps.payments.models import GymPaymentConfig

        active_plans = MembershipPlan.all_objects.filter(
            gym=gym, is_active=True
        ).order_by("-created_at")

        payment_cfg = GymPaymentConfig.all_objects.filter(gym=gym).first()
        online_payment_verified = bool(
            payment_cfg
            and payment_cfg.is_configured
            and payment_cfg.is_verified
            and payment_cfg.is_enabled
        )

        from apps.tenants.models import get_gym_capabilities

        caps = get_gym_capabilities(gym)
        if not caps.get("has_trainer_module", False):
            active_plans = active_plans.exclude(trainer_inclusive=True)

        data = {
            "still_securing": False,
            "gym_id": gym.id,
            "name": gym.name,
            "subdomain": gym.subdomain,
            "tier": gym.tier,
            "capabilities": caps,
            "brand_color": getattr(config, "brand_color", None) if config else None,
            "logo": getattr(config, "logo", None) if config else None,
            "phone": gym.contact_phone,
            "location": gym.location,
            "currency": gym.currency,
            "plans": PublicPlanSerializer(active_plans, many=True).data,
            "online_payment_verified": online_payment_verified,
            "has_group_classes": (
                getattr(config, "has_group_classes", False) if config else False
            ),
        }
        return Response(data, status=status.HTTP_200_OK)


class GymAnalyticsOverviewView(APIView):
    """
    Dashboard analytics for Gym Owner and Gym Manager.
    Returns active members, today's check-ins, monthly net revenue,
    memberships expiring in 7 days, and premium revenue by plan (Growth/Pro only).
    """

    required_flag = "has_analytics"
    authentication_classes = [FitGateJWTAuthentication]
    permission_classes = [IsAuthenticated, RequirePasswordChanged, IsOwnerOrManager]

    @extend_schema(
        summary="Get gym analytics overview",
        description="Returns core operational metrics and revenue by plan for Owner and Manager.",
        responses={200: OpenApiResponse(description="Analytics overview metrics")},
    )
    def get(self, request):
        tenant = request.tenant
        if not tenant:
            raise PermissionDenied("Tenant context required.")

        from apps.tenants.analytics import get_gym_analytics_overview

        data = get_gym_analytics_overview(tenant)
        return Response(data, status=status.HTTP_200_OK)


class GymNoticeListCreateView(APIView):
    """
    List notices for all authenticated gym users (members and staff).
    Post notice for Owner and Manager only, with optional Telegram channel broadcast.
    Gated by GymConfig.has_notices (Growth/Pro only).
    """

    required_flag = "has_notices"
    permission_classes = [IsAuthenticated, RequirePasswordChanged]

    def get(self, request, *args, **kwargs):
        from apps.accounts.models import User
        from apps.tenants.models import GymConfig, GymNotice
        from apps.tenants.serializers import GymNoticeSerializer

        tenant = getattr(request, "tenant", None)
        if not tenant:
            return Response([], status=status.HTTP_200_OK)

        config = GymConfig.objects.filter(gym=tenant).first()
        has_notices = getattr(config, "has_notices", False) if config else False

        if not has_notices:
            raise PermissionDenied(
                "Notice board is not available on this gym's current tier."
            )

        from django.db.models import Q

        if getattr(request.user, "role", None) == User.ROLE_OWNER:
            notices = GymNotice.all_objects.filter(
                Q(gym=tenant) | Q(gym__isnull=True)
            ).order_by("-created_at")
        else:
            notices = GymNotice.objects.filter(gym=tenant).order_by("-created_at")
        serializer = GymNoticeSerializer(notices, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        from apps.accounts.models import User
        from apps.accounts.services import record_audit_log
        from apps.tenants.models import GymConfig, GymNotice
        from apps.tenants.serializers import GymNoticeSerializer
        from apps.tenants.telegram import send_telegram_channel_message

        tenant = getattr(request, "tenant", None)
        if not tenant:
            return Response(
                {"detail": "Tenant required."}, status=status.HTTP_400_BAD_REQUEST
            )

        config = GymConfig.objects.filter(gym=tenant).first()
        if not config or not config.has_notices:
            raise PermissionDenied(
                "Notice board is not available on this gym's current tier."
            )

        role = getattr(request.user, "role", None)
        if role not in (User.ROLE_OWNER, User.ROLE_MANAGER):
            raise PermissionDenied("Only Owner and Manager can post announcements.")

        serializer = GymNoticeSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        notice = GymNotice.objects.create(
            gym=tenant,
            posted_by=request.user,
            title=serializer.validated_data["title"],
            body=serializer.validated_data["body"],
        )

        config = GymConfig.objects.filter(gym=tenant).first()
        telegram_channel = getattr(config, "telegram_channel", "") if config else ""
        telegram_sent = False
        telegram_note = "Telegram channel is not configured for this gym."

        if telegram_channel:
            telegram_msg = f"*{notice.title}*\n\n{notice.body}"
            telegram_sent, telegram_note = send_telegram_channel_message(
                channel=telegram_channel,
                message=telegram_msg,
            )

        record_audit_log(
            actor=request.user,
            action_type="notice_posted",
            affected_record_type="GymNotice",
            affected_record_id=str(notice.id),
            gym=tenant,
            metadata={
                "title": notice.title,
                "telegram_channel": telegram_channel,
                "telegram_sent": telegram_sent,
            },
        )

        data = GymNoticeSerializer(notice).data
        data["telegram_sent"] = telegram_sent
        data["telegram_note"] = telegram_note
        return Response(data, status=status.HTTP_201_CREATED)


class GymNoticeDetailView(APIView):
    """Delete a notice board announcement (Owner and Manager only)."""

    required_flag = "has_notices"
    permission_classes = [IsAuthenticated, RequirePasswordChanged]

    def delete(self, request, pk, *args, **kwargs):
        from apps.accounts.models import User
        from apps.accounts.services import record_audit_log
        from apps.tenants.models import GymConfig, GymNotice

        tenant = getattr(request, "tenant", None)
        config = GymConfig.objects.filter(gym=tenant).first()
        if not config or not config.has_notices:
            raise PermissionDenied(
                "Notice board is not available on this gym's current tier."
            )

        role = getattr(request.user, "role", None)
        if role not in (User.ROLE_OWNER, User.ROLE_MANAGER):
            raise PermissionDenied("Only Owner and Manager can delete announcements.")

        try:
            notice = GymNotice.all_objects.get(id=pk)
        except GymNotice.DoesNotExist:
            return Response(
                {"detail": "Notice not found."}, status=status.HTTP_404_NOT_FOUND
            )

        if notice.gym is None:
            raise PermissionDenied("Only Super Admin can delete platform notices.")
        if notice.gym != tenant:
            return Response(
                {"detail": "Notice not found."}, status=status.HTTP_404_NOT_FOUND
            )

        notice_title = notice.title
        notice_id = str(notice.id)
        notice.delete()

        record_audit_log(
            actor=request.user,
            action_type="notice_deleted",
            affected_record_type="GymNotice",
            affected_record_id=notice_id,
            gym=tenant,
            metadata={"title": notice_title},
        )

        return Response(status=status.HTTP_204_NO_CONTENT)


class TelegramTestMessageView(APIView):
    """Send a test message to the configured gym Telegram channel (Owner only)."""

    required_flag = "has_notices"
    permission_classes = [IsAuthenticated, RequirePasswordChanged, CanEditGymSettings]

    def post(self, request, *args, **kwargs):
        from apps.tenants.models import GymConfig
        from apps.tenants.telegram import send_telegram_channel_message

        tenant = getattr(request, "tenant", None)
        config = GymConfig.objects.filter(gym=tenant).first()
        if not config or not config.has_notices:
            raise PermissionDenied(
                "Telegram integration is not available on this gym's current tier."
            )
        channel = getattr(config, "telegram_channel", "") if config else ""

        if not channel:
            return Response(
                {
                    "success": False,
                    "detail": "Please configure and save a Telegram channel first.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        test_msg = f"🔔 FitGate Test: Telegram channel broadcast is configured successfully for {tenant.name}!"
        success, note = send_telegram_channel_message(channel, test_msg)

        return Response(
            {"success": success, "detail": note},
            status=status.HTTP_200_OK if success else status.HTTP_400_BAD_REQUEST,
        )


class PlatformNoticeListCreateView(APIView):
    """
    Super Admin endpoint to list and post platform notices.
    Broadcasts announcements to targeted gym Owners across any tier.
    """

    required_flag = None
    permission_classes = [IsAuthenticated, RequirePasswordChanged, IsSuperAdmin]

    def get(self, request, *args, **kwargs):
        if getattr(request, "tenant", None) is not None:
            raise PermissionDenied(
                "Super Admin operations must be performed at the apex platform domain."
            )
        from apps.tenants.models import PlatformNotice
        from apps.tenants.serializers import PlatformNoticeSerializer

        notices = (
            PlatformNotice.objects.all()
            .prefetch_related("target_gyms")
            .order_by("-created_at")
        )
        serializer = PlatformNoticeSerializer(notices, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        if getattr(request, "tenant", None) is not None:
            raise PermissionDenied(
                "Super Admin operations must be performed at the apex platform domain."
            )
        from apps.accounts.models import User
        from apps.accounts.notifications import create_notification
        from apps.accounts.services import record_audit_log
        from apps.tenants.models import GymTenant, PlatformNotice
        from apps.tenants.serializers import PlatformNoticeSerializer

        serializer = PlatformNoticeSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data.copy()
        target_gyms = data.pop("target_gyms", [])
        notice = PlatformNotice.objects.create(posted_by=request.user, **data)
        if target_gyms:
            notice.target_gyms.set(target_gyms)

        allowed_statuses = [GymTenant.STATUS_ACTIVE, GymTenant.STATUS_PENDING]
        if notice.audience_type == PlatformNotice.AUDIENCE_ALL:
            eligible_gyms = GymTenant.objects.filter(status__in=allowed_statuses)
        else:
            eligible_gyms = notice.target_gyms.filter(status__in=allowed_statuses)

        target_owners = User.all_objects.filter(
            gym__in=eligible_gyms,
            role=User.ROLE_OWNER,
            is_active=True,
        ).select_related("gym")

        for owner in target_owners:
            create_notification(
                recipient=owner,
                notification_type="platform_notice",
                message=f"Platform announcement: {notice.title}",
                gym=owner.gym,
            )

        record_audit_log(
            actor=request.user,
            action_type="platform_notice_created",
            affected_record_type="PlatformNotice",
            affected_record_id=str(notice.id),
            gym=None,
            metadata={
                "title": notice.title,
                "audience_type": notice.audience_type,
                "target_gym_count": eligible_gyms.count(),
            },
        )

        return Response(
            PlatformNoticeSerializer(notice).data, status=status.HTTP_201_CREATED
        )


class PlatformNoticeDetailView(APIView):
    """Super Admin endpoint to withdraw a platform notice."""

    required_flag = None
    permission_classes = [IsAuthenticated, RequirePasswordChanged, IsSuperAdmin]

    def delete(self, request, pk, *args, **kwargs):
        if getattr(request, "tenant", None) is not None:
            raise PermissionDenied(
                "Super Admin operations must be performed at the apex platform domain."
            )
        from apps.accounts.services import record_audit_log
        from apps.tenants.models import PlatformNotice

        try:
            notice = PlatformNotice.objects.get(id=pk)
        except PlatformNotice.DoesNotExist:
            return Response(
                {"detail": "Platform notice not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        notice.is_withdrawn = True
        notice.withdrawn_at = timezone.now()
        notice.withdrawn_by = request.user
        notice.save(
            update_fields=["is_withdrawn", "withdrawn_at", "withdrawn_by", "updated_at"]
        )

        record_audit_log(
            actor=request.user,
            action_type="platform_notice_withdrawn",
            affected_record_type="PlatformNotice",
            affected_record_id=str(notice.id),
            gym=None,
            metadata={"title": notice.title},
        )

        return Response(status=status.HTTP_204_NO_CONTENT)

    def post(self, request, pk, *args, **kwargs):
        """Allow explicit POST withdraw endpoint."""
        return self.delete(request, pk, *args, **kwargs)


class GymPlatformNoticeListView(APIView):
    """
    Gym-side endpoint for Owner to view platform notices from FitGate.
    Tier-exempt (available on Starter, Growth, etc.).
    Only for role Owner.
    Suspended and terminated gyms receive nothing.
    """

    required_flag = None
    permission_classes = [IsAuthenticated, RequirePasswordChanged]

    def get(self, request, *args, **kwargs):
        tenant = getattr(request, "tenant", None)
        if not tenant:
            return Response(
                {"detail": "Tenant required."}, status=status.HTTP_400_BAD_REQUEST
            )
        if request.user.role != User.ROLE_OWNER:
            return Response(
                {"detail": "Platform notices are accessible to gym Owners only."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if tenant.status in [GymTenant.STATUS_SUSPENDED, GymTenant.STATUS_TERMINATED]:
            return Response([], status=status.HTTP_200_OK)

        from django.db.models import Q

        from apps.tenants.models import PlatformNotice
        from apps.tenants.serializers import PlatformNoticeSerializer

        today = timezone.localdate()
        notices = (
            PlatformNotice.objects.filter(is_withdrawn=False)
            .filter(
                Q(audience_type=PlatformNotice.AUDIENCE_ALL) | Q(target_gyms=tenant)
            )
            .filter(Q(show_until__isnull=True) | Q(show_until__gte=today))
            .distinct()
            .order_by("-created_at")
        )

        serializer = PlatformNoticeSerializer(notices, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class GymSupportRequestListCreateView(APIView):
    """
    Gym staff (Owner and Manager) support request inbox and creation.
    Tier-exempt (available on every tier).
    Reception, Trainer, and Member are refused (403).
    Suspended/terminated gyms cannot send.
    Limit 5 new requests per gym per calendar day.
    """

    required_flag = None
    permission_classes = [IsAuthenticated, RequirePasswordChanged]

    def _check_access(self, request):
        tenant = getattr(request, "tenant", None)
        if not tenant:
            raise PermissionDenied("Gym context is required.")
        if request.user.role not in [User.ROLE_OWNER, User.ROLE_MANAGER]:
            raise PermissionDenied(
                "Contact FitGate is only accessible to gym Owners and Managers."
            )
        return tenant

    def get(self, request, *args, **kwargs):
        tenant = self._check_access(request)
        from apps.tenants.models import SupportRequest
        from apps.tenants.serializers import SupportRequestSerializer

        requests = (
            SupportRequest.objects.filter(gym=tenant)
            .prefetch_related("messages", "messages__sender")
            .order_by("-updated_at")
        )
        serializer = SupportRequestSerializer(requests, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        tenant = self._check_access(request)
        if tenant.status in [GymTenant.STATUS_SUSPENDED, GymTenant.STATUS_TERMINATED]:
            raise PermissionDenied(
                "Suspended or terminated gyms cannot submit support requests."
            )

        from apps.accounts.models import User
        from apps.accounts.notifications import create_notification
        from apps.accounts.services import record_audit_log
        from apps.tenants.models import SupportMessage, SupportRequest
        from apps.tenants.serializers import (
            SupportRequestCreateSerializer,
            SupportRequestSerializer,
        )

        # 5 new requests per calendar day limit
        today = timezone.localdate()
        today_count = SupportRequest.objects.filter(
            gym=tenant,
            created_at__date=today,
        ).count()
        if today_count >= 5:
            return Response(
                {
                    "detail": "Your gym has reached the limit of 5 new support requests for today. Please wait until tomorrow or reply to an existing request."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = SupportRequestCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        with transaction.atomic():
            req = SupportRequest.objects.create(
                gym=tenant,
                created_by=request.user,
                request_type=data["request_type"],
                subject=data["subject"],
                status=SupportRequest.STATUS_OPEN,
            )
            SupportMessage.objects.create(
                request=req,
                sender=request.user,
                sender_role=request.user.role,
                message=data["message"],
            )

        # Platform alert for Super Admin
        super_admins = User.all_objects.filter(
            role=User.ROLE_SUPER_ADMIN, is_active=True
        )
        for admin in super_admins:
            create_notification(
                recipient=admin,
                notification_type="support_request",
                message=f"New support request from {tenant.name}: {req.subject}",
                gym=None,
            )

        record_audit_log(
            actor=request.user,
            action_type="support_request_created",
            affected_record_type="SupportRequest",
            affected_record_id=str(req.id),
            gym=tenant,
            metadata={"subject": req.subject, "request_type": req.request_type},
        )

        return Response(
            SupportRequestSerializer(req).data, status=status.HTTP_201_CREATED
        )


class GymSupportRequestDetailReplyView(APIView):
    """
    Gym staff detail view and thread reply.
    Tier-exempt. Max 20 messages per thread.
    Gym reply on resolved reopens it.
    """

    required_flag = None
    permission_classes = [IsAuthenticated, RequirePasswordChanged]

    def _check_access(self, request, pk):
        tenant = getattr(request, "tenant", None)
        if not tenant:
            raise PermissionDenied("Gym context is required.")
        if request.user.role not in [User.ROLE_OWNER, User.ROLE_MANAGER]:
            raise PermissionDenied(
                "Contact FitGate is only accessible to gym Owners and Managers."
            )
        from apps.tenants.models import SupportRequest

        try:
            req = SupportRequest.objects.prefetch_related(
                "messages", "messages__sender"
            ).get(id=pk, gym=tenant)
        except SupportRequest.DoesNotExist:
            raise PermissionDenied("Support request not found.")
        return tenant, req

    def get(self, request, pk, *args, **kwargs):
        tenant, req = self._check_access(request, pk)
        from apps.tenants.serializers import SupportRequestSerializer

        return Response(SupportRequestSerializer(req).data, status=status.HTTP_200_OK)

    def post(self, request, pk, *args, **kwargs):
        tenant, req = self._check_access(request, pk)
        if tenant.status in [GymTenant.STATUS_SUSPENDED, GymTenant.STATUS_TERMINATED]:
            raise PermissionDenied(
                "Suspended or terminated gyms cannot reply to support requests."
            )

        if req.messages.count() >= 20:
            return Response(
                {
                    "detail": "This thread has reached the maximum limit of 20 messages. Please open a new request if you have further questions."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        from apps.accounts.models import User
        from apps.accounts.notifications import create_notification
        from apps.accounts.services import record_audit_log
        from apps.tenants.models import SupportMessage, SupportRequest
        from apps.tenants.serializers import (
            SupportReplySerializer,
            SupportRequestSerializer,
        )

        serializer = SupportReplySerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            SupportMessage.objects.create(
                request=req,
                sender=request.user,
                sender_role=request.user.role,
                message=serializer.validated_data["message"],
            )
            if req.status == SupportRequest.STATUS_RESOLVED:
                req.status = SupportRequest.STATUS_OPEN
            req.save(update_fields=["status", "updated_at"])

        # Alert Super Admins
        super_admins = User.all_objects.filter(
            role=User.ROLE_SUPER_ADMIN, is_active=True
        )
        for admin in super_admins:
            create_notification(
                recipient=admin,
                notification_type="support_message",
                message=f"New reply from {tenant.name} on '{req.subject}'",
                gym=None,
            )

        record_audit_log(
            actor=request.user,
            action_type="support_request_replied",
            affected_record_type="SupportRequest",
            affected_record_id=str(req.id),
            gym=tenant,
            metadata={"subject": req.subject},
        )

        return Response(SupportRequestSerializer(req).data, status=status.HTTP_200_OK)


class PlatformSupportRequestListView(APIView):
    """
    Super Admin support requests queue.
    Filters: status, gym_id, type.
    Super Admin sees only gym name and request text, never operational data.
    """

    required_flag = None
    permission_classes = [IsAuthenticated, RequirePasswordChanged, IsSuperAdmin]

    def get(self, request, *args, **kwargs):
        if getattr(request, "tenant", None) is not None:
            raise PermissionDenied(
                "Super Admin operations must be performed at the apex platform domain."
            )

        from apps.tenants.models import SupportRequest
        from apps.tenants.serializers import SupportRequestSerializer

        qs = (
            SupportRequest.objects.all()
            .select_related("gym", "created_by")
            .prefetch_related("messages", "messages__sender")
            .order_by("-updated_at")
        )

        status_param = request.query_params.get("status")
        if status_param:
            qs = qs.filter(status=status_param)

        gym_id = request.query_params.get("gym_id")
        if gym_id:
            qs = qs.filter(gym_id=gym_id)

        req_type = request.query_params.get("type")
        if req_type:
            qs = qs.filter(request_type=req_type)

        serializer = SupportRequestSerializer(qs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class PlatformSupportRequestDetailReplyView(APIView):
    """
    Super Admin view and reply to a support request thread.
    Dispatches bell notification to gym Owner and creating Manager.
    """

    required_flag = None
    permission_classes = [IsAuthenticated, RequirePasswordChanged, IsSuperAdmin]

    def get(self, request, pk, *args, **kwargs):
        if getattr(request, "tenant", None) is not None:
            raise PermissionDenied(
                "Super Admin operations must be performed at the apex platform domain."
            )

        from apps.tenants.models import SupportRequest
        from apps.tenants.serializers import SupportRequestSerializer

        try:
            req = (
                SupportRequest.objects.select_related("gym", "created_by")
                .prefetch_related("messages", "messages__sender")
                .get(id=pk)
            )
        except SupportRequest.DoesNotExist:
            return Response(
                {"detail": "Support request not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(SupportRequestSerializer(req).data, status=status.HTTP_200_OK)

    def post(self, request, pk, *args, **kwargs):
        if getattr(request, "tenant", None) is not None:
            raise PermissionDenied(
                "Super Admin operations must be performed at the apex platform domain."
            )

        from apps.accounts.models import User
        from apps.accounts.notifications import create_notification
        from apps.accounts.services import record_audit_log
        from apps.tenants.models import SupportMessage, SupportRequest
        from apps.tenants.serializers import (
            SupportReplySerializer,
            SupportRequestSerializer,
        )

        try:
            req = (
                SupportRequest.objects.select_related("gym", "created_by")
                .prefetch_related("messages")
                .get(id=pk)
            )
        except SupportRequest.DoesNotExist:
            return Response(
                {"detail": "Support request not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if req.messages.count() >= 20:
            return Response(
                {"detail": "This thread has reached the maximum limit of 20 messages."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = SupportReplySerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            SupportMessage.objects.create(
                request=req,
                sender=request.user,
                sender_role="super_admin",
                message=serializer.validated_data["message"],
            )
            if req.status == SupportRequest.STATUS_OPEN:
                req.status = SupportRequest.STATUS_IN_PROGRESS
            req.save(update_fields=["status", "updated_at"])

        # Bell notification for Owner and creating Manager
        recipients = list(
            User.all_objects.filter(gym=req.gym, role=User.ROLE_OWNER, is_active=True)
        )
        if (
            req.created_by
            and req.created_by.role == User.ROLE_MANAGER
            and req.created_by.is_active
            and req.created_by not in recipients
        ):
            recipients.append(req.created_by)

        for user in recipients:
            create_notification(
                recipient=user,
                notification_type="support_reply",
                message=f"FitGate Support replied to '{req.subject}'",
                gym=req.gym,
            )

        record_audit_log(
            actor=request.user,
            action_type="support_request_admin_replied",
            affected_record_type="SupportRequest",
            affected_record_id=str(req.id),
            gym=req.gym,
            metadata={"subject": req.subject},
        )

        return Response(SupportRequestSerializer(req).data, status=status.HTTP_200_OK)


class PlatformSupportRequestStatusView(APIView):
    """Super Admin change support request status (open, in_progress, resolved)."""

    required_flag = None
    permission_classes = [IsAuthenticated, RequirePasswordChanged, IsSuperAdmin]

    def patch(self, request, pk, *args, **kwargs):
        if getattr(request, "tenant", None) is not None:
            raise PermissionDenied(
                "Super Admin operations must be performed at the apex platform domain."
            )

        from apps.accounts.services import record_audit_log
        from apps.tenants.models import SupportRequest
        from apps.tenants.serializers import SupportRequestSerializer

        try:
            req = SupportRequest.objects.get(id=pk)
        except SupportRequest.DoesNotExist:
            return Response(
                {"detail": "Support request not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        new_status = request.data.get("status")
        valid_statuses = [s[0] for s in SupportRequest.STATUS_CHOICES]
        if new_status not in valid_statuses:
            return Response(
                {"detail": f"Status must be one of: {', '.join(valid_statuses)}."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        req.status = new_status
        req.save(update_fields=["status", "updated_at"])

        record_audit_log(
            actor=request.user,
            action_type="support_request_status_changed",
            affected_record_type="SupportRequest",
            affected_record_id=str(req.id),
            gym=req.gym,
            metadata={"new_status": new_status, "subject": req.subject},
        )

        return Response(SupportRequestSerializer(req).data, status=status.HTTP_200_OK)


class GymSubscriptionView(APIView):
    """
    Read-only gym subscription information for Owner.
    Returns: tier, status, subscription_expires_at, past platform payments.
    """

    required_flag = None
    permission_classes = [IsAuthenticated, RequirePasswordChanged, CanEditGymSettings]

    def get(self, request, *args, **kwargs):
        gym = request.tenant
        from apps.payments.models import Payment

        past_payments = Payment.all_objects.filter(
            gym=gym,
            payer_type=Payment.PAYER_TYPE_GYM_SUBSCRIPTION,
        ).order_by("-created_at")

        payments_data = [
            {
                "id": str(p.id),
                "date": p.created_at.date().isoformat() if p.created_at else None,
                "amount": str(p.amount_etb),
                "method": p.method,
                "reference": p.bank_reference or p.bank_reference_normalized or "-",
                "status": p.status,
            }
            for p in past_payments
        ]

        data = {
            "tier": gym.tier,
            "status": gym.status,
            "subscription_expires_at": (
                gym.subscription_expires_at.isoformat()
                if gym.subscription_expires_at
                else None
            ),
            "past_payments": payments_data,
        }
        return Response(data, status=status.HTTP_200_OK)


class GymTerminateView(APIView):
    """
    Super Admin endpoint to terminate a gym tenant (Sprint 35 Block 3).
    A gym can move from suspended to terminated only by Super Admin action.
    Cannot move directly from active to terminated.
    Requires gym to be currently suspended AND suspension must be at least 7 days old.
    Requires typing the exact gym subdomain to confirm.
    """

    required_flag = None

    permission_classes = [IsAuthenticated, RequirePasswordChanged, IsSuperAdmin]

    def post(self, request, gym_id, *args, **kwargs):
        if getattr(request, "tenant", None) is not None:
            raise PermissionDenied(
                "Super Admin operations must be performed at the apex platform domain."
            )
        from apps.accounts.services import record_audit_log
        from apps.tenants.models import GymTenant
        from apps.tenants.serializers import GymTenantSummarySerializer

        try:
            gym = GymTenant.objects.get(id=gym_id)
        except GymTenant.DoesNotExist:
            return Response(
                {"detail": "Gym tenant not found."}, status=status.HTTP_404_NOT_FOUND
            )

        if gym.status == GymTenant.STATUS_ACTIVE:
            return Response(
                {
                    "detail": "An active gym cannot be terminated directly; it must be suspended first."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if gym.status != GymTenant.STATUS_SUSPENDED:
            return Response(
                {
                    "detail": f"Only suspended gyms can be terminated (current status: {gym.status})."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        now = timezone.now()
        if not gym.suspended_at or now < (gym.suspended_at + timedelta(days=7)):
            return Response(
                {
                    "detail": "Gym suspension must be at least 7 days old before termination."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        confirmation = (
            str(request.data.get("subdomain_confirmation") or "").strip().lower()
        )
        if confirmation != gym.subdomain.lower():
            return Response(
                {
                    "detail": "Subdomain confirmation does not match the gym's exact subdomain."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        gym.status = GymTenant.STATUS_TERMINATED
        gym.save(update_fields=["status", "updated_at"])

        record_audit_log(
            actor=request.user,
            action_type="gym_terminated",
            affected_record_type="GymTenant",
            affected_record_id=str(gym.id),
            gym=gym,
            metadata={"subdomain": gym.subdomain, "name": gym.name},
        )

        return Response(GymTenantSummarySerializer(gym).data, status=status.HTTP_200_OK)


class GymReinstateView(APIView):
    """
    Super Admin endpoint to reinstate a terminated gym tenant back to suspended (Sprint 35 Block 3).
    A terminated gym can be reinstated back to 'suspended' only (never directly to active).
    From suspended, the existing payment and reactivation flow applies.
    """

    required_flag = None

    permission_classes = [IsAuthenticated, RequirePasswordChanged, IsSuperAdmin]

    def post(self, request, gym_id, *args, **kwargs):
        if getattr(request, "tenant", None) is not None:
            raise PermissionDenied(
                "Super Admin operations must be performed at the apex platform domain."
            )
        from apps.accounts.services import record_audit_log
        from apps.tenants.models import GymTenant
        from apps.tenants.serializers import GymTenantSummarySerializer

        try:
            gym = GymTenant.objects.get(id=gym_id)
        except GymTenant.DoesNotExist:
            return Response(
                {"detail": "Gym tenant not found."}, status=status.HTTP_404_NOT_FOUND
            )

        if gym.status != GymTenant.STATUS_TERMINATED:
            return Response(
                {
                    "detail": f"Only terminated gyms can be reinstated (current status: {gym.status})."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        confirmation = (
            str(request.data.get("subdomain_confirmation") or "").strip().lower()
        )
        if confirmation != gym.subdomain.lower():
            return Response(
                {
                    "detail": "Subdomain confirmation does not match the gym's exact subdomain."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        gym.status = GymTenant.STATUS_SUSPENDED
        gym.save(update_fields=["status", "updated_at"])

        record_audit_log(
            actor=request.user,
            action_type="gym_reinstated",
            affected_record_type="GymTenant",
            affected_record_id=str(gym.id),
            gym=gym,
            metadata={
                "subdomain": gym.subdomain,
                "name": gym.name,
                "reinstated_to": "suspended",
            },
        )

        return Response(GymTenantSummarySerializer(gym).data, status=status.HTTP_200_OK)


class PlatformAnalyticsOverviewView(APIView):
    """
    Platform revenue and metrics for Super Admin.
    Counts confirmed gym_subscription payments only and excludes demo gyms.
    Excludes demo and terminated gyms from active gym counts.
    """

    required_flag = None
    permission_classes = [IsAuthenticated, RequirePasswordChanged, IsSuperAdmin]

    def get(self, request, *args, **kwargs):
        if getattr(request, "tenant", None) is not None:
            raise PermissionDenied(
                "Super Admin operations must be performed at the apex platform domain."
            )
        from django.db.models import Sum

        from apps.payments.models import Payment
        from apps.tenants.models import GymTenant

        # Exclude demo gyms
        non_demo_gyms = GymTenant.objects.filter(is_demo=False)
        active_gyms = non_demo_gyms.filter(status=GymTenant.STATUS_ACTIVE).count()
        suspended_gyms = non_demo_gyms.filter(status=GymTenant.STATUS_SUSPENDED).count()
        terminated_gyms = non_demo_gyms.filter(
            status=GymTenant.STATUS_TERMINATED
        ).count()

        # Confirmed gym_subscription payments only, excluding demo gyms
        revenue_agg = Payment.all_objects.filter(
            payer_type=Payment.PAYER_TYPE_GYM_SUBSCRIPTION,
            status=Payment.STATUS_CONFIRMED,
            gym__is_demo=False,
        ).aggregate(total=Sum("amount_etb"))["total"]

        platform_revenue = str(revenue_agg) if revenue_agg is not None else "0.00"

        return Response(
            {
                "active_gyms": active_gyms,
                "suspended_gyms": suspended_gyms,
                "terminated_gyms": terminated_gyms,
                "platform_revenue_etb": platform_revenue,
            },
            status=status.HTTP_200_OK,
        )


class GymSuspendView(APIView):
    """
    Super Admin endpoint to suspend an active gym tenant (Sprint 35).
    """

    permission_classes = [IsAuthenticated, RequirePasswordChanged, IsSuperAdmin]
    required_flag = None

    def post(self, request, gym_id, *args, **kwargs):
        if getattr(request, "tenant", None) is not None:
            raise PermissionDenied(
                "Super Admin operations must be performed at the apex platform domain."
            )
        from apps.accounts.services import record_audit_log
        from apps.tenants.models import GymTenant
        from apps.tenants.serializers import GymTenantSummarySerializer

        try:
            gym = GymTenant.objects.get(id=gym_id)
        except GymTenant.DoesNotExist:
            return Response(
                {"detail": "Gym tenant not found."}, status=status.HTTP_404_NOT_FOUND
            )

        if gym.status != GymTenant.STATUS_ACTIVE:
            return Response(
                {
                    "detail": f"Only active gyms can be suspended (current status: {gym.status})."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        now = timezone.now()
        gym.status = GymTenant.STATUS_SUSPENDED
        gym.suspended_at = now
        gym.save(update_fields=["status", "suspended_at", "updated_at"])

        record_audit_log(
            actor=request.user,
            action_type="gym_suspended",
            affected_record_type="GymTenant",
            affected_record_id=str(gym.id),
            gym=gym,
            metadata={"subdomain": gym.subdomain, "name": gym.name},
        )

        return Response(GymTenantSummarySerializer(gym).data, status=status.HTTP_200_OK)


class GymRenewView(APIView):
    """
    Super Admin endpoint to record a renewal payment and extend gym subscription (Sprint 35).
    Renewal: Super Admin records a bank_transfer payment (amount, reference);
    subscription_expires_at extends by one year from the later of the current expiry or today,
    the lapse flag clears, and a suspended gym is reactivated.
    """

    required_flag = None
    permission_classes = [IsAuthenticated, RequirePasswordChanged, IsSuperAdmin]

    def post(self, request, gym_id, *args, **kwargs):
        if getattr(request, "tenant", None) is not None:
            raise PermissionDenied(
                "Super Admin operations must be performed at the apex platform domain."
            )
        from decimal import Decimal

        from apps.accounts.services import record_audit_log
        from apps.payments.models import Payment
        from apps.tenants.models import GymTenant
        from apps.tenants.serializers import GymTenantSummarySerializer

        try:
            gym = GymTenant.objects.get(id=gym_id)
        except GymTenant.DoesNotExist:
            return Response(
                {"detail": "Gym tenant not found."}, status=status.HTTP_404_NOT_FOUND
            )

        if gym.status == GymTenant.STATUS_TERMINATED:
            return Response(
                {"detail": "Terminated gyms cannot be renewed. Reinstate first."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        amount_raw = request.data.get("amount_etb") or request.data.get("amount")
        reference = str(request.data.get("reference") or "").strip()

        if not amount_raw:
            return Response(
                {"detail": "Amount in ETB is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            amount_val = Decimal(str(amount_raw))
            if amount_val <= 0:
                raise ValueError()
        except Exception:
            return Response(
                {"detail": "Amount must be a positive number."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not reference:
            return Response(
                {"detail": "Payment reference is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        now = timezone.now()
        base_date = (
            gym.subscription_expires_at
            if (gym.subscription_expires_at and gym.subscription_expires_at > now)
            else now
        )
        gym.subscription_expires_at = base_date + timedelta(days=365)
        gym.lapse_flagged_at = None

        was_suspended = gym.status == GymTenant.STATUS_SUSPENDED
        if was_suspended:
            gym.status = GymTenant.STATUS_ACTIVE
            gym.suspended_at = None

        gym.save(
            update_fields=[
                "subscription_expires_at",
                "lapse_flagged_at",
                "status",
                "suspended_at",
                "updated_at",
            ]
        )

        Payment.objects.create(
            gym=gym,
            payer_type=Payment.PAYER_TYPE_GYM_SUBSCRIPTION,
            method=Payment.METHOD_BANK_TRANSFER,
            amount_etb=amount_val,
            bank_reference=reference,
            bank_reference_normalized=reference.strip().upper(),
            status=Payment.STATUS_CONFIRMED,
            confirmed_by=request.user,
        )

        record_audit_log(
            actor=request.user,
            action_type="gym_renewed",
            affected_record_type="GymTenant",
            affected_record_id=str(gym.id),
            gym=gym,
            metadata={
                "subdomain": gym.subdomain,
                "name": gym.name,
                "amount_etb": str(amount_val),
                "reference": reference,
                "new_subscription_expires_at": gym.subscription_expires_at.isoformat(),
                "reactivated": was_suspended,
            },
        )

        return Response(GymTenantSummarySerializer(gym).data, status=status.HTTP_200_OK)
