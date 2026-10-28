"""Views for member registration, email verification, member profile management, and body metrics."""

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.http import Http404
from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.accounts.permissions import (
    IsGymStaff,
    IsMember,
    IsOwnerOrManager,
    RequirePasswordChanged,
)
from apps.accounts.services import record_audit_log
from apps.memberships.models import (
    BodyMetrics,
    Member,
    MemberFreeze,
    MembershipPlan,
)
from apps.memberships.serializers import (
    BodyMetricsSerializer,
    MemberDetailSerializer,
    MemberFreezeAllowanceSerializer,
    MemberFreezeRejectSerializer,
    MemberFreezeRequestSerializer,
    MemberFreezeSerializer,
    MemberSerializer,
    MembershipPlanSerializer,
    MemberSuspendRequestSerializer,
    MemberUpdateSerializer,
    PublicMemberRegistrationSerializer,
    PublicPlanSerializer,
    RecordBodyMetricsSerializer,
    StaffMemberRegistrationSerializer,
    VerifyEmailRequestSerializer,
)
from apps.memberships.services import (
    approve_membership_freeze,
    get_member_freeze_allowance,
    reactivate_member,
    register_member_self_service,
    register_member_staff_assisted,
    reject_membership_freeze,
    request_membership_freeze,
    suspend_member,
    verify_member_email,
)
from apps.memberships.throttling import (
    MemberRegistrationGymRateThrottle,
    MemberRegistrationIpRateThrottle,
    MemberRegistrationRateThrottle,
)


class PublicMemberRegistrationView(APIView):
    """
    Public endpoint for self-service member registration on a gym subdomain.
    Requires health waiver acceptance and rate-limited.
    """

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [
        MemberRegistrationRateThrottle,
        MemberRegistrationIpRateThrottle,
        MemberRegistrationGymRateThrottle,
    ]

    @extend_schema(
        summary="Self-service member registration",
        description="Public registration for new gym members on a gym subdomain. Requires health waiver.",
        request=PublicMemberRegistrationSerializer,
        responses={
            201: MemberSerializer,
            400: OpenApiResponse(
                description="Validation error, missing waiver, or duplicate email/phone"
            ),
            404: OpenApiResponse(description="Gym tenant not found"),
        },
    )
    def post(self, request, *args, **kwargs):
        tenant = getattr(request, "tenant", None)
        if tenant is None:
            return Response(
                {"detail": "Member registration is only available on a gym portal."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = PublicMemberRegistrationSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            member, _ = register_member_self_service(tenant, serializer.validated_data)
        except ValidationError as exc:
            detail = exc.message_dict if hasattr(exc, "message_dict") else exc.messages
            return Response(detail, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                "detail": "Registration successful. Please check your email to verify your account.",
                "member": MemberSerializer(member).data,
            },
            status=status.HTTP_201_CREATED,
        )


class VerifyEmailView(APIView):
    """
    Public endpoint to verify member email address with a single-use token.
    """

    permission_classes = [AllowAny]
    authentication_classes = []
    is_auth_endpoint = True

    @extend_schema(
        summary="Verify member email",
        description="Validates single-use token to verify self-registered member email address.",
        request=VerifyEmailRequestSerializer,
        responses={
            200: OpenApiResponse(description="Email verified successfully"),
            400: OpenApiResponse(description="Invalid or expired token"),
        },
    )
    def post(self, request, *args, **kwargs):
        serializer = VerifyEmailRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        raw_token = serializer.validated_data["token"]
        tenant = getattr(request, "tenant", None)

        try:
            verify_member_email(raw_token, tenant=tenant)
        except ValidationError as exc:
            detail = exc.message_dict if hasattr(exc, "message_dict") else exc.messages
            return Response(detail, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {"detail": "Email verified successfully."},
            status=status.HTTP_200_OK,
        )


class GymMemberListCreateView(APIView):
    """
    Staff endpoint to list gym members or register a new member (staff-assisted).
    List: Owner, Manager, Trainer, Reception.
    Create: Owner, Manager, Reception (Trainer gets 403).
    """

    parser_classes = [MultiPartParser, FormParser, JSONParser]
    permission_classes = [IsAuthenticated, RequirePasswordChanged, IsGymStaff]

    @extend_schema(
        summary="List gym members",
        description="Retrieves a list of members belonging to the current gym tenant.",
        responses={200: MemberSerializer(many=True)},
    )
    def get(self, request, *args, **kwargs):
        queryset = Member.objects.select_related("user").prefetch_related(
            "body_metrics"
        )

        search = request.query_params.get("search", "").strip()
        if search:
            queryset = queryset.filter(
                Q(full_name__icontains=search)
                | Q(phone__icontains=search)
                | Q(user__email__icontains=search)
            )

        status_filter = request.query_params.get("status", "").strip()
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        limit_param = request.query_params.get("limit")
        if limit_param:
            try:
                limit = min(max(int(limit_param), 1), 50)
                queryset = queryset[:limit]
            except ValueError:
                pass

        return Response(
            MemberSerializer(queryset, many=True, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        summary="Staff-assisted member registration",
        description="Registers a new member with set-password invitation link. Allowed for Owner, Manager, Reception.",
        request=StaffMemberRegistrationSerializer,
        responses={
            201: MemberSerializer,
            400: OpenApiResponse(description="Validation error or duplicate"),
            403: OpenApiResponse(
                description="Forbidden - Trainers cannot register members"
            ),
        },
    )
    def post(self, request, *args, **kwargs):
        role = getattr(request.user, "role", None)
        if role not in (User.ROLE_OWNER, User.ROLE_MANAGER, User.ROLE_RECEPTION):
            raise PermissionDenied(
                "Only Gym Owner, Manager, or Reception can register members."
            )

        serializer = StaffMemberRegistrationSerializer(
            data=request.data, context={"request": request}
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        reg_data = dict(serializer.validated_data)
        if "screenshot" in request.FILES:
            reg_data["screenshot_file"] = request.FILES["screenshot"]

        try:
            member, _ = register_member_staff_assisted(
                request.user,
                request.tenant,
                reg_data,
            )
        except ValidationError as exc:
            detail = exc.message_dict if hasattr(exc, "message_dict") else exc.messages
            return Response(detail, status=status.HTTP_400_BAD_REQUEST)

        created_receipt = getattr(member, "_created_receipt", None)
        from apps.payments.serializers import ReceiptSerializer

        return Response(
            {
                "detail": "Member registered successfully. Invitation email sent.",
                "member": MemberSerializer(member, context={"request": request}).data,
                "receipt": (
                    ReceiptSerializer(created_receipt).data if created_receipt else None
                ),
            },
            status=status.HTTP_201_CREATED,
        )


class GymMemberDetailView(APIView):
    """
    Staff endpoint for viewing and updating member details.
    """

    permission_classes = [IsAuthenticated, RequirePasswordChanged, IsGymStaff]

    def get_object(self, pk, gym):
        try:
            return (
                Member.objects.select_related("user")
                .prefetch_related("body_metrics")
                .get(pk=pk, gym=gym)
            )
        except Member.DoesNotExist:
            raise Http404("Member not found.")

    @extend_schema(
        summary="Get member details",
        description="Retrieves detailed member profile with body metrics history and estimates.",
        responses={
            200: MemberDetailSerializer,
            404: OpenApiResponse(description="Not found"),
        },
    )
    def get(self, request, pk, *args, **kwargs):
        member = self.get_object(pk, request.tenant)
        return Response(
            MemberDetailSerializer(member, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        summary="Update member profile",
        description="Allows Owner, Manager, or Reception to update member information.",
        request=MemberUpdateSerializer,
        responses={
            200: MemberDetailSerializer,
            400: OpenApiResponse(description="Validation error"),
            403: OpenApiResponse(description="Forbidden"),
            404: OpenApiResponse(description="Not found"),
        },
    )
    def patch(self, request, pk, *args, **kwargs):
        role = getattr(request.user, "role", None)
        if role not in (User.ROLE_OWNER, User.ROLE_MANAGER, User.ROLE_RECEPTION):
            raise PermissionDenied(
                "Only Gym Owner, Manager, or Reception can update member details."
            )

        member = self.get_object(pk, request.tenant)
        serializer = MemberUpdateSerializer(member, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            serializer.save()
            # Also sync full_name and phone to user record if modified
            user_updates = []
            if "full_name" in serializer.validated_data:
                member.user.full_name = serializer.validated_data["full_name"]
                user_updates.append("full_name")
            if "phone" in serializer.validated_data:
                member.user.phone = serializer.validated_data["phone"]
                user_updates.append("phone")
            if user_updates:
                member.user.save(update_fields=user_updates)

            record_audit_log(
                action_type="member_updated",
                affected_record_type="Member",
                affected_record_id=str(member.id),
                actor=request.user,
                gym=request.tenant,
                metadata={"status": member.status, "full_name": member.full_name},
            )

        return Response(
            MemberDetailSerializer(member, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )


class GymMemberRecordMetricsView(APIView):
    """
    Endpoint for viewing and recording body composition measurements for a member.
    - GET: Trainer, Owner, Manager of current gym (Reception, Member, Super Admin refused).
    - POST: Trainer ONLY of current gym (fail-closed: Owner, Manager, Reception, Member, Super Admin refused).
    """

    permission_classes = [IsAuthenticated, RequirePasswordChanged]

    def _get_member_or_check_tenant(self, pk, tenant):
        if not tenant:
            raise PermissionDenied("Gym tenant context required.")
        try:
            member = Member.all_objects.select_related("gym").get(pk=pk)
        except Member.DoesNotExist:
            raise Http404("Member not found.")

        if member.gym_id != tenant.id:
            raise PermissionDenied(
                "Cannot record or view measurements for a member of another gym."
            )
        return member

    @extend_schema(
        summary="List member body metrics",
        description="Retrieves body metrics history for a member. Allowed for Trainer, Owner, Manager.",
        responses={
            200: BodyMetricsSerializer(many=True),
            403: OpenApiResponse(description="Forbidden"),
            404: OpenApiResponse(description="Member not found"),
        },
    )
    def get(self, request, pk, *args, **kwargs):
        role = getattr(request.user, "role", None)
        if role not in (User.ROLE_TRAINER, User.ROLE_OWNER, User.ROLE_MANAGER):
            raise PermissionDenied(
                "Only Trainers, Owners, and Managers can view member measurements."
            )

        if getattr(request.user, "gym_id", None) != getattr(request.tenant, "id", None):
            raise PermissionDenied("Gym tenant context mismatch.")

        member = self._get_member_or_check_tenant(pk, request.tenant)
        metrics = member.body_metrics.all().order_by("-recorded_at")
        return Response(
            BodyMetricsSerializer(
                metrics, many=True, context={"request": request}
            ).data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        summary="Record member body metrics",
        description="Records new measurements for a member. Allowed for Trainer ONLY.",
        request=RecordBodyMetricsSerializer,
        responses={
            201: BodyMetricsSerializer,
            400: OpenApiResponse(description="Validation error"),
            403: OpenApiResponse(description="Forbidden - Trainer only"),
            404: OpenApiResponse(description="Member not found"),
        },
    )
    def post(self, request, pk, *args, **kwargs):
        role = getattr(request.user, "role", None)
        if role != User.ROLE_TRAINER:
            raise PermissionDenied("Only Trainers can record member body measurements.")

        if getattr(request.user, "gym_id", None) != getattr(request.tenant, "id", None):
            raise PermissionDenied("Gym tenant context mismatch.")

        member = self._get_member_or_check_tenant(pk, request.tenant)

        serializer = RecordBodyMetricsSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        validated = serializer.validated_data
        measurements = dict(validated.get("measurements") or {})
        for field in ("waist_cm", "neck_cm", "hip_cm"):
            val = validated.get(field)
            if val is not None:
                measurements[field] = float(val)

        with transaction.atomic():
            metrics = BodyMetrics.objects.create(
                gym=request.tenant,
                member=member,
                weight_kg=validated["weight_kg"],
                height_cm=validated["height_cm"],
                measurements=measurements,
                recorded_by=request.user,
                recorded_at=timezone.now(),
            )
            record_audit_log(
                action_type="member_metrics_recorded",
                affected_record_type="BodyMetrics",
                affected_record_id=str(metrics.id),
                actor=request.user,
                gym=request.tenant,
                metadata={
                    "member_id": str(member.id),
                    "weight_kg": str(metrics.weight_kg),
                    "height_cm": str(metrics.height_cm),
                    "trainer_id": str(request.user.id),
                    "trainer_name": request.user.full_name,
                },
            )

        return Response(
            BodyMetricsSerializer(metrics, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class MemberSelfProfileView(APIView):
    """
    Member self-service endpoint to view and update own profile.
    """

    permission_classes = [IsAuthenticated, RequirePasswordChanged, IsMember]

    @extend_schema(
        summary="View own member profile",
        description="Retrieves the logged-in member's profile and body metrics calculations.",
        responses={200: MemberDetailSerializer},
    )
    def get(self, request, *args, **kwargs):
        member = getattr(request.user, "member_profile", None)
        if member is None:
            raise Http404("Member profile not found.")

        return Response(
            MemberDetailSerializer(member, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        summary="Update own member contact info",
        description="Refused - members cannot edit personal details. Only password changes are permitted.",
        request=MemberUpdateSerializer,
        responses={
            403: OpenApiResponse(description="Forbidden - members cannot edit details"),
        },
    )
    def patch(self, request, *args, **kwargs):
        raise PermissionDenied(
            "Members cannot edit profile details. Only password changes are permitted."
        )


class MemberSelfMetricsView(APIView):
    """
    Member self-service endpoint to list own metrics.
    Members cannot enter or edit measurements.
    """

    permission_classes = [IsAuthenticated, RequirePasswordChanged, IsMember]

    @extend_schema(
        summary="List own body metrics history",
        description="Retrieves past body metrics records for the logged-in member.",
        responses={200: BodyMetricsSerializer(many=True)},
    )
    def get(self, request, *args, **kwargs):
        member = getattr(request.user, "member_profile", None)
        if member is None:
            raise Http404("Member profile not found.")

        metrics = member.body_metrics.all().order_by("-recorded_at")
        return Response(
            BodyMetricsSerializer(
                metrics, many=True, context={"request": request}
            ).data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        summary="Record own body metrics",
        description="Refused - members cannot enter or edit measurements.",
        responses={403: OpenApiResponse(description="Forbidden")},
    )
    def post(self, request, *args, **kwargs):
        raise PermissionDenied(
            "Members cannot enter or edit measurements. A trainer records measurements."
        )


class MembershipPlanListCreateView(APIView):
    """
    List and create membership plans for the gym.
    Read: Gym Staff (all plans) and Members (active plans only).
    Write: Owner and Manager only.
    """

    permission_classes = [IsAuthenticated, RequirePasswordChanged]

    @extend_schema(
        summary="List gym membership plans",
        description="Returns membership plans configured for the gym.",
        responses={200: MembershipPlanSerializer(many=True)},
    )
    def get(self, request, *args, **kwargs):
        tenant = getattr(request, "tenant", None)
        if tenant is None:
            raise Http404("Gym tenant context required.")

        plans = MembershipPlan.objects.filter(gym=tenant).order_by("-created_at")
        if request.user.role == User.ROLE_MEMBER:
            plans = plans.filter(is_active=True)

        return Response(
            MembershipPlanSerializer(plans, many=True).data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        summary="Create gym membership plan",
        description="Owner or Manager creates a new membership plan. Warns if trainer-inclusive with no trainers.",
        request=MembershipPlanSerializer,
        responses={
            201: MembershipPlanSerializer,
            400: OpenApiResponse(description="Validation error"),
            403: OpenApiResponse(description="Forbidden"),
        },
    )
    def post(self, request, *args, **kwargs):
        tenant = getattr(request, "tenant", None)
        if tenant is None:
            raise Http404("Gym tenant context required.")

        # RBAC: Only Owner or Manager can create plans
        if request.user.role not in (User.ROLE_OWNER, User.ROLE_MANAGER):
            raise PermissionDenied(
                "Only gym owners and managers can create membership plans."
            )

        serializer = MembershipPlanSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        trainer_inclusive = serializer.validated_data.get("trainer_inclusive", False)
        warning = None
        if trainer_inclusive:
            has_trainers = User.objects.filter(
                gym=tenant, role=User.ROLE_TRAINER, is_active=True
            ).exists()
            if not has_trainers:
                warning = (
                    "This gym currently has no active trainers. The plan has been created, "
                    "but trainer assignment will not be possible until trainers are added."
                )

        with transaction.atomic():
            plan = serializer.save(gym=tenant)
            record_audit_log(
                action_type="membership_plan_created",
                affected_record_type="MembershipPlan",
                affected_record_id=str(plan.id),
                actor=request.user,
                gym=tenant,
                metadata={
                    "name": plan.name,
                    "duration": f"{plan.duration_value} {plan.duration_unit}",
                    "price_etb": str(plan.price_etb),
                    "trainer_inclusive": plan.trainer_inclusive,
                },
            )

        resp_data = MembershipPlanSerializer(plan).data
        resp_data["has_no_trainers_warning"] = bool(warning)
        if warning:
            resp_data["warning"] = warning

        return Response(resp_data, status=status.HTTP_201_CREATED)


class MembershipPlanDetailView(APIView):
    """
    Retrieve, update, or deactivate a membership plan.
    Read: Gym Staff.
    Write/Deactivate: Owner and Manager only.
    """

    permission_classes = [IsAuthenticated, RequirePasswordChanged, IsGymStaff]

    def _get_plan(self, pk, tenant):
        plan = MembershipPlan.objects.filter(id=pk, gym=tenant).first()
        if not plan:
            raise Http404("Membership plan not found.")
        return plan

    @extend_schema(
        summary="Retrieve membership plan details",
        responses={200: MembershipPlanSerializer},
    )
    def get(self, request, pk, *args, **kwargs):
        tenant = getattr(request, "tenant", None)
        if tenant is None:
            raise Http404("Gym tenant context required.")
        plan = self._get_plan(pk, tenant)
        return Response(MembershipPlanSerializer(plan).data, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Update membership plan",
        description="Owner or Manager updates a plan. Price changes do not affect past payments or existing subscriptions.",
        request=MembershipPlanSerializer,
        responses={
            200: MembershipPlanSerializer,
            403: OpenApiResponse(description="Forbidden"),
        },
    )
    def patch(self, request, pk, *args, **kwargs):
        tenant = getattr(request, "tenant", None)
        if tenant is None:
            raise Http404("Gym tenant context required.")

        if request.user.role not in (User.ROLE_OWNER, User.ROLE_MANAGER):
            raise PermissionDenied(
                "Only gym owners and managers can update membership plans."
            )

        plan = self._get_plan(pk, tenant)
        serializer = MembershipPlanSerializer(plan, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        trainer_inclusive = serializer.validated_data.get(
            "trainer_inclusive", plan.trainer_inclusive
        )
        warning = None
        if trainer_inclusive:
            has_trainers = User.objects.filter(
                gym=tenant, role=User.ROLE_TRAINER, is_active=True
            ).exists()
            if not has_trainers:
                warning = (
                    "This gym currently has no active trainers. The plan has been updated, "
                    "but trainer assignment will not be possible until trainers are added."
                )

        with transaction.atomic():
            old_price_etb = str(plan.price_etb)
            updated_plan = serializer.save()
            record_audit_log(
                action_type="membership_plan_updated",
                affected_record_type="MembershipPlan",
                affected_record_id=str(updated_plan.id),
                actor=request.user,
                gym=tenant,
                metadata={
                    "name": updated_plan.name,
                    "old_price_etb": old_price_etb,
                    "price_etb": str(updated_plan.price_etb),
                    "is_active": updated_plan.is_active,
                },
            )

        resp_data = MembershipPlanSerializer(updated_plan).data
        resp_data["has_no_trainers_warning"] = bool(warning)
        if warning:
            resp_data["warning"] = warning

        return Response(resp_data, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Deactivate membership plan",
        description="Owner or Manager deactivates plan. Existing subscriptions remain intact.",
        responses={200: OpenApiResponse(description="Plan deactivated")},
    )
    def delete(self, request, pk, *args, **kwargs):
        tenant = getattr(request, "tenant", None)
        if tenant is None:
            raise Http404("Gym tenant context required.")

        if request.user.role not in (User.ROLE_OWNER, User.ROLE_MANAGER):
            raise PermissionDenied(
                "Only gym owners and managers can deactivate membership plans."
            )

        plan = self._get_plan(pk, tenant)
        with transaction.atomic():
            plan.is_active = False
            plan.save(update_fields=["is_active", "updated_at"])
            record_audit_log(
                action_type="membership_plan_deactivated",
                affected_record_type="MembershipPlan",
                affected_record_id=str(plan.id),
                actor=request.user,
                gym=tenant,
                metadata={"name": plan.name},
            )

        return Response(
            {
                "detail": "Membership plan deactivated successfully.",
                "plan": MembershipPlanSerializer(plan).data,
            },
            status=status.HTTP_200_OK,
        )


class PublicPlanListView(APIView):
    """
    Public endpoint on gym subdomain returning all active membership plans.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        summary="List active plans publicly",
        description="Visitors can view all active plans and prices without logging in.",
        responses={200: PublicPlanSerializer(many=True)},
    )
    def get(self, request, *args, **kwargs):
        tenant = getattr(request, "tenant", None)
        if tenant is None:
            subdomain = request.query_params.get("subdomain")
            if subdomain:
                from apps.tenants.models import GymTenant

                tenant = GymTenant.objects.filter(
                    subdomain=subdomain.strip().lower()
                ).first()

        if tenant is None:
            return Response(
                {"detail": "Gym tenant context required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        plans = MembershipPlan.all_objects.filter(gym=tenant, is_active=True).order_by(
            "-created_at"
        )
        return Response(
            PublicPlanSerializer(plans, many=True).data,
            status=status.HTTP_200_OK,
        )


class MemberSuspendView(APIView):
    """
    Suspend a gym member.
    Allowed: Owner and Manager only.
    """

    permission_classes = [IsAuthenticated, RequirePasswordChanged, IsOwnerOrManager]

    @extend_schema(
        summary="Suspend a member",
        description="Owner or Manager suspends a member. Moves subscription status to suspended.",
        request=MemberSuspendRequestSerializer,
        responses={200: OpenApiResponse(description="Member suspended")},
    )
    def post(self, request, pk, *args, **kwargs):
        tenant = getattr(request, "tenant", None)
        if tenant is None:
            raise Http404("Gym tenant context required.")

        member = Member.objects.filter(id=pk, gym=tenant).first()
        if not member:
            raise Http404("Member not found.")

        serializer = MemberSuspendRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reason = serializer.validated_data.get("reason", "")

        suspended_member = suspend_member(member, actor=request.user, reason=reason)
        return Response(
            {
                "detail": f"Member {suspended_member.full_name} has been suspended.",
                "status": suspended_member.status,
                "member": MemberDetailSerializer(
                    suspended_member, context={"request": request}
                ).data,
            },
            status=status.HTTP_200_OK,
        )


class MemberReactivateView(APIView):
    """
    Reactivate a suspended gym member.
    Allowed: Owner and Manager only.
    """

    permission_classes = [IsAuthenticated, RequirePasswordChanged, IsOwnerOrManager]

    @extend_schema(
        summary="Reactivate a suspended member",
        description="Owner or Manager reactivates a suspended member.",
        responses={200: OpenApiResponse(description="Member reactivated")},
    )
    def post(self, request, pk, *args, **kwargs):
        tenant = getattr(request, "tenant", None)
        if tenant is None:
            raise Http404("Gym tenant context required.")

        member = Member.objects.filter(id=pk, gym=tenant).first()
        if not member:
            raise Http404("Member not found.")

        reactivated_member = reactivate_member(member, actor=request.user)
        return Response(
            {
                "detail": f"Member {reactivated_member.full_name} has been reactivated.",
                "status": reactivated_member.status,
                "member": MemberDetailSerializer(
                    reactivated_member, context={"request": request}
                ).data,
            },
            status=status.HTTP_200_OK,
        )


class MemberFreezeRequestView(APIView):
    """
    Submit a membership freeze request for the logged-in member.
    Allowed: Member of that gym only. Denied: All other roles, Super Admin, cross-gym (403).
    """

    permission_classes = [IsAuthenticated, RequirePasswordChanged, IsMember]

    @extend_schema(
        summary="Submit a membership freeze request (Member only)",
        description="Submits a freeze request for the authenticated member's active subscription.",
        request=MemberFreezeRequestSerializer,
        responses={
            201: MemberFreezeSerializer,
            400: OpenApiResponse(description="Validation error or allowance exceeded"),
            403: OpenApiResponse(description="Permission denied"),
        },
    )
    def post(self, request, *args, **kwargs):
        if request.user.role == User.ROLE_SUPER_ADMIN:
            return Response(
                {"detail": "Super Admin cannot request a membership freeze."},
                status=status.HTTP_403_FORBIDDEN,
            )
        tenant = getattr(request, "tenant", None)
        if not tenant:
            return Response(
                {"detail": "Tenant required."}, status=status.HTTP_400_BAD_REQUEST
            )

        member = Member.all_objects.filter(user=request.user, gym=tenant).first()
        if not member:
            return Response(
                {"detail": "Member profile not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = MemberFreezeRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        start_date = serializer.validated_data["start_date"]
        end_date = serializer.validated_data["end_date"]
        reason = serializer.validated_data["reason"]

        try:
            freeze = request_membership_freeze(
                member=member,
                start_date=start_date,
                end_date=end_date,
                reason=reason,
            )
        except ValidationError as exc:
            detail = exc.message_dict if hasattr(exc, "message_dict") else exc.messages
            return Response({"detail": detail}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            MemberFreezeSerializer(freeze).data,
            status=status.HTTP_201_CREATED,
        )


class MemberMyFreezesView(APIView):
    """
    List freeze requests submitted by the logged-in member.
    Allowed: Member only. Denied: All other roles, Super Admin (403).
    """

    permission_classes = [IsAuthenticated, RequirePasswordChanged, IsMember]

    @extend_schema(
        summary="List my freeze requests (Member only)",
        description="Returns all freeze requests for the logged-in member.",
        responses={200: MemberFreezeSerializer(many=True)},
    )
    def get(self, request, *args, **kwargs):
        if request.user.role == User.ROLE_SUPER_ADMIN:
            return Response(
                {"detail": "Super Admin cannot view member freezes."},
                status=status.HTTP_403_FORBIDDEN,
            )
        tenant = getattr(request, "tenant", None)
        if not tenant:
            return Response(
                {"detail": "Tenant required."}, status=status.HTTP_400_BAD_REQUEST
            )

        member = Member.all_objects.filter(user=request.user, gym=tenant).first()
        if not member:
            return Response(
                {"detail": "Member profile not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        freezes = MemberFreeze.all_objects.filter(member=member, gym=tenant).order_by(
            "-created_at"
        )

        return Response(
            MemberFreezeSerializer(freezes, many=True).data,
            status=status.HTTP_200_OK,
        )


class MemberFreezeAllowanceView(APIView):
    """
    Check remaining freeze days and allowance for the logged-in member.
    Allowed: Member only. Denied: Super Admin and staff (403).
    """

    permission_classes = [IsAuthenticated, RequirePasswordChanged, IsMember]

    @extend_schema(
        summary="Check member freeze allowance (Member only)",
        description="Returns total allowed, used, and remaining freeze days.",
        responses={200: MemberFreezeAllowanceSerializer},
    )
    def get(self, request, *args, **kwargs):
        if request.user.role == User.ROLE_SUPER_ADMIN:
            return Response(
                {"detail": "Super Admin cannot view member freeze allowance."},
                status=status.HTTP_403_FORBIDDEN,
            )
        tenant = getattr(request, "tenant", None)
        if not tenant:
            return Response(
                {"detail": "Tenant required."}, status=status.HTTP_400_BAD_REQUEST
            )

        member = Member.all_objects.filter(user=request.user, gym=tenant).first()
        if not member:
            return Response(
                {"detail": "Member profile not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        allowance = get_member_freeze_allowance(member)
        return Response(
            MemberFreezeAllowanceSerializer(allowance).data,
            status=status.HTTP_200_OK,
        )


class GymFreezeListView(APIView):
    """
    List gym membership freeze requests for staff review.
    Allowed: Owner and Manager of that gym only. Denied: Super Admin, Reception, Trainer, Member (403).
    """

    permission_classes = [IsAuthenticated, RequirePasswordChanged, IsOwnerOrManager]

    @extend_schema(
        summary="List gym freeze requests (Owner, Manager)",
        description="Returns all freeze requests for the gym, filterable by status.",
        responses={200: MemberFreezeSerializer(many=True)},
    )
    def get(self, request, *args, **kwargs):
        if request.user.role == User.ROLE_SUPER_ADMIN:
            return Response(
                {"detail": "Super Admin cannot view gym freeze requests."},
                status=status.HTTP_403_FORBIDDEN,
            )
        tenant = getattr(request, "tenant", None)
        if not tenant:
            return Response(
                {"detail": "Tenant required."}, status=status.HTTP_400_BAD_REQUEST
            )

        qs = (
            MemberFreeze.all_objects.select_related("member", "approved_by")
            .filter(gym=tenant)
            .order_by("-created_at")
        )

        status_param = request.query_params.get("status")
        if status_param:
            qs = qs.filter(status=status_param)

        return Response(
            MemberFreezeSerializer(qs, many=True).data,
            status=status.HTTP_200_OK,
        )


class GymFreezeApproveView(APIView):
    """
    Approve a pending membership freeze request.
    Allowed: Owner and Manager of that gym only. Denied: Super Admin, Reception, Trainer, Member (403).
    """

    permission_classes = [IsAuthenticated, RequirePasswordChanged, IsOwnerOrManager]

    @extend_schema(
        summary="Approve a freeze request (Owner, Manager)",
        description="Approves a member freeze, pauses pass, extends subscription end date once, and notifies member.",
        responses={
            200: MemberFreezeSerializer,
            400: OpenApiResponse(description="Validation error"),
            403: OpenApiResponse(description="Permission denied"),
        },
    )
    def post(self, request, freeze_id, *args, **kwargs):
        if request.user.role == User.ROLE_SUPER_ADMIN:
            return Response(
                {"detail": "Super Admin cannot approve freeze requests."},
                status=status.HTTP_403_FORBIDDEN,
            )
        tenant = getattr(request, "tenant", None)
        if not tenant:
            return Response(
                {"detail": "Tenant required."}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            freeze = approve_membership_freeze(
                freeze_id=freeze_id,
                reviewer=request.user,
                gym=tenant,
            )
        except ValidationError as exc:
            detail = exc.message_dict if hasattr(exc, "message_dict") else exc.messages
            return Response({"detail": detail}, status=status.HTTP_400_BAD_REQUEST)
        except PermissionDenied as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)

        return Response(
            {
                "detail": f"Freeze request for {freeze.days} day(s) has been approved.",
                "freeze": MemberFreezeSerializer(freeze).data,
            },
            status=status.HTTP_200_OK,
        )


class GymFreezeRejectView(APIView):
    """
    Reject a pending membership freeze request.
    Allowed: Owner and Manager of that gym only. Denied: Super Admin, Reception, Trainer, Member (403).
    """

    permission_classes = [IsAuthenticated, RequirePasswordChanged, IsOwnerOrManager]

    @extend_schema(
        summary="Reject a freeze request (Owner, Manager)",
        description="Rejects a member freeze request with explanation and notifies member.",
        request=MemberFreezeRejectSerializer,
        responses={
            200: MemberFreezeSerializer,
            400: OpenApiResponse(description="Validation error"),
            403: OpenApiResponse(description="Permission denied"),
        },
    )
    def post(self, request, freeze_id, *args, **kwargs):
        if request.user.role == User.ROLE_SUPER_ADMIN:
            return Response(
                {"detail": "Super Admin cannot reject freeze requests."},
                status=status.HTTP_403_FORBIDDEN,
            )
        tenant = getattr(request, "tenant", None)
        if not tenant:
            return Response(
                {"detail": "Tenant required."}, status=status.HTTP_400_BAD_REQUEST
            )

        serializer = MemberFreezeRejectSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        rejection_reason = serializer.validated_data["rejection_reason"]

        try:
            freeze = reject_membership_freeze(
                freeze_id=freeze_id,
                reviewer=request.user,
                rejection_reason=rejection_reason,
                gym=tenant,
            )
        except ValidationError as exc:
            detail = exc.message_dict if hasattr(exc, "message_dict") else exc.messages
            return Response({"detail": detail}, status=status.HTTP_400_BAD_REQUEST)
        except PermissionDenied as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)

        return Response(
            {
                "detail": "Freeze request has been rejected.",
                "freeze": MemberFreezeSerializer(freeze).data,
            },
            status=status.HTTP_200_OK,
        )
