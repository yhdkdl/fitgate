"""Rate throttles for public demo requests."""

from django.core.cache import caches
from rest_framework.throttling import SimpleRateThrottle


class DemoRequestRateThrottle(SimpleRateThrottle):
    """
    Rate throttle for public demo requests.

    Uses the database cache backend (`db_cache`) so rate limits are persisted
    and enforced without requiring Redis in production.
    """

    scope = "demo_request"
    rate = "10/hour"

    def __init__(self):
        super().__init__()
        self.cache = caches["default"]

    def get_cache_key(self, request, view):
        ident = self.get_ident(request)
        if not ident:
            return None
        return self.cache_format % {"scope": self.scope, "ident": ident}
