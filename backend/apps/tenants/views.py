"""API views for gym tenant administration and Super Admin platform management."""

from django.core.exceptions import ValidationError
from drf_spectacular.utils import OpenApiResponse, extend_schema, inline_serializer
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsSuperAdmin, RequirePasswordChanged
from apps.accounts.serializers import UserSummarySerializer
from apps.tenants.models import GymTenant
from apps.tenants.serializers import (
    ConfirmTLSResponseSerializer,
    CreateGymRequestSerializer,
    CreateGymResponseSerializer,
    GymConfigSerializer,
    GymTenantSummarySerializer,
    ProposeSubdomainResponseSerializer,
)
from apps.tenants.services import confirm_gym_tls, create_gym, propose_subdomain


class CreateGymView(APIView):
    """
    Super Admin endpoint to atomically create a new gym tenant, payment record,
    owner account, and provision the subdomain via cPanel UAPI.
    """

    permission_classes = [IsSuperAdmin, RequirePasswordChanged]

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

    permission_classes = [IsSuperAdmin, RequirePasswordChanged]

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

    permission_classes = [IsSuperAdmin, RequirePasswordChanged]

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

    permission_classes = [IsSuperAdmin, RequirePasswordChanged]

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

    permission_classes = [IsSuperAdmin, RequirePasswordChanged]

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
