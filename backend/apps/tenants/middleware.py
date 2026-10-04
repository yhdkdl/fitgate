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
    - If host matches the apex domain (settings.DOMAIN) or direct hostnames
      (e.g., localhost, testserver), request.tenant is set to None (platform traffic).
    - If host matches {subdomain}.{DOMAIN}, extracts {subdomain} via suffix-matching
      and looks up the active GymTenant.
    - If subdomain is not found, returns a 404 response.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        host = request.get_host().split(":")[0].strip().lower().rstrip(".")
        domain = getattr(settings, "DOMAIN", "").strip().lower().rstrip(".")

        tenant: Optional[GymTenant] = None
        subdomain: Optional[str] = None

        # 1. Apex domain or direct local / internal access
        if host == domain or host in {
            "localhost",
            "127.0.0.1",
            "testserver",
            "backend",
        }:
            tenant = None
        # 2. Suffix match against configured DOMAIN
        elif domain and host.endswith(f".{domain}"):
            subdomain = host[: -len(f".{domain}")]
        # 3. Fallback for test harness and local dev subdomains
        elif host.endswith(".localhost"):
            subdomain = host[: -len(".localhost")]
        elif host.endswith(".testserver"):
            subdomain = host[: -len(".testserver")]
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
