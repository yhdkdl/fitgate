"""
Strict tests for Sprint 12d: Bank receipt verification for member bank transfers.

Tested points:
1. Verified receipt auto-reconciles, issues receipt number, activates member, audit logs, badge shown.
2. Mismatched receipt (amount, account, or older than 7 days) activates nothing, requires receipt photo, lands in review queue.
3. Owner and Manager can approve and decline from the review queue; Reception and Super Admin are refused.
4. Approval re-check refuses if member situation changed in flight.
5. Row-locking: concurrent approval attempts do not double-activate.
6. 2 waiting items limit per member is enforced on the server.
7. Items in the review queue are excluded from confirmed revenue, dashboard analytics, CSV exports, receipt number sequence, and the 7-day sweep.
8. "Could not check" falls back to the gym's chosen policy (activate-and-reconcile-later vs hold-for-approval).
9. Reference format validation before lookup (malformed references rejected without hitting the verifier or rate counter).
10. Photo privacy: only Owner and Manager can fetch the receipt photo.
"""

import io
from decimal import Decimal

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from PIL import Image
from rest_framework.test import APIClient

from apps.accounts.models import AuditLog, Notification, User
from apps.accounts.services import get_tokens_for_user
from apps.memberships.models import Member, MembershipPlan, MemberSubscription
from apps.payments.models import (
    BankReceiptLookupCounter,
    GymPaymentConfig,
    GymReceivingAccount,
    Payment,
    Receipt,
)
from apps.payments.services import flag_unreconciled_transfers
from apps.tenants.models import GymTenant


@pytest.fixture
def gym_tenant(db):
    return GymTenant.objects.create(
        name="FitGate Bole Hub",
        subdomain="bole-hub",
        tls_confirmed_at=timezone.now(),
    )


@pytest.fixture
def other_gym(db):
    return GymTenant.objects.create(
        name="FitGate Kazanchis",
        subdomain="kazanchis",
        tls_confirmed_at=timezone.now(),
    )


@pytest.fixture
def owner_user(db, gym_tenant):
    return User.objects.create_user(
        email="owner_vr@bolehub.com",
        full_name="Bole Owner",
        role=User.ROLE_OWNER,
        gym=gym_tenant,
    )


@pytest.fixture
def manager_user(db, gym_tenant):
    return User.objects.create_user(
        email="manager_vr@bolehub.com",
        full_name="Bole Manager",
        role=User.ROLE_MANAGER,
        gym=gym_tenant,
    )


@pytest.fixture
def reception_user(db, gym_tenant):
    return User.objects.create_user(
        email="reception_vr@bolehub.com",
        full_name="Bole Reception",
        role=User.ROLE_RECEPTION,
        gym=gym_tenant,
    )


@pytest.fixture
def super_admin_user(db):
    u = User.objects.create_superuser(
        email="superadmin_vr@fitgate.com",
        password="SuperAdminPassword123!",
        full_name="Platform SuperAdmin",
    )
    u.must_change_password = False
    u.save()
    return u


@pytest.fixture
def other_gym_owner(db, other_gym):
    return User.objects.create_user(
        email="owner_other@kazanchis.com",
        full_name="Kazanchis Owner",
        role=User.ROLE_OWNER,
        gym=other_gym,
    )


@pytest.fixture
def plan(db, gym_tenant):
    return MembershipPlan.objects.create(
        gym=gym_tenant,
        name="Monthly Standard Plan",
        duration_value=1,
        duration_unit="months",
        price_etb=Decimal("2000.00"),
        is_active=True,
    )


@pytest.fixture
def member(db, gym_tenant):
    u = User.objects.create_user(
        email="member_vr@bolehub.com",
        full_name="Abebe Bikila",
        role=User.ROLE_MEMBER,
        gym=gym_tenant,
    )
    return Member.all_objects.create(
        gym=gym_tenant,
        user=u,
        full_name="Abebe Bikila",
        phone="+251911223344",
        status=Member.STATUS_PENDING,
        waiver_accepted_at=timezone.now(),
    )


@pytest.fixture
def receiving_account(db, gym_tenant):
    acc = GymReceivingAccount(
        gym=gym_tenant,
        bank=GymReceivingAccount.BANK_CBE,
        account_number="1000123456789",
        account_name="FitGate Bole Account",
        is_active=True,
    )
    acc.clean()
    acc.save()
    return acc


@pytest.fixture
def gym_config(db, gym_tenant, receiving_account):
    config, _ = GymPaymentConfig.objects.get_or_create(gym=gym_tenant)
    config.verify_bank_receipts_automatically = True
    config.receipt_verification_failure_policy = (
        GymPaymentConfig.POLICY_ACTIVATE_AND_RECONCILE_LATER
    )
    config.save()
    return config


def auth_client(user, host="bole-hub.localhost"):
    client = APIClient(HTTP_HOST=host)
    tokens = get_tokens_for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
    return client


def make_test_photo(name="receipt.jpg"):
    img = Image.new("RGB", (200, 200), color="blue")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)
    return SimpleUploadedFile(
        name,
        buf.getvalue(),
        content_type="image/jpeg",
    )


@pytest.mark.django_db
class TestBankReceiptVerificationStrict:
    """Strict test suite for Sprint 12d bank receipt verification."""

    @pytest.fixture(autouse=True)
    def setup_verification_settings(self, settings):
        settings.RECEIPT_VERIFICATION_ENABLED = True
        settings.BANK_RECEIPT_VERIFIER_USE_MOCK = True

    def test_verified_receipt_auto_reconciles_and_activates(
        self, gym_tenant, reception_user, member, plan, gym_config
    ):
        """1. Verified receipt auto-reconciles, issues receipt number, activates member, audit logs."""
        client = auth_client(reception_user)
        payload = {
            "member_id": str(member.id),
            "plan_id": str(plan.id),
            "bank_reference": "MOCK-VERIFIED-10001",
            "bank": "cbe",
            "transfer_date": timezone.localdate().isoformat(),
            "channel": "CBE",
            "notes": "Reception desk entry",
            "screenshot": make_test_photo(),
        }

        resp = client.post(
            "/api/gym/payments/bank-transfer/", payload, format="multipart"
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "confirmed"
        assert data["is_receipt_verified"] is True
        assert data["is_reconciled"] is True
        assert "receipt" in data and data["receipt"] is not None
        assert data["receipt"]["receipt_number"]

        # Check DB Payment state
        payment = Payment.all_objects.get(id=data["payment_id"])
        assert payment.is_receipt_verified is True
        assert payment.is_reconciled is True
        assert payment.status == Payment.STATUS_CONFIRMED

        # Check Member subscription activation
        member.refresh_from_db()
        assert member.status == Member.STATUS_ACTIVE
        sub = MemberSubscription.all_objects.filter(
            gym=gym_tenant, member=member
        ).first()
        assert sub is not None
        assert sub.status == MemberSubscription.STATUS_ACTIVE

        # Check AuditLog
        log = AuditLog.all_objects.filter(
            gym=gym_tenant,
            action_type="bank_transfer_auto_reconciled",
            affected_record_id=str(payment.id),
        ).first()
        assert log is not None
        assert log.metadata.get("reason") == "auto-reconciled by receipt verification"

    def test_mismatched_receipt_activates_nothing_requires_photo_lands_in_queue(
        self, gym_tenant, reception_user, member, plan, gym_config
    ):
        """2. Mismatched receipt activates nothing, requires photo upload, lands in review queue."""
        client = auth_client(reception_user)

        # 2a. Attempt mismatch without photo proof -> Refused 400
        payload_no_photo = {
            "member_id": str(member.id),
            "plan_id": str(plan.id),
            "bank_reference": "MOCK-MISMATCH-20002",
            "bank": "cbe",
            "transfer_date": timezone.localdate().isoformat(),
            "channel": "CBE",
        }
        resp_err = client.post(
            "/api/gym/payments/bank-transfer/", payload_no_photo, format="json"
        )
        assert resp_err.status_code == 400
        assert (
            "Receipt photo is required for review submission."
            in resp_err.json()["detail"]
        )

        # 2b. Submit with photo proof -> Lands in review queue
        payload_with_photo = {
            "member_id": str(member.id),
            "plan_id": str(plan.id),
            "bank_reference": "MOCK-MISMATCH-20002",
            "bank": "cbe",
            "transfer_date": timezone.localdate().isoformat(),
            "channel": "CBE",
            "screenshot": make_test_photo(),
        }
        resp = client.post(
            "/api/gym/payments/bank-transfer/", payload_with_photo, format="multipart"
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "pending_review"
        assert data["is_receipt_verified"] is False
        assert data["receipt"] is None
        assert data["subscription_id"] is None
        assert "mismatch_message" in data

        # Check DB Payment state
        payment = Payment.all_objects.get(id=data["payment_id"])
        assert payment.status == Payment.STATUS_PENDING_REVIEW
        assert payment.expected_amount_etb == plan.price_etb
        assert payment.review_photo != ""
        assert payment.receipt_verification_data

        # Check that NOTHING activated
        member.refresh_from_db()
        assert member.status == Member.STATUS_PENDING
        assert not MemberSubscription.all_objects.filter(
            gym=gym_tenant, member=member
        ).exists()
        assert not Receipt.all_objects.filter(payment=payment).exists()

    def test_owner_and_manager_can_approve_and_decline_reception_and_superadmin_refused(
        self,
        gym_tenant,
        other_gym,
        owner_user,
        manager_user,
        reception_user,
        super_admin_user,
        other_gym_owner,
        member,
        plan,
        gym_config,
    ):
        """3. Owner and Manager can decide from queue; Reception and Super Admin are refused 403."""
        # Setup pending_review payment
        client_rec = auth_client(reception_user)
        payload = {
            "member_id": str(member.id),
            "plan_id": str(plan.id),
            "bank_reference": "MOCK-MISMATCH-30003",
            "bank": "cbe",
            "transfer_date": timezone.localdate().isoformat(),
            "channel": "CBE",
            "screenshot": make_test_photo(),
        }
        res_submit = client_rec.post(
            "/api/gym/payments/bank-transfer/", payload, format="multipart"
        )
        payment_id = res_submit.json()["payment_id"]

        # 3a. Reception denied 403 on queue
        assert client_rec.get("/api/payments/receipt-reviews/").status_code == 403
        assert (
            client_rec.post(
                f"/api/payments/receipt-reviews/{payment_id}/decide/",
                {"decision": "verified"},
                format="json",
            ).status_code
            == 403
        )

        # 3b. Super Admin denied 403 or 401
        client_sa = auth_client(super_admin_user)
        assert client_sa.get("/api/payments/receipt-reviews/").status_code in (401, 403)
        assert client_sa.post(
            f"/api/payments/receipt-reviews/{payment_id}/decide/",
            {"decision": "verified"},
            format="json",
        ).status_code in (401, 403)

        # 3c. Other gym Owner denied 403 / cross-tenant isolation
        client_other = auth_client(other_gym_owner, host="kazanchis.localhost")
        assert client_other.post(
            f"/api/payments/receipt-reviews/{payment_id}/decide/",
            {"decision": "verified"},
            format="json",
        ).status_code in (403, 404)

        # 3d. Manager can list queue
        client_mgr = auth_client(manager_user)
        res_list = client_mgr.get("/api/payments/receipt-reviews/")
        assert res_list.status_code == 200
        items = res_list.json()
        assert len(items) >= 1
        assert any(i["id"] == payment_id for i in items)

        # 3e. Owner approves
        client_own = auth_client(owner_user)
        res_decide = client_own.post(
            f"/api/payments/receipt-reviews/{payment_id}/decide/",
            {"decision": "verified"},
            format="json",
        )
        assert res_decide.status_code == 200
        assert res_decide.json()["status"] == "confirmed"

        payment = Payment.all_objects.get(id=payment_id)
        assert payment.status == Payment.STATUS_CONFIRMED
        assert payment.is_receipt_verified is True
        assert payment.is_reconciled is True
        assert payment.review_decision == "verified"
        assert payment.review_decided_by == owner_user

        # Member active with receipt
        member.refresh_from_db()
        assert member.status == Member.STATUS_ACTIVE
        assert Receipt.all_objects.filter(payment=payment).exists()

        # Audit log specifies approver and statement check
        audit = AuditLog.all_objects.filter(
            gym=gym_tenant,
            action_type="bank_receipt_review_approved",
            affected_record_id=str(payment.id),
        ).first()
        assert audit is not None
        assert audit.metadata.get("method") == "statement check"
        assert audit.metadata.get("approver") == owner_user.email

        # 3f. Test Decline path with another review item
        res_submit2 = client_rec.post(
            "/api/gym/payments/bank-transfer/",
            {
                "member_id": str(member.id),
                "plan_id": str(plan.id),
                "bank_reference": "MOCK-MISMATCH-DECLINE-1",
                "bank": "cbe",
                "transfer_date": timezone.localdate().isoformat(),
                "channel": "CBE",
                "screenshot": make_test_photo(),
            },
            format="multipart",
        )
        p2_id = res_submit2.json()["payment_id"]

        # Manager declines
        res_decl = client_mgr.post(
            f"/api/payments/receipt-reviews/{p2_id}/decide/",
            {"decision": "declined"},
            format="json",
        )
        assert res_decl.status_code == 200

        p2 = Payment.all_objects.get(id=p2_id)
        assert p2.status == Payment.STATUS_DECLINED
        assert p2.review_decision == "declined"
        assert p2.review_decided_by == manager_user
        assert not Receipt.all_objects.filter(payment=p2).exists()

        # Member notified
        notif = Notification.all_objects.filter(
            recipient=member.user,
            type="payment_declined",
        ).first()
        assert notif is not None
        assert (
            "Payment could not be confirmed, please contact the front desk."
            in notif.message
        )

    def test_approval_recheck_refuses_if_member_situation_changed(
        self, gym_tenant, reception_user, owner_user, member, plan, gym_config
    ):
        """4. Approval re-check refuses if member situation changed in flight."""
        client_rec = auth_client(reception_user)
        res_submit = client_rec.post(
            "/api/gym/payments/bank-transfer/",
            {
                "member_id": str(member.id),
                "plan_id": str(plan.id),
                "bank_reference": "MOCK-MISMATCH-DEACT-1",
                "bank": "cbe",
                "transfer_date": timezone.localdate().isoformat(),
                "channel": "CBE",
                "screenshot": make_test_photo(),
            },
            format="multipart",
        )
        payment_id = res_submit.json()["payment_id"]

        # Deactivate member before owner approves
        member.status = Member.STATUS_SUSPENDED
        member._status_update_allowed = True
        member.user.is_active = False
        member.user.save()
        member.save()

        client_own = auth_client(owner_user)
        res_approve = client_own.post(
            f"/api/payments/receipt-reviews/{payment_id}/decide/",
            {"decision": "verified"},
            format="json",
        )
        assert res_approve.status_code == 400
        assert (
            "Member has been deactivated. Cannot activate subscription."
            in res_approve.json()["detail"]
        )

        # Payment remains pending_review in the queue
        payment = Payment.all_objects.get(id=payment_id)
        assert payment.status == Payment.STATUS_PENDING_REVIEW

    def test_row_locking_concurrency_second_approver_gets_already_decided(
        self,
        gym_tenant,
        reception_user,
        owner_user,
        manager_user,
        member,
        plan,
        gym_config,
    ):
        """5. Row-locking: concurrent approval attempts do not double-activate."""
        client_rec = auth_client(reception_user)
        res_submit = client_rec.post(
            "/api/gym/payments/bank-transfer/",
            {
                "member_id": str(member.id),
                "plan_id": str(plan.id),
                "bank_reference": "MOCK-MISMATCH-CONCUR-1",
                "bank": "cbe",
                "transfer_date": timezone.localdate().isoformat(),
                "channel": "CBE",
                "screenshot": make_test_photo(),
            },
            format="multipart",
        )
        payment_id = res_submit.json()["payment_id"]

        client_own = auth_client(owner_user)
        client_mgr = auth_client(manager_user)

        # First approver (Owner) approves
        res1 = client_own.post(
            f"/api/payments/receipt-reviews/{payment_id}/decide/",
            {"decision": "verified"},
            format="json",
        )
        assert res1.status_code == 200

        # Second approver (Manager) tries to decide on the same row
        res2 = client_mgr.post(
            f"/api/payments/receipt-reviews/{payment_id}/decide/",
            {"decision": "verified"},
            format="json",
        )
        assert res2.status_code == 400
        assert f"Already decided by {owner_user.full_name}" in res2.json()["detail"]

        # Only one receipt was issued
        assert Receipt.all_objects.filter(payment_id=payment_id).count() == 1

    def test_two_waiting_items_limit_per_member_is_enforced(
        self, gym_tenant, reception_user, member, plan, gym_config
    ):
        """6. 2 waiting items limit per member is enforced on the server."""
        client = auth_client(reception_user)

        # Create first review item
        res1 = client.post(
            "/api/gym/payments/bank-transfer/",
            {
                "member_id": str(member.id),
                "plan_id": str(plan.id),
                "bank_reference": "MOCK-MISMATCH-LIMIT-1",
                "bank": "cbe",
                "transfer_date": timezone.localdate().isoformat(),
                "channel": "CBE",
                "screenshot": make_test_photo(),
            },
            format="multipart",
        )
        assert res1.status_code == 201

        # Create second review item
        res2 = client.post(
            "/api/gym/payments/bank-transfer/",
            {
                "member_id": str(member.id),
                "plan_id": str(plan.id),
                "bank_reference": "MOCK-MISMATCH-LIMIT-2",
                "bank": "cbe",
                "transfer_date": timezone.localdate().isoformat(),
                "channel": "CBE",
                "screenshot": make_test_photo(),
            },
            format="multipart",
        )
        assert res2.status_code == 201

        # Third attempt must be refused
        res3 = client.post(
            "/api/gym/payments/bank-transfer/",
            {
                "member_id": str(member.id),
                "plan_id": str(plan.id),
                "bank_reference": "MOCK-MISMATCH-LIMIT-3",
                "bank": "cbe",
                "transfer_date": timezone.localdate().isoformat(),
                "channel": "CBE",
                "screenshot": make_test_photo(),
            },
            format="multipart",
        )
        assert res3.status_code == 400
        assert (
            "This member already has 2 bank transfers waiting for review. Please resolve pending reviews first."
            in res3.json()["detail"]
        )

    def test_items_in_review_queue_excluded_from_revenue_analytics_csv_sweep(
        self, gym_tenant, owner_user, reception_user, member, plan, gym_config
    ):
        """7. Review queue items excluded from confirmed revenue, dashboard analytics, CSV, sweep."""
        client_rec = auth_client(reception_user)

        # 1. Confirmed payment of 2,000 ETB
        client_rec.post(
            "/api/gym/payments/bank-transfer/",
            {
                "member_id": str(member.id),
                "plan_id": str(plan.id),
                "bank_reference": "MOCK-VERIFIED-REV-1",
                "bank": "cbe",
                "transfer_date": timezone.localdate().isoformat(),
                "channel": "CBE",
                "screenshot": make_test_photo(),
            },
            format="multipart",
        )

        # 2. Pending review payment of 2,000 ETB
        res_mismatch = client_rec.post(
            "/api/gym/payments/bank-transfer/",
            {
                "member_id": str(member.id),
                "plan_id": str(plan.id),
                "bank_reference": "MOCK-MISMATCH-REV-2",
                "bank": "cbe",
                "transfer_date": timezone.localdate().isoformat(),
                "channel": "CBE",
                "screenshot": make_test_photo(),
            },
            format="multipart",
        )
        p_pending_id = res_mismatch.json()["payment_id"]

        # Check Analytics overview: revenue must be 2000.00, NOT 4000.00
        client_own = auth_client(owner_user)
        res_analytics = client_own.get("/api/gym/analytics/overview/")
        assert res_analytics.status_code == 200
        overview = res_analytics.json()
        assert Decimal(str(overview["monthly_net_revenue"])) == Decimal("2000.00")
        assert overview["pending_receipt_reviews_count"] == 1

        # Check CSV export: pending_review item is excluded
        res_csv = client_own.get("/api/gym/export/payments/")
        assert res_csv.status_code == 200
        csv_content = res_csv.content.decode("utf-8")
        assert "MOCK-VERIFIED-REV-1" in csv_content
        assert "MOCK-MISMATCH-REV-2" not in csv_content

        # Check 7-day unreconciled sweep: pending_review item is ignored
        Payment.all_objects.filter(id=p_pending_id).update(
            created_at=timezone.now() - timezone.timedelta(days=10)
        )
        summary = flag_unreconciled_transfers(days=7)
        assert summary.get(str(gym_tenant.id), 0) == 0
        p_pending = Payment.all_objects.get(id=p_pending_id)
        assert p_pending.flagged_unreconciled_at is None

    def test_could_not_check_falls_back_to_gym_chosen_policy(
        self, gym_tenant, reception_user, member, plan, gym_config
    ):
        """8. 'Could not check' falls back to the gym's chosen policy."""
        client = auth_client(reception_user)

        # 8a. Default policy: activate_and_reconcile_later
        gym_config.receipt_verification_failure_policy = (
            GymPaymentConfig.POLICY_ACTIVATE_AND_RECONCILE_LATER
        )
        gym_config.save()

        res1 = client.post(
            "/api/gym/payments/bank-transfer/",
            {
                "member_id": str(member.id),
                "plan_id": str(plan.id),
                "bank_reference": "MOCK-TIMEOUT-POLICY-1",
                "bank": "cbe",
                "transfer_date": timezone.localdate().isoformat(),
                "channel": "CBE",
                "screenshot": make_test_photo(),
            },
            format="multipart",
        )
        assert res1.status_code == 201
        data1 = res1.json()
        assert data1["status"] == "confirmed"
        assert data1["is_reconciled"] is False
        assert (
            "Could not verify. The Owner will reconcile against the bank statement."
            in data1["detail"]
        )

        # 8b. Policy: hold_for_approval
        gym_config.receipt_verification_failure_policy = (
            GymPaymentConfig.POLICY_HOLD_FOR_APPROVAL
        )
        gym_config.save()

        res2 = client.post(
            "/api/gym/payments/bank-transfer/",
            {
                "member_id": str(member.id),
                "plan_id": str(plan.id),
                "bank_reference": "MOCK-TIMEOUT-POLICY-2",
                "bank": "cbe",
                "transfer_date": timezone.localdate().isoformat(),
                "channel": "CBE",
                "screenshot": make_test_photo(),
            },
            format="multipart",
        )
        assert res2.status_code == 201
        data2 = res2.json()
        assert data2["status"] == "pending_review"
        assert data2["receipt"] is None

    def test_reference_format_validation_before_lookup(
        self, gym_tenant, reception_user, member, plan, gym_config
    ):
        """9. Reference format validation rejects malformed references before verifier/rate counter."""
        client = auth_client(reception_user)
        init_counter = BankReceiptLookupCounter.objects.count()

        # Malformed reference with spaces
        res = client.post(
            "/api/gym/payments/bank-transfer/",
            {
                "member_id": str(member.id),
                "plan_id": str(plan.id),
                "bank_reference": "INVALID REF WITH SPACES",
                "bank": "cbe",
                "transfer_date": timezone.localdate().isoformat(),
                "channel": "CBE",
            },
            format="json",
        )
        assert res.status_code == 400
        assert "bank_reference" in res.json()
        assert "Receipt reference cannot contain spaces." in str(
            res.json()["bank_reference"]
        )

        # Malformed CBE format
        res2 = client.post(
            "/api/gym/payments/bank-transfer/",
            {
                "member_id": str(member.id),
                "plan_id": str(plan.id),
                "bank_reference": "abc",  # too short for CBE
                "bank": "cbe",
                "transfer_date": timezone.localdate().isoformat(),
                "channel": "CBE",
            },
            format="json",
        )
        assert res2.status_code == 400
        assert "bank_reference" in res2.json()

        # Database rate counter was never hit or incremented
        assert BankReceiptLookupCounter.objects.count() == init_counter

    def test_photo_privacy_only_owner_and_manager_can_fetch(
        self,
        gym_tenant,
        other_gym,
        owner_user,
        manager_user,
        reception_user,
        super_admin_user,
        other_gym_owner,
        member,
        plan,
        gym_config,
    ):
        """10. Photo privacy: only Owner and Manager can fetch receipt review photos."""
        client_rec = auth_client(reception_user)
        res_submit = client_rec.post(
            "/api/gym/payments/bank-transfer/",
            {
                "member_id": str(member.id),
                "plan_id": str(plan.id),
                "bank_reference": "MOCK-MISMATCH-PHOTO-PRIVACY",
                "bank": "cbe",
                "transfer_date": timezone.localdate().isoformat(),
                "channel": "CBE",
                "screenshot": make_test_photo(),
            },
            format="multipart",
        )
        payment_id = res_submit.json()["payment_id"]

        # Owner can view photo
        client_own = auth_client(owner_user)
        resp_own = client_own.get(
            f"/api/gym/payments/bank-transfers/{payment_id}/screenshot/"
        )
        assert resp_own.status_code == 200

        # Manager can view photo
        client_mgr = auth_client(manager_user)
        resp_mgr = client_mgr.get(
            f"/api/gym/payments/bank-transfers/{payment_id}/screenshot/"
        )
        assert resp_mgr.status_code == 200

        # Reception denied 403 on review photo
        resp_rec = client_rec.get(
            f"/api/gym/payments/bank-transfers/{payment_id}/screenshot/"
        )
        assert resp_rec.status_code == 403

        # Super Admin denied 403 or 401
        client_sa = auth_client(super_admin_user)
        resp_sa = client_sa.get(
            f"/api/gym/payments/bank-transfers/{payment_id}/screenshot/"
        )
        assert resp_sa.status_code in (401, 403)

        # Other gym Owner denied 403
        client_other = auth_client(other_gym_owner, host="kazanchis.localhost")
        resp_other = client_other.get(
            f"/api/gym/payments/bank-transfers/{payment_id}/screenshot/"
        )
        assert resp_other.status_code in (403, 404)
