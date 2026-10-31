from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.authentication import FitGateJWTAuthentication
from apps.accounts.permissions import RequirePasswordChanged
from apps.accounts.services import record_audit_log
from apps.memberships.models import Member, MemberSubscription
from apps.trainers.models import FitnessProfile, Trainer, TrainerAssignment
from apps.trainers.permissions import (
    CanAccessMemberFitnessProfile,
    CanAccessMemberSelfFitnessProfile,
    HasTrainerModule,
    IsOwnerOrManager,
    IsTrainerRole,
)
from apps.trainers.serializers import (
    FitnessProfileSerializer,
    ManualReassignRequestSerializer,
    ManualReassignResponseSerializer,
    TrainerAssignmentDetailSerializer,
    TrainerCapacityUpdateResponseSerializer,
    TrainerCapacityUpdateSerializer,
    TrainerMyClientSerializer,
    TrainerSerializer,
    UnassignedMemberSerializer,
)
from apps.trainers.services import reassign_trainer


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
                raise DRFValidationError(
                    {"max_clients": ["Reassign some clients first."]}
                )
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


class GymAssignmentListView(APIView):
    """List trainer assignments for the gym (Owner, Manager only)."""

    authentication_classes = [FitGateJWTAuthentication]
    permission_classes = [
        IsAuthenticated,
        RequirePasswordChanged,
        HasTrainerModule,
        IsOwnerOrManager,
    ]

    @extend_schema(
        tags=["trainers"],
        summary="List gym trainer assignments (Owner, Manager)",
        description="Returns trainer assignments for the gym.",
        responses={
            200: TrainerAssignmentDetailSerializer(many=True),
            401: OpenApiResponse(description="Authentication required"),
            403: OpenApiResponse(description="Forbidden"),
        },
    )
    def get(self, request, *args, **kwargs):
        tenant = request.tenant
        active_only = request.query_params.get("active_only", "true").lower() == "true"
        qs = TrainerAssignment.all_objects.filter(gym=tenant).select_related(
            "member", "trainer__user", "assigned_by"
        )
        if active_only:
            qs = qs.filter(ended_at__isnull=True)
        return Response(TrainerAssignmentDetailSerializer(qs, many=True).data)


class GymUnassignedMembersView(APIView):
    """List members on trainer-inclusive active plans without an assigned trainer."""

    authentication_classes = [FitGateJWTAuthentication]
    permission_classes = [
        IsAuthenticated,
        RequirePasswordChanged,
        HasTrainerModule,
        IsOwnerOrManager,
    ]

    @extend_schema(
        tags=["trainers"],
        summary="List unassigned members on trainer plans (Owner, Manager)",
        description="Returns members who have an active trainer-inclusive plan but no open assignment.",
        responses={
            200: UnassignedMemberSerializer(many=True),
            401: OpenApiResponse(description="Authentication required"),
            403: OpenApiResponse(description="Forbidden"),
        },
    )
    def get(self, request, *args, **kwargs):
        tenant = request.tenant
        today = timezone.localdate()

        active_subs = (
            MemberSubscription.all_objects.filter(
                gym=tenant,
                status=MemberSubscription.STATUS_ACTIVE,
                plan__trainer_inclusive=True,
                end_date__gte=today,
            )
            .select_related("member", "plan")
            .order_by("-start_date")
        )

        # Filter out members who already have an open assignment
        assigned_member_ids = set(
            TrainerAssignment.all_objects.filter(
                gym=tenant, ended_at__isnull=True
            ).values_list("member_id", flat=True)
        )

        unassigned_data = []
        seen_members = set()
        for sub in active_subs:
            if (
                sub.member_id not in assigned_member_ids
                and sub.member_id not in seen_members
            ):
                seen_members.add(sub.member_id)
                unassigned_data.append(
                    {
                        "member_id": sub.member_id,
                        "full_name": sub.member.full_name,
                        "phone": sub.member.phone,
                        "status": sub.member.status,
                        "plan_name": sub.plan.name,
                        "subscription_id": sub.id,
                        "start_date": sub.start_date,
                        "end_date": sub.end_date,
                    }
                )

        return Response(UnassignedMemberSerializer(unassigned_data, many=True).data)


class GymReassignTrainerView(APIView):
    """Manually assign or reassign a trainer to a member."""

    authentication_classes = [FitGateJWTAuthentication]
    permission_classes = [
        IsAuthenticated,
        RequirePasswordChanged,
        HasTrainerModule,
        IsOwnerOrManager,
    ]

    @extend_schema(
        tags=["trainers"],
        summary="Manually assign or reassign trainer (Owner, Manager)",
        description="Closes the previous open assignment and opens a new one.",
        request=ManualReassignRequestSerializer,
        responses={
            200: ManualReassignResponseSerializer,
            400: OpenApiResponse(
                description="Validation error or capacity confirmation needed"
            ),
            401: OpenApiResponse(description="Authentication required"),
            403: OpenApiResponse(description="Forbidden"),
            404: OpenApiResponse(description="Member or Trainer not found"),
        },
    )
    def post(self, request, *args, **kwargs):
        serializer = ManualReassignRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        member_id = serializer.validated_data["member_id"]
        trainer_id = serializer.validated_data["trainer_id"]
        confirm_over_capacity = serializer.validated_data.get(
            "confirm_over_capacity", False
        )

        tenant = request.tenant
        member = Member.all_objects.filter(id=member_id, gym=tenant).first()
        if not member:
            return Response(
                {"detail": "Member not found in this gym."},
                status=status.HTTP_404_NOT_FOUND,
            )

        trainer = (
            Trainer.all_objects.filter(id=trainer_id).select_related("user").first()
        )
        if not trainer:
            return Response(
                {"detail": "Trainer not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            assignment = reassign_trainer(
                member=member,
                new_trainer=trainer,
                actor=request.user,
                confirm_over_capacity=confirm_over_capacity,
            )
        except DjangoValidationError as exc:
            msg = (
                exc.message_dict
                if hasattr(exc, "message_dict")
                else {"detail": exc.messages if hasattr(exc, "messages") else str(exc)}
            )
            return Response(msg, status=status.HTTP_400_BAD_REQUEST)
        except DRFValidationError as exc:
            return Response(exc.detail, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                "detail": "Trainer assigned successfully.",
                "assignment": TrainerAssignmentDetailSerializer(assignment).data,
            },
            status=status.HTTP_200_OK,
        )


class TrainerMyClientsView(APIView):
    """View active clients assigned to the authenticated trainer."""

    authentication_classes = [FitGateJWTAuthentication]
    permission_classes = [
        IsAuthenticated,
        RequirePasswordChanged,
        HasTrainerModule,
        IsTrainerRole,
    ]

    @extend_schema(
        tags=["trainers"],
        summary="View own assigned clients (Trainer only)",
        description="Returns list of active clients assigned to the logged-in trainer.",
        responses={
            200: TrainerMyClientSerializer(many=True),
            401: OpenApiResponse(description="Authentication required"),
            403: OpenApiResponse(description="Forbidden"),
        },
    )
    def get(self, request, *args, **kwargs):
        tenant = request.tenant
        trainer = Trainer.all_objects.filter(user=request.user, gym=tenant).first()
        if not trainer:
            raise NotFound({"detail": "Trainer profile not found."})

        active_assignments = (
            TrainerAssignment.all_objects.filter(
                trainer=trainer,
                gym=tenant,
                ended_at__isnull=True,
            )
            .select_related("member")
            .order_by("-assigned_at")
        )

        today = timezone.localdate()
        clients_data = []
        for a in active_assignments:
            sub = (
                MemberSubscription.all_objects.filter(
                    gym=tenant,
                    member=a.member,
                    status=MemberSubscription.STATUS_ACTIVE,
                    end_date__gte=today,
                )
                .order_by("-end_date")
                .first()
            )
            plan_name = sub.plan.name if sub else "—"
            clients_data.append(
                {
                    "assignment_id": a.id,
                    "member_id": a.member_id,
                    "member_name": a.member.full_name,
                    "member_phone": a.member.phone,
                    "photo_url": a.member.photo_url or "",
                    "plan_name": plan_name,
                    "assigned_at": a.assigned_at,
                    "has_measurements": a.member.body_metrics.exists(),
                }
            )

        return Response(TrainerMyClientSerializer(clients_data, many=True).data)


class GymMemberFitnessProfileView(APIView):
    """
    Fitness profile endpoint for a gym member.
    GET: Retrieves the fitness profile along with latest trainer measurements.
    POST / PUT: Creates or updates the fitness profile.
    Access strictly enforced:
    - Assigned Trainer: Allowed
    - Owner / Manager: Allowed
    - Unrelated Trainer, Reception, Super Admin, other gyms, Member: 403 Forbidden.
    """

    permission_classes = [CanAccessMemberFitnessProfile]

    @extend_schema(
        summary="Get member fitness profile",
        responses={200: FitnessProfileSerializer},
    )
    def get(self, request, member_id):
        tenant = request.tenant
        member = Member.objects.filter(id=member_id, gym=tenant).first()
        if not member:
            raise NotFound({"detail": "Member not found."})

        profile = FitnessProfile.objects.filter(member=member, gym=tenant).first()
        if not profile:
            dummy_profile = FitnessProfile(member=member, gym=tenant)
            dummy_serializer = FitnessProfileSerializer(dummy_profile)
            return Response(
                {
                    "detail": "Fitness profile not found.",
                    "member_id": str(member.id),
                    "latest_measurements": dummy_serializer.data.get(
                        "latest_measurements"
                    ),
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = FitnessProfileSerializer(profile)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Create or update member fitness profile",
        request=FitnessProfileSerializer,
        responses={200: FitnessProfileSerializer},
    )
    def post(self, request, member_id):
        return self.save_profile(request, member_id)

    @extend_schema(
        summary="Update member fitness profile",
        request=FitnessProfileSerializer,
        responses={200: FitnessProfileSerializer},
    )
    def put(self, request, member_id):
        return self.save_profile(request, member_id)

    @extend_schema(
        summary="Partially update member fitness profile",
        request=FitnessProfileSerializer,
        responses={200: FitnessProfileSerializer},
    )
    def patch(self, request, member_id):
        return self.save_profile(request, member_id)

    def save_profile(self, request, member_id):
        tenant = request.tenant
        member = Member.objects.filter(id=member_id, gym=tenant).first()
        if not member:
            raise NotFound({"detail": "Member not found."})

        serializer = FitnessProfileSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        from apps.trainers.services import save_fitness_profile

        profile = save_fitness_profile(
            member=member,
            gym=tenant,
            data=serializer.validated_data,
            acting_user=request.user,
        )
        return Response(
            FitnessProfileSerializer(profile).data, status=status.HTTP_200_OK
        )


class MemberSelfFitnessProfileView(APIView):
    """
    Read-only fitness profile view for the authenticated member.
    """

    permission_classes = [CanAccessMemberSelfFitnessProfile]

    @extend_schema(
        summary="Get authenticated member own fitness profile",
        responses={200: FitnessProfileSerializer},
    )
    def get(self, request):
        tenant = request.tenant
        member = Member.objects.filter(user=request.user, gym=tenant).first()
        if not member:
            raise NotFound({"detail": "Member profile not found."})

        profile = FitnessProfile.objects.filter(member=member, gym=tenant).first()
        if not profile:
            raise NotFound({"detail": "Fitness profile not found."})

        serializer = FitnessProfileSerializer(profile)
        return Response(serializer.data, status=status.HTTP_200_OK)
