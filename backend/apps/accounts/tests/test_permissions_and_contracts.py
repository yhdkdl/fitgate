"""Tests for permissions, contracts, Django admin access, and OpenAPI docs gates."""

from unittest.mock import patch

import pytest
from django.conf import settings
from django.urls import get_resolver
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.tokens import get_tokens_for_user
from apps.tenants.models import GymTenant


@pytest.mark.django_db
@pytest.mark.urls("apps.accounts.tests.urls")
class TestPermissionsAndProjectContracts:
    """Contract tests for explicit permissions, must_change_password gates, docs, and admin."""

    def test_all_project_apiviews_declare_permission_classes_explicitly(self):
        """
        Contract test: every project APIView/ViewSet must declare permission_classes explicitly
        on the class itself, preventing accidental reliance on inherited defaults.
        """
        resolver = get_resolver()

        def inspect_patterns(patterns):
            view_classes = set()
            for pattern in patterns:
                if hasattr(pattern, "url_patterns"):
                    view_classes.update(inspect_patterns(pattern.url_patterns))
                elif hasattr(pattern, "callback"):
                    callback = pattern.callback
                    # Check class-based views
                    if hasattr(callback, "view_class"):
                        view_classes.add(callback.view_class)
                    elif hasattr(callback, "cls"):
                        view_classes.add(callback.cls)
            return view_classes

        all_view_classes = inspect_patterns(resolver.url_patterns)

        for view_cls in all_view_classes:
            module = getattr(view_cls, "__module__", "")
            # Only enforce on project code, ignore django internal or third-party
            if module.startswith("apps.") or module.startswith("fitgate."):
                assert "permission_classes" in view_cls.__dict__, (
                    f"View class '{view_cls.__name__}' in module '{module}' "
                    f"must declare 'permission_classes' explicitly."
                )
                assert view_cls.permission_classes is not None

                from rest_framework.permissions import AllowAny

                # Contract: every view declaring AllowAny must declare authentication_classes explicitly
                if AllowAny in view_cls.permission_classes:
                    assert "authentication_classes" in view_cls.__dict__, (
                        f"View class '{view_cls.__name__}' in module '{module}' "
                        f"declares AllowAny but does not declare 'authentication_classes' explicitly."
                    )
                else:
                    # Contract: every authenticated non-auth view must require RequirePasswordChanged
                    is_auth = getattr(view_cls, "is_auth_endpoint", False)
                    if not is_auth and not module.startswith("fitgate.urls"):
                        from apps.accounts.permissions import RequirePasswordChanged

                        assert RequirePasswordChanged in view_cls.permission_classes, (
                            f"Authenticated non-auth view class '{view_cls.__name__}' in module '{module}' "
                            f"must declare RequirePasswordChanged in permission_classes."
                        )

    def test_must_change_password_blocks_authenticated_endpoints_with_403(self):
        """
        While must_change_password is True, authenticated endpoints (except auth endpoints)
        are blocked with 403 'password_change_required'.
        """
        admin = User.objects.create_superuser(
            email="mustchange@fitgate.org",
            password="InitialPassword123!",
            must_change_password=True,
        )
        tokens = get_tokens_for_user(admin)

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

        response = client.get("/api/test/must-change-password/", HTTP_HOST="localhost")
        assert response.status_code == 403
        assert response.json() == {"detail": "password_change_required"}

        # When must_change_password is False, access is permitted
        admin.must_change_password = False
        admin.save()

        response_ok = client.get(
            "/api/test/must-change-password/", HTTP_HOST="localhost"
        )
        assert response_ok.status_code == 200
        assert response_ok.json() == {"status": "ok"}

    def test_must_change_password_does_not_block_auth_endpoints(self):
        """Auth endpoints (like logout, refresh) are not blocked while must_change_password is True."""
        admin = User.objects.create_superuser(
            email="auth_exempt@fitgate.org",
            password="InitialPassword123!",
            must_change_password=True,
        )
        tokens = get_tokens_for_user(admin)

        client = APIClient()
        # Logout succeeds even when must_change_password is True
        logout_resp = client.post(
            "/api/auth/logout/",
            {"refresh": tokens["refresh"]},
            HTTP_HOST="localhost",
        )
        assert logout_resp.status_code == 200

    def test_openapi_docs_permission_debug_vs_production(self):
        """
        OpenAPI docs endpoints:
        - When settings.DEBUG is True -> public access permitted.
        - When settings.DEBUG is False -> restricted to Super Admin only.
        """
        client = APIClient()

        # 1. DEBUG = True -> public (200 OK)
        with patch.object(settings, "DEBUG", True):
            resp_debug = client.get("/api/schema/", HTTP_HOST="localhost")
            assert resp_debug.status_code == 200

        # 2. DEBUG = False, unauthenticated -> 401
        with patch.object(settings, "DEBUG", False):
            resp_prod_anon = client.get("/api/schema/", HTTP_HOST="localhost")
            assert resp_prod_anon.status_code == 401

        # 3. DEBUG = False, Super Admin -> 200 OK
        admin = User.objects.create_superuser(
            email="docs.admin@fitgate.org",
            password="AdminPassword123!",
        )
        tokens = get_tokens_for_user(admin)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

        with patch.object(settings, "DEBUG", False):
            resp_prod_admin = client.get("/api/schema/", HTTP_HOST="localhost")
            assert resp_prod_admin.status_code == 200

    def test_django_admin_served_on_apex_only(self):
        """
        Django admin /admin/ is served on the apex domain, but returns 404 on gym subdomains.
        """
        GymTenant.objects.create(name="Gold Gym", subdomain="goldgym")
        client = APIClient()

        # 1. On apex domain: /admin/ responds (302 redirect to admin login or 200)
        apex_resp = client.get("/admin/", HTTP_HOST="localhost")
        assert apex_resp.status_code in [200, 302]

        # 2. On gym subdomain: /admin/ returns 404
        gym_resp = client.get("/admin/", HTTP_HOST="goldgym.localhost")
        assert gym_resp.status_code == 404

    def test_owner_cannot_use_admin_on_apex_super_admin_can(self):
        """
        An Owner cannot log into /admin/ on the apex because is_staff is False.
        A Super Admin can access /admin/ because is_staff is True.
        """
        gym = GymTenant.objects.create(name="Titan Gym", subdomain="titangym")

        owner = User.objects.create_user(
            email="owner@titangym.com",
            password="OwnerPassword123!",
            role=User.ROLE_OWNER,
            gym=gym,
        )

        super_admin = User.objects.create_superuser(
            email="super@titangym.com",
            password="SuperPassword123!",
        )

        client = APIClient()

        # Owner logs in via session authentication for django admin
        client.force_login(owner)
        owner_resp = client.get("/admin/", HTTP_HOST="localhost")
        # Django admin redirects non-staff users or returns 302 to login with ?next=/admin/
        # Check that owner is not recognized as staff
        assert owner.is_staff is False
        assert owner_resp.status_code in [302, 403]
        if owner_resp.status_code == 302:
            assert "/admin/login/" in owner_resp.headers.get("Location", "")

        # Super Admin logs in via session
        client.force_login(super_admin)
        admin_resp = client.get("/admin/", HTTP_HOST="localhost")
        assert super_admin.is_staff is True
        assert admin_resp.status_code == 200
