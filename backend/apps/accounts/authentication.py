"""Custom JWT Authentication for FitGate multi-tenancy and session validity."""

from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication

from apps.accounts.models import User
from apps.accounts.tokens import datetime_to_microseconds


class FitGateJWTAuthentication(JWTAuthentication):
    """
    Custom JWT authentication class enforcing FitGate security properties:

    1. Defines authenticate_header(request) returning 'Bearer realm="api"' so missing/invalid
       tokens on protected views return 401 Unauthorized rather than 403 Forbidden.
    2. Validates user is active (user.is_active is True).
    3. Validates session freshness: token password_changed_at claim matches user's current
       password_changed_at (invalidates tokens immediately on password change).
    4. Validates tenant/host alignment:
       - On apex domain (request.tenant is None): only platform users (super_admin, gym_id null).
       - On gym subdomain (request.tenant is set): token gym_id must match request.tenant.id.
    """

    def authenticate_header(self, request) -> str:
        """Return Bearer realm so DRF yields 401 on missing or invalid authentication."""
        return 'Bearer realm="api"'

    def get_user(self, validated_token):
        """
        Fetch user across all tenants and validate active status.

        Uses User.all_objects so lookups succeed regardless of request tenant context.
        """
        user_id = validated_token.get("user_id")
        if not user_id:
            raise AuthenticationFailed(
                "Token contains no user identifier.", code="token_invalid"
            )

        user = User.all_objects.filter(id=user_id).first()
        if user is None:
            raise AuthenticationFailed("User not found.", code="user_not_found")

        if not user.is_active:
            raise AuthenticationFailed("User is inactive.", code="user_inactive")

        return user

    def authenticate(self, request):
        """Authenticate request, validate user state, password timestamp, and tenant scope."""
        header = self.get_header(request)
        if header is None:
            return None

        raw_token = self.get_raw_token(header)
        if raw_token is None:
            return None

        validated_token = self.get_validated_token(raw_token)
        user = self.get_user(validated_token)

        # 1. Password freshness check (microsecond precision)
        claimed_pca = validated_token.get("password_changed_at")
        actual_pca = datetime_to_microseconds(user.password_changed_at)
        if claimed_pca != actual_pca:
            raise AuthenticationFailed(
                "Token has been invalidated due to a password change.",
                code="password_changed",
            )

        # 2. Host / Tenant scoping check
        token_gym_id = validated_token.get("gym_id")
        token_role = validated_token.get("role")
        current_tenant = getattr(request, "tenant", None)

        if current_tenant is None:
            # Apex domain: only Super Admin platform tokens allowed
            if token_gym_id is not None or token_role != User.ROLE_SUPER_ADMIN:
                raise AuthenticationFailed(
                    "Token is not authorized for apex platform access.",
                    code="tenant_mismatch",
                )
        else:
            # Gym subdomain: token gym_id must match active tenant
            if token_gym_id is None or str(token_gym_id) != str(current_tenant.id):
                raise AuthenticationFailed(
                    "Token is not authorized for this gym domain.",
                    code="tenant_mismatch",
                )

        return (user, validated_token)


try:
    from drf_spectacular.extensions import OpenApiAuthenticationExtension

    class FitGateJWTAuthenticationScheme(OpenApiAuthenticationExtension):
        """OpenAPI authentication extension documenting Bearer JWT authentication."""

        target_class = "apps.accounts.authentication.FitGateJWTAuthentication"
        name = "jwtAuth"

        def get_security_definition(self, auto_schema):
            return {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
            }

except ImportError:  # pragma: no cover
    pass
