from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.authentication import FitGateJWTAuthentication
from apps.accounts.permissions import RequirePasswordChanged
from apps.accounts.services import record_audit_log
from apps.trainers.models import Trainer
from apps.trainers.permissions import (
    HasTrainerModule,
    IsOwnerOrManager,
    IsTrainerRole,
)
from apps.trainers.serializers import (
    TrainerCapacityUpdateResponseSerializer,
    TrainerCapacityUpdateSerializer,
    TrainerSerializer,
)


class GymTrainerListView(APIView):
    """List all trainers with client counts and capacities for the gym."""

    authentication_classes = [FitGateJWTAuthentication]
    permission_classes = [
        IsAuthenticated,
        RequirePasswordChanged,
        HasTrainerModule,
        IsOwnerOrManager,
    ]

    @extend_schema(
        tags=["trainers"],
        summary="List gym trainers (Owner, Manager)",
        description="Returns all trainers for the gym with their active client count and capacity.",
        responses={
            200: TrainerSerializer(many=True),
            401: OpenApiResponse(description="Authentication required"),
            403: OpenApiResponse(
                description="Permission denied or trainer module not enabled"
            ),
        },
    )
    def get(self, request, *args, **kwargs):
        tenant = request.tenant
        trainers = (
            Trainer.all_objects.filter(gym=tenant)
            .select_related("user")
            .order_by("user__full_name", "user__email")
        )
        return Response(TrainerSerializer(trainers, many=True).data)


class GymTrainerDetailView(APIView):
    """Retrieve or update a trainer's capacity and details."""

    authentication_classes = [FitGateJWTAuthentication]
    permission_classes = [
        IsAuthenticated,
        RequirePasswordChanged,
        HasTrainerModule,
        IsOwnerOrManager,
    ]

    def _get_trainer(self, request, pk):
        tenant = request.tenant
        trainer = (
            Trainer.all_objects.filter(id=pk, gym=tenant).select_related("user").first()
        )
        if not trainer:
            raise NotFound({"detail": "Trainer not found."})
        return trainer

    @extend_schema(
        tags=["trainers"],
        summary="Get trainer details (Owner, Manager)",
        description="Returns details, capacity, and active client count for a trainer.",
        responses={
            200: TrainerSerializer,
            401: OpenApiResponse(description="Authentication required"),
            403: OpenApiResponse(
                description="Permission denied or trainer module not enabled"
            ),
            404: OpenApiResponse(description="Trainer not found"),
        },
    )
    def get(self, request, pk, *args, **kwargs):
        trainer = self._get_trainer(request, pk)
        return Response(TrainerSerializer(trainer).data)

    @extend_schema(
        tags=["trainers"],
        summary="Update trainer capacity (Owner, Manager)",
        description="Updates a trainer's maximum client capacity (1 to 200). Warns if set below current client count.",
        request=TrainerCapacityUpdateSerializer,
        responses={
            200: TrainerCapacityUpdateResponseSerializer,
            400: OpenApiResponse(description="Invalid capacity value"),
            401: OpenApiResponse(description="Authentication required"),
            403: OpenApiResponse(
                description="Permission denied or trainer module not enabled"
            ),
            404: OpenApiResponse(description="Trainer not found"),
        },
    )
    def patch(self, request, pk, *args, **kwargs):
        trainer = self._get_trainer(request, pk)
        serializer = TrainerCapacityUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        old_capacity = trainer.max_clients
        current_clients = trainer.client_count
        warning = None

        if "max_clients" in serializer.validated_data:
            new_capacity = serializer.validated_data["max_clients"]
            if new_capacity < current_clients:
                warning = f"Capacity set to {new_capacity}, which is below the current active client count of {current_clients}."
            trainer.max_clients = new_capacity

        if "specialization" in serializer.validated_data:
            trainer.specialization = serializer.validated_data["specialization"]

        trainer.save()

        record_audit_log(
            action_type="trainer_capacity_updated",
            affected_record_type="Trainer",
            affected_record_id=str(trainer.id),
            actor=request.user,
            gym=request.tenant,
            metadata={
                "trainer_user_id": str(trainer.user_id),
                "trainer_email": trainer.user.email,
                "old_max_clients": old_capacity,
                "new_max_clients": trainer.max_clients,
                "current_client_count": current_clients,
            },
        )

        response_data = {
            "detail": "Trainer capacity updated successfully.",
            "warning": warning,
            "trainer": TrainerSerializer(trainer).data,
        }
        return Response(response_data, status=status.HTTP_200_OK)


class TrainerMeView(APIView):
    """View own trainer profile and client count."""

    authentication_classes = [FitGateJWTAuthentication]
    permission_classes = [
        IsAuthenticated,
        RequirePasswordChanged,
        HasTrainerModule,
        IsTrainerRole,
    ]

    @extend_schema(
        tags=["trainers"],
        summary="Get own trainer profile (Trainer only)",
        description="Returns the authenticated trainer's profile, client count, and capacity.",
        responses={
            200: TrainerSerializer,
            401: OpenApiResponse(description="Authentication required"),
            403: OpenApiResponse(
                description="Permission denied or trainer module not enabled"
            ),
            404: OpenApiResponse(description="Trainer profile not found"),
        },
    )
    def get(self, request, *args, **kwargs):
        tenant = request.tenant
        trainer = (
            Trainer.all_objects.filter(user=request.user, gym=tenant)
            .select_related("user")
            .first()
        )
        if not trainer:
            raise NotFound({"detail": "Trainer profile not found."})
        return Response(TrainerSerializer(trainer).data)
