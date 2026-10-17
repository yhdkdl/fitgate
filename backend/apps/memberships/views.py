"""Views for member registration, email verification, member profile management, and body metrics."""

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.http import Http404
from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.accounts.permissions import (
    IsGymStaff,
    IsMember,
    RequirePasswordChanged,
)
from apps.accounts.services import record_audit_log
from apps.memberships.models import BodyMetrics, Member
from apps.memberships.serializers import (
    BodyMetricsSerializer,
    MemberDetailSerializer,
    MemberSerializer,
    MemberUpdateSerializer,
    PublicMemberRegistrationSerializer,
    RecordBodyMetricsSerializer,
    StaffMemberRegistrationSerializer,
    VerifyEmailRequestSerializer,
)
from apps.memberships.services import (
    register_member_self_service,
    register_member_staff_assisted,
    verify_member_email,
)
from apps.memberships.throttling import MemberRegistrationRateThrottle


class PublicMemberRegistrationView(APIView):
    """
    Public endpoint for self-service member registration on a gym subdomain.
    Requires health waiver acceptance and rate-limited.
    """

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [MemberRegistrationRateThrottle]

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

        serializer = StaffMemberRegistrationSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            member, _ = register_member_staff_assisted(
                request.user,
                request.tenant,
                serializer.validated_data,
            )
        except ValidationError as exc:
            detail = exc.message_dict if hasattr(exc, "message_dict") else exc.messages
            return Response(detail, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                "detail": "Member registered successfully. Invitation email sent.",
                "member": MemberSerializer(member, context={"request": request}).data,
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
        description="Updates logged-in member's phone and emergency contact details.",
        request=MemberUpdateSerializer,
        responses={
            200: MemberDetailSerializer,
            400: OpenApiResponse(description="Validation error"),
        },
    )
    def patch(self, request, *args, **kwargs):
        member = getattr(request.user, "member_profile", None)
        if member is None:
            raise Http404("Member profile not found.")

        # Members can update phone and emergency contact only
        allowed_fields = {"phone", "emergency_contact"}
        filtered_data = {k: v for k, v in request.data.items() if k in allowed_fields}

        serializer = MemberUpdateSerializer(member, data=filtered_data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            serializer.save()
            if "phone" in filtered_data:
                member.user.phone = filtered_data["phone"]
                member.user.save(update_fields=["phone"])

            record_audit_log(
                action_type="member_profile_updated",
                affected_record_type="Member",
                affected_record_id=str(member.id),
                actor=request.user,
                gym=request.tenant,
                metadata={"phone": member.phone},
            )

        return Response(
            MemberDetailSerializer(member, context={"request": request}).data,
            status=status.HTTP_200_OK,
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
