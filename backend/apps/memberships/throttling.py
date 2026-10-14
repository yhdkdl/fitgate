"""Rate throttle for public self-service member registration."""

from django.core.cache import caches
from rest_framework.throttling import SimpleRateThrottle


class MemberRegistrationRateThrottle(SimpleRateThrottle):
    """
    Rate throttle for public member self-service registration.
    Uses db_cache so limits persist and enforce without requiring Redis.
    """

    scope = "member_registration"
    rate = "10/hour"

    def __init__(self):
        super().__init__()
        if "db_cache" in caches:
            self.cache = caches["db_cache"]
        else:
            self.cache = caches["default"]

    def get_cache_key(self, request, view):
        ident = self.get_ident(request)
        if not ident:
            return None
        tenant_id = getattr(request.tenant, "id", "no-tenant")
        return self.cache_format % {
            "scope": self.scope,
            "ident": f"{tenant_id}:{ident}",
        }
