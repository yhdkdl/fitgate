"""Subdomain resolution middleware for FitGate multi-tenancy."""

from datetime import timedelta
from typing import Callable, Optional

from django.conf import settings
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils import timezone

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
        dev_tunnel_host = getattr(settings, "DEV_TUNNEL_HOST", "") or ""
        dev_tunnel_host = dev_tunnel_host.split(":")[0].strip().lower().rstrip(".")

        tenant: Optional[GymTenant] = None
        subdomain: Optional[str] = None

        # 0. Development tunnel host (development only, restricted strictly to webhook endpoints)
        if dev_tunnel_host and host == dev_tunnel_host:
            path = (request.path_info or request.path or "").rstrip("/")
            if path == "/api/webhooks/chapa":
                tenant = None
            else:
                return JsonResponse(
                    {"detail": "Tunnel host only permitted for payment webhooks."},
                    status=403,
                )
        # 1. Apex domain or extra platform hosts
        elif host == domain or host in extra_platform_hosts:
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
            if tenant is not None:
                path = request.path_info or request.path
                if path.startswith("/admin/") or path == "/admin":
                    return JsonResponse({"detail": "Not found."}, status=404)

                norm_path = path.rstrip("/")

                # 1. Terminated gym enforcement
                if tenant.status == GymTenant.STATUS_TERMINATED:
                    if norm_path == "/api/health":
                        pass
                    elif norm_path == "/api/public/gym-entry":
                        return JsonResponse(
                            {
                                "terminated": True,
                                "message": "This gym is no longer on FitGate.",
                            },
                            status=200,
                        )
                    elif path.startswith("/api/"):
                        return JsonResponse(
                            {"detail": "This gym account has been closed."},
                            status=403,
                        )
                    else:
                        return HttpResponse(
                            "<!DOCTYPE html><html><head><title>FitGate</title></head><body><h1>This gym is no longer on FitGate.</h1></body></html>",
                            content_type="text/html",
                            status=200,
                        )

                # 2. Suspended gym enforcement (7-day export window only)
                if tenant.status == GymTenant.STATUS_SUSPENDED:
                    now = timezone.now()
                    is_within_export_window = bool(
                        tenant.suspended_at
                        and now <= (tenant.suspended_at + timedelta(days=7))
                    )
                    if (
                        norm_path == "/api/health"
                        or norm_path == "/api/public/gym-entry"
                        or norm_path.startswith("/api/auth")
                    ):
                        pass
                    elif norm_path.startswith("/api/gym/export"):
                        if not is_within_export_window:
                            return JsonResponse(
                                {
                                    "detail": "The 7-day export window for this suspended gym has expired."
                                },
                                status=403,
                            )
                    elif path.startswith("/api/"):
                        return JsonResponse(
                            {
                                "detail": "This gym account is suspended. Only data exports are permitted during the 7-day grace window."
                            },
                            status=403,
                        )

                if tenant.tls_confirmed_at is None:
                    if (
                        norm_path == "/api/health"
                        or norm_path == "/api/public/gym-entry"
                    ):
                        pass
                    elif path.startswith("/api/") or path == "/api":
                        return JsonResponse({"detail": "still_securing"}, status=503)

            response = self.get_response(request)
        finally:
            reset_current_tenant(token)

        return response
