from datetime import datetime, time

from django.core.exceptions import ValidationError
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.accounts.permissions import RequirePasswordChanged
from apps.classes.constants import (
    BOOKING_STATUS_BOOKED,
)
from apps.classes.models import ClassBooking, ClassSession
from apps.classes.permissions import (
    CanMarkClassAttendance,
    HasGroupClassesEnabled,
    IsClassManager,
)
from apps.classes.serializers import (
    BookClassSerializer,
    ClassBookingSerializer,
    ClassSessionCreateSerializer,
    ClassSessionSerializer,
    ClassSessionUpdateSerializer,
    MarkAttendanceSerializer,
)
from apps.classes.services import (
    book_class_session,
    cancel_class_booking,
    cancel_class_session,
    create_class_sessions,
    mark_class_attendance,
    update_class_session,
)
from apps.memberships.models import Member
from apps.trainers.models import Trainer


class ClassSessionListCreateView(APIView):
    required_flag = "has_group_classes"
    """
    GET: List sessions for the gym.
         Query params:
         - start_date (YYYY-MM-DD): defaults to today
         - end_date (YYYY-MM-DD): defaults to today + 14 days
         - trainer_id (UUID): filter by trainer
         - status: scheduled/cancelled (defaults to scheduled, or 'all')
    POST: Create a session (with optional repeat_weeks 1-12).
          Restricted to Owner and Manager.
    """

    permission_classes = [
        IsAuthenticated,
        RequirePasswordChanged,
        HasGroupClassesEnabled,
    ]

    def get_permissions(self):
        if self.request.method == "POST":
            return [
                IsAuthenticated(),
                RequirePasswordChanged(),
                HasGroupClassesEnabled(),
                IsClassManager(),
            ]
        return [IsAuthenticated(), RequirePasswordChanged(), HasGroupClassesEnabled()]

    def get(self, request):
        gym = request.tenant
        qs = (
            ClassSession.objects.filter(gym=gym)
            .select_related("trainer__user")
            .prefetch_related("bookings")
        )

        start_date_param = request.query_params.get("start_date")
        end_date_param = request.query_params.get("end_date")
        trainer_id_param = request.query_params.get("trainer_id")
        status_param = request.query_params.get("status")

        if start_date_param:
            try:
                sd = datetime.strptime(start_date_param, "%Y-%m-%d").date()
                dt_start = timezone.make_aware(datetime.combine(sd, time.min))
                qs = qs.filter(start_time__gte=dt_start)
            except ValueError:
                pass
        else:
            # Default to beginning of today
            today = timezone.localtime(timezone.now()).date()
            dt_start = timezone.make_aware(datetime.combine(today, time.min))
            qs = qs.filter(start_time__gte=dt_start)

        if end_date_param:
            try:
                ed = datetime.strptime(end_date_param, "%Y-%m-%d").date()
                dt_end = timezone.make_aware(datetime.combine(ed, time.max))
                qs = qs.filter(start_time__lte=dt_end)
            except ValueError:
                pass

        if trainer_id_param:
            qs = qs.filter(trainer_id=trainer_id_param)

        if status_param and status_param != "all":
            qs = qs.filter(status=status_param)

        serializer = ClassSessionSerializer(qs, many=True, context={"request": request})
        return Response(serializer.data)

    def post(self, request):
        gym = request.tenant
        serializer = ClassSessionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        trainer_id = serializer.validated_data["trainer_id"]
        trainer = Trainer.objects.filter(id=trainer_id, gym=gym).first()
        if not trainer:
            return Response(
                {"error": "Trainer not found in this gym."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            sessions = create_class_sessions(
                gym=gym,
                title=serializer.validated_data["title"],
                other_title=serializer.validated_data.get("other_title", ""),
                trainer=trainer,
                start_time=serializer.validated_data["start_time"],
                duration_minutes=serializer.validated_data["duration_minutes"],
                capacity=serializer.validated_data["capacity"],
                repeat_weeks=serializer.validated_data.get("repeat_weeks", 1),
            )
        except ValidationError as e:
            return Response(
                {"error": str(e.message if hasattr(e, "message") else e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        out_serializer = ClassSessionSerializer(
            sessions,
            many=True,
            context={"request": request},
        )
        return Response(out_serializer.data, status=status.HTTP_201_CREATED)


class ClassSessionDetailView(APIView):
    required_flag = "has_group_classes"
    """
    GET: Retrieve session detail.
    PATCH: Update session (Owner and Manager only).
    """

    permission_classes = [
        IsAuthenticated,
        RequirePasswordChanged,
        HasGroupClassesEnabled,
    ]

    def get_permissions(self):
        if self.request.method == "PATCH":
            return [
                IsAuthenticated(),
                RequirePasswordChanged(),
                HasGroupClassesEnabled(),
                IsClassManager(),
            ]
        return [IsAuthenticated(), RequirePasswordChanged(), HasGroupClassesEnabled()]

    def get(self, request, pk):
        gym = request.tenant
        session = (
            ClassSession.objects.filter(id=pk, gym=gym)
            .select_related("trainer__user")
            .prefetch_related("bookings")
            .first()
        )
        if not session:
            return Response(
                {"error": "Class session not found."}, status=status.HTTP_404_NOT_FOUND
            )

        serializer = ClassSessionSerializer(session, context={"request": request})
        return Response(serializer.data)

    def patch(self, request, pk):
        gym = request.tenant
        session = ClassSession.objects.filter(id=pk, gym=gym).first()
        if not session:
            return Response(
                {"error": "Class session not found."}, status=status.HTTP_404_NOT_FOUND
            )

        serializer = ClassSessionUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        trainer = None
        trainer_id = serializer.validated_data.get("trainer_id")
        if trainer_id:
            trainer = Trainer.objects.filter(id=trainer_id, gym=gym).first()
            if not trainer:
                return Response(
                    {"error": "Trainer not found in this gym."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        try:
            updated = update_class_session(
                session=session,
                title=serializer.validated_data.get("title"),
                other_title=serializer.validated_data.get("other_title"),
                trainer=trainer,
                start_time=serializer.validated_data.get("start_time"),
                duration_minutes=serializer.validated_data.get("duration_minutes"),
                capacity=serializer.validated_data.get("capacity"),
            )
        except ValidationError as e:
            return Response(
                {"error": str(e.message if hasattr(e, "message") else e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            ClassSessionSerializer(updated, context={"request": request}).data
        )


class ClassSessionCancelView(APIView):
    required_flag = "has_group_classes"
    """Cancel a scheduled class session. Owner and Manager only."""

    permission_classes = [
        IsAuthenticated,
        RequirePasswordChanged,
        HasGroupClassesEnabled,
        IsClassManager,
    ]

    def post(self, request, pk):
        gym = request.tenant
        session = ClassSession.objects.filter(id=pk, gym=gym).first()
        if not session:
            return Response(
                {"error": "Class session not found."}, status=status.HTTP_404_NOT_FOUND
            )

        try:
            cancelled = cancel_class_session(session, cancelled_by=request.user)
        except ValidationError as e:
            return Response(
                {"error": str(e.message if hasattr(e, "message") else e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            ClassSessionSerializer(cancelled, context={"request": request}).data
        )


class ClassSessionRosterView(APIView):
    required_flag = "has_group_classes"
    """
    Retrieve roster of booked members for a session.
    Allowed: Owner, Manager, Reception, or assigned Trainer.
    """

    permission_classes = [
        IsAuthenticated,
        RequirePasswordChanged,
        HasGroupClassesEnabled,
    ]

    def get(self, request, pk):
        gym = request.tenant
        session = (
            ClassSession.objects.filter(id=pk, gym=gym)
            .select_related("trainer__user")
            .first()
        )
        if not session:
            return Response(
                {"error": "Class session not found."}, status=status.HTTP_404_NOT_FOUND
            )

        # RBAC check: Members cannot view the full roster
        if request.user.role == User.ROLE_MEMBER:
            return Response(
                {"error": "Members cannot view class rosters."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Trainer can view roster for their own class
        if request.user.role == User.ROLE_TRAINER:
            if session.trainer.user_id != request.user.id:
                return Response(
                    {
                        "error": "Trainers can only view rosters for their assigned classes."
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

        bookings = (
            session.bookings.filter(status=BOOKING_STATUS_BOOKED)
            .select_related("member")
            .order_by("created_at")
        )
        serializer = ClassBookingSerializer(bookings, many=True)
        return Response(
            {
                "session": ClassSessionSerializer(
                    session, context={"request": request}
                ).data,
                "bookings": serializer.data,
            }
        )


class BookClassSessionView(APIView):
    required_flag = "has_group_classes"
    """
    POST: Book a slot in a class session.
    - Member books themselves.
    - Owner, Manager, Reception can book on behalf of a member (providing member_id).
    """

    permission_classes = [
        IsAuthenticated,
        RequirePasswordChanged,
        HasGroupClassesEnabled,
    ]

    def post(self, request, pk):
        gym = request.tenant
        serializer = BookClassSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        target_member = None

        if request.user.role == User.ROLE_MEMBER:
            target_member = getattr(request.user, "member_profile", None)
            if not target_member or target_member.gym_id != gym.id:
                return Response(
                    {"error": "Member profile not found."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        elif request.user.role in [
            User.ROLE_OWNER,
            User.ROLE_MANAGER,
            User.ROLE_RECEPTION,
        ]:
            member_id = serializer.validated_data.get("member_id")
            if not member_id:
                return Response(
                    {
                        "error": "member_id is required when booking on behalf of a member."
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            target_member = Member.objects.filter(id=member_id, gym=gym).first()
            if not target_member:
                return Response(
                    {"error": "Member not found in this gym."},
                    status=status.HTTP_404_NOT_FOUND,
                )
        else:
            return Response(
                {"error": "You do not have permission to book classes."},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            booking = book_class_session(
                gym=gym,
                session_id=pk,
                member=target_member,
                booked_by=request.user,
            )
        except ValidationError as e:
            return Response(
                {"error": str(e.message if hasattr(e, "message") else e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            ClassBookingSerializer(booking).data, status=status.HTTP_201_CREATED
        )


class CancelClassBookingView(APIView):
    required_flag = "has_group_classes"
    """
    POST: Cancel a booking.
    - Member can cancel their own booking (<= 2 hours cutoff).
    - Staff (Owner, Manager, Reception) can cancel anytime prior to class start.
    Query param or body param `booking_id` can be used.
    If Member role and no booking_id passed, finds the member's active booking for session pk.
    """

    permission_classes = [
        IsAuthenticated,
        RequirePasswordChanged,
        HasGroupClassesEnabled,
    ]

    def post(self, request, pk):
        gym = request.tenant
        booking_id = request.data.get("booking_id") or request.query_params.get(
            "booking_id"
        )

        if not booking_id:
            if request.user.role == User.ROLE_MEMBER:
                member = getattr(request.user, "member_profile", None)
                if not member:
                    return Response(
                        {"error": "Member profile not found."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                active_booking = ClassBooking.objects.filter(
                    session_id=pk,
                    member=member,
                    status=BOOKING_STATUS_BOOKED,
                ).first()
                if not active_booking:
                    return Response(
                        {"error": "No active booking found for this class."},
                        status=status.HTTP_404_NOT_FOUND,
                    )
                booking_id = active_booking.id
            else:
                return Response(
                    {"error": "booking_id is required."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        try:
            cancelled = cancel_class_booking(
                gym=gym,
                booking_id=booking_id,
                cancelled_by=request.user,
            )
        except ValidationError as e:
            return Response(
                {"error": str(e.message if hasattr(e, "message") else e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(ClassBookingSerializer(cancelled).data)


class MarkClassAttendanceView(APIView):
    required_flag = "has_group_classes"
    """
    POST: Mark attendance for a member in a class.
    Allowed roles: Owner, Manager, or the assigned Trainer.
    Does NOT create daily Attendance check-in rows.
    """

    permission_classes = [
        RequirePasswordChanged,
        HasGroupClassesEnabled,
        CanMarkClassAttendance,
    ]

    def post(self, request, pk):
        gym = request.tenant
        serializer = MarkAttendanceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        member_id = serializer.validated_data["member_id"]
        attended = serializer.validated_data["attended"]

        try:
            booking = mark_class_attendance(
                gym=gym,
                session_id=pk,
                member_id=member_id,
                attended=attended,
                marked_by=request.user,
            )
        except ValidationError as e:
            return Response(
                {"error": str(e.message if hasattr(e, "message") else e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(ClassBookingSerializer(booking).data)


class MemberClassBookingsView(APIView):
    required_flag = "has_group_classes"
    """
    GET: List current member's upcoming and past class bookings.
    Only accessible by members.
    """

    permission_classes = [
        IsAuthenticated,
        RequirePasswordChanged,
        HasGroupClassesEnabled,
    ]

    def get(self, request):
        if request.user.role != User.ROLE_MEMBER:
            return Response(
                {"error": "Only members can access member class bookings."},
                status=status.HTTP_403_FORBIDDEN,
            )

        member = getattr(request.user, "member_profile", None)
        if not member:
            return Response(
                {"error": "Member profile not found."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        bookings = (
            ClassBooking.objects.filter(
                gym=request.tenant,
                member=member,
            )
            .select_related("session__trainer__user")
            .order_by("-session__start_time")
        )

        serializer = ClassBookingSerializer(bookings, many=True)
        return Response(serializer.data)


class TrainerClassSessionsView(APIView):
    required_flag = "has_group_classes"
    """
    GET: List sessions assigned to the requesting trainer.
    Upcoming first, then past.
    """

    permission_classes = [
        IsAuthenticated,
        RequirePasswordChanged,
        HasGroupClassesEnabled,
    ]

    def get(self, request):
        if request.user.role != User.ROLE_TRAINER:
            return Response(
                {"error": "Only trainers can access trainer class sessions."},
                status=status.HTTP_403_FORBIDDEN,
            )

        trainer = Trainer.objects.filter(user=request.user, gym=request.tenant).first()
        if not trainer:
            return Response(
                {"error": "Trainer profile not found."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        now = timezone.now()
        upcoming = (
            ClassSession.objects.filter(
                gym=request.tenant,
                trainer=trainer,
                start_time__gte=now,
            )
            .select_related("trainer__user")
            .prefetch_related("bookings")
            .order_by("start_time")
        )

        past = (
            ClassSession.objects.filter(
                gym=request.tenant,
                trainer=trainer,
                start_time__lt=now,
            )
            .select_related("trainer__user")
            .prefetch_related("bookings")
            .order_by("-start_time")[:30]
        )

        upcoming_data = ClassSessionSerializer(
            upcoming, many=True, context={"request": request}
        ).data
        past_data = ClassSessionSerializer(
            past, many=True, context={"request": request}
        ).data

        return Response(
            {
                "upcoming": upcoming_data,
                "past": past_data,
                "sessions": list(upcoming_data) + list(past_data),
            }
        )
