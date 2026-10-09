"""Tests for Super Admin bootstrap command and platform administration endpoints."""

import os
from unittest.mock import patch

import pytest
from django.core.management import CommandError, call_command
from django.urls import get_resolver
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.tokens import get_tokens_for_user
from apps.tenants.models import GymTenant


@pytest.mark.django_db
class TestSuperAdminBootstrapAndCreation:
    """Test create_super_admin command and POST /api/platform/super-admins/."""

    def test_create_super_admin_command_reads_env_and_creates_admin(self):
        """create_super_admin reads env vars and sets must_change_password=True."""
        env_vars = {
            "SUPERADMIN_EMAIL": "FIRST.ADMIN@FitGate.ORG",
            "SUPERADMIN_PASSWORD": "SecureAdminPassword123!",
        }

        with patch.dict(os.environ, env_vars, clear=False):
            call_command("create_super_admin")

        admin = User.all_objects.get(email="first.admin@fitgate.org")
        assert admin.role == User.ROLE_SUPER_ADMIN
        assert admin.gym is None
        assert admin.must_change_password is True
        assert admin.is_active is True
        assert admin.check_password("SecureAdminPassword123!") is True

    def test_create_super_admin_command_fails_if_env_missing(self):
        """create_super_admin fails with CommandError if env vars are missing."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(CommandError, match="SUPERADMIN_EMAIL"):
                call_command("create_super_admin")

    def test_create_super_admin_command_is_idempotent(self):
        """If any Super Admin exists, create_super_admin changes nothing and exits 0."""
        existing = User.objects.create_superuser(
            email="existing.admin@fitgate.org",
            password="OriginalPassword123!",
            must_change_password=False,
        )

        env_vars = {
            "SUPERADMIN_EMAIL": "different.admin@fitgate.org",
            "SUPERADMIN_PASSWORD": "DifferentPassword123!",
        }

        with patch.dict(os.environ, env_vars, clear=False):
            call_command("create_super_admin")

        # Proves second admin was not created and existing was untouched
        assert User.all_objects.filter(role=User.ROLE_SUPER_ADMIN).count() == 1
        assert not User.all_objects.filter(email="different.admin@fitgate.org").exists()
        existing.refresh_from_db()
        assert existing.must_change_password is False

    def test_no_http_route_can_create_first_super_admin(self):
        """Contract test: no public unauthenticated HTTP route exists for creating a Super Admin."""
        resolver = get_resolver()

        def collect_routes(patterns, prefix=""):
            routes = []
            for pattern in patterns:
                if hasattr(pattern, "url_patterns"):
                    routes.extend(
                        collect_routes(
                            pattern.url_patterns, prefix + str(pattern.pattern)
                        )
                    )
                else:
                    routes.append(prefix + str(pattern.pattern))
            return routes

        all_routes = collect_routes(resolver.url_patterns)

        # Confirm no public registration/signup route exists
        for route in all_routes:
            assert "register" not in route.lower() or "member" in route.lower()
            assert "super-admin/register" not in route.lower()
            assert "superadmin/register" not in route.lower()
            assert "bootstrap" not in route.lower()

    def test_create_additional_super_admin_endpoint_success(self):
        """
        POST /api/platform/super-admins/ on apex domain by active Super Admin
        with valid current_password creates new Super Admin with must_change_password=True.
        """
        actor = User.objects.create_superuser(
            email="actor.admin@fitgate.org",
            password="ActorPassword123!",
        )
        tokens = get_tokens_for_user(actor)

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

        response = client.post(
            "/api/platform/super-admins/",
            {
                "email": "NEW.ADMIN@FitGate.org",
                "password": "NewAdminPassword123!",
                "current_password": "ActorPassword123!",
            },
            HTTP_HOST="localhost",
        )

        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "new.admin@fitgate.org"
        assert data["role"] == "super_admin"
        assert data["must_change_password"] is True

        new_admin = User.all_objects.get(email="new.admin@fitgate.org")
        assert new_admin.gym is None
        assert new_admin.check_password("NewAdminPassword123!") is True

    def test_create_additional_super_admin_wrong_current_password_fails(self):
        """Actor providing incorrect current password fails with 400."""
        actor = User.objects.create_superuser(
            email="actor2@fitgate.org",
            password="ActorPassword123!",
        )
        tokens = get_tokens_for_user(actor)

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

        response = client.post(
            "/api/platform/super-admins/",
            {
                "email": "another@fitgate.org",
                "password": "NewPassword123!",
                "current_password": "WrongActorPassword!",
            },
            HTTP_HOST="localhost",
        )
        assert response.status_code == 400

    def test_create_additional_super_admin_non_super_admin_forbidden(self):
        """Non-super-admin user (e.g. Owner) gets 403 on /api/platform/super-admins/."""
        gym = GymTenant.objects.create(name="Apex Gym", subdomain="apex")
        owner = User.objects.create_user(
            email="owner@apex.com",
            password="OwnerPassword123!",
            role=User.ROLE_OWNER,
            gym=gym,
        )

        client = APIClient()
        client.force_authenticate(user=owner)

        response = client.post(
            "/api/platform/super-admins/",
            {
                "email": "third@fitgate.org",
                "password": "Password123!",
                "current_password": "OwnerPassword123!",
            },
            HTTP_HOST="localhost",
        )
        assert response.status_code == 403

    def test_create_additional_super_admin_on_gym_subdomain_rejected(self):
        """Calling /api/platform/super-admins/ on a gym subdomain returns 403/401."""
        actor = User.objects.create_superuser(
            email="actor3@fitgate.org",
            password="ActorPassword123!",
        )
        tokens = get_tokens_for_user(actor)
        GymTenant.objects.create(name="Gym Test", subdomain="gymtest")

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

        response = client.post(
            "/api/platform/super-admins/",
            {
                "email": "fourth@fitgate.org",
                "password": "Password123!",
                "current_password": "ActorPassword123!",
            },
            HTTP_HOST="gymtest.localhost",
        )
        # Token gym mismatch or domain restriction returns 401 or 403
        assert response.status_code in [401, 403]
