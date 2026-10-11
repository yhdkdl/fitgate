"""Comprehensive tests for Sprint 4a: Public Demo Requests and Super Admin lead list."""

import pytest
from django.core.cache import caches
from rest_framework.test import APIClient

from apps.accounts.models import Notification, User
from apps.accounts.tokens import get_tokens_for_user
from apps.tenants.models import DemoRequest, GymTenant
from apps.tenants.services import create_gym
from apps.tenants.uapi import MockCPanelUAPIClient


@pytest.mark.django_db
class TestDemoRequestsSuite:
    """Test suite for public demo requests, rate limiting, honeypot, notifications, and lead management."""

    @pytest.fixture(autouse=True)
    def clear_throttling_cache(self):
        """Clear cache before each test to prevent throttling bleed."""
        if "db_cache" in caches:
            caches["db_cache"].clear()
        caches["default"].clear()
        yield
        if "db_cache" in caches:
            caches["db_cache"].clear()
        caches["default"].clear()

    @pytest.fixture
    def super_admin(self):
        """Create active platform Super Admin."""
        return User.objects.create_superuser(
            email="superadmin@fitgate.org",
            password="SuperPassword123!",
            must_change_password=False,
        )

    @pytest.fixture
    def super_admin_client(self, super_admin):
        """API client authenticated as Super Admin on apex."""
        client = APIClient()
        tokens = get_tokens_for_user(super_admin)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        return client

    @pytest.fixture
    def gym_tenant(self):
        """Create an active gym tenant."""
        return GymTenant.objects.create(
            name="Alpha Gym",
            subdomain="alphagym",
            status=GymTenant.STATUS_ACTIVE,
            tier=GymTenant.TIER_GROWTH,
        )

    @pytest.fixture
    def gym_owner(self, gym_tenant):
        """Create gym owner."""
        user = User(
            email="owner@alphagym.com",
            role=User.ROLE_OWNER,
            gym=gym_tenant,
            must_change_password=False,
            is_active=True,
        )
        user.set_password("OwnerPassword123!")
        user.save()
        return user

    @pytest.fixture
    def gym_owner_client(self, gym_owner):
        """API client authenticated as gym owner on gym subdomain."""
        client = APIClient()
        tokens = get_tokens_for_user(gym_owner)
        client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {tokens['access']}",
            HTTP_HOST="alphagym.localhost:8000",
        )
        return client

    def test_public_demo_request_creation_at_apex(self, super_admin):
        """Submitting demo request at apex creates DemoRequest and Super Admin Notification."""
        client = APIClient()
        payload = {
            "gym_name": "Arsho Fitness",
            "contact_name": "Arsho Lemma",
            "phone": "+251911223344",
            "city": "Addis Ababa",
            "email": "arsho@example.com",
            "message": "Interested in growth plan with 3 trainers.",
        }

        response = client.post(
            "/api/platform/demo-requests/public/",
            data=payload,
            format="json",
        )

        assert response.status_code == 201
        assert response.data["detail"] == "demo_request_received"
        assert "id" in response.data

        # Verify DemoRequest in DB
        demo = DemoRequest.objects.get(id=response.data["id"])
        assert demo.gym_name == "Arsho Fitness"
        assert demo.contact_name == "Arsho Lemma"
        assert demo.phone == "+251911223344"
        assert demo.city == "Addis Ababa"
        assert demo.email == "arsho@example.com"
        assert demo.message == "Interested in growth plan with 3 trainers."
        assert demo.status == DemoRequest.STATUS_NEW
        assert demo.notes == ""

        # Verify platform-level notification for Super Admin
        notification = Notification.objects.get(
            recipient=super_admin, type="demo_request"
        )
        assert "Arsho Fitness" in notification.message
        assert notification.gym is None  # Platform level
        assert not notification.is_read

    def test_public_demo_request_rejected_on_gym_subdomain(self, gym_tenant):
        """Demo requests sent to gym subdomains are rejected with 400 Bad Request."""
        client = APIClient()
        payload = {
            "gym_name": "Subdomain Attempt Gym",
            "contact_name": "Test Contact",
            "phone": "+251912345678",
        }

        # Request to gym subdomain
        response = client.post(
            "/api/platform/demo-requests/public/",
            data=payload,
            format="json",
            HTTP_HOST=f"{gym_tenant.subdomain}.localhost:8000",
        )

        assert response.status_code == 400
        assert "apex platform domain" in response.data["detail"]
        assert not DemoRequest.objects.filter(gym_name="Subdomain Attempt Gym").exists()

    def test_public_demo_request_honeypot_silently_ignored(self, super_admin):
        """When honeypot field is filled, return success but store nothing in DB."""
        client = APIClient()
        payload = {
            "gym_name": "Spam Bot Gym",
            "contact_name": "Spam Bot",
            "phone": "+251999999999",
            "website": "http://spambot-link.com",  # Honeypot filled
        }

        response = client.post(
            "/api/platform/demo-requests/public/",
            data=payload,
            format="json",
        )

        # Returns 201 success to trick bot
        assert response.status_code == 201
        assert response.data["detail"] == "demo_request_received"
        assert "id" not in response.data

        # Ensure NOTHING was stored in database
        assert not DemoRequest.objects.filter(gym_name="Spam Bot Gym").exists()
        assert not Notification.objects.filter(type="demo_request").exists()

    def test_public_demo_request_validation_errors(self):
        """Missing required fields returns 400 with field-level errors."""
        client = APIClient()
        response = client.post(
            "/api/platform/demo-requests/public/",
            data={"city": "Addis Ababa"},
            format="json",
        )

        assert response.status_code == 400
        assert "gym_name" in response.data
        assert "contact_name" in response.data
        assert "phone" in response.data

    def test_public_demo_request_rate_limiting(self):
        """Exceeding rate limit returns 429 Too Many Requests."""
        client = APIClient()
        payload = {
            "gym_name": "Rapid Gym",
            "contact_name": "Rapid Contact",
            "phone": "+251911001122",
        }

        # Make 10 allowed requests (throttle limit is 10/hour)
        for _ in range(10):
            res = client.post(
                "/api/platform/demo-requests/public/",
                data=payload,
                format="json",
            )
            assert res.status_code == 201

        # 11th request must be throttled
        response = client.post(
            "/api/platform/demo-requests/public/",
            data=payload,
            format="json",
        )
        assert response.status_code == 429

    def test_super_admin_list_and_filter_demo_requests(
        self, super_admin_client, super_admin
    ):
        """Super Admin can list requests and filter by status."""
        d1 = DemoRequest.objects.create(
            gym_name="Gym New",
            contact_name="Contact 1",
            phone="0911",
            status=DemoRequest.STATUS_NEW,
        )
        d2 = DemoRequest.objects.create(
            gym_name="Gym Contacted",
            contact_name="Contact 2",
            phone="0922",
            status=DemoRequest.STATUS_CONTACTED,
            handled_by=super_admin,
        )

        # List all
        res_all = super_admin_client.get("/api/platform/demo-requests/")
        assert res_all.status_code == 200
        assert len(res_all.data) >= 2

        # Filter by status 'new'
        res_new = super_admin_client.get("/api/platform/demo-requests/?status=new")
        assert res_new.status_code == 200
        assert all(r["status"] == "new" for r in res_new.data)
        assert any(r["id"] == str(d1.id) for r in res_new.data)

        # Filter by status 'contacted'
        res_contacted = super_admin_client.get(
            "/api/platform/demo-requests/?status=contacted"
        )
        assert res_contacted.status_code == 200
        assert all(r["status"] == "contacted" for r in res_contacted.data)
        assert any(r["id"] == str(d2.id) for r in res_contacted.data)

    def test_super_admin_detail_and_patch_status_and_notes(
        self, super_admin_client, super_admin
    ):
        """Super Admin can view details and update notes and move status."""
        demo = DemoRequest.objects.create(
            gym_name="Lideta Fitness",
            contact_name="Lideta Contact",
            phone="+251911998877",
            status=DemoRequest.STATUS_NEW,
        )

        # Detail view
        res = super_admin_client.get(f"/api/platform/demo-requests/{demo.id}/")
        assert res.status_code == 200
        assert res.data["gym_name"] == "Lideta Fitness"
        assert res.data["status"] == "new"

        # PATCH update
        patch_res = super_admin_client.patch(
            f"/api/platform/demo-requests/{demo.id}/",
            data={
                "status": DemoRequest.STATUS_CONTACTED,
                "notes": "Spoke on phone, scheduled demo presentation for Friday 3pm.",
            },
            format="json",
        )
        assert patch_res.status_code == 200
        assert patch_res.data["status"] == "contacted"
        assert "scheduled demo presentation" in patch_res.data["notes"]
        assert patch_res.data["handled_by_email"] == super_admin.email

        # Verify DB
        demo.refresh_from_db()
        assert demo.status == DemoRequest.STATUS_CONTACTED
        assert demo.handled_by == super_admin

    def test_convert_prefill_endpoint(self, super_admin_client):
        """Convert endpoint returns pre-filled data to populate Create Gym form."""
        demo = DemoRequest.objects.create(
            gym_name="Meskel Square Gym",
            contact_name="Abebe Bikila",
            phone="+251944556677",
            email="abebe@meskelgym.com",
            city="Addis Ababa, Meskel Square",
            status=DemoRequest.STATUS_DEMO_DONE,
        )

        res = super_admin_client.get(f"/api/platform/demo-requests/{demo.id}/convert/")
        assert res.status_code == 200
        assert res.data["demo_request_id"] == str(demo.id)
        assert res.data["name"] == "Meskel Square Gym"
        assert res.data["contact_name"] == "Abebe Bikila"
        assert res.data["contact_phone"] == "+251944556677"
        assert res.data["contact_email"] == "abebe@meskelgym.com"
        assert res.data["location"] == "Addis Ababa, Meskel Square"

    def test_create_gym_converts_demo_request(self, super_admin):
        """Creating a gym with demo_request_id links tenant and sets status to converted."""
        demo = DemoRequest.objects.create(
            gym_name="Olympic Gym",
            contact_name="Haile Gebrselassie",
            phone="+251911334455",
            email="haile@olympicgym.com",
            status=DemoRequest.STATUS_DEMO_DONE,
        )

        mock_uapi = MockCPanelUAPIClient()
        result = create_gym(
            name="Olympic Gym",
            subdomain="olympic-gym",
            tier=GymTenant.TIER_GROWTH,
            location="Bole, Addis Ababa",
            contact_name="Haile Gebrselassie",
            contact_phone="+251911334455",
            contact_email="haile@olympicgym.com",
            owner_name="Haile Gebrselassie",
            owner_email="haile@olympicgym.com",
            payment_amount=15000,
            payment_reference="CBE-OLYMPIC-2026",
            payment_method="bank_transfer",
            acting_super_admin=super_admin,
            demo_request_id=str(demo.id),
            uapi_client=mock_uapi,
        )

        gym = result["gym"]
        demo.refresh_from_db()
        assert demo.status == DemoRequest.STATUS_CONVERTED
        assert demo.converted_gym == gym
        assert demo.handled_by == super_admin

    def test_non_super_admin_forbidden_from_demo_requests(self, gym_owner_client):
        """Non-Super Admin users (e.g. gym owners) get 403 on lead endpoints."""
        res_list = gym_owner_client.get("/api/platform/demo-requests/")
        assert res_list.status_code == 403

        fake_id = "00000000-0000-0000-0000-000000000001"
        res_detail = gym_owner_client.get(f"/api/platform/demo-requests/{fake_id}/")
        assert res_detail.status_code == 403

        res_convert = gym_owner_client.get(
            f"/api/platform/demo-requests/{fake_id}/convert/"
        )
        assert res_convert.status_code == 403
