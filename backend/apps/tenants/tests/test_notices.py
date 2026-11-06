"""Tests for Sprint 28: Notice board announcements and Telegram channel bridge."""

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import AuditLog, Notification, User
from apps.accounts.tokens import get_tokens_for_user
from apps.tenants.models import GymConfig, GymNotice, GymTenant
from apps.tenants.telegram import clear_mock_messages, get_mock_messages


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def gym_tenant_a(db):
    gym = GymTenant.objects.create(
        name="FitGate Bole",
        subdomain="fitgate-bole",
        tier=GymTenant.TIER_GROWTH,
        status=GymTenant.STATUS_ACTIVE,
        tls_confirmed_at=timezone.now(),
    )
    GymConfig.objects.update_or_create(gym=gym)
    return gym


@pytest.fixture
def gym_tenant_b(db):
    gym = GymTenant.objects.create(
        name="FitGate Kazanchis",
        subdomain="fitgate-kazanchis",
        tier=GymTenant.TIER_GROWTH,
        status=GymTenant.STATUS_ACTIVE,
        tls_confirmed_at=timezone.now(),
    )
    GymConfig.objects.update_or_create(gym=gym)
    return gym


def create_user(gym, role, email):
    user = User.objects.create_user(
        email=email,
        password="ValidPassword123!",
        role=role,
        gym=gym,
        full_name=f"Test {role.capitalize()}",
        is_active=True,
    )
    user.force_password_change = False
    user.must_change_password = False
    user.save()
    return user


def auth_client(client, user, gym=None):
    tokens = get_tokens_for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
    if gym:
        client.defaults["HTTP_HOST"] = f"{gym.subdomain}.localhost"
    else:
        client.defaults["HTTP_HOST"] = "localhost"
    return client


@pytest.mark.django_db
class TestNoticeBoardCRUDAndPermissions:
    def test_owner_and_manager_can_post_and_delete_notice(
        self, api_client, gym_tenant_a
    ):
        owner = create_user(gym_tenant_a, User.ROLE_OWNER, "owner_notice@bole.com")
        auth_client(api_client, owner, gym_tenant_a)

        # 1. Post notice
        res = api_client.post(
            "/api/gym/notices/",
            {
                "title": "Holiday Opening Hours",
                "body": "The gym will be open from 8:00 AM to 6:00 PM on national holidays.",
            },
            format="json",
        )
        assert res.status_code == 201
        assert res.data["title"] == "Holiday Opening Hours"
        notice_id = res.data["id"]

        # Crucial requirement: Do NOT create one notification row per member!
        assert Notification.objects.count() == 0

        # Audit log verification
        audit = AuditLog.all_objects.filter(
            action_type="notice_posted",
            affected_record_id=notice_id,
        ).first()
        assert audit is not None
        assert audit.metadata["title"] == "Holiday Opening Hours"

        # 2. Manager can delete notice
        manager = create_user(
            gym_tenant_a, User.ROLE_MANAGER, "manager_notice@bole.com"
        )
        auth_client(api_client, manager, gym_tenant_a)

        res_del = api_client.delete(f"/api/gym/notices/{notice_id}/")
        assert res_del.status_code == 204
        assert GymNotice.all_objects.filter(id=notice_id).count() == 0

    def test_reception_trainer_member_cannot_post_or_delete(
        self, api_client, gym_tenant_a
    ):
        owner = create_user(gym_tenant_a, User.ROLE_OWNER, "owner_perm@bole.com")
        notice = GymNotice.objects.create(
            gym=gym_tenant_a,
            posted_by=owner,
            title="General Maintenance",
            body="Showers undergoing routine maintenance this Thursday afternoon.",
        )

        for role, email in [
            (User.ROLE_RECEPTION, "reception_perm@bole.com"),
            (User.ROLE_TRAINER, "trainer_perm@bole.com"),
            (User.ROLE_MEMBER, "member_perm@bole.com"),
        ]:
            user = create_user(gym_tenant_a, role, email)
            auth_client(api_client, user, gym_tenant_a)

            # Refused post
            res_post = api_client.post(
                "/api/gym/notices/",
                {
                    "title": "Unauthorized Notice",
                    "body": "Should fail with 403 Forbidden.",
                },
                format="json",
            )
            assert res_post.status_code == 403

            # Refused delete
            res_del = api_client.delete(f"/api/gym/notices/{notice.id}/")
            assert res_del.status_code == 403

    def test_tenant_isolation_members_only_see_their_gym_notices(
        self, api_client, gym_tenant_a, gym_tenant_b
    ):
        owner_a = create_user(gym_tenant_a, User.ROLE_OWNER, "owner_a@bole.com")
        GymNotice.objects.create(
            gym=gym_tenant_a,
            posted_by=owner_a,
            title="Bole Special Announcement",
            body="Special event for Bole members only.",
        )

        owner_b = create_user(gym_tenant_b, User.ROLE_OWNER, "owner_b@kazanchis.com")
        GymNotice.objects.create(
            gym=gym_tenant_b,
            posted_by=owner_b,
            title="Kazanchis Special Announcement",
            body="Special event for Kazanchis members only.",
        )

        # Member A lists notices
        member_a = create_user(gym_tenant_a, User.ROLE_MEMBER, "member_a@bole.com")
        auth_client(api_client, member_a, gym_tenant_a)

        res_a = api_client.get("/api/gym/notices/")
        assert res_a.status_code == 200
        titles_a = [n["title"] for n in res_a.data]
        assert "Bole Special Announcement" in titles_a
        assert "Kazanchis Special Announcement" not in titles_a

        # Member B lists notices
        member_b = create_user(gym_tenant_b, User.ROLE_MEMBER, "member_b@kazanchis.com")
        auth_client(api_client, member_b, gym_tenant_b)

        res_b = api_client.get("/api/gym/notices/")
        assert res_b.status_code == 200
        titles_b = [n["title"] for n in res_b.data]
        assert "Kazanchis Special Announcement" in titles_b
        assert "Bole Special Announcement" not in titles_b


@pytest.mark.django_db
class TestTelegramBridgeAndSettings:
    def test_telegram_channel_validation_in_settings(self, api_client, gym_tenant_a):
        owner = create_user(gym_tenant_a, User.ROLE_OWNER, "owner_tg@bole.com")
        auth_client(api_client, owner, gym_tenant_a)

        # Valid channel
        res = api_client.patch(
            "/api/gym/settings/",
            {"telegram_channel": "@fitgate_announcements"},
            format="json",
        )
        assert res.status_code == 200
        config = GymConfig.objects.get(gym=gym_tenant_a)
        assert config.telegram_channel == "@fitgate_announcements"

        # Invalid channels: missing leading @
        res_bad1 = api_client.patch(
            "/api/gym/settings/",
            {"telegram_channel": "fitgate_announcements"},
            format="json",
        )
        assert res_bad1.status_code == 400

        # Invalid: starts with number
        res_bad2 = api_client.patch(
            "/api/gym/settings/",
            {"telegram_channel": "@123channel"},
            format="json",
        )
        assert res_bad2.status_code == 400

        # Invalid: too short (< 5 chars)
        res_bad3 = api_client.patch(
            "/api/gym/settings/",
            {"telegram_channel": "@abc"},
            format="json",
        )
        assert res_bad3.status_code == 400

    def test_notice_telegram_broadcast_with_mock_sender(self, api_client, gym_tenant_a):
        clear_mock_messages()
        owner = create_user(gym_tenant_a, User.ROLE_OWNER, "owner_broadcast@bole.com")
        auth_client(api_client, owner, gym_tenant_a)

        # Configure telegram channel
        config = GymConfig.objects.get(gym=gym_tenant_a)
        config.telegram_channel = "@fitgate_bole_live"
        config.save()

        # Post notice -> broadcast sent to mock sender
        res = api_client.post(
            "/api/gym/notices/",
            {
                "title": "Grand Reopening Party",
                "body": "Join us this Saturday at 10:00 AM for healthy snacks and music!",
            },
            format="json",
        )
        assert res.status_code == 201
        assert res.data["telegram_sent"] is True

        messages = get_mock_messages()
        assert len(messages) >= 1
        assert messages[-1]["channel"] == "@fitgate_bole_live"
        assert "Grand Reopening Party" in messages[-1]["message"]

    def test_unconfigured_telegram_resilience(self, api_client, gym_tenant_a):
        clear_mock_messages()
        owner = create_user(gym_tenant_a, User.ROLE_OWNER, "owner_unconf@bole.com")
        auth_client(api_client, owner, gym_tenant_a)

        # Telegram channel is empty
        config = GymConfig.objects.get(gym=gym_tenant_a)
        config.telegram_channel = ""
        config.save()

        res = api_client.post(
            "/api/gym/notices/",
            {
                "title": "Local Announcement Only",
                "body": "This in-app notice succeeds even without a Telegram channel.",
            },
            format="json",
        )
        assert res.status_code == 201
        assert res.data["telegram_sent"] is False
        assert "not configured" in res.data["telegram_note"]
        # In-app notice exists!
        assert GymNotice.all_objects.filter(title="Local Announcement Only").exists()

    def test_telegram_test_message_endpoint(self, api_client, gym_tenant_a):
        clear_mock_messages()
        owner = create_user(
            gym_tenant_a, User.ROLE_OWNER, "owner_test_endpoint@bole.com"
        )
        auth_client(api_client, owner, gym_tenant_a)

        # When channel is not configured -> 400
        config = GymConfig.objects.get(gym=gym_tenant_a)
        config.telegram_channel = ""
        config.save()

        res_no_channel = api_client.post("/api/gym/settings/telegram/test/")
        assert res_no_channel.status_code == 400

        # When channel is configured -> 200 and mock message recorded
        config.telegram_channel = "@fitgate_bole_test"
        config.save()

        res_ok = api_client.post("/api/gym/settings/telegram/test/")
        assert res_ok.status_code == 200
        assert res_ok.data["success"] is True

        msgs = get_mock_messages()
        assert len(msgs) >= 1
        assert msgs[-1]["channel"] == "@fitgate_bole_test"

        # Member receives 403 on test message endpoint
        member = create_user(gym_tenant_a, User.ROLE_MEMBER, "member_no_test@bole.com")
        auth_client(api_client, member, gym_tenant_a)
        res_mem = api_client.post("/api/gym/settings/telegram/test/")
        assert res_mem.status_code == 403

    def test_telegram_channel_uniqueness_across_gyms(
        self, api_client, gym_tenant_a, gym_tenant_b
    ):
        """A second gym entering an already-used Telegram channel is rejected."""
        owner_a = create_user(gym_tenant_a, User.ROLE_OWNER, "owner_a_tg@bole.com")
        owner_b = create_user(gym_tenant_b, User.ROLE_OWNER, "owner_b_tg@adama.com")

        # Gym A configures channel
        auth_client(api_client, owner_a, gym_tenant_a)
        res_a = api_client.patch(
            "/api/gym/settings/",
            {"telegram_channel": "@fitgate_announcements"},
            format="json",
        )
        assert res_a.status_code == 200
        assert res_a.data["telegram_channel"] == "@fitgate_announcements"

        # Gym B attempts to configure the same channel -> rejected
        auth_client(api_client, owner_b, gym_tenant_b)
        res_b = api_client.patch(
            "/api/gym/settings/",
            {"telegram_channel": "@fitgate_announcements"},
            format="json",
        )
        assert res_b.status_code == 400
        assert "already connected to another gym" in str(res_b.data)

    def test_telegram_channel_resave_same_gym_succeeds(self, api_client, gym_tenant_a):
        """A gym can re-save its own settings with its existing channel without duplicate refusal."""
        owner = create_user(gym_tenant_a, User.ROLE_OWNER, "owner_resave_tg@bole.com")
        auth_client(api_client, owner, gym_tenant_a)

        # First save with channel
        res1 = api_client.patch(
            "/api/gym/settings/",
            {"telegram_channel": "@my_gym_channel", "show_unavailable_equipment": True},
            format="json",
        )
        assert res1.status_code == 200

        # Re-save with same channel and updated show_unavailable_equipment
        res2 = api_client.patch(
            "/api/gym/settings/",
            {
                "telegram_channel": "@my_gym_channel",
                "show_unavailable_equipment": False,
            },
            format="json",
        )
        assert res2.status_code == 200
        assert res2.data["telegram_channel"] == "@my_gym_channel"
        assert res2.data["show_unavailable_equipment"] is False
