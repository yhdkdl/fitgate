"""Rate throttle for public self-service member registration."""

from django.core.cache import caches
from rest_framework.throttling import SimpleRateThrottle


class MemberRegistrationRateThrottle(SimpleRateThrottle):
    """
    Rate throttle for public member self-service registration per gym and IP.
    """

    scope = "member_registration"
    rate = "10/hour"

    def __init__(self):
        super().__init__()
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


class MemberRegistrationIpRateThrottle(SimpleRateThrottle):
    """Per-IP rate limit for public self-registration."""

    scope = "member_registration_ip"
    rate = "10/hour"

    def __init__(self):
        super().__init__()
        self.cache = caches["default"]

    def get_cache_key(self, request, view):
        ident = self.get_ident(request)
        if not ident:
            return None
        return self.cache_format % {"scope": self.scope, "ident": ident}


class MemberRegistrationGymRateThrottle(SimpleRateThrottle):
    """Per-gym rate limit for public self-registration."""

    scope = "member_registration_gym"
    rate = "30/hour"

    def __init__(self):
        super().__init__()
        self.cache = caches["default"]

    def get_cache_key(self, request, view):
        tenant_id = getattr(request.tenant, "id", None)
        if not tenant_id:
            return None
        return self.cache_format % {"scope": self.scope, "ident": str(tenant_id)}
