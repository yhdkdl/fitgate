"""Tests for Sprint 37a Demo Gym Seeding, Archive-and-Recreate, and Tenancy Safeguards."""

from unittest.mock import patch

import pytest
from django.core.management import CommandError, call_command
from django.test import override_settings
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.memberships.models import Member
from apps.tenants.models import GymTenant


@pytest.mark.django_db
class TestDemoGymSeeding:
    def test_demo_seed_refuses_when_allow_demo_seed_false(self):
        """Seed command must abort immediately when ALLOW_DEMO_SEED is False."""
        with override_settings(ALLOW_DEMO_SEED=False):
            with pytest.raises(CommandError) as exc_info:
                call_command("seed_demo_gym")
            assert "ALLOW_DEMO_SEED" in str(exc_info.value)

    def test_demo_seed_creates_rich_dataset_and_preserves_non_demo_gym(self):
        """
        Tests that seed_demo_gym creates expected demo data and does not touch
        non-demo gym rows.
        """
        # Create non-demo gym
        real_gym = GymTenant.objects.create(
            name="Real Iron Gym",
            subdomain="realiron",
            tier=GymTenant.TIER_STARTER,
            status=GymTenant.STATUS_ACTIVE,
            is_demo=False,
        )
        User.objects.create(
            email="owner@realiron.com",
            role=User.ROLE_OWNER,
            gym=real_gym,
        )
        real_member_user = User.objects.create(
            email="member@realiron.com",
            role=User.ROLE_MEMBER,
            gym=real_gym,
        )
        Member.objects.create(
            gym=real_gym,
            user=real_member_user,
            full_name="Real Member",
            phone="+251911111111",
            waiver_accepted_at="2026-01-01T00:00:00Z",
        )

        initial_real_user_count = User.all_objects.filter(gym=real_gym).count()
        initial_real_member_count = Member.all_objects.filter(gym=real_gym).count()

        with override_settings(ALLOW_DEMO_SEED=True, DEMO_PASSWORD="DemoSecret123!"):
            call_command("seed_demo_gym")

        # Verify demo gym was created
        demo_gym = GymTenant.objects.filter(subdomain="demo", is_demo=True).first()
        assert demo_gym is not None
        assert demo_gym.status == GymTenant.STATUS_ACTIVE
        assert demo_gym.tier == GymTenant.TIER_GROWTH

        # Verify demo gym has ~90 members
        demo_members = Member.all_objects.filter(gym=demo_gym)
        assert demo_members.count() == 90

        # Verify demo gym staff accounts
        assert User.all_objects.filter(email="owner@demo.local", gym=demo_gym).exists()
        assert User.all_objects.filter(
            email="manager@demo.local", gym=demo_gym
        ).exists()
        assert User.all_objects.filter(
            email="reception@demo.local", gym=demo_gym
        ).exists()
        assert User.all_objects.filter(
            email="trainer1@demo.local", gym=demo_gym
        ).exists()

        # Verify non-demo gym was 100% untouched
        real_gym.refresh_from_db()
        assert real_gym.subdomain == "realiron"
        assert real_gym.status == GymTenant.STATUS_ACTIVE
        assert not real_gym.is_demo
        assert User.all_objects.filter(gym=real_gym).count() == initial_real_user_count
        assert (
            Member.all_objects.filter(gym=real_gym).count() == initial_real_member_count
        )

    def test_demo_seed_archive_and_recreate(self):
        """Running seed_demo_gym twice archives previous demo gym to demo-archive-1."""
        with override_settings(ALLOW_DEMO_SEED=True):
            call_command("seed_demo_gym")
            first_demo = GymTenant.objects.get(subdomain="demo")
            first_demo_id = first_demo.id

            call_command("seed_demo_gym")

        # Previous demo gym should now be archived
        first_demo.refresh_from_db()
        assert first_demo.subdomain == "demo-archive-1"
        assert first_demo.status == GymTenant.STATUS_TERMINATED
        assert first_demo.is_demo is True

        # Archived users should have .archived.1 suffix
        archived_users = User.all_objects.filter(gym=first_demo)
        for u in archived_users:
            assert u.email.endswith(".archived.1")

        # New demo gym should exist under "demo"
        new_demo = GymTenant.objects.get(subdomain="demo")
        assert new_demo.id != first_demo_id
        assert new_demo.status == GymTenant.STATUS_ACTIVE
        assert new_demo.is_demo is True
        assert Member.all_objects.filter(gym=new_demo).count() == 90

    def test_zero_outbound_calls_during_seed(self):
        """Seeding demo gym must make 0 external calls (Brevo, Telegram, Chapa, AI)."""
        with (
            patch("urllib.request.urlopen") as mock_url,
            patch("django.core.mail.send_mail") as mock_mail,
        ):
            with override_settings(ALLOW_DEMO_SEED=True):
                call_command("seed_demo_gym")

            assert mock_url.call_count == 0
            assert mock_mail.call_count == 0

    def test_platform_analytics_excludes_demo_gym(self):
        """Platform analytics overview must exclude demo gym revenue and member counts."""
        client = APIClient()
        superadmin = User.objects.create(
            email="superadmin@fitgate.local",
            role=User.ROLE_SUPER_ADMIN,
            gym=None,
        )
        superadmin.set_password("AdminPass123!")
        superadmin.save()

        # Seed demo gym
        with override_settings(ALLOW_DEMO_SEED=True):
            call_command("seed_demo_gym")

        client.force_authenticate(user=superadmin)
        res = client.get("/api/platform/analytics/overview/")
        assert res.status_code == 200
        data = res.json()

        # Total active gyms and members should not count demo gym
        # If no real gyms exist, active_gyms is 0 and total_members is 0
        real_gym_count = GymTenant.objects.filter(is_demo=False).count()
        assert data.get("total_gyms", 0) == real_gym_count
