"""Tests for TenantSubdomainMiddleware."""

import json

import pytest
from django.http import HttpResponse
from django.test import RequestFactory, override_settings

from apps.tenants.context import get_current_tenant
from apps.tenants.middleware import TenantSubdomainMiddleware
from apps.tenants.models import GymTenant


@pytest.mark.django_db
class TestTenantSubdomainMiddleware:
    """Tests for subdomain extraction and tenant resolution in middleware."""

    @pytest.fixture
    def factory(self):
        return RequestFactory()

    @pytest.fixture
    def gym_tenant(self):
        return GymTenant.objects.create(name="Gym Name", subdomain="gymname")

    # -------------------------------------------------------------------------
    # Multi-label DOMAIN tests (fitgate.tebebtech.com)
    # -------------------------------------------------------------------------

    @override_settings(
        DOMAIN="fitgate.tebebtech.com",
        ALLOWED_HOSTS=["fitgate.tebebtech.com", ".fitgate.tebebtech.com"],
    )
    def test_multi_label_domain_gym_subdomain_resolves_tenant(
        self, factory, gym_tenant
    ):
        """
        Case 1: host = "gymname.fitgate.tebebtech.com" -> resolves to that gym tenant.
        Ensures suffix-matching against the two-label base domain extracts 'gymname'.
        """
        resolved_tenant_in_view = None

        def dummy_view(request):
            nonlocal resolved_tenant_in_view
            resolved_tenant_in_view = getattr(request, "tenant", None)
            assert get_current_tenant() == gym_tenant
            return HttpResponse("OK")

        middleware = TenantSubdomainMiddleware(dummy_view)
        request = factory.get("/", HTTP_HOST="gymname.fitgate.tebebtech.com")

        response = middleware(request)

        assert response.status_code == 200
        assert resolved_tenant_in_view == gym_tenant
        assert request.tenant == gym_tenant
        # Context must be cleaned up after response
        assert get_current_tenant() is None

    @override_settings(
        DOMAIN="fitgate.tebebtech.com",
        ALLOWED_HOSTS=["fitgate.tebebtech.com", ".fitgate.tebebtech.com"],
    )
    def test_multi_label_domain_apex_sets_tenant_none(self, factory):
        """
        Case 2: host = "fitgate.tebebtech.com" (the apex, no gym) -> request.tenant is None, not 404.
        Ensures platform routes (marketing, registration, admin) succeed without tenant scoping.
        """
        view_called = False
        resolved_tenant_in_view = "INITIAL_SENTINEL"

        def dummy_view(request):
            nonlocal view_called, resolved_tenant_in_view
            view_called = True
            resolved_tenant_in_view = getattr(request, "tenant", None)
            assert get_current_tenant() is None
            return HttpResponse("Apex Platform Landing")

        middleware = TenantSubdomainMiddleware(dummy_view)
        request = factory.get("/", HTTP_HOST="fitgate.tebebtech.com")

        response = middleware(request)

        assert response.status_code == 200
        assert view_called is True
        assert resolved_tenant_in_view is None
        assert request.tenant is None
        assert response.content == b"Apex Platform Landing"
        assert get_current_tenant() is None

    @override_settings(
        DOMAIN="fitgate.tebebtech.com",
        ALLOWED_HOSTS=["fitgate.tebebtech.com", ".fitgate.tebebtech.com"],
    )
    def test_multi_label_domain_unknown_subdomain_returns_404(self, factory):
        """Unknown gym subdomain returns 404 JSON, not proceeding with no tenant."""
        middleware = TenantSubdomainMiddleware(lambda req: HttpResponse("OK"))
        request = factory.get("/", HTTP_HOST="unknown.fitgate.tebebtech.com")

        response = middleware(request)

        assert response.status_code == 404
        assert json.loads(response.content) == {"detail": "Gym tenant not found."}
        assert get_current_tenant() is None

    @override_settings(
        DOMAIN="fitgate.tebebtech.com",
        ALLOWED_HOSTS=["fitgate.tebebtech.com", ".fitgate.tebebtech.com"],
    )
    def test_multi_label_domain_nested_subdomain_rejected(self, factory):
        """Multi-level subdomain like a.b.fitgate.tebebtech.com returns 404."""
        middleware = TenantSubdomainMiddleware(lambda req: HttpResponse("OK"))
        request = factory.get("/", HTTP_HOST="a.b.fitgate.tebebtech.com")

        response = middleware(request)

        assert response.status_code == 404
        assert json.loads(response.content) == {"detail": "Gym tenant not found."}

    # -------------------------------------------------------------------------
    # Single-label / default domain tests
    # -------------------------------------------------------------------------

    @override_settings(
        DOMAIN="fitgate.org",
        ALLOWED_HOSTS=["fitgate.org", ".fitgate.org"],
    )
    def test_single_label_domain_resolution_and_apex(self, factory, gym_tenant):
        """Single-label DOMAIN handles both subdomain resolution and apex access."""
        middleware = TenantSubdomainMiddleware(lambda req: HttpResponse("OK"))

        # Subdomain request
        req_sub = factory.get("/", HTTP_HOST="gymname.fitgate.org")
        res_sub = middleware(req_sub)
        assert res_sub.status_code == 200
        assert req_sub.tenant == gym_tenant

        # Apex request
        req_apex = factory.get("/", HTTP_HOST="fitgate.org")
        res_apex = middleware(req_apex)
        assert res_apex.status_code == 200
        assert req_apex.tenant is None

    @override_settings(
        DOMAIN="localhost",
        ALLOWED_HOSTS=["localhost", "127.0.0.1", "testserver"],
    )
    def test_localhost_and_internal_hosts_set_tenant_none(self, factory):
        """Localhost, 127.0.0.1, and testserver set tenant to None."""
        middleware = TenantSubdomainMiddleware(lambda req: HttpResponse("OK"))

        for host in ["localhost", "127.0.0.1", "testserver"]:
            req = factory.get("/", HTTP_HOST=host)
            res = middleware(req)
            assert res.status_code == 200
            assert req.tenant is None

    @override_settings(
        DOMAIN="localhost",
        ALLOWED_HOSTS=["localhost", ".localhost", "127.0.0.1", "testserver"],
    )
    def test_context_cleaned_up_on_view_exception(self, factory, gym_tenant):
        """Context variable is safely reset even if the inner view raises an exception."""

        def failing_view(request):
            assert get_current_tenant() == gym_tenant
            raise RuntimeError("Something failed in view")

        middleware = TenantSubdomainMiddleware(failing_view)
        request = factory.get("/", HTTP_HOST="gymname.localhost")

        with pytest.raises(RuntimeError):
            middleware(request)

        assert get_current_tenant() is None
