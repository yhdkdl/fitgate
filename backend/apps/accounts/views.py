"""API views for authentication and platform administration."""

import logging
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.core.exceptions import ValidationError
from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.dashboards import dashboard_config_for
from apps.accounts.models import User
from apps.accounts.notifications import notify_account_locked
from apps.accounts.permissions import IsSuperAdmin, RequirePasswordChanged
from apps.accounts.serializers import (
    CreateSuperAdminRequestSerializer,
    LoginRequestSerializer,
    LoginResponseSerializer,
    LogoutRequestSerializer,
    SuperAdminResponseSerializer,
    TokenRefreshRequestSerializer,
    TokenRefreshResponseSerializer,
    UserSummarySerializer,
)
from apps.accounts.services import create_additional_super_admin
from apps.accounts.tokens import datetime_to_microseconds, get_tokens_for_user

# Precomputed hash for dummy password check to mitigate timing enumeration attacks
DUMMY_PASSWORD_HASH = make_password("fitgate-timing-mitigation-dummy-password")

logger = logging.getLogger(__name__)


def perform_dummy_password_check(password: str) -> None:
    """Perform a dummy password verification so non-existent users undergo equal hashing work."""
    check_password(password, DUMMY_PASSWORD_HASH)


def generic_auth_error_response() -> Response:
    """Return uniform 401 response for all authentication failure cases."""
    return Response(
        {"detail": "Invalid credentials."},
        status=status.HTTP_401_UNAUTHORIZED,
        headers={"Content-Type": "application/json"},
    )


class LoginView(APIView):
    """
    Authenticate user and return JWT tokens and role dashboard config.

    Enforces:
    - Host scoping: apex domain sees only platform Super Admins; gym subdomain sees only its users.
    - Uniform 401 error response across unknown email, wrong password, wrong host, lock, or inactive.
    - Constant-time dummy hash check on missing/out-of-scope users.
    - Lockout after 5 consecutive failed attempts.
    """

    permission_classes = [AllowAny]
    authentication_classes = []
    is_auth_endpoint = True

    @extend_schema(
        summary="User login",
        description="Authenticates user with email and password, returning tokens and dashboard config.",
        request=LoginRequestSerializer,
        responses={
            200: LoginResponseSerializer,
            401: OpenApiResponse(description="Invalid credentials"),
        },
    )
    def post(self, request, *args, **kwargs):
        serializer = LoginRequestSerializer(data=request.data)
        if not serializer.is_valid():
            perform_dummy_password_check("dummy_password")
            return generic_auth_error_response()

        raw_email = serializer.validated_data["email"]
        password = serializer.validated_data["password"]
        normalized_email = raw_email.strip().lower()

        # Host-scoped lookup via default manager
        user = User.objects.filter(email=normalized_email).first()

        now = timezone.now()

        # 1. Unknown user or user not visible on this host/subdomain
        if user is None:
            perform_dummy_password_check(password)
            return generic_auth_error_response()

        # 2. Account currently locked
        if user.locked_until:
            if user.locked_until > now:
                perform_dummy_password_check(password)
                return generic_auth_error_response()
            # Lock has expired - clear lockout and reset failed count
            user.locked_until = None
            user.failed_login_count = 0
            user.save(update_fields=["locked_until", "failed_login_count"])

        # 3. Inactive account
        if not user.is_active:
            perform_dummy_password_check(password)
            return generic_auth_error_response()

        # 4. Password verification failure
        if not user.check_password(password):
            user.failed_login_count += 1
            lockout_minutes = getattr(settings, "LOGIN_LOCKOUT_MINUTES", 15)

            if user.failed_login_count >= 5:
                user.locked_until = now + timedelta(minutes=lockout_minutes)
                user.save(update_fields=["failed_login_count", "locked_until"])
                try:
                    notify_account_locked(user)
                except Exception:
                    logger.exception(
                        "Failed to send lockout notification for user %s",
                        user.id,
                    )
            else:
                user.save(update_fields=["failed_login_count"])

            return generic_auth_error_response()

        # 5. Success: reset lockout counters and record login
        user.failed_login_count = 0
        user.locked_until = None
        user.last_login = now
        user.save(update_fields=["failed_login_count", "locked_until", "last_login"])

        tokens = get_tokens_for_user(user)
        dashboard = dashboard_config_for(user)

        response_data = {
            "access": tokens["access"],
            "refresh": tokens["refresh"],
            "user": UserSummarySerializer(user).data,
            "dashboard": dashboard,
        }
        return Response(response_data, status=status.HTTP_200_OK)


class TokenRefreshView(APIView):
    """
    Refresh access token given a valid refresh token.

    Validates:
    - User is active.
    - Token password_changed_at matches current user password_changed_at.
    - Token gym_id matches current request tenant context.
    """

    permission_classes = [AllowAny]
    authentication_classes = []
    is_auth_endpoint = True

    @extend_schema(
        summary="Refresh access token",
        description="Issues a fresh access token given a valid refresh token.",
        request=TokenRefreshRequestSerializer,
        responses={
            200: TokenRefreshResponseSerializer,
            401: OpenApiResponse(description="Invalid or expired refresh token"),
        },
    )
    def post(self, request, *args, **kwargs):
        serializer = TokenRefreshRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"detail": "Refresh token is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        refresh_raw = serializer.validated_data["refresh"]

        try:
            token = RefreshToken(refresh_raw)
        except TokenError:
            return Response(
                {"detail": "Invalid or expired token."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        user_id = token.get("user_id")
        user = User.all_objects.filter(id=user_id).first()
        if user is None or not user.is_active:
            return Response(
                {"detail": "User not found or inactive."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # Microsecond password change check
        claimed_pca = token.get("password_changed_at")
        actual_pca = datetime_to_microseconds(user.password_changed_at)
        if claimed_pca != actual_pca:
            return Response(
                {"detail": "Token has expired due to a password change."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # Host / Tenant check
        token_gym_id = token.get("gym_id")
        token_role = token.get("role")
        current_tenant = getattr(request, "tenant", None)

        if current_tenant is None:
            if token_gym_id is not None or token_role != User.ROLE_SUPER_ADMIN:
                return Response(
                    {"detail": "Token is not authorized for apex platform access."},
                    status=status.HTTP_401_UNAUTHORIZED,
                )
        else:
            if token_gym_id is None or str(token_gym_id) != str(current_tenant.id):
                return Response(
                    {"detail": "Token is not authorized for this gym domain."},
                    status=status.HTTP_401_UNAUTHORIZED,
                )

        access = token.access_token
        access["user_id"] = str(user.id)
        access["role"] = user.role
        access["gym_id"] = str(user.gym_id) if user.gym_id else None
        access["password_changed_at"] = actual_pca

        return Response({"access": str(access)}, status=status.HTTP_200_OK)


class LogoutView(APIView):
    """
    Log out user by blacklisting their refresh token.
    """

    permission_classes = [AllowAny]
    authentication_classes = []
    is_auth_endpoint = True

    @extend_schema(
        summary="User logout",
        description="Blacklists the provided refresh token.",
        request=LogoutRequestSerializer,
        responses={
            200: OpenApiResponse(description="Successfully logged out"),
            400: OpenApiResponse(description="Invalid refresh token"),
        },
    )
    def post(self, request, *args, **kwargs):
        serializer = LogoutRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"detail": "Refresh token is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        refresh_raw = serializer.validated_data["refresh"]
        try:
            token = RefreshToken(refresh_raw)
            token.blacklist()
        except TokenError:
            return Response(
                {"detail": "Invalid or expired token."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {"detail": "Successfully logged out."},
            status=status.HTTP_200_OK,
        )


class CreateSuperAdminView(APIView):
    """
    Create an additional Super Admin account (apex only, Super Admin only).

    Requires re-authenticating the actor's current password.
    """

    permission_classes = [IsAuthenticated, RequirePasswordChanged, IsSuperAdmin]

    @extend_schema(
        summary="Create additional Super Admin",
        description="Creates a new Super Admin account. Requires active Super Admin credentials.",
        request=CreateSuperAdminRequestSerializer,
        responses={
            201: SuperAdminResponseSerializer,
            400: OpenApiResponse(description="Validation error"),
            403: OpenApiResponse(description="Forbidden"),
        },
    )
    def post(self, request, *args, **kwargs):
        current_tenant = getattr(request, "tenant", None)
        if current_tenant is not None:
            return Response(
                {
                    "detail": "Super Admin creation is only permitted on the apex domain."
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = CreateSuperAdminRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        email = serializer.validated_data["email"]
        password = serializer.validated_data["password"]
        current_password = serializer.validated_data["current_password"]

        try:
            new_super_admin = create_additional_super_admin(
                actor=request.user,
                email=email,
                password=password,
                current_password=current_password,
            )
        except ValidationError as exc:
            return Response(
                (
                    exc.message_dict
                    if hasattr(exc, "message_dict")
                    else {"detail": exc.messages}
                ),
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            SuperAdminResponseSerializer(new_super_admin).data,
            status=status.HTTP_201_CREATED,
        )
