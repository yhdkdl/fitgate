"""JWT token classes and utilities for FitGate authentication."""

from datetime import datetime

from rest_framework_simplejwt.tokens import RefreshToken


def datetime_to_microseconds(dt: datetime | None) -> int:
    """Convert a timezone-aware datetime to integer microseconds since Unix epoch."""
    if dt is None:
        return 0
    return int(dt.timestamp() * 1_000_000)


class FitGateRefreshToken(RefreshToken):
    """
    FitGate refresh token injecting custom claims:
    - user_id (UUID string)
    - role (string)
    - gym_id (nullable UUID string)
    - password_changed_at (integer microsecond value)
    """

    @classmethod
    def for_user(cls, user):
        token = super().for_user(user)
        pca_int = datetime_to_microseconds(user.password_changed_at)
        token["user_id"] = str(user.id)
        token["role"] = user.role
        token["gym_id"] = str(user.gym_id) if user.gym_id else None
        token["password_changed_at"] = pca_int
        return token

    @property
    def access_token(self):
        access = super().access_token
        access["user_id"] = self["user_id"]
        access["role"] = self["role"]
        access["gym_id"] = self["gym_id"]
        access["password_changed_at"] = self["password_changed_at"]
        return access


def get_tokens_for_user(user) -> dict[str, str]:
    """Generate access and refresh JWT tokens for the specified user."""
    refresh = FitGateRefreshToken.for_user(user)
    return {
        "refresh": str(refresh),
        "access": str(refresh.access_token),
    }
