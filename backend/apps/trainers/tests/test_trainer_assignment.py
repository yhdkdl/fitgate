import secrets
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import AuditLog, Notification, User
from apps.accounts.services import deactivate_staff_member
from apps.accounts.tokens import get_tokens_for_user
from apps.memberships.models import Member, MembershipPlan, MemberSubscription
from apps.payments.models import Payment
from apps.payments.services import record_cash_payment
from apps.tenants.models import GymConfig, GymTenant
from apps.trainers.models import Trainer, TrainerAssignment
from apps.trainers.services import (
    auto_assign_trainer_for_subscription,
    reassign_trainer,
)


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
        defaults={"has_trainer_module": True},
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
        defaults={"has_trainer_module": True},
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


def make_member(gym: GymTenant, email: str, name: str) -> Member:
    u = User.objects.create_user(
        email=email,
        password="MemberPassword123!",
        gym=gym,
        role=User.ROLE_MEMBER,
    )
    phone_suffix = secrets.randbelow(8999999) + 1000000
    return Member.all_objects.create(
        gym=gym,
        user=u,
        full_name=name,
        phone=f"+25191{phone_suffix}",
        waiver_accepted_at=timezone.now(),
        status=Member.STATUS_ACTIVE,
    )


def make_trainer(
    gym: GymTenant, email: str, name: str, max_clients: int = 5
) -> Trainer:
    u = User.objects.create_user(
        email=email,
        password="TrainerPassword123!",
        gym=gym,
        role=User.ROLE_TRAINER,
        full_name=name,
    )
    trainer = Trainer.all_objects.get(user=u)
    trainer.max_clients = max_clients
    trainer.save()
    return trainer


@pytest.mark.django_db
class TestAutomaticAssignmentRules:
    """
    Tests tie-break, capacity rules, and renewal preservation on a seeded scenario:
    - Lowest client count wins.
    - Tie-break: oldest last assignment wins.
    - Trainer at capacity is never chosen.
    - If all at capacity, no assignment is made and Owner/Manager are notified.
    - A member already assigned keeps trainer on renewal.
    """

    def test_seeded_tie_break_and_capacity_selection(
        self, gym_tenant, owner_user, manager_user
    ):
        now = timezone.now()

        # Seed 3 trainers
        trainer_a = make_trainer(
            gym_tenant, "trainer_a@bolehub.com", "Trainer A", max_clients=5
        )
        trainer_b = make_trainer(
            gym_tenant, "trainer_b@bolehub.com", "Trainer B", max_clients=5
        )
        trainer_c = make_trainer(
            gym_tenant, "trainer_c@bolehub.com", "Trainer C", max_clients=2
        )

        # Seed existing assignments:
        # Trainer A: 2 clients, last assigned 2 days ago
        m1 = make_member(gym_tenant, "m1@bolehub.com", "Member 1")
        m2 = make_member(gym_tenant, "m2@bolehub.com", "Member 2")
        TrainerAssignment.all_objects.create(
            gym=gym_tenant,
            member=m1,
            trainer=trainer_a,
            assigned_at=now - timedelta(days=3),
        )
        TrainerAssignment.all_objects.create(
            gym=gym_tenant,
            member=m2,
            trainer=trainer_a,
            assigned_at=now - timedelta(days=2),
        )

        # Trainer B: 1 client, last assigned 1 day ago
        m3 = make_member(gym_tenant, "m3@bolehub.com", "Member 3")
        TrainerAssignment.all_objects.create(
            gym=gym_tenant,
            member=m3,
            trainer=trainer_b,
            assigned_at=now - timedelta(days=1),
        )

        # Trainer C: 2 clients (at capacity: 2/2)
        m4 = make_member(gym_tenant, "m4@bolehub.com", "Member 4")
        m5 = make_member(gym_tenant, "m5@bolehub.com", "Member 5")
        TrainerAssignment.all_objects.create(
            gym=gym_tenant,
            member=m4,
            trainer=trainer_c,
            assigned_at=now - timedelta(days=4),
        )
        TrainerAssignment.all_objects.create(
            gym=gym_tenant,
            member=m5,
            trainer=trainer_c,
            assigned_at=now - timedelta(days=4),
        )

        assert trainer_a.client_count == 2
        assert trainer_b.client_count == 1
        assert trainer_c.client_count == 2

        plan = MembershipPlan.all_objects.create(
            gym=gym_tenant,
            name="Trainer Inclusive Plan",
            duration_value=1,
            duration_unit="months",
            price_etb=1500,
            trainer_inclusive=True,
            is_active=True,
        )

        # 1. New Member 6 activates: Trainer B has lowest client count (1 < 2) -> Wins!
        m6 = make_member(gym_tenant, "m6@bolehub.com", "Member 6")
        sub6 = MemberSubscription.all_objects.create(
            gym=gym_tenant,
            member=m6,
            plan=plan,
            start_date=timezone.localdate(),
            end_date=timezone.localdate() + timedelta(days=30),
            status=MemberSubscription.STATUS_ACTIVE,
        )
        assign6 = auto_assign_trainer_for_subscription(sub6)
        assert assign6 is not None
        assert assign6.trainer_id == trainer_b.id

        # 2. Now Trainer A (2 clients, last assigned 2 days ago) and Trainer B (2 clients, last assigned now) are tied on count.
        # Trainer A has the oldest last assignment (2 days ago vs now) -> Trainer A wins!
        assert trainer_a.client_count == 2
        assert trainer_b.client_count == 2

        m7 = make_member(gym_tenant, "m7@bolehub.com", "Member 7")
        sub7 = MemberSubscription.all_objects.create(
            gym=gym_tenant,
            member=m7,
            plan=plan,
            start_date=timezone.localdate(),
            end_date=timezone.localdate() + timedelta(days=30),
            status=MemberSubscription.STATUS_ACTIVE,
        )
        assign7 = auto_assign_trainer_for_subscription(sub7)
        assert assign7 is not None
        assert assign7.trainer_id == trainer_a.id

        # 3. Trainer C at capacity (2/2) was never chosen in either assignment
        assert trainer_c.client_count == 2

        # 4. Renewal keeps existing assignment
        sub7_renewal = MemberSubscription.all_objects.create(
            gym=gym_tenant,
            member=m7,
            plan=plan,
            start_date=timezone.localdate() + timedelta(days=31),
            end_date=timezone.localdate() + timedelta(days=60),
            status=MemberSubscription.STATUS_ACTIVE,
        )
        assign7_renew = auto_assign_trainer_for_subscription(sub7_renewal)
        assert assign7_renew.id == assign7.id
        assert assign7_renew.trainer_id == trainer_a.id

        # 5. When all trainers reach capacity, no assignment is made and Owner & Manager are notified
        trainer_a.max_clients = 3  # now at 3/3
        trainer_a.save()
        trainer_b.max_clients = 2  # now at 2/2
        trainer_b.save()
        # trainer_c is already 2/2

        m8 = make_member(gym_tenant, "m8@bolehub.com", "Member 8")
        sub8 = MemberSubscription.all_objects.create(
            gym=gym_tenant,
            member=m8,
            plan=plan,
            start_date=timezone.localdate(),
            end_date=timezone.localdate() + timedelta(days=30),
            status=MemberSubscription.STATUS_ACTIVE,
        )
        assign8 = auto_assign_trainer_for_subscription(sub8)
        assert assign8 is None
        assert not TrainerAssignment.all_objects.filter(
            member=m8, ended_at__isnull=True
        ).exists()

        # Check notification recorded for Owner and Manager
        notifs = Notification.all_objects.filter(
            gym=gym_tenant,
            type="trainer_capacity_exhausted",
            message__contains=str(m8.id),
        )
        assert notifs.count() >= 1


@pytest.mark.django_db
class TestDatabaseConcurrencyAndOpenAssignmentsConstraint:
    """Enforces that a member can never have two open assignments simultaneously at DB level."""

    def test_member_cannot_get_two_open_assignments(self, gym_tenant):
        trainer1 = make_trainer(gym_tenant, "t1_two@bolehub.com", "Trainer 1")
        trainer2 = make_trainer(gym_tenant, "t2_two@bolehub.com", "Trainer 2")
        member = make_member(gym_tenant, "mem_two@bolehub.com", "Member Open")

        # Open assignment 1
        TrainerAssignment.all_objects.create(
            gym=gym_tenant,
            member=member,
            trainer=trainer1,
            ended_at=None,
        )

        # Attempting second open assignment raises IntegrityError
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                TrainerAssignment.all_objects.create(
                    gym=gym_tenant,
                    member=member,
                    trainer=trainer2,
                    ended_at=None,
                )

        # However, creating a second assignment after closing the first succeeds cleanly
        assignment1 = TrainerAssignment.all_objects.get(
            member=member, ended_at__isnull=True
        )
        assignment1.ended_at = timezone.now()
        assignment1.save()

        assignment2 = TrainerAssignment.all_objects.create(
            gym=gym_tenant,
            member=member,
            trainer=trainer2,
            ended_at=None,
        )
        assert assignment2.id is not None


@pytest.mark.django_db
class TestManualReassignmentRestrictions:
    """Verifies tenancy, active trainer status, plan requirements, and capacity confirmation."""

    def test_trainer_in_another_gym_is_refused(
        self, gym_tenant, other_gym_tenant, owner_user
    ):
        member = make_member(gym_tenant, "m_cross@bolehub.com", "Cross Member")
        other_trainer = make_trainer(
            other_gym_tenant, "other_tr@kazanchis.com", "Other Trainer"
        )

        # Create active trainer plan
        plan = MembershipPlan.all_objects.create(
            gym=gym_tenant,
            name="Plan Cross",
            duration_value=1,
            duration_unit="months",
            price_etb=1000,
            trainer_inclusive=True,
            is_active=True,
        )
        MemberSubscription.all_objects.create(
            gym=gym_tenant,
            member=member,
            plan=plan,
            start_date=timezone.localdate(),
            end_date=timezone.localdate() + timedelta(days=30),
            status=MemberSubscription.STATUS_ACTIVE,
        )

        with pytest.raises(Exception) as exc_info:
            reassign_trainer(
                member=member,
                new_trainer=other_trainer,
                actor=owner_user,
            )
        assert "another gym" in str(exc_info.value)

    def test_over_capacity_reassignment_needs_confirmation(
        self, gym_tenant, owner_user
    ):
        trainer = make_trainer(
            gym_tenant, "full_tr@bolehub.com", "Full Trainer", max_clients=1
        )
        m1 = make_member(gym_tenant, "full_m1@bolehub.com", "Full M1")
        m2 = make_member(gym_tenant, "full_m2@bolehub.com", "Full M2")

        plan = MembershipPlan.all_objects.create(
            gym=gym_tenant,
            name="Plan Cap",
            duration_value=1,
            duration_unit="months",
            price_etb=1000,
            trainer_inclusive=True,
            is_active=True,
        )
        for m in [m1, m2]:
            MemberSubscription.all_objects.create(
                gym=gym_tenant,
                member=m,
                plan=plan,
                start_date=timezone.localdate(),
                end_date=timezone.localdate() + timedelta(days=30),
                status=MemberSubscription.STATUS_ACTIVE,
            )

        # m1 assigned to trainer -> trainer at 1/1 capacity
        TrainerAssignment.all_objects.create(gym=gym_tenant, member=m1, trainer=trainer)
        assert trainer.client_count == 1

        # Reassigning m2 to trainer without confirm_over_capacity is refused
        with pytest.raises(Exception) as exc_info:
            reassign_trainer(
                member=m2,
                new_trainer=trainer,
                actor=owner_user,
                confirm_over_capacity=False,
            )
        assert "requires_confirmation" in str(exc_info.value) or "capacity" in str(
            exc_info.value
        )

        # Reassigning with confirm_over_capacity=True succeeds and writes audit log
        assign = reassign_trainer(
            member=m2, new_trainer=trainer, actor=owner_user, confirm_over_capacity=True
        )
        assert assign is not None
        assert trainer.client_count == 2

        log = AuditLog.all_objects.filter(
            action_type="trainer_reassigned",
            affected_record_id=str(assign.id),
        ).first()
        assert log is not None
        assert log.metadata["confirmed_over_capacity"] is True


@pytest.mark.django_db
class TestAssignmentFailureDoesNotUndoPayment:
    """Verifies that if automatic assignment fails, the payment and subscription still stand."""

    def test_payment_and_subscription_succeed_when_assignment_fails(
        self, gym_tenant, owner_user
    ):
        member = make_member(gym_tenant, "mem_pay@bolehub.com", "Paying Member")
        plan = MembershipPlan.all_objects.create(
            gym=gym_tenant,
            name="VIP Trainer Plan",
            duration_value=1,
            duration_unit="months",
            price_etb=2000,
            trainer_inclusive=True,
            is_active=True,
        )

        # Mock auto_assign_trainer_for_subscription to simulate an unexpected crash
        with patch(
            "apps.trainers.services.auto_assign_trainer_for_subscription",
            side_effect=RuntimeError("Simulated assignment service crash"),
        ):
            payment, receipt, subscription = record_cash_payment(
                gym=gym_tenant,
                member=member,
                plan=plan,
                recorded_by=owner_user,
            )

        # Payment, Receipt, and Subscription must stand confirmed in the DB!
        assert payment.status == Payment.STATUS_CONFIRMED
        assert receipt.id is not None
        assert subscription.status == MemberSubscription.STATUS_ACTIVE
        assert member.status == Member.STATUS_ACTIVE


@pytest.mark.django_db
class TestDeactivateTrainerWithClientsGuard:
    """Verifies that deactivating a trainer with active clients is refused unless all clients are reassigned."""

    def test_deactivating_trainer_with_clients_refused_without_reassignments(
        self, gym_tenant, owner_user
    ):
        trainer1 = make_trainer(gym_tenant, "tr_deact1@bolehub.com", "Deact Trainer 1")
        trainer2 = make_trainer(gym_tenant, "tr_deact2@bolehub.com", "Deact Trainer 2")
        client_mem = make_member(
            gym_tenant, "client_deact@bolehub.com", "Client Member"
        )

        plan = MembershipPlan.all_objects.create(
            gym=gym_tenant,
            name="Deact Plan",
            duration_value=1,
            duration_unit="months",
            price_etb=1000,
            trainer_inclusive=True,
            is_active=True,
        )
        MemberSubscription.all_objects.create(
            gym=gym_tenant,
            member=client_mem,
            plan=plan,
            start_date=timezone.localdate(),
            end_date=timezone.localdate() + timedelta(days=30),
            status=MemberSubscription.STATUS_ACTIVE,
        )

        TrainerAssignment.all_objects.create(
            gym=gym_tenant, member=client_mem, trainer=trainer1
        )
        assert trainer1.client_count == 1

        # Deactivation refused without reassignments
        with pytest.raises(Exception) as exc_info:
            deactivate_staff_member(acting_user=owner_user, target_user=trainer1.user)
        assert "active client" in str(exc_info.value)

        # Deactivation succeeds when reassignment is provided
        deactivated = deactivate_staff_member(
            acting_user=owner_user,
            target_user=trainer1.user,
            reassignments_data={"reassign_to_trainer_id": str(trainer2.id)},
        )
        assert deactivated.is_active is False
        assert trainer1.client_count == 0
        assert trainer2.client_count == 1
        active_assignment = TrainerAssignment.all_objects.get(
            member=client_mem, ended_at__isnull=True
        )
        assert active_assignment.trainer_id == trainer2.id


@pytest.mark.django_db
class TestSprint17RBACPermissionMatrix:
    """Tests allowed and denied access for every role on the new endpoints."""

    def test_assignments_endpoints_rbac(
        self,
        api_client,
        gym_tenant,
        owner_user,
        manager_user,
        reception_user,
        superadmin_user,
    ):
        trainer_user = make_trainer(
            gym_tenant, "tr_rbac@bolehub.com", "RBAC Trainer"
        ).user
        member_user = make_member(gym_tenant, "m_rbac@bolehub.com", "RBAC Member").user

        # 1. GET /api/gym/assignments/ (Owner, Manager allowed; others denied)
        for user in [owner_user, manager_user]:
            client = auth_client(api_client, user, gym_tenant.subdomain)
            resp = client.get("/api/gym/assignments/")
            assert resp.status_code == 200

        for user in [trainer_user, reception_user, member_user, superadmin_user]:
            client = auth_client(api_client, user, gym_tenant.subdomain)
            resp = client.get("/api/gym/assignments/")
            assert resp.status_code in (401, 403)

        # 2. GET /api/gym/unassigned-members/ (Owner, Manager allowed; others denied)
        for user in [owner_user, manager_user]:
            client = auth_client(api_client, user, gym_tenant.subdomain)
            resp = client.get("/api/gym/unassigned-members/")
            assert resp.status_code == 200

        for user in [trainer_user, reception_user, member_user, superadmin_user]:
            client = auth_client(api_client, user, gym_tenant.subdomain)
            resp = client.get("/api/gym/unassigned-members/")
            assert resp.status_code in (401, 403)

        # 3. GET /api/trainers/me/clients/ (Trainer allowed; others denied)
        client = auth_client(api_client, trainer_user, gym_tenant.subdomain)
        resp = client.get("/api/trainers/me/clients/")
        assert resp.status_code == 200

        for user in [
            owner_user,
            manager_user,
            reception_user,
            member_user,
            superadmin_user,
        ]:
            client = auth_client(api_client, user, gym_tenant.subdomain)
            resp = client.get("/api/trainers/me/clients/")
            assert resp.status_code in (401, 403)
