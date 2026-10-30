"""FitGate URL Configuration."""

import mimetypes

from django.conf import settings
from django.contrib import admin
from django.http import FileResponse, HttpResponse, HttpResponseNotFound, JsonResponse
from django.urls import include, path, re_path
from django.views.static import serve
from drf_spectacular.utils import extend_schema, inline_serializer
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
from rest_framework import serializers
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.accounts.permissions import DocsPermission


class FitGateSpectacularAPIView(SpectacularAPIView):
    """Schema view restricted to Super Admin when DOCS_PUBLIC is False."""

    permission_classes = [DocsPermission]


class FitGateSpectacularSwaggerView(SpectacularSwaggerView):
    """Swagger UI restricted to Super Admin when DOCS_PUBLIC is False."""

    permission_classes = [DocsPermission]


class FitGateSpectacularRedocView(SpectacularRedocView):
    """Redoc UI restricted to Super Admin when DOCS_PUBLIC is False."""

    permission_classes = [DocsPermission]


@extend_schema(
    summary="Health check",
    description="Returns the operational status of the FitGate backend service.",
    responses={
        200: inline_serializer(
            name="HealthCheckResponse",
            fields={
                "status": serializers.CharField(default="ok"),
                "app": serializers.CharField(default="FitGate API"),
            },
        )
    },
)
@api_view(["GET"])
@permission_classes([AllowAny])
@authentication_classes([])
def health_check(request):
    """Simple API health check endpoint."""
    return Response({"status": "ok", "app": "FitGate API"})


def api_not_found_view(request, exception=None, *args, **kwargs):
    """Ensure 404 responses for /api/ return JSON rather than HTML."""
    if request.path_info.startswith("/api/"):
        return JsonResponse({"detail": "Not found."}, status=404)
    return HttpResponseNotFound("Not found")


def serve_react_app(request, *args, **kwargs):
    """
    Serve the compiled React SPA (frontend/dist):
    - Directly serves requested dist static assets if present (e.g. assets/*, favicon.ico).
    - Falls back to index.html for all non-API, non-static SPA routes.
    """
    dist_dir = getattr(
        settings, "FRONTEND_DIST_DIR", settings.BASE_DIR.parent / "frontend" / "dist"
    )
    rel_path = request.path_info.lstrip("/")

    if rel_path:
        candidate_file = dist_dir / rel_path
        try:
            resolved = candidate_file.resolve()
            if resolved.is_file() and str(resolved).startswith(str(dist_dir.resolve())):
                content_type, _ = mimetypes.guess_type(str(resolved))
                return FileResponse(open(resolved, "rb"), content_type=content_type)
        except (ValueError, OSError):
            pass

    index_file = dist_dir / "index.html"
    if index_file.is_file():
        return HttpResponse(
            index_file.read_bytes(), content_type="text/html; charset=utf-8"
        )

    return HttpResponse(
        "FitGate frontend build not found. Run 'npm run build' in the frontend directory.",
        status=503,
        content_type="text/plain",
    )


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health/", health_check, name="health-check"),
    path("", include("apps.accounts.urls")),
    path("", include("apps.tenants.urls")),
    path("", include("apps.memberships.urls")),
    path("", include("apps.attendance.urls")),
    path("", include("apps.payments.urls")),
    path("", include("apps.trainers.urls")),
    # OpenAPI Documentation
    path("api/schema/", FitGateSpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        FitGateSpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path(
        "api/redoc/",
        FitGateSpectacularRedocView.as_view(url_name="schema"),
        name="redoc",
    ),
    # Public assets (logos) serve route - strictly restricted to logos/
    path(
        "media/logos/<path:path>",
        serve,
        {"document_root": settings.MEDIA_ROOT / "logos"},
        name="public-logo-serve",
    ),
    # Catch-all for non-API, non-static, non-media paths to serve React SPA
    re_path(r"^(?!api/|static/|media/).*$", serve_react_app, name="spa-catchall"),
]

handler404 = "fitgate.urls.api_not_found_view"
