"""Test URLconf including base URLs and dummy test endpoints."""

from django.urls import path
from fitgate.urls import urlpatterns as base_urlpatterns
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import RequirePasswordChanged


class DummyProtectedView(APIView):
    """Protected dummy view for authentication tests."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({"status": "authenticated", "user": str(request.user.email)})


class DummyMustChangePasswordView(APIView):
    """Protected dummy view enforcing password change check."""

    permission_classes = [IsAuthenticated, RequirePasswordChanged]

    def get(self, request):
        return Response({"status": "ok"})


urlpatterns = list(base_urlpatterns) + [
    path("api/test/protected/", DummyProtectedView.as_view(), name="test-protected"),
    path(
        "api/test/must-change-password/",
        DummyMustChangePasswordView.as_view(),
        name="test-must-change-password",
    ),
]
