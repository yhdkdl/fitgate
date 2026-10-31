from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import AuditLog, User
from apps.accounts.tokens import get_tokens_for_user
from apps.memberships.models import (
    BodyMetrics,
    Member,
    MembershipPlan,
    MemberSubscription,
)
from apps.tenants.models import GymConfig, GymTenant
from apps.trainers.models import TrainerAssignment


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def gym_tenant(db):
    gym = GymTenant.objects.create(
        name="FitGate Bole Hub",
        subdomain="bolehub",
        tier=GymTenant.TIER_GROWTH,
        status=GymTenant.STATUS_ACTIVE,
        contact_phone="+251911223344",
        location="Bole, Addis Ababa",
        tls_confirmed_at="2026-10-11T10:00:00Z",
    )
    GymConfig.objects.update_or_create(
        gym=gym,
        defaults={"has_trainer_module": True, "has_ai_plans": True},
    )
    gym.refresh_from_db()
    return gym


@pytest.fixture
def other_gym_tenant(db):
    gym = GymTenant.objects.create(
        name="Apex Kazanchis",
        subdomain="kazanchis",
        tier=GymTenant.TIER_GROWTH,
        status=GymTenant.STATUS_ACTIVE,
        contact_phone="+251922334455",
        location="Kazanchis, Addis Ababa",
        tls_confirmed_at="2026-10-11T10:00:00Z",
    )
    GymConfig.objects.update_or_create(
        gym=gym,
        defaults={"has_trainer_module": True, "has_ai_plans": True},
    )
    gym.refresh_from_db()
    return gym


@pytest.fixture
def owner_user(db, gym_tenant):
    return User.objects.create_user(
        email="owner@bolehub.com",
        password="OwnerPassword123!",
        gym=gym_tenant,
        role=User.ROLE_OWNER,
        must_change_password=False,
    )


@pytest.fixture
def manager_user(db, gym_tenant):
    return User.objects.create_user(
        email="manager@bolehub.com",
        password="ManagerPassword123!",
        gym=gym_tenant,
        role=User.ROLE_MANAGER,
        must_change_password=False,
    )


@pytest.fixture
def reception_user(db, gym_tenant):
    return User.objects.create_user(
        email="reception@bolehub.com",
        password="ReceptionPassword123!",
        gym=gym_tenant,
        role=User.ROLE_RECEPTION,
        must_change_password=False,
    )


@pytest.fixture
def superadmin_user(db):
    return User.objects.create_user(
        email="superadmin@fitgate.internal",
        password="SuperPassword123!",
        role=User.ROLE_SUPER_ADMIN,
        must_change_password=False,
    )


@pytest.fixture
def assigned_trainer_user(db, gym_tenant):
    user = User.objects.create_user(
        email="trainer1@bolehub.com",
        password="TrainerPassword123!",
        full_name="Abebe Bikila",
        gym=gym_tenant,
        role=User.ROLE_TRAINER,
        must_change_password=False,
    )
    return user


@pytest.fixture
def unrelated_trainer_user(db, gym_tenant):
    user = User.objects.create_user(
        email="trainer2@bolehub.com",
        password="TrainerPassword123!",
        full_name="Derartu Tulu",
        gym=gym_tenant,
        role=User.ROLE_TRAINER,
        must_change_password=False,
    )
    return user


@pytest.fixture
def other_gym_trainer_user(db, other_gym_tenant):
    user = User.objects.create_user(
        email="trainer_other@kazanchis.com",
        password="TrainerPassword123!",
        full_name="Haile Gebrselassie",
        gym=other_gym_tenant,
        role=User.ROLE_TRAINER,
        must_change_password=False,
    )
    return user


@pytest.fixture
def member_user(db, gym_tenant):
    user = User.objects.create_user(
        email="member1@bolehub.com",
        password="MemberPassword123!",
        gym=gym_tenant,
        role=User.ROLE_MEMBER,
        must_change_password=False,
    )
    return user


@pytest.fixture
def member_entity(db, gym_tenant, member_user, assigned_trainer_user):
    plan = MembershipPlan.objects.create(
        gym=gym_tenant,
        name="Pro Athlete + Trainer",
        price_etb=4000,
        duration_value=1,
        duration_unit=MembershipPlan.DURATION_MONTHS,
        trainer_inclusive=True,
        is_active=True,
    )
    member = Member.objects.create(
        gym=gym_tenant,
        user=member_user,
        full_name="Kenubish Bekele",
        phone="+251911002233",
        status=Member.STATUS_ACTIVE,
        waiver_accepted_at=timezone.now(),
    )
    _ = MemberSubscription.objects.create(
        gym=gym_tenant,
        member=member,
        plan=plan,
        start_date=timezone.now().date(),
        end_date=timezone.now().date() + timedelta(days=30),
        status=MemberSubscription.STATUS_ACTIVE,
    )
    trainer = assigned_trainer_user.trainer_profile
    TrainerAssignment.objects.create(
        gym=gym_tenant,
        member=member,
        trainer=trainer,
    )
    return member


def auth_client(
    client: APIClient, user: User, tenant_subdomain: str | None = None
) -> APIClient:
    tokens = get_tokens_for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
    if user.role == User.ROLE_SUPER_ADMIN:
        client.defaults["HTTP_HOST"] = "localhost"
    elif tenant_subdomain:
        client.defaults["HTTP_HOST"] = f"{tenant_subdomain}.localhost"
    else:
        client.defaults["HTTP_HOST"] = "localhost"
    return client


@pytest.mark.django_db
class TestFitnessProfileRBACAndTenancy:
    """Security matrix tests for FitnessProfile access."""

    valid_payload = {
        "goal": "fat_loss",
        "fitness_level": "intermediate",
        "training_days_per_week": 4,
        "session_length_minutes": 60,
        "health_limitations": "Slight lower back tension",
        "equipment_access": "Full gym barbell and dumbbell access",
        "dietary_notes": "Ethiopian Orthodox fasting periods observed (Wednesday & Friday vegan)",
    }

    def test_assigned_trainer_can_get_and_post_fitness_profile(
        self, api_client, gym_tenant, assigned_trainer_user, member_entity
    ):
        client = auth_client(api_client, assigned_trainer_user, gym_tenant.subdomain)
        url = f"/api/gym/members/{member_entity.id}/fitness-profile/"

        # Initially 404 or empty GET
        get_res = client.get(url)
        assert get_res.status_code == 404

        # POST to create
        post_res = client.post(url, data=self.valid_payload, format="json")
        assert post_res.status_code == 200
        data = post_res.json()
        assert data["goal"] == "fat_loss"
        assert data["fitness_level"] == "intermediate"
        assert data["training_days_per_week"] == 4
        assert data["session_length_minutes"] == 60
        assert "Wednesday & Friday vegan" in data["dietary_notes"]

        # GET now succeeds
        get_res2 = client.get(url)
        assert get_res2.status_code == 200
        assert get_res2.json()["goal"] == "fat_loss"

    def test_owner_and_manager_can_view_and_edit_profile(
        self, api_client, gym_tenant, owner_user, manager_user, member_entity
    ):
        # Owner creates profile
        owner_c = auth_client(api_client, owner_user, gym_tenant.subdomain)
        url = f"/api/gym/members/{member_entity.id}/fitness-profile/"

        res = owner_c.post(url, data=self.valid_payload, format="json")
        assert res.status_code == 200

        # Manager updates profile
        manager_c = auth_client(api_client, manager_user, gym_tenant.subdomain)
        updated_payload = dict(
            self.valid_payload, goal="muscle_gain", training_days_per_week=5
        )
        res_mgr = manager_c.post(url, data=updated_payload, format="json")
        assert res_mgr.status_code == 200
        assert res_mgr.json()["goal"] == "muscle_gain"
        assert res_mgr.json()["training_days_per_week"] == 5

    def test_unrelated_trainer_is_forbidden(
        self, api_client, gym_tenant, unrelated_trainer_user, member_entity
    ):
        client = auth_client(api_client, unrelated_trainer_user, gym_tenant.subdomain)
        url = f"/api/gym/members/{member_entity.id}/fitness-profile/"

        res_get = client.get(url)
        assert res_get.status_code == 403

        res_post = client.post(url, data=self.valid_payload, format="json")
        assert res_post.status_code == 403

    def test_reception_and_super_admin_are_forbidden(
        self, api_client, gym_tenant, reception_user, superadmin_user, member_entity
    ):
        url = f"/api/gym/members/{member_entity.id}/fitness-profile/"

        # Reception
        rec_c = auth_client(api_client, reception_user, gym_tenant.subdomain)
        assert rec_c.get(url).status_code == 403
        assert (
            rec_c.post(url, data=self.valid_payload, format="json").status_code == 403
        )

        # Super Admin
        sa_c = auth_client(api_client, superadmin_user)
        assert sa_c.get(url).status_code == 403
        assert sa_c.post(url, data=self.valid_payload, format="json").status_code == 403

    def test_other_gym_trainer_cannot_access_profile(
        self, api_client, other_gym_tenant, other_gym_trainer_user, member_entity
    ):
        client = auth_client(
            api_client, other_gym_trainer_user, other_gym_tenant.subdomain
        )
        url = f"/api/gym/members/{member_entity.id}/fitness-profile/"
        res = client.get(url)
        assert res.status_code in (403, 404)

    def test_member_read_only_access_via_me_endpoint(
        self, api_client, gym_tenant, member_user, member_entity, assigned_trainer_user
    ):
        # First create profile via assigned trainer
        trainer_c = auth_client(api_client, assigned_trainer_user, gym_tenant.subdomain)
        trainer_c.post(
            f"/api/gym/members/{member_entity.id}/fitness-profile/",
            data=self.valid_payload,
            format="json",
        )

        # Member checks /api/members/me/fitness-profile/
        member_c = auth_client(api_client, member_user, gym_tenant.subdomain)
        res_me = member_c.get("/api/members/me/fitness-profile/")
        assert res_me.status_code == 200
        assert res_me.json()["goal"] == "fat_loss"

        # Member cannot POST/PUT to /api/members/me/fitness-profile/ (Method Not Allowed)
        res_post_me = member_c.post(
            "/api/members/me/fitness-profile/", data=self.valid_payload, format="json"
        )
        assert res_post_me.status_code in (403, 405)

        # Member cannot access gym staff endpoint
        res_gym_endpoint = member_c.get(
            f"/api/gym/members/{member_entity.id}/fitness-profile/"
        )
        assert res_gym_endpoint.status_code == 403


@pytest.mark.django_db
class TestFitnessProfileValidationAndAudit:
    """Validation boundaries and audit log verification."""

    valid_payload = {
        "goal": "strength",
        "fitness_level": "advanced",
        "training_days_per_week": 3,
        "session_length_minutes": 45,
        "health_limitations": "None",
        "equipment_access": "Full gym",
        "dietary_notes": "High protein",
    }

    def test_missing_required_fields_rejects_with_400(
        self, api_client, gym_tenant, assigned_trainer_user, member_entity
    ):
        client = auth_client(api_client, assigned_trainer_user, gym_tenant.subdomain)
        url = f"/api/gym/members/{member_entity.id}/fitness-profile/"

        for field in [
            "goal",
            "fitness_level",
            "training_days_per_week",
            "session_length_minutes",
        ]:
            payload = dict(self.valid_payload)
            del payload[field]
            res = client.post(url, data=payload, format="json")
            assert res.status_code == 400
            assert field in res.json()

    def test_training_days_per_week_range_limits(
        self, api_client, gym_tenant, assigned_trainer_user, member_entity
    ):
        client = auth_client(api_client, assigned_trainer_user, gym_tenant.subdomain)
        url = f"/api/gym/members/{member_entity.id}/fitness-profile/"

        # 1 day is invalid (below 2)
        payload = dict(self.valid_payload, training_days_per_week=1)
        res1 = client.post(url, data=payload, format="json")
        assert res1.status_code == 400

        # 7 days is invalid (above 6)
        payload = dict(self.valid_payload, training_days_per_week=7)
        res7 = client.post(url, data=payload, format="json")
        assert res7.status_code == 400

        # 2 and 6 days are valid
        payload = dict(self.valid_payload, training_days_per_week=2)
        assert client.post(url, data=payload, format="json").status_code == 200

        payload = dict(self.valid_payload, training_days_per_week=6)
        assert client.post(url, data=payload, format="json").status_code == 200

    def test_session_length_minutes_choices(
        self, api_client, gym_tenant, assigned_trainer_user, member_entity
    ):
        client = auth_client(api_client, assigned_trainer_user, gym_tenant.subdomain)
        url = f"/api/gym/members/{member_entity.id}/fitness-profile/"

        # 25 is not allowed
        payload = dict(self.valid_payload, session_length_minutes=25)
        res = client.post(url, data=payload, format="json")
        assert res.status_code == 400

        # Allowed values: 30, 45, 60, 90
        for mins in [30, 45, 60, 90]:
            payload = dict(self.valid_payload, session_length_minutes=mins)
            res_ok = client.post(url, data=payload, format="json")
            assert res_ok.status_code == 200

    def test_dietary_notes_max_length(
        self, api_client, gym_tenant, assigned_trainer_user, member_entity
    ):
        client = auth_client(api_client, assigned_trainer_user, gym_tenant.subdomain)
        url = f"/api/gym/members/{member_entity.id}/fitness-profile/"

        payload = dict(self.valid_payload, dietary_notes="A" * 1001)
        res = client.post(url, data=payload, format="json")
        assert res.status_code == 400

    def test_latest_measurements_populated_from_body_metrics(
        self, api_client, gym_tenant, assigned_trainer_user, member_entity
    ):
        # Record latest BodyMetrics
        BodyMetrics.objects.create(
            gym=gym_tenant,
            member=member_entity,
            recorded_by=assigned_trainer_user,
            weight_kg=75.5,
            height_cm=180.0,
            measurements={
                "waist_cm": 82.0,
                "neck_cm": 38.0,
                "resting_heart_rate": 62,
                "body_fat_percentage": 15.5,
            },
        )

        client = auth_client(api_client, assigned_trainer_user, gym_tenant.subdomain)
        url = f"/api/gym/members/{member_entity.id}/fitness-profile/"
        res = client.post(url, data=self.valid_payload, format="json")
        assert res.status_code == 200
        meas = res.json()["latest_measurements"]
        assert meas is not None
        assert float(meas["weight_kg"]) == 75.5
        assert float(meas["height_cm"]) == 180.0
        assert float(meas["body_fat_percentage"]) == 15.5
        assert meas["resting_heart_rate"] == 62

    def test_saving_fitness_profile_creates_audit_log(
        self, api_client, gym_tenant, assigned_trainer_user, member_entity
    ):
        client = auth_client(api_client, assigned_trainer_user, gym_tenant.subdomain)
        url = f"/api/gym/members/{member_entity.id}/fitness-profile/"

        initial_count = AuditLog.all_objects.filter(
            action_type="fitness_profile_saved"
        ).count()
        res = client.post(url, data=self.valid_payload, format="json")
        assert res.status_code == 200

        new_count = AuditLog.all_objects.filter(
            action_type="fitness_profile_saved"
        ).count()
        assert new_count == initial_count + 1

        log_entry = AuditLog.all_objects.filter(
            action_type="fitness_profile_saved"
        ).latest("timestamp")
        assert log_entry.actor == assigned_trainer_user
        assert log_entry.affected_record_id == str(member_entity.id)
