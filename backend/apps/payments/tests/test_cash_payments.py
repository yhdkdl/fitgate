"""
Unit and integration tests for Sprint 12: Manual cash payments, digital receipts,
double-submit protection, payment history, and registration-to-payment flow.
"""

from decimal import Decimal

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, connection, transaction
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import AuditLog, Notification, User
from apps.accounts.services import get_tokens_for_user
from apps.memberships.models import Member, MembershipPlan, MemberSubscription
from apps.payments.models import Payment, Receipt
from apps.payments.services import record_cash_payment
from apps.tenants.models import GymTenant


@pytest.fixture
def gym_tenant(db):
    """Primary gym tenant for testing."""
    return GymTenant.objects.create(
        name="FitGate Bole Hub",
        subdomain="bole-hub",
        tls_confirmed_at=timezone.now(),
    )


@pytest.fixture
def owner_user(db, gym_tenant):
    return User.objects.create_user(
        email="owner_cash@bolehub.com",
        full_name="Bole Owner",
        role=User.ROLE_OWNER,
        gym=gym_tenant,
    )


@pytest.fixture
def manager_user(db, gym_tenant):
    return User.objects.create_user(
        email="manager_cash@bolehub.com",
        full_name="Bole Manager",
        role=User.ROLE_MANAGER,
        gym=gym_tenant,
    )


@pytest.fixture
def reception_user(db, gym_tenant):
    return User.objects.create_user(
        email="reception_cash@bolehub.com",
        full_name="Bole Reception",
        role=User.ROLE_RECEPTION,
        gym=gym_tenant,
    )


@pytest.fixture
def trainer_user(db, gym_tenant):
    return User.objects.create_user(
        email="trainer_cash@bolehub.com",
        full_name="Bole Trainer",
        role=User.ROLE_TRAINER,
        gym=gym_tenant,
    )


@pytest.fixture
def member_user(db, gym_tenant):
    u = User.objects.create_user(
        email="other_mem_cash@bolehub.com",
        full_name="Other Member",
        role=User.ROLE_MEMBER,
        gym=gym_tenant,
    )
    Member.all_objects.create(
        gym=gym_tenant,
        user=u,
        full_name="Other Member",
        phone="+251911888888",
        waiver_accepted_at=timezone.now(),
    )
    return u


@pytest.fixture
def super_admin_user(db):
    return User.objects.create_user(
        email="superadmin_cash@fitgate.com",
        full_name="FitGate Admin",
        role=User.ROLE_SUPER_ADMIN,
        gym=None,
        must_change_password=False,
    )


@pytest.fixture
def other_gym(db):
    """Secondary gym tenant for testing cross-gym isolation."""
    gym = GymTenant.objects.create(
        name="FitGate Kazanchis",
        subdomain="kazanchis",
        tls_confirmed_at=timezone.now(),
    )
    return gym


@pytest.fixture
def standard_plan(db, gym_tenant):
    """Active membership plan for bole hub."""
    return MembershipPlan.objects.create(
        gym=gym_tenant,
        name="Monthly Standard",
        duration_value=1,
        duration_unit="months",
        price_etb=Decimal("1800.00"),
        is_active=True,
    )


@pytest.fixture
def cash_member(db, gym_tenant):
    """Pending member awaiting payment."""
    user = User.objects.create_user(
        email="cash_tester@bolehub.com",
        full_name="Abebe Bikila",
        phone="+251911223344",
        role=User.ROLE_MEMBER,
        gym=gym_tenant,
    )
    member = Member.all_objects.create(
        gym=gym_tenant,
        user=user,
        full_name="Abebe Bikila",
        phone="+251911223344",
        waiver_accepted_at=timezone.now(),
    )
    return member


@pytest.mark.django_db
class TestRecordCashPaymentService:
    """Test the atomic record_cash_payment business service."""

    def test_cash_payment_creates_payment_receipt_and_activates_subscription_in_one_tx(
        self, gym_tenant, standard_plan, cash_member, reception_user
    ):
        """Cash payment, receipt, and subscription activation succeed atomically."""
        assert cash_member.status == Member.STATUS_PENDING

        payment, receipt, subscription = record_cash_payment(
            gym=gym_tenant,
            member=cash_member,
            plan=standard_plan,
            recorded_by=reception_user,
            notes="Paid in cash at front desk",
            idempotency_key="req-key-001",
        )

        # 1. Payment verified
        assert payment.gym_id == gym_tenant.id
        assert payment.member_id == cash_member.id
        assert payment.plan_id == standard_plan.id
        assert payment.subscription_id == subscription.id
        assert payment.method == Payment.METHOD_CASH
        assert payment.amount_etb == Decimal("1800.00")
        assert payment.status == Payment.STATUS_CONFIRMED
        assert payment.confirmed_by_id == reception_user.id
        assert payment.idempotency_key == "req-key-001"
        assert payment.metadata["notes"] == "Paid in cash at front desk"

        # 2. Receipt verified
        assert receipt is not None
        assert receipt.payment_id == payment.id
        assert receipt.gym_id == gym_tenant.id
        assert receipt.receipt_number == "REC-000001"
        assert receipt.sequence_number == 1
        assert receipt.amount_etb == Decimal("1800.00")
        assert receipt.payment_method == Payment.METHOD_CASH
        assert receipt.member_name == "Abebe Bikila"
        assert receipt.plan_name == "Monthly Standard"
        assert receipt.issued_by_id == reception_user.id
        assert receipt.notes == "Paid in cash at front desk"

        # 3. Subscription and derived member status verified
        assert subscription.status == MemberSubscription.STATUS_ACTIVE
        assert subscription.member_id == cash_member.id
        cash_member.refresh_from_db()
        assert cash_member.status == Member.STATUS_ACTIVE

        # 4. Audit log verified
        audit = AuditLog.all_objects.filter(
            gym=gym_tenant,
            action_type="cash_payment_confirmed",
            affected_record_id=str(payment.id),
        ).first()
        assert audit is not None
        assert audit.actor_id == reception_user.id
        assert audit.metadata["receipt_number"] == "REC-000001"

        # 5. Member notification verified
        notif = Notification.all_objects.filter(
            gym=gym_tenant,
            recipient=cash_member.user,
            type="payment_confirmed",
        ).first()
        assert notif is not None
        assert "REC-000001" in notif.message
        assert "1800.00 ETB" in notif.message

    def test_reception_owner_and_manager_can_record_cash(
        self,
        gym_tenant,
        standard_plan,
        cash_member,
        owner_user,
        manager_user,
        reception_user,
    ):
        """Owner, Manager, and Reception are authorized to confirm cash payments."""
        for idx, staff in enumerate(
            [owner_user, manager_user, reception_user], start=1
        ):
            payment, receipt, _ = record_cash_payment(
                gym=gym_tenant,
                member=cash_member,
                plan=standard_plan,
                recorded_by=staff,
                idempotency_key=f"staff-auth-test-{idx}",
            )
            assert payment.confirmed_by_id == staff.id
            assert receipt.issued_by_id == staff.id

    def test_trainers_members_and_super_admin_cannot_record_cash(
        self,
        gym_tenant,
        standard_plan,
        cash_member,
        trainer_user,
        member_user,
        super_admin_user,
    ):
        """Unauthorized roles raise PermissionDenied."""
        for unauthorized in [trainer_user, member_user, super_admin_user]:
            with pytest.raises(PermissionDenied):
                record_cash_payment(
                    gym=gym_tenant,
                    member=cash_member,
                    plan=standard_plan,
                    recorded_by=unauthorized,
                )

    def test_rejects_cross_gym_member(
        self, gym_tenant, other_gym, standard_plan, reception_user
    ):
        """Cannot record cash payment for member belonging to another gym."""
        other_user = User.objects.create_user(
            email="other_gym_mem@kazanchis.com",
            full_name="Other Member",
            role=User.ROLE_MEMBER,
            gym=other_gym,
        )
        other_member = Member.all_objects.create(
            gym=other_gym,
            user=other_user,
            full_name="Other Member",
            phone="+251922334455",
            waiver_accepted_at=timezone.now(),
        )

        with pytest.raises(ValidationError) as exc:
            record_cash_payment(
                gym=gym_tenant,
                member=other_member,
                plan=standard_plan,
                recorded_by=reception_user,
            )
        assert "Member does not belong to this gym" in str(exc.value)

    def test_rejects_cross_gym_plan(
        self, gym_tenant, other_gym, cash_member, reception_user
    ):
        """Cannot record cash payment with a plan from another gym."""
        other_plan = MembershipPlan.objects.create(
            gym=other_gym,
            name="Other Gym Plan",
            duration_value=1,
            duration_unit="months",
            price_etb=Decimal("2000.00"),
            is_active=True,
        )
        with pytest.raises(ValidationError) as exc:
            record_cash_payment(
                gym=gym_tenant,
                member=cash_member,
                plan=other_plan,
                recorded_by=reception_user,
            )
        assert "Plan does not belong to this gym" in str(exc.value)

    def test_rejects_deactivated_plan(
        self, gym_tenant, standard_plan, cash_member, reception_user
    ):
        """Deactivated plans cannot be used for new cash payment confirmations."""
        standard_plan.is_active = False
        standard_plan.save(update_fields=["is_active"])

        with pytest.raises(ValidationError) as exc:
            record_cash_payment(
                gym=gym_tenant,
                member=cash_member,
                plan=standard_plan,
                recorded_by=reception_user,
            )
        assert "deactivated plan" in str(exc.value)

    def test_plan_price_at_payment_moment_is_immutable(
        self, gym_tenant, standard_plan, cash_member, reception_user
    ):
        """Editing plan price later never changes recorded payment or receipt amount."""
        payment, receipt, _ = record_cash_payment(
            gym=gym_tenant,
            member=cash_member,
            plan=standard_plan,
            recorded_by=reception_user,
        )
        assert payment.amount_etb == Decimal("1800.00")
        assert receipt.amount_etb == Decimal("1800.00")

        # Now edit the plan price
        standard_plan.price_etb = Decimal("2500.00")
        standard_plan.save(update_fields=["price_etb"])

        payment.refresh_from_db()
        receipt.refresh_from_db()
        assert payment.amount_etb == Decimal("1800.00")
        assert receipt.amount_etb == Decimal("1800.00")


@pytest.mark.django_db
class TestDoubleSubmitGuard:
    """Test double-submit protection via idempotency key and database constraints."""

    def test_idempotent_submission_returns_existing_without_duplicate(
        self, gym_tenant, standard_plan, cash_member, reception_user
    ):
        """Repeated submission with identical idempotency key returns existing payment & receipt."""
        p1, r1, s1 = record_cash_payment(
            gym=gym_tenant,
            member=cash_member,
            plan=standard_plan,
            recorded_by=reception_user,
            idempotency_key="idemp-key-repeat-123",
        )

        p2, r2, s2 = record_cash_payment(
            gym=gym_tenant,
            member=cash_member,
            plan=standard_plan,
            recorded_by=reception_user,
            idempotency_key="idemp-key-repeat-123",
        )

        assert p1.id == p2.id
        assert r1.id == r2.id
        assert s1.id == s2.id
        assert (
            Payment.all_objects.filter(
                gym=gym_tenant, idempotency_key="idemp-key-repeat-123"
            ).count()
            == 1
        )
        assert Receipt.all_objects.filter(gym=gym_tenant).count() == 1

    def test_db_unique_constraint_enforces_idempotency_key_per_gym(
        self, gym_tenant, standard_plan, cash_member, reception_user
    ):
        """Direct DB insert with duplicate idempotency key raises IntegrityError."""
        Payment.all_objects.create(
            gym=gym_tenant,
            payer_type=Payment.PAYER_TYPE_MEMBER,
            member=cash_member,
            plan=standard_plan,
            method=Payment.METHOD_CASH,
            amount_etb=Decimal("1800.00"),
            status=Payment.STATUS_CONFIRMED,
            confirmed_by=reception_user,
            idempotency_key="duplicate-db-test-key",
        )

        with pytest.raises(IntegrityError):
            Payment.all_objects.create(
                gym=gym_tenant,
                payer_type=Payment.PAYER_TYPE_MEMBER,
                member=cash_member,
                plan=standard_plan,
                method=Payment.METHOD_CASH,
                amount_etb=Decimal("1800.00"),
                status=Payment.STATUS_CONFIRMED,
                confirmed_by=reception_user,
                idempotency_key="duplicate-db-test-key",
            )


@pytest.mark.django_db
class TestReceiptSequentialAndImmutability:
    """Test sequential numbering, tenant isolation, and strict immutability of digital receipts."""

    def test_receipt_numbers_are_sequential_and_unique_per_gym(
        self, gym_tenant, other_gym, standard_plan, cash_member, reception_user
    ):
        """Receipt numbers sequence starting at 1 per gym."""
        _, r1, _ = record_cash_payment(
            gym=gym_tenant,
            member=cash_member,
            plan=standard_plan,
            recorded_by=reception_user,
        )
        _, r2, _ = record_cash_payment(
            gym=gym_tenant,
            member=cash_member,
            plan=standard_plan,
            recorded_by=reception_user,
        )

        assert r1.receipt_number == "REC-000001"
        assert r1.sequence_number == 1
        assert r2.receipt_number == "REC-000002"
        assert r2.sequence_number == 2

        # In other gym, sequence also starts independently at 1
        other_staff = User.objects.create_user(
            email="rec_kaz@kazanchis.com",
            full_name="Kaz Reception",
            role=User.ROLE_RECEPTION,
            gym=other_gym,
        )
        other_plan = MembershipPlan.objects.create(
            gym=other_gym,
            name="Kaz Plan",
            duration_value=1,
            duration_unit="months",
            price_etb=Decimal("1500.00"),
            is_active=True,
        )
        other_mem_u = User.objects.create_user(
            email="kaz_member@kazanchis.com",
            full_name="Kaz Member",
            role=User.ROLE_MEMBER,
            gym=other_gym,
        )
        other_member = Member.all_objects.create(
            gym=other_gym,
            user=other_mem_u,
            full_name="Kaz Member",
            phone="+251933445566",
            waiver_accepted_at=timezone.now(),
        )

        _, other_r1, _ = record_cash_payment(
            gym=other_gym,
            member=other_member,
            plan=other_plan,
            recorded_by=other_staff,
        )
        assert other_r1.receipt_number == "REC-000001"
        assert other_r1.sequence_number == 1

    @pytest.mark.django_db(transaction=True)
    def test_receipt_counter_concurrency_no_duplicates_no_gaps(
        self, gym_tenant, standard_plan, reception_user
    ):
        """
        Receipt numbers generated under concurrency are sequential, unique, and gapless,
        using per-gym row-locked GymReceiptCounter inside the payment transaction.
        """
        import concurrent.futures

        u1 = User.objects.create_user(
            email="conc1@bolehub.com",
            full_name="Concurrent Member One",
            role=User.ROLE_MEMBER,
            gym=gym_tenant,
        )
        u2 = User.objects.create_user(
            email="conc2@bolehub.com",
            full_name="Concurrent Member Two",
            role=User.ROLE_MEMBER,
            gym=gym_tenant,
        )
        member1 = Member.all_objects.create(
            gym=gym_tenant,
            user=u1,
            full_name="Concurrent Member One",
            phone="+251911000001",
            status=Member.STATUS_PENDING,
            waiver_accepted_at=timezone.now(),
        )
        member2 = Member.all_objects.create(
            gym=gym_tenant,
            user=u2,
            full_name="Concurrent Member Two",
            phone="+251911000002",
            status=Member.STATUS_PENDING,
            waiver_accepted_at=timezone.now(),
        )

        def make_payment(member, key):
            connection.close()
            try:
                _, receipt, _ = record_cash_payment(
                    gym=gym_tenant,
                    member=member,
                    plan=standard_plan,
                    recorded_by=reception_user,
                    idempotency_key=key,
                )
                return receipt.receipt_number, receipt.sequence_number
            finally:
                connection.close()

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            fut1 = executor.submit(make_payment, member1, "conc-key-1")
            fut2 = executor.submit(make_payment, member2, "conc-key-2")
            res1 = fut1.result()
            res2 = fut2.result()

        receipt_numbers = {res1[0], res2[0]}
        sequence_numbers = {res1[1], res2[1]}

        assert len(receipt_numbers) == 2
        assert sequence_numbers == {1, 2}
        assert receipt_numbers == {"REC-000001", "REC-000002"}

    def test_receipt_cannot_be_updated_in_python(
        self, gym_tenant, standard_plan, cash_member, reception_user
    ):
        """Attempting to update an existing receipt raises ValidationError."""
        _, receipt, _ = record_cash_payment(
            gym=gym_tenant,
            member=cash_member,
            plan=standard_plan,
            recorded_by=reception_user,
        )
        receipt.notes = "Tampered notes"
        with pytest.raises(ValidationError) as exc:
            receipt.save()
        assert "immutable" in str(exc.value)

    def test_receipt_cannot_be_deleted_in_python(
        self, gym_tenant, standard_plan, cash_member, reception_user
    ):
        """Attempting to delete a receipt raises ValidationError."""
        _, receipt, _ = record_cash_payment(
            gym=gym_tenant,
            member=cash_member,
            plan=standard_plan,
            recorded_by=reception_user,
        )
        with pytest.raises(ValidationError) as exc:
            receipt.delete()
        assert "cannot be deleted" in str(exc.value)

    def test_receipt_cannot_be_updated_or_deleted_via_raw_sql(
        self, gym_tenant, standard_plan, cash_member, reception_user
    ):
        """PostgreSQL database triggers raise exception on UPDATE and DELETE."""
        _, receipt, _ = record_cash_payment(
            gym=gym_tenant,
            member=cash_member,
            plan=standard_plan,
            recorded_by=reception_user,
        )

        # UPDATE attempt
        with pytest.raises(Exception) as exc_update:
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute(
                        "UPDATE payments_receipt SET notes = 'tampered' WHERE id = %s",
                        [str(receipt.id)],
                    )
        assert "immutable" in str(exc_update.value).lower()

        # DELETE attempt
        with pytest.raises(Exception) as exc_delete:
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute(
                        "DELETE FROM payments_receipt WHERE id = %s",
                        [str(receipt.id)],
                    )
        assert "immutable" in str(exc_delete.value).lower()


@pytest.mark.django_db
class TestPaymentHistoryEndpoints:
    """Test staff and member payment history endpoints and receipts."""

    def test_member_payment_history_shows_dates_amounts_and_receipt_references(
        self, gym_tenant, standard_plan, cash_member, reception_user
    ):
        """Member can view their complete payment history with receipt references."""
        payment, receipt, sub = record_cash_payment(
            gym=gym_tenant,
            member=cash_member,
            plan=standard_plan,
            recorded_by=reception_user,
        )

        client = APIClient()
        tokens = get_tokens_for_user(cash_member.user)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

        resp = client.get(
            "/api/payments/history/", HTTP_HOST=f"{gym_tenant.subdomain}.localhost"
        )
        assert resp.status_code == 200
        data = resp.json()["results"]
        assert len(data) == 1
        item = data[0]
        assert item["id"] == str(payment.id)
        assert item["plan_name"] == "Monthly Standard"
        assert item["method"] == "cash"
        assert Decimal(str(item["amount_etb"])) == Decimal("1800.00")
        assert item["status"] == "confirmed"
        assert item["receipt_number"] == receipt.receipt_number
        assert item["subscription_start_date"] == str(sub.start_date)
        assert item["subscription_end_date"] == str(sub.end_date)

    def test_staff_payment_list_filters_and_revenue_summary(
        self, gym_tenant, standard_plan, cash_member, owner_user, reception_user
    ):
        """Owner and Manager review gym payments and revenue total."""
        p1, _, _ = record_cash_payment(
            gym=gym_tenant,
            member=cash_member,
            plan=standard_plan,
            recorded_by=reception_user,
        )

        client = APIClient()
        tokens = get_tokens_for_user(owner_user)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

        # 1. Full list
        resp = client.get(
            "/api/gym/payments/", HTTP_HOST=f"{gym_tenant.subdomain}.localhost"
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] == 1
        assert Decimal(body["total_confirmed_revenue_etb"]) == Decimal("1800.00")
        assert body["results"][0]["id"] == str(p1.id)
        assert body["results"][0]["confirmed_by_id"] == str(reception_user.id)

        # 2. Filter by method
        resp_cash = client.get(
            "/api/gym/payments/?method=cash",
            HTTP_HOST=f"{gym_tenant.subdomain}.localhost",
        )
        assert resp_cash.json()["count"] == 1

        resp_chapa = client.get(
            "/api/gym/payments/?method=chapa",
            HTTP_HOST=f"{gym_tenant.subdomain}.localhost",
        )
        assert resp_chapa.json()["count"] == 0

    def test_reception_cannot_view_gym_wide_payment_list(
        self, gym_tenant, reception_user
    ):
        """Receptionist is denied on the gym-wide payment history list (403)."""
        client = APIClient()
        tokens = get_tokens_for_user(reception_user)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

        resp = client.get(
            "/api/gym/payments/", HTTP_HOST=f"{gym_tenant.subdomain}.localhost"
        )
        assert resp.status_code == 403

    def test_receipt_detail_endpoint_access(
        self, gym_tenant, standard_plan, cash_member, reception_user, trainer_user
    ):
        """Staff and paying member can view receipt; trainer and unrelated member cannot."""
        _, receipt, _ = record_cash_payment(
            gym=gym_tenant,
            member=cash_member,
            plan=standard_plan,
            recorded_by=reception_user,
        )

        url = f"/api/gym/receipts/{receipt.id}/"
        host = f"{gym_tenant.subdomain}.localhost"

        # 1. Reception: allowed (200)
        rec_client = APIClient()
        rec_tokens = get_tokens_for_user(reception_user)
        rec_client.credentials(HTTP_AUTHORIZATION=f"Bearer {rec_tokens['access']}")
        assert rec_client.get(url, HTTP_HOST=host).status_code == 200

        # 2. Member who paid: allowed (200)
        mem_client = APIClient()
        mem_tokens = get_tokens_for_user(cash_member.user)
        mem_client.credentials(HTTP_AUTHORIZATION=f"Bearer {mem_tokens['access']}")
        resp_mem = mem_client.get(url, HTTP_HOST=host)
        assert resp_mem.status_code == 200
        assert resp_mem.json()["receipt_number"] == "REC-000001"

        # 3. Trainer: denied (403)
        tr_client = APIClient()
        tr_tokens = get_tokens_for_user(trainer_user)
        tr_client.credentials(HTTP_AUTHORIZATION=f"Bearer {tr_tokens['access']}")
        assert tr_client.get(url, HTTP_HOST=host).status_code == 403

    def test_idempotency_key_double_submit_and_mismatch_rejection(
        self, gym_tenant, standard_plan, cash_member, reception_user
    ):
        """
        Double submit with the same idempotency key returns the original result (same receipt).
        Same key with a different member or plan is rejected with 400.
        """
        client = APIClient()
        tokens = get_tokens_for_user(reception_user)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        host = f"{gym_tenant.subdomain}.localhost"

        key = "idemp-test-cash-001"
        payload = {
            "member_id": str(cash_member.id),
            "plan_id": str(standard_plan.id),
            "notes": "First submission",
            "idempotency_key": key,
        }

        # 1. First submission succeeds and creates receipt
        resp1 = client.post(
            "/api/gym/payments/cash/", payload, format="json", HTTP_HOST=host
        )
        assert resp1.status_code == 201
        data1 = resp1.json()
        payment_id_1 = data1["payment_id"]
        receipt_no_1 = data1["receipt"]["receipt_number"]

        # 2. Second submission with the exact same key returns original receipt
        resp2 = client.post(
            "/api/gym/payments/cash/", payload, format="json", HTTP_HOST=host
        )
        assert resp2.status_code == 201
        data2 = resp2.json()
        assert data2["payment_id"] == payment_id_1
        assert data2["receipt"]["receipt_number"] == receipt_no_1
        assert Receipt.all_objects.filter(gym=gym_tenant).count() == 1

        # 3. Submission with same key but different plan is rejected
        other_plan = MembershipPlan.objects.create(
            gym=gym_tenant,
            name="Alternative Plan",
            duration_value=3,
            duration_unit="months",
            price_etb=Decimal("4500.00"),
        )
        bad_payload = {
            "member_id": str(cash_member.id),
            "plan_id": str(other_plan.id),
            "notes": "Mismatch attempt",
            "idempotency_key": key,
        }
        resp3 = client.post(
            "/api/gym/payments/cash/", bad_payload, format="json", HTTP_HOST=host
        )
        assert resp3.status_code == 400
        assert "Idempotency key has already been used" in str(resp3.json())

    def test_super_admin_denied_on_gym_payments_and_receipts(
        self, gym_tenant, standard_plan, cash_member, reception_user, super_admin_user
    ):
        """Super Admin must NOT reach any gym's member payments, receipts, or ledger."""
        _, receipt, _ = record_cash_payment(
            gym=gym_tenant,
            member=cash_member,
            plan=standard_plan,
            recorded_by=reception_user,
        )

        admin_client = APIClient()
        admin_tokens = get_tokens_for_user(super_admin_user)
        admin_client.credentials(HTTP_AUTHORIZATION=f"Bearer {admin_tokens['access']}")
        # Super Admin on apex domain (localhost) gets 403 Forbidden
        resp_list = admin_client.get(
            f"/api/gym/payments/?gym_id={gym_tenant.id}", HTTP_HOST="localhost"
        )
        assert resp_list.status_code == 403

        # Super Admin denied on receipt detail
        resp_rcpt = admin_client.get(
            f"/api/gym/receipts/{receipt.id}/", HTTP_HOST="localhost"
        )
        assert resp_rcpt.status_code == 403

        # Super Admin on tenant subdomain is also denied / unauthorized
        resp_sub = admin_client.get(
            "/api/gym/payments/", HTTP_HOST=f"{gym_tenant.subdomain}.localhost"
        )
        assert resp_sub.status_code in (401, 403)
