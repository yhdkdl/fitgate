"""Subdomain resolution middleware for FitGate multi-tenancy."""

from typing import Callable, Optional

from django.conf import settings
from django.http import HttpRequest, HttpResponse, JsonResponse

from apps.tenants.context import reset_current_tenant, set_current_tenant
from apps.tenants.models import GymTenant


class TenantSubdomainMiddleware:
    """
    Resolves the tenant based on the request's hostname.

    Uses suffix matching against settings.DOMAIN:
    - If host matches the apex domain (settings.DOMAIN) or extra platform hosts
      (from settings.TENANT_EXTRA_PLATFORM_HOSTS), request.tenant is set to None (platform traffic).
    - If host matches {subdomain}.{DOMAIN}, extracts {subdomain} via suffix-matching
      and looks up the GymTenant.
    - If host is neither apex/extra platform host nor under {DOMAIN}, or if subdomain is not found,
      returns a 404 response.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        host = request.get_host().split(":")[0].strip().lower().rstrip(".")
        domain = settings.DOMAIN.strip().lower().rstrip(".")
        extra_platform_hosts = set(getattr(settings, "TENANT_EXTRA_PLATFORM_HOSTS", []))

        tenant: Optional[GymTenant] = None
        subdomain: Optional[str] = None

        # 1. Apex domain or extra platform hosts
        if host == domain or host in extra_platform_hosts:
            tenant = None
        # 2. Suffix match against configured DOMAIN
        elif domain and host.endswith(f".{domain}"):
            subdomain = host[: -len(f".{domain}")]
        else:
            return JsonResponse({"detail": "Gym tenant not found."}, status=404)

        if subdomain is not None:
            # Subdomains must be single labels (no nested dots) and non-empty
            if "." in subdomain or not subdomain:
                return JsonResponse({"detail": "Gym tenant not found."}, status=404)

            tenant = GymTenant.objects.filter(subdomain=subdomain).first()
            if tenant is None:
                return JsonResponse({"detail": "Gym tenant not found."}, status=404)

        request.tenant = tenant
        token = set_current_tenant(tenant)

        try:
            response = self.get_response(request)
        finally:
            reset_current_tenant(token)

        return response
