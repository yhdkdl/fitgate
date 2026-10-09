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

    @override_settings(
        DOMAIN="fitgate.tebebtech.com",
        ALLOWED_HOSTS=["fitgate.tebebtech.com", "evilfitgate.tebebtech.com"],
    )
    def test_dot_boundary_evil_domain_rejected(self, factory):
        """
        Dot boundary check: 'evilfitgate.tebebtech.com' lacks the '.' separator before DOMAIN.
        Suffix-matching against f'.{domain}' must reject it with 404 rather than matching.
        """
        middleware = TenantSubdomainMiddleware(lambda req: HttpResponse("OK"))
        request = factory.get("/", HTTP_HOST="evilfitgate.tebebtech.com")

        response = middleware(request)

        assert response.status_code == 404
        assert json.loads(response.content) == {"detail": "Gym tenant not found."}

    @override_settings(
        DOMAIN="fitgate.tebebtech.com",
        ALLOWED_HOSTS=["fitgate.tebebtech.com", "foreignsite.org"],
    )
    def test_foreign_host_rejected(self, factory):
        """A foreign host that is neither apex nor subdomained under DOMAIN returns 404."""
        middleware = TenantSubdomainMiddleware(lambda req: HttpResponse("OK"))
        request = factory.get("/", HTTP_HOST="foreignsite.org")

        response = middleware(request)

        assert response.status_code == 404
        assert json.loads(response.content) == {"detail": "Gym tenant not found."}

    @override_settings(
        DOMAIN="fitgate.tebebtech.com",
        ALLOWED_HOSTS=["fitgate.tebebtech.com", ".fitgate.tebebtech.com"],
    )
    def test_trailing_dot_normalized(self, factory, gym_tenant):
        """FQDN hosts with a trailing dot are normalized and resolved properly."""
        middleware = TenantSubdomainMiddleware(lambda req: HttpResponse("OK"))

        # Gym subdomain with trailing dot
        req_sub = factory.get("/", HTTP_HOST="gymname.fitgate.tebebtech.com.")
        res_sub = middleware(req_sub)
        assert res_sub.status_code == 200
        assert req_sub.tenant == gym_tenant

        # Apex domain with trailing dot
        req_apex = factory.get("/", HTTP_HOST="fitgate.tebebtech.com.")
        res_apex = middleware(req_apex)
        assert res_apex.status_code == 200
        assert req_apex.tenant is None

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
        DOMAIN="fitgate.tebebtech.com",
        ALLOWED_HOSTS=["fitgate.tebebtech.com", ".fitgate.tebebtech.com"],
    )
    def test_port_stripped_from_host(self, factory, gym_tenant):
        """Port numbers on HTTP_HOST are stripped before matching."""
        middleware = TenantSubdomainMiddleware(lambda req: HttpResponse("OK"))

        req_sub = factory.get("/", HTTP_HOST="gymname.fitgate.tebebtech.com:8000")
        res_sub = middleware(req_sub)
        assert res_sub.status_code == 200
        assert req_sub.tenant == gym_tenant

        req_apex = factory.get("/", HTTP_HOST="fitgate.tebebtech.com:8000")
        res_apex = middleware(req_apex)
        assert res_apex.status_code == 200
        assert req_apex.tenant is None

    @override_settings(
        DOMAIN="fitgate.tebebtech.com",
        ALLOWED_HOSTS=["fitgate.tebebtech.com", ".fitgate.tebebtech.com"],
    )
    def test_host_lowercased_for_matching(self, factory, gym_tenant):
        """Mixed-case and uppercase HTTP_HOST headers are lowercased for resolution."""
        middleware = TenantSubdomainMiddleware(lambda req: HttpResponse("OK"))

        req = factory.get("/", HTTP_HOST="GYMNAME.FITGATE.TEBEBTECH.COM")
        res = middleware(req)
        assert res.status_code == 200
        assert req.tenant == gym_tenant

    @override_settings(
        DOMAIN="fitgate.tebebtech.com",
        TENANT_EXTRA_PLATFORM_HOSTS=[],
        ALLOWED_HOSTS=["fitgate.tebebtech.com", "localhost", "127.0.0.1", "testserver"],
    )
    def test_extra_platform_hosts_empty_by_default_rejects_arbitrary_hosts(
        self, factory
    ):
        """In production where TENANT_EXTRA_PLATFORM_HOSTS is empty, non-domain hosts return 404."""
        middleware = TenantSubdomainMiddleware(lambda req: HttpResponse("OK"))

        for host in ["localhost", "127.0.0.1", "testserver"]:
            req = factory.get("/", HTTP_HOST=host)
            res = middleware(req)
            assert res.status_code == 404

    @override_settings(
        DOMAIN="fitgate.tebebtech.com",
        TENANT_EXTRA_PLATFORM_HOSTS=["custom-platform", "testserver"],
        ALLOWED_HOSTS=["fitgate.tebebtech.com", "custom-platform", "testserver"],
    )
    def test_extra_platform_hosts_configured_resolves_tenant_none(self, factory):
        """When TENANT_EXTRA_PLATFORM_HOSTS is set in local/test settings, hosts resolve to tenant=None."""
        middleware = TenantSubdomainMiddleware(lambda req: HttpResponse("OK"))

        for host in ["custom-platform", "testserver"]:
            req = factory.get("/", HTTP_HOST=host)
            res = middleware(req)
            assert res.status_code == 200
            assert req.tenant is None

    def test_domain_setting_fails_fast_without_default(self, monkeypatch):
        """Verify removing DOMAIN from environment causes loading settings to raise ImproperlyConfigured."""
        import importlib

        from django.core.exceptions import ImproperlyConfigured
        from fitgate.settings import base

        monkeypatch.setattr(
            "environ.Env.read_env", staticmethod(lambda *args, **kwargs: None)
        )
        monkeypatch.delenv("DOMAIN", raising=False)

        try:
            with pytest.raises(ImproperlyConfigured) as exc_info:
                importlib.reload(base)
            assert "DOMAIN" in str(exc_info.value)
        finally:
            monkeypatch.undo()
            importlib.reload(base)

    def test_env_example_lists_domain(self):
        """Verify .env.example contains DOMAIN definition."""
        from django.conf import settings

        env_example_path = settings.BASE_DIR.parent / ".env.example"
        assert env_example_path.exists()
        content = env_example_path.read_text(encoding="utf-8")
        assert "DOMAIN=" in content

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

    def test_build_allowed_hosts_helper(self):
        """Verify build_allowed_hosts starts with domain and .domain, is additive, dedupes, and rejects '*'."""
        from django.core.exceptions import ImproperlyConfigured
        from fitgate.settings.hosts import build_allowed_hosts

        # Starts with domain and .domain; env hosts are added, never replace
        domain = "example.com"
        result = build_allowed_hosts(
            domain,
            env_hosts=["custom1.com", "custom2.com"],
            extra=["extra1.com"],
        )
        assert result[0] == domain
        assert result[1] == f".{domain}"
        assert result == [
            "example.com",
            ".example.com",
            "extra1.com",
            "custom1.com",
            "custom2.com",
        ]

        # Duplicates removed while preserving initial order
        deduped = build_allowed_hosts(
            domain,
            env_hosts=["example.com", ".example.com", "extra1.com", "new.com"],
            extra=["extra1.com"],
        )
        assert deduped == ["example.com", ".example.com", "extra1.com", "new.com"]

        # '*' in env_hosts, extra, or domain raises ImproperlyConfigured
        with pytest.raises(ImproperlyConfigured):
            build_allowed_hosts(domain, env_hosts=["*"])

        with pytest.raises(ImproperlyConfigured):
            build_allowed_hosts(domain, extra=["*"])

        with pytest.raises(ImproperlyConfigured):
            build_allowed_hosts("*")

    def test_real_settings_allowed_hosts_validation(self):
        """Verify real settings ALLOWED_HOSTS validates domain subdomains and rejects arbitrary hosts."""
        from django.conf import settings
        from django.http.request import validate_host

        # Derive everything from settings.DOMAIN, not literal "localhost"
        assert validate_host(f"gym1.{settings.DOMAIN}", settings.ALLOWED_HOSTS) is True
        assert (
            validate_host(f"nothere.{settings.DOMAIN}", settings.ALLOWED_HOSTS) is True
        )
        assert validate_host("evil.com", settings.ALLOWED_HOSTS) is False

    def test_allowed_hosts_derived_from_domain_without_wildcard(self, monkeypatch):
        """Verify ALLOWED_HOSTS is derived from DOMAIN and forbids wildcards in base, local, and prod."""
        import importlib

        from django.core.exceptions import ImproperlyConfigured
        from fitgate.settings import base, local, prod

        for s in (base, local, prod):
            assert "*" not in s.ALLOWED_HOSTS
            assert s.DOMAIN in s.ALLOWED_HOSTS
            assert f".{s.DOMAIN}" in s.ALLOWED_HOSTS

        # Prod and local raise ImproperlyConfigured if wildcard is configured
        for mod in (local, prod):
            monkeypatch.setenv("ALLOWED_HOSTS", "localhost,*")
            try:
                with pytest.raises(ImproperlyConfigured):
                    importlib.reload(mod)
            finally:
                monkeypatch.delenv("ALLOWED_HOSTS", raising=False)
                importlib.reload(mod)
