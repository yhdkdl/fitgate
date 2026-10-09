"""FitGate URL Configuration."""

from apps.accounts.permissions import DocsPermission
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.utils import extend_schema, inline_serializer
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


class FitGateSpectacularAPIView(SpectacularAPIView):
    """Schema view restricted to Super Admin when DEBUG is False."""

    permission_classes = [DocsPermission]


class FitGateSpectacularSwaggerView(SpectacularSwaggerView):
    """Swagger UI restricted to Super Admin when DEBUG is False."""

    permission_classes = [DocsPermission]


class FitGateSpectacularRedocView(SpectacularRedocView):
    """Redoc UI restricted to Super Admin when DEBUG is False."""

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
def health_check(request):
    """Simple API health check endpoint."""
    return Response({"status": "ok", "app": "FitGate API"})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health/", health_check, name="health-check"),
    path("", include("apps.accounts.urls")),
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
]
