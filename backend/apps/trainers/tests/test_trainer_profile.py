import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import AuditLog, User
from apps.accounts.tokens import get_tokens_for_user
from apps.memberships.models import Member
from apps.tenants.models import GymConfig, GymTenant
from apps.trainers.models import Trainer, TrainerAssignment


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
    # Ensure gym has GymConfig with has_trainer_module=True
    GymConfig.objects.update_or_create(
        gym=gym,
        defaults={"has_trainer_module": True},
    )
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
        defaults={"has_trainer_module": True},
    )
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
def trainer_user(db, gym_tenant):
    return User.objects.create_user(
        email="trainer@bolehub.com",
        password="TrainerPassword123!",
        gym=gym_tenant,
        role=User.ROLE_TRAINER,
        full_name="Coach Dawit",
        must_change_password=False,
    )


@pytest.fixture
def other_trainer_user(db, other_gym_tenant):
    return User.objects.create_user(
        email="trainer@kazanchis.com",
        password="OtherTrainerPassword123!",
        gym=other_gym_tenant,
        role=User.ROLE_TRAINER,
        full_name="Coach Kazanchis",
        must_change_password=False,
    )


@pytest.fixture
def member_user(db, gym_tenant):
    user = User.objects.create_user(
        email="member@bolehub.com",
        password="MemberPassword123!",
        gym=gym_tenant,
        role=User.ROLE_MEMBER,
        must_change_password=False,
    )
    Member.all_objects.create(
        gym=gym_tenant,
        user=user,
        full_name="Member One",
        phone="+251911000001",
        waiver_accepted_at=timezone.now(),
        status=Member.STATUS_ACTIVE,
    )
    return user


@pytest.fixture
def superadmin_user(db):
    return User.objects.create_user(
        email="superadmin@apex.com",
        password="SuperPassword123!",
        role=User.ROLE_SUPER_ADMIN,
        must_change_password=False,
    )


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
class TestTrainerProfileAutoCreation:
    """Verifies that creating a User with role=trainer creates a Trainer profile in the same step."""

    def test_trainer_user_creation_creates_trainer_profile(self, gym_tenant):
        user = User.objects.create_user(
            email="newtrainer@bolehub.com",
            password="TrainerPassword123!",
            gym=gym_tenant,
            role=User.ROLE_TRAINER,
            full_name="New Coach",
        )
        trainer = Trainer.all_objects.filter(user=user).first()
        assert trainer is not None
        assert trainer.gym_id == gym_tenant.id
        assert trainer.max_clients == 20
        assert trainer.client_count == 0

    def test_non_trainer_user_creation_does_not_create_trainer_profile(
        self, gym_tenant
    ):
        user = User.objects.create_user(
            email="newreception@bolehub.com",
            password="ReceptionPassword123!",
            gym=gym_tenant,
            role=User.ROLE_RECEPTION,
            full_name="Front Desk",
        )
        assert not Trainer.all_objects.filter(user=user).exists()


@pytest.mark.django_db
class TestTrainerEndpointsRBAC:
    """Covers permission matrix: allowed and denied for every role on the new endpoints."""

    def test_list_trainers_allowed_for_owner_and_manager(
        self, api_client, gym_tenant, owner_user, manager_user, trainer_user
    ):
        for user in [owner_user, manager_user]:
            client = auth_client(api_client, user, gym_tenant.subdomain)
            resp = client.get("/api/gym/trainers/")
            assert resp.status_code == 200
            assert isinstance(resp.data, list)
            assert len(resp.data) >= 1
            assert resp.data[0]["user"]["email"] == trainer_user.email
            assert "max_clients" in resp.data[0]
            assert "client_count" in resp.data[0]

    def test_list_trainers_denied_for_other_roles(
        self,
        api_client,
        gym_tenant,
        trainer_user,
        reception_user,
        member_user,
        superadmin_user,
    ):
        for user in [trainer_user, reception_user, member_user]:
            client = auth_client(api_client, user, gym_tenant.subdomain)
            resp = client.get("/api/gym/trainers/")
            assert resp.status_code == 403

        # Super Admin on gym subdomain or apex is denied
        client = auth_client(api_client, superadmin_user, gym_tenant.subdomain)
        resp = client.get("/api/gym/trainers/")
        assert resp.status_code == 403

    def test_update_trainer_capacity_allowed_for_owner_and_manager(
        self, api_client, gym_tenant, owner_user, manager_user, trainer_user
    ):
        trainer = Trainer.all_objects.get(user=trainer_user)
        for user, new_cap in [(owner_user, 25), (manager_user, 30)]:
            client = auth_client(api_client, user, gym_tenant.subdomain)
            resp = client.patch(
                f"/api/gym/trainers/{trainer.id}/",
                {"max_clients": new_cap},
                format="json",
            )
            assert resp.status_code == 200
            assert resp.data["trainer"]["max_clients"] == new_cap

    def test_update_trainer_capacity_denied_for_other_roles(
        self,
        api_client,
        gym_tenant,
        trainer_user,
        reception_user,
        member_user,
        superadmin_user,
    ):
        trainer = Trainer.all_objects.get(user=trainer_user)
        for user in [trainer_user, reception_user, member_user]:
            client = auth_client(api_client, user, gym_tenant.subdomain)
            resp = client.patch(
                f"/api/gym/trainers/{trainer.id}/",
                {"max_clients": 50},
                format="json",
            )
            assert resp.status_code == 403

        client = auth_client(api_client, superadmin_user, gym_tenant.subdomain)
        resp = client.patch(
            f"/api/gym/trainers/{trainer.id}/",
            {"max_clients": 50},
            format="json",
        )
        assert resp.status_code == 403

    def test_trainer_me_allowed_for_trainer_denied_for_others(
        self,
        api_client,
        gym_tenant,
        trainer_user,
        owner_user,
        manager_user,
        reception_user,
        member_user,
        superadmin_user,
    ):
        client = auth_client(api_client, trainer_user, gym_tenant.subdomain)
        resp = client.get("/api/trainers/me/")
        assert resp.status_code == 200
        assert resp.data["user"]["email"] == trainer_user.email
        assert resp.data["max_clients"] == 20

        for user in [owner_user, manager_user, reception_user, member_user]:
            client = auth_client(api_client, user, gym_tenant.subdomain)
            resp = client.get("/api/trainers/me/")
            assert resp.status_code == 403

        client = auth_client(api_client, superadmin_user, gym_tenant.subdomain)
        resp = client.get("/api/trainers/me/")
        assert resp.status_code == 403


@pytest.mark.django_db
class TestTrainerModuleServerGating:
    """Verifies that gym without has_trainer_module gets 403 on all trainer endpoints."""

    def test_endpoints_refused_when_trainer_module_disabled(
        self, api_client, gym_tenant, owner_user, trainer_user
    ):
        gym_tenant.config.has_trainer_module = False
        gym_tenant.config.save()

        client = auth_client(api_client, owner_user, gym_tenant.subdomain)
        resp = client.get("/api/gym/trainers/")
        assert resp.status_code == 403
        assert "Trainer module is not enabled for this gym." in str(resp.data)

        trainer = Trainer.all_objects.get(user=trainer_user)
        resp_patch = client.patch(
            f"/api/gym/trainers/{trainer.id}/", {"max_clients": 15}, format="json"
        )
        assert resp_patch.status_code == 403

        client_trainer = auth_client(api_client, trainer_user, gym_tenant.subdomain)
        resp_me = client_trainer.get("/api/trainers/me/")
        assert resp_me.status_code == 403


@pytest.mark.django_db
class TestTrainerCapacityUpdatesAndValidation:
    """Verifies server-side validation, warnings on lowering below client count, and audit logging."""

    def test_capacity_validation_bounds(
        self, api_client, gym_tenant, owner_user, trainer_user
    ):
        trainer = Trainer.all_objects.get(user=trainer_user)
        client = auth_client(api_client, owner_user, gym_tenant.subdomain)

        # 0 is rejected
        resp_zero = client.patch(
            f"/api/gym/trainers/{trainer.id}/", {"max_clients": 0}, format="json"
        )
        assert resp_zero.status_code == 400

        # > 200 is rejected
        resp_over = client.patch(
            f"/api/gym/trainers/{trainer.id}/", {"max_clients": 201}, format="json"
        )
        assert resp_over.status_code == 400

        # Non-integer is rejected
        resp_str = client.patch(
            f"/api/gym/trainers/{trainer.id}/", {"max_clients": "twenty"}, format="json"
        )
        assert resp_str.status_code == 400

    def test_lowering_below_client_count_shows_warning_and_audit_logs(
        self, api_client, gym_tenant, owner_user, trainer_user, member_user
    ):
        trainer = Trainer.all_objects.get(user=trainer_user)
        member = Member.all_objects.get(user=member_user)

        # Create 2 active assignments
        member2_user = User.objects.create_user(
            email="member2@bolehub.com",
            password="Password123!",
            gym=gym_tenant,
            role=User.ROLE_MEMBER,
        )
        member2 = Member.all_objects.create(
            gym=gym_tenant,
            user=member2_user,
            full_name="Member Two",
            phone="+251911000002",
            waiver_accepted_at=timezone.now(),
            status=Member.STATUS_ACTIVE,
        )

        TrainerAssignment.all_objects.create(
            gym=gym_tenant, member=member, trainer=trainer
        )
        TrainerAssignment.all_objects.create(
            gym=gym_tenant, member=member2, trainer=trainer
        )

        assert trainer.client_count == 2

        client = auth_client(api_client, owner_user, gym_tenant.subdomain)
        # Lower capacity to 1 (below 2 active clients)
        resp = client.patch(
            f"/api/gym/trainers/{trainer.id}/",
            {"max_clients": 1},
            format="json",
        )
        assert resp.status_code == 200
        assert resp.data["trainer"]["max_clients"] == 1
        assert resp.data["warning"] is not None
        assert "below the current active client count of 2" in resp.data["warning"]

        # Audit log verification
        log = AuditLog.all_objects.filter(
            action_type="trainer_capacity_updated",
            affected_record_id=str(trainer.id),
        ).first()
        assert log is not None
        assert log.actor == owner_user
        assert log.gym == gym_tenant
        assert log.metadata["old_max_clients"] == 20
        assert log.metadata["new_max_clients"] == 1
        assert log.metadata["current_client_count"] == 2


@pytest.mark.django_db
class TestTrainerTenancyIsolation:
    """Verifies that trainers cannot be accessed or updated across gym tenants."""

    def test_owner_cannot_access_or_edit_trainer_of_another_gym(
        self, api_client, gym_tenant, other_gym_tenant, owner_user, other_trainer_user
    ):
        other_trainer = Trainer.all_objects.get(user=other_trainer_user)
        client = auth_client(api_client, owner_user, gym_tenant.subdomain)

        # Detail on other gym trainer returns 404
        resp_get = client.get(f"/api/gym/trainers/{other_trainer.id}/")
        assert resp_get.status_code == 404

        resp_patch = client.patch(
            f"/api/gym/trainers/{other_trainer.id}/",
            {"max_clients": 10},
            format="json",
        )
        assert resp_patch.status_code == 404

        # List only returns own gym trainers
        resp_list = client.get("/api/gym/trainers/")
        assert resp_list.status_code == 200
        ids = [t["id"] for t in resp_list.data]
        assert str(other_trainer.id) not in ids
