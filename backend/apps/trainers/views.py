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
from apps.trainers.ai.base import (
    AIPlanGenerationError,
    AIPlanStructureError,
    AIProviderTimeoutError,
)
from apps.trainers.models import (
    FitnessProfile,
    Trainer,
    TrainerAssignment,
    TrainingPlan,
)
from apps.trainers.permissions import (
    CanAccessMemberApprovedPlans,
    CanAccessMemberFitnessProfile,
    CanAccessMemberSelfFitnessProfile,
    CanManageMemberTrainingPlans,
    CanManageTrainingPlanDetail,
    HasAIPlansEnabled,
    HasTrainerModule,
    IsOwnerOrManager,
    IsTrainerRole,
)
from apps.trainers.serializers import (
    EditPlanRequestSerializer,
    FitnessProfileSerializer,
    GeneratePlanRequestSerializer,
    ManualReassignRequestSerializer,
    ManualReassignResponseSerializer,
    RejectPlanRequestSerializer,
    TrainerAssignmentDetailSerializer,
    TrainerCapacityUpdateResponseSerializer,
    TrainerCapacityUpdateSerializer,
    TrainerMyClientSerializer,
    TrainerSerializer,
    TrainingPlanSerializer,
    UnassignedMemberSerializer,
)
from apps.trainers.services import reassign_trainer


class GymTrainerListView(APIView):
    required_flag = "has_trainer_module"
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
    required_flag = "has_trainer_module"
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
    required_flag = "has_trainer_module"
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
    required_flag = "has_trainer_module"
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
    required_flag = "has_trainer_module"
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
    required_flag = "has_trainer_module"
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
    required_flag = "has_trainer_module"
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

        import datetime

        today = timezone.localdate()
        monday = today - datetime.timedelta(days=today.weekday())

        member_ids = [a.member_id for a in active_assignments]
        weekly_plans = TrainingPlan.all_objects.filter(
            gym=tenant,
            member_id__in=member_ids,
            week_start_date=monday,
        ).values("member_id", "status")

        member_plan_statuses = {}
        for wp in weekly_plans:
            m_id = str(wp["member_id"])
            member_plan_statuses.setdefault(m_id, set()).add(wp["status"])

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

            statuses = member_plan_statuses.get(str(a.member_id), set())
            has_approved = TrainingPlan.STATUS_APPROVED in statuses
            if has_approved:
                plan_status = "approved"
            elif TrainingPlan.STATUS_PENDING_REVIEW in statuses:
                plan_status = "pending_review"
            else:
                plan_status = "no_draft"

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
                    "has_approved_plan_this_week": has_approved,
                    "plan_status_this_week": plan_status,
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

    required_flag = "has_trainer_module"
    permission_classes = [
        IsAuthenticated,
        RequirePasswordChanged,
        HasTrainerModule,
        CanAccessMemberFitnessProfile,
    ]

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

    required_flag = "has_trainer_module"
    permission_classes = [
        IsAuthenticated,
        RequirePasswordChanged,
        HasTrainerModule,
        CanAccessMemberSelfFitnessProfile,
    ]

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


# ==============================================================================
# SPRINT 22: TRAINING PLAN VIEWS
# ==============================================================================


class GymMemberPlanStatusView(APIView):
    required_flag = "has_ai_plans"
    """
    Returns plan generation prerequisites and readiness status for a member.
    """

    authentication_classes = [FitGateJWTAuthentication]
    permission_classes = [
        IsAuthenticated,
        RequirePasswordChanged,
        HasTrainerModule,
        HasAIPlansEnabled,
        CanManageMemberTrainingPlans,
    ]

    @extend_schema(
        tags=["training-plans"],
        summary="Get plan generation prerequisites status for a member",
        responses={200: OpenApiResponse(description="Prerequisites status")},
    )
    def get(self, request, member_id):
        tenant = request.tenant
        member = Member.objects.filter(id=member_id, gym=tenant).first()
        if not member:
            raise NotFound({"detail": "Member not found."})

        from apps.trainers.services import get_plan_generation_prerequisites

        prereqs = get_plan_generation_prerequisites(member=member, gym=tenant)
        profile = getattr(member, "fitness_profile", None)
        has_caution = profile.has_medical_caution if profile else False

        return Response(
            {
                "eligible": prereqs["eligible"],
                "can_generate_this_week": prereqs["can_generate_this_week"],
                "can_generate_next_week": prereqs["can_generate_next_week"],
                "missing_requirements": prereqs["missing_requirements"],
                "this_week_draft_count": prereqs["this_week_draft_count"],
                "next_week_draft_count": prereqs["next_week_draft_count"],
                "has_open_draft_this_week": prereqs["has_open_draft_this_week"],
                "has_open_draft_next_week": prereqs["has_open_draft_next_week"],
                "open_draft_id_this_week": prereqs["open_draft_id_this_week"],
                "open_draft_id_next_week": prereqs["open_draft_id_next_week"],
                "has_medical_caution": has_caution,
            },
            status=status.HTTP_200_OK,
        )


class GymMemberTrainingPlanListView(APIView):
    required_flag = "has_ai_plans"
    """
    List training plans or generate a new draft for a member.
    """

    authentication_classes = [FitGateJWTAuthentication]
    permission_classes = [
        IsAuthenticated,
        RequirePasswordChanged,
        HasTrainerModule,
        HasAIPlansEnabled,
        CanManageMemberTrainingPlans,
    ]

    @extend_schema(
        tags=["training-plans"],
        summary="List training plans for a member",
        responses={200: TrainingPlanSerializer(many=True)},
    )
    def get(self, request, member_id):
        tenant = request.tenant
        member = Member.objects.filter(id=member_id, gym=tenant).first()
        if not member:
            raise NotFound({"detail": "Member not found."})

        plans = TrainingPlan.all_objects.filter(member=member, gym=tenant).order_by(
            "-week_start_date", "-draft_number"
        )
        serializer = TrainingPlanSerializer(plans, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        tags=["training-plans"],
        summary="Generate a training plan draft for a member",
        request=GeneratePlanRequestSerializer,
        responses={201: TrainingPlanSerializer},
    )
    def post(self, request, member_id):
        tenant = request.tenant
        member = Member.objects.filter(id=member_id, gym=tenant).first()
        if not member:
            raise NotFound({"detail": "Member not found."})

        serializer = GeneratePlanRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        from apps.trainers.services import generate_training_plan

        try:
            plan = generate_training_plan(
                member=member,
                gym=tenant,
                acting_user=request.user,
                week_choice=serializer.validated_data.get("week_choice", "this_week"),
                focus_this_week=serializer.validated_data.get(
                    "focus_this_week", ["no_focus"]
                ),
                other_focus=serializer.validated_data.get("other_focus", ""),
                trainer_notes="",
            )
            return Response(
                TrainingPlanSerializer(plan).data, status=status.HTTP_201_CREATED
            )
        except (
            AIPlanGenerationError,
            AIProviderTimeoutError,
            AIPlanStructureError,
        ):
            return Response(
                {"detail": "Generation failed, try again later"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except (DjangoValidationError, DRFValidationError) as exc:
            detail = getattr(
                exc,
                "detail",
                getattr(exc, "message", getattr(exc, "messages", str(exc))),
            )
            return Response({"detail": detail}, status=status.HTTP_400_BAD_REQUEST)


class GymTrainingPlanDetailView(APIView):
    required_flag = "has_ai_plans"
    """
    Retrieve details of a training plan.
    """

    authentication_classes = [FitGateJWTAuthentication]
    permission_classes = [
        IsAuthenticated,
        RequirePasswordChanged,
        HasTrainerModule,
        HasAIPlansEnabled,
        CanManageTrainingPlanDetail,
    ]

    @extend_schema(
        tags=["training-plans"],
        summary="Get training plan details",
        responses={200: TrainingPlanSerializer},
    )
    def get(self, request, pk):
        tenant = request.tenant

        plan = TrainingPlan.all_objects.filter(id=pk, gym=tenant).first()
        if not plan:
            raise NotFound({"detail": "Training plan not found."})

        return Response(TrainingPlanSerializer(plan).data, status=status.HTTP_200_OK)


class GymTrainingPlanApproveView(APIView):
    required_flag = "has_ai_plans"
    """
    Approve a pending training plan draft.
    """

    authentication_classes = [FitGateJWTAuthentication]
    permission_classes = [
        IsAuthenticated,
        RequirePasswordChanged,
        HasTrainerModule,
        HasAIPlansEnabled,
        CanManageTrainingPlanDetail,
    ]

    @extend_schema(
        tags=["training-plans"],
        summary="Approve a training plan draft",
        responses={200: TrainingPlanSerializer},
    )
    def post(self, request, pk):
        tenant = request.tenant

        plan = TrainingPlan.all_objects.filter(id=pk, gym=tenant).first()
        if not plan:
            raise NotFound({"detail": "Training plan not found."})

        from apps.trainers.services import approve_training_plan

        try:
            approved_plan = approve_training_plan(plan=plan, acting_user=request.user)
            return Response(
                TrainingPlanSerializer(approved_plan).data, status=status.HTTP_200_OK
            )
        except (DjangoValidationError, DRFValidationError) as exc:
            detail = getattr(
                exc,
                "detail",
                getattr(exc, "message", getattr(exc, "messages", str(exc))),
            )
            return Response({"detail": detail}, status=status.HTTP_400_BAD_REQUEST)


class GymTrainingPlanRejectView(APIView):
    required_flag = "has_ai_plans"
    """
    Reject a pending training plan draft and trigger regeneration.
    """

    authentication_classes = [FitGateJWTAuthentication]
    permission_classes = [
        IsAuthenticated,
        RequirePasswordChanged,
        HasTrainerModule,
        HasAIPlansEnabled,
        CanManageTrainingPlanDetail,
    ]

    @extend_schema(
        tags=["training-plans"],
        summary="Reject a training plan draft and regenerate",
        request=RejectPlanRequestSerializer,
        responses={201: TrainingPlanSerializer},
    )
    def post(self, request, pk):
        tenant = request.tenant

        plan = TrainingPlan.all_objects.filter(id=pk, gym=tenant).first()
        if not plan:
            raise NotFound({"detail": "Training plan not found."})

        serializer = RejectPlanRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        from apps.trainers.services import reject_training_plan

        try:
            new_draft = reject_training_plan(
                plan=plan,
                rejection_reasons=serializer.validated_data.get(
                    "rejection_reasons", []
                ),
                other_rejection_reason=serializer.validated_data.get(
                    "other_rejection_reason", ""
                ),
                acting_user=request.user,
            )
            return Response(
                TrainingPlanSerializer(new_draft).data, status=status.HTTP_201_CREATED
            )
        except (
            AIPlanGenerationError,
            AIProviderTimeoutError,
            AIPlanStructureError,
        ):
            return Response(
                {"detail": "Generation failed, try again later"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except (DjangoValidationError, DRFValidationError) as exc:
            detail = getattr(
                exc,
                "detail",
                getattr(exc, "message", getattr(exc, "messages", str(exc))),
            )
            return Response({"detail": detail}, status=status.HTTP_400_BAD_REQUEST)


class GymTrainingPlanEditView(APIView):
    required_flag = "has_ai_plans"
    """
    Directly edit exercises or nutrition guidance of a pending training plan draft.
    """

    authentication_classes = [FitGateJWTAuthentication]
    permission_classes = [
        IsAuthenticated,
        RequirePasswordChanged,
        HasTrainerModule,
        HasAIPlansEnabled,
        CanManageTrainingPlanDetail,
    ]

    @extend_schema(
        tags=["training-plans"],
        summary="Directly edit a pending training plan draft",
        request=EditPlanRequestSerializer,
        responses={200: TrainingPlanSerializer},
    )
    def patch(self, request, pk):
        tenant = request.tenant

        plan = TrainingPlan.all_objects.filter(id=pk, gym=tenant).first()
        if not plan:
            raise NotFound({"detail": "Training plan not found."})

        serializer = EditPlanRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        from apps.trainers.services import edit_training_plan_draft

        try:
            edited_plan = edit_training_plan_draft(
                plan=plan,
                plan_data=serializer.validated_data["plan_data"],
                acting_user=request.user,
            )
            return Response(
                TrainingPlanSerializer(edited_plan).data, status=status.HTTP_200_OK
            )
        except (DjangoValidationError, DRFValidationError) as exc:
            detail = getattr(
                exc,
                "detail",
                getattr(exc, "message", getattr(exc, "messages", str(exc))),
            )
            return Response({"detail": detail}, status=status.HTTP_400_BAD_REQUEST)


class MemberSelfTrainingPlanListView(APIView):
    """
    Read-only list of approved training plans for the authenticated member.
    Unapproved drafts and rejected plans are never visible to the member.
    """

    required_flag = "has_ai_plans"
    authentication_classes = [FitGateJWTAuthentication]
    permission_classes = [
        IsAuthenticated,
        RequirePasswordChanged,
        HasTrainerModule,
        HasAIPlansEnabled,
        CanAccessMemberApprovedPlans,
    ]

    @extend_schema(
        tags=["training-plans"],
        summary="Get approved training plans for authenticated member",
        responses={200: TrainingPlanSerializer(many=True)},
    )
    def get(self, request):
        tenant = request.tenant

        plans = TrainingPlan.all_objects.filter(
            member__user=request.user,
            gym=tenant,
            status=TrainingPlan.STATUS_APPROVED,
        ).order_by("-week_start_date")
        serializer = TrainingPlanSerializer(plans, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
