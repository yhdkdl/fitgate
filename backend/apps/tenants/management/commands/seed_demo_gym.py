"""Management command to seed a rich, realistic demo gym on the 'demo' subdomain.

Sprint 37a (Demo Gym):
- Reset via Archive-and-Recreate:
  - Preserves immutable financial, receipt, and audit rows.
  - Archives previous demo gym subdomain to 'demo-archive-N', renames users' emails
    to '.archived.N', marks status as 'terminated' and 'is_demo=True'.
  - Carries over 'tls_confirmed_at' so the new demo gym bypasses certificate safeguard.
  - Non-demo gyms are never touched.
- Execution Guards:
  - Refuses to run unless ALLOW_DEMO_SEED=True is set.
  - Only the exact subdomain 'demo' may bypass reserved name checks.
- Zero Outbound Calls:
  - No email (Brevo), Telegram, Chapa, bank, or AI calls.
- Rich Dataset:
  - 90 members across active, frozen, expired, pending, expiring soon, queued, and upgraded states.
  - Equipment with prices and total investment.
  - Group classes with bookings and attendance.
  - Expenses and financial report data with voided entries.
  - Bank transfers including one in pending review queue.
  - Trainers with client assignments, fitness profiles, body metrics, and approved AI plans.
  - Pre-created role accounts at @demo.local with DEMO_PASSWORD.
"""

import logging
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.attendance.models import Attendance
from apps.classes.constants import (
    BOOKING_STATUS_BOOKED,
    CLASS_TITLE_CROSSFIT,
    CLASS_TITLE_SPINNING,
    CLASS_TITLE_YOGA,
    SESSION_STATUS_SCHEDULED,
)
from apps.classes.models import ClassBooking, ClassSession
from apps.equipment.models import (
    CONDITION_GOOD,
    CONDITION_OUT_OF_SERVICE,
    Equipment,
)
from apps.memberships.models import (
    BodyMetrics,
    Member,
    MemberFreeze,
    MembershipPlan,
    MemberSubscription,
)
from apps.memberships.services import update_member_status
from apps.payments.models import (
    Expense,
    GymPaymentConfig,
    GymReceiptCounter,
    Payment,
    Receipt,
)
from apps.tenants.models import (
    GymConfig,
    GymNotice,
    GymTenant,
)
from apps.trainers.models import (
    FitnessProfile,
    Trainer,
    TrainerAssignment,
    TrainingPlan,
)

logger = logging.getLogger(__name__)


FIRST_NAMES = [
    "Abebe",
    "Almaz",
    "Bereket",
    "Blen",
    "Chala",
    "Danait",
    "Dawit",
    "Desta",
    "Eden",
    "Ermias",
    "Eyob",
    "Fasika",
    "Fikadu",
    "Frehiwot",
    "Genet",
    "Getachew",
    "Girma",
    "Hanan",
    "Helen",
    "Henok",
    "Hiwot",
    "Ismael",
    "Jemila",
    "Kalkidan",
    "Kassahun",
    "Kidus",
    "Lensa",
    "Leul",
    "Liya",
    "Mahlet",
    "Meklit",
    "Meron",
    "Nardos",
    "Natnael",
    "Nebiyu",
    "Rahel",
    "Robel",
    "Ruth",
    "Samuel",
    "Selamawit",
    "Senait",
    "Solomon",
    "Tariku",
    "Tigist",
    "Tsedey",
    "Yared",
    "Yohannes",
    "Yonas",
    "Zelalem",
    "Aster",
]

LAST_NAMES = [
    "Tesfaye",
    "Haile",
    "Kebede",
    "Alemu",
    "Tadesse",
    "Bekele",
    "Desta",
    "Mekonnen",
    "Worku",
    "Girma",
    "Assefa",
    "Kassa",
    "Negash",
    "Berhanu",
    "Mengistu",
    "Abebe",
    "Wolde",
    "Tekle",
    "Fikre",
    "Ayuele",
    "Gedamu",
    "Getahun",
    "Lemma",
    "Mulugeta",
    "Tefera",
    "Zewde",
    "Bayu",
    "Demissie",
    "Eshatu",
    "Gebre",
]


class Command(BaseCommand):
    help = "Seed a comprehensive, realistic demo gym on the 'demo' subdomain using archive-and-recreate."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Bypass interactive confirmation if running non-interactively.",
        )

    def handle(self, *args, **options):
        # 1. Execution guard: check ALLOW_DEMO_SEED
        allow_demo_seed = getattr(settings, "ALLOW_DEMO_SEED", False)
        if not allow_demo_seed:
            raise CommandError(
                "ALLOW_DEMO_SEED environment variable must be set to True to run demo seeding. "
                "Aborting to protect production data."
            )

        demo_password = getattr(settings, "DEMO_PASSWORD", "FitGateDemo2026!")
        hashed_demo_pw = make_password(demo_password)

        self.stdout.write(
            self.style.NOTICE("Starting FitGate Demo Gym seeding process...")
        )

        today = timezone.localdate()
        now = timezone.now()

        with transaction.atomic():
            # 2. Archive existing demo gym if present (Reset = Archive and Recreate)
            existing_demo = GymTenant.objects.filter(subdomain="demo").first()
            carried_tls = now
            if existing_demo:
                # Count existing archives to compute suffix N
                archive_count = (
                    GymTenant.objects.filter(
                        subdomain__startswith="demo-archive-"
                    ).count()
                    + 1
                )
                archive_subdomain = f"demo-archive-{archive_count}"
                self.stdout.write(
                    f"Archiving existing demo gym '{existing_demo.name}' to subdomain '{archive_subdomain}'..."
                )

                if existing_demo.tls_confirmed_at:
                    carried_tls = existing_demo.tls_confirmed_at

                existing_demo.subdomain = archive_subdomain
                existing_demo.status = GymTenant.STATUS_TERMINATED
                existing_demo.is_demo = True
                existing_demo.save(update_fields=["subdomain", "status", "is_demo"])

                # Rename all users of the archived gym to .archived.N
                archived_users = User.all_objects.filter(gym=existing_demo)
                for u in archived_users:
                    if not u.email.endswith(f".archived.{archive_count}"):
                        u.email = f"{u.email}.archived.{archive_count}"
                        u.save(update_fields=["email"])

                self.stdout.write(
                    self.style.SUCCESS(
                        f"Archived previous demo gym to '{archive_subdomain}' with status=terminated."
                    )
                )

            # 3. Create fresh demo gym
            self.stdout.write("Provisioning clean demo gym on subdomain 'demo'...")
            demo_gym = GymTenant.objects.create(
                name="FitGate Demo Gym",
                subdomain="demo",
                tier=GymTenant.TIER_GROWTH,
                status=GymTenant.STATUS_ACTIVE,
                is_demo=True,
                contact_phone="+251911000000",
                contact_email="owner@demo.local",
                location="Bole Atlas, Addis Ababa, Ethiopia",
                currency="ETB",
                tls_confirmed_at=carried_tls,
                subscription_expires_at=now
                + timedelta(days=365 * 4),  # Valid until ~2030
            )

            # 4. Configure GymConfig with Growth tier capabilities
            config, _ = GymConfig.objects.get_or_create(gym=demo_gym)
            config.has_trainer_module = True
            config.has_ai_plans = True
            config.has_analytics = True
            config.has_group_classes = True
            config.has_notices = True
            config.has_expenses = True
            config.has_multi_branch = False
            config.freeze_days_allowed = 30
            config.freeze_days_cap = 30
            config.payment_grace_days = 7
            config.subscription_reminder_days = [14, 7]
            config.member_reminder_days = [7, 2]
            config.brand_color = "#2563EB"
            config.is_equipment_list_complete = True
            config.show_unavailable_equipment = False
            config.telegram_channel = ""  # Zero live external calls
            config.disabled_roles = []
            config.save()

            # 5. Reset sequential receipt counter
            counter = GymReceiptCounter.all_objects.filter(gym=demo_gym).first()
            if not counter:
                counter = GymReceiptCounter.all_objects.create(gym=demo_gym)
            counter.last_receipt_number = 0
            counter.save(update_fields=["last_receipt_number"])

            # 6. Seed Gym Payment Config
            payment_cfg = GymPaymentConfig.all_objects.filter(gym=demo_gym).first()
            if not payment_cfg:
                GymPaymentConfig.all_objects.create(
                    gym=demo_gym,
                    is_verified=True,
                    is_enabled=True,
                    encrypted_public_key="mock_enc_demo_pub_key",
                    encrypted_secret_key="mock_enc_demo_sec_key",
                    encrypted_webhook_secret="mock_demo_webhook_secret",
                )

            # 7. Create staff accounts (@demo.local)
            staff_users = {}
            roles_spec = [
                ("owner", "owner@demo.local", "Abebe Bekele", User.ROLE_OWNER),
                ("manager", "manager@demo.local", "Hiwot Tadesse", User.ROLE_MANAGER),
                (
                    "reception",
                    "reception@demo.local",
                    "Selamawit Desta",
                    User.ROLE_RECEPTION,
                ),
                ("trainer1", "trainer1@demo.local", "Dawit Alemu", User.ROLE_TRAINER),
                ("trainer2", "trainer2@demo.local", "Tigist Haile", User.ROLE_TRAINER),
            ]

            for key, email, full_name, role in roles_spec:
                u = User.objects.create(
                    email=email,
                    password=hashed_demo_pw,
                    full_name=full_name,
                    role=role,
                    gym=demo_gym,
                    phone=f"+251911{len(staff_users):06d}",
                    is_active=True,
                    email_verified_at=now,
                    must_change_password=False,
                )
                staff_users[key] = u

            trainer1_obj = Trainer.all_objects.filter(
                gym=demo_gym, user=staff_users["trainer1"]
            ).first()
            if not trainer1_obj:
                trainer1_obj = Trainer.all_objects.create(
                    gym=demo_gym, user=staff_users["trainer1"], max_clients=30
                )
            else:
                trainer1_obj.max_clients = 30
                trainer1_obj.save(update_fields=["max_clients"])

            trainer2_obj = Trainer.all_objects.filter(
                gym=demo_gym, user=staff_users["trainer2"]
            ).first()
            if not trainer2_obj:
                trainer2_obj = Trainer.all_objects.create(
                    gym=demo_gym, user=staff_users["trainer2"], max_clients=25
                )
            else:
                trainer2_obj.max_clients = 25
                trainer2_obj.save(update_fields=["max_clients"])

            # 8. Seed one gym_subscription payment for platform revenue testing
            Payment.objects.create(
                gym=demo_gym,
                payer_type=Payment.PAYER_TYPE_GYM_SUBSCRIPTION,
                amount_etb=Decimal("30000.00"),
                gross_amount_etb=Decimal("30000.00"),
                method=Payment.METHOD_BANK_TRANSFER,
                status=Payment.STATUS_CONFIRMED,
                bank_reference="DEMO-GYM-SUB-001",
                confirmed_by=staff_users["owner"],
            )

            # 9. Create membership plans
            plan_standard_monthly = MembershipPlan.objects.create(
                gym=demo_gym,
                name="Monthly Standard",
                description="Unlimited gym access to cardio and resistance training equipment.",
                price_etb=Decimal("1500.00"),
                duration_value=1,
                duration_unit=MembershipPlan.DURATION_MONTHS,
                trainer_inclusive=False,
                is_active=True,
            )
            plan_standard_quarterly = MembershipPlan.objects.create(
                gym=demo_gym,
                name="Quarterly Standard",
                description="3 months full gym floor access with locker room amenities.",
                price_etb=Decimal("4000.00"),
                duration_value=3,
                duration_unit=MembershipPlan.DURATION_MONTHS,
                trainer_inclusive=False,
                is_active=True,
            )
            plan_trainer_monthly = MembershipPlan.objects.create(
                gym=demo_gym,
                name="Monthly VIP Trainer",
                description="Full gym access plus assigned personal trainer and weekly AI workout plans.",
                price_etb=Decimal("3500.00"),
                duration_value=1,
                duration_unit=MembershipPlan.DURATION_MONTHS,
                trainer_inclusive=True,
                is_active=True,
            )
            MembershipPlan.objects.create(
                gym=demo_gym,
                name="Annual VIP Elite",
                description="Full 12 months access with dedicated personal trainer and body composition history.",
                price_etb=Decimal("36000.00"),
                duration_value=12,
                duration_unit=MembershipPlan.DURATION_MONTHS,
                trainer_inclusive=True,
                is_active=True,
            )
            MembershipPlan.objects.create(
                gym=demo_gym,
                name="Weekly Trial Pass",
                description="7 days introductory pass.",
                price_etb=Decimal("500.00"),
                duration_value=7,
                duration_unit=MembershipPlan.DURATION_DAYS,
                trainer_inclusive=False,
                is_active=True,
            )

            # Helper for sequential receipts
            receipt_seq = 0

            def create_receipt_for_payment(pmt, user_actor):
                nonlocal receipt_seq
                receipt_seq += 1
                rec_num = f"REC-{receipt_seq:06d}"
                return Receipt.objects.create(
                    gym=demo_gym,
                    payment=pmt,
                    receipt_number=rec_num,
                    sequence_number=receipt_seq,
                    issued_by=user_actor,
                    amount_etb=pmt.amount_etb,
                    gross_amount_etb=pmt.gross_amount_etb or pmt.amount_etb,
                    credit_amount_etb=pmt.credit_amount_etb or Decimal("0.00"),
                )

            # 10. Seed 90 members with diverse statuses
            members_created = []
            trainer_clients = []

            for i in range(1, 91):
                first_name = FIRST_NAMES[(i - 1) % len(FIRST_NAMES)]
                last_name = LAST_NAMES[((i - 1) // 3) % len(LAST_NAMES)]
                full_name = f"{first_name} {last_name}"
                email = f"member{i}@demo.local"
                phone = f"+251912{i:06d}"

                u = User.objects.create(
                    email=email,
                    password=hashed_demo_pw,
                    full_name=full_name,
                    role=User.ROLE_MEMBER,
                    gym=demo_gym,
                    phone=phone,
                    is_active=True,
                    email_verified_at=(
                        now if (i <= 85) else None
                    ),  # 5 unverified members
                    must_change_password=False,
                )

                m = Member.objects.create(
                    gym=demo_gym,
                    user=u,
                    full_name=full_name,
                    phone=phone,
                    waiver_accepted_at=now - timedelta(days=60),
                )
                members_created.append((u, m, i))

            # Categorize members into target lifecycle states:
            # 1..10: Pending (new registrations with no payments/subscriptions - default status is pending)

            # 11..20: Expired members (subscription ended 1 to 30 days ago)
            for u, m, idx in members_created[10:20]:
                start_d = today - timedelta(days=60)
                end_d = today - timedelta(days=idx - 10)
                MemberSubscription.objects.create(
                    gym=demo_gym,
                    member=m,
                    plan=plan_standard_monthly,
                    start_date=start_d,
                    end_date=end_d,
                    status=MemberSubscription.STATUS_EXPIRED,
                )
                update_member_status(m, today=today)

            # 21..28: Frozen members (8 members with active freeze requests)
            for u, m, idx in members_created[20:28]:
                start_d = today - timedelta(days=15)
                end_d = today + timedelta(days=15)
                sub = MemberSubscription.objects.create(
                    gym=demo_gym,
                    member=m,
                    plan=plan_standard_monthly,
                    start_date=start_d,
                    end_date=end_d,
                    status=MemberSubscription.STATUS_FROZEN,
                )
                MemberFreeze.objects.create(
                    gym=demo_gym,
                    subscription=sub,
                    member=m,
                    start_date=today - timedelta(days=5),
                    end_date=today + timedelta(days=10),
                    days=15,
                    reason="Travel out of city for work",
                    status=MemberFreeze.STATUS_APPROVED,
                    approved_by=staff_users["manager"],
                    reviewed_at=now - timedelta(days=5),
                    extension_applied=True,
                )
                update_member_status(m, today=today)

            # 29..33: Expiring soon (5 members with subscriptions expiring in <= 7 days)
            for u, m, idx in members_created[28:33]:
                days_left = (idx - 28) + 1  # 1 to 5 days remaining
                sub = MemberSubscription.objects.create(
                    gym=demo_gym,
                    member=m,
                    plan=plan_standard_monthly,
                    start_date=today - timedelta(days=25),
                    end_date=today + timedelta(days=days_left),
                    status=MemberSubscription.STATUS_ACTIVE,
                )
                pmt = Payment.objects.create(
                    gym=demo_gym,
                    member=m,
                    plan=plan_standard_monthly,
                    payer_type=Payment.PAYER_TYPE_MEMBER,
                    amount_etb=plan_standard_monthly.price_etb,
                    method=Payment.METHOD_CASH,
                    status=Payment.STATUS_CONFIRMED,
                    confirmed_by=staff_users["reception"],
                )
                create_receipt_for_payment(pmt, staff_users["reception"])
                update_member_status(m, today=today)

            # 34: Member with queued following plan
            u_q, m_q, _ = members_created[33]
            MemberSubscription.objects.create(
                gym=demo_gym,
                member=m_q,
                plan=plan_standard_monthly,
                start_date=today - timedelta(days=27),
                end_date=today + timedelta(days=3),
                status=MemberSubscription.STATUS_ACTIVE,
            )
            MemberSubscription.objects.create(
                gym=demo_gym,
                member=m_q,
                plan=plan_standard_quarterly,
                start_date=today + timedelta(days=4),
                end_date=today + timedelta(days=94),
                status=MemberSubscription.STATUS_ACTIVE,
            )
            pmt_q = Payment.objects.create(
                gym=demo_gym,
                member=m_q,
                plan=plan_standard_quarterly,
                payer_type=Payment.PAYER_TYPE_MEMBER,
                amount_etb=plan_standard_quarterly.price_etb,
                method=Payment.METHOD_CASH,
                status=Payment.STATUS_CONFIRMED,
                confirmed_by=staff_users["reception"],
            )
            create_receipt_for_payment(pmt_q, staff_users["reception"])
            update_member_status(m_q, today=today)

            # 35: Member with upgraded plan (superseded old subscription)
            u_up, m_up, _ = members_created[34]
            MemberSubscription.objects.create(
                gym=demo_gym,
                member=m_up,
                plan=plan_standard_monthly,
                start_date=today - timedelta(days=40),
                end_date=today + timedelta(days=20),
                status=MemberSubscription.STATUS_SUPERSEDED,
            )
            MemberSubscription.objects.create(
                gym=demo_gym,
                member=m_up,
                plan=plan_trainer_monthly,
                start_date=today - timedelta(days=5),
                end_date=today + timedelta(days=25),
                status=MemberSubscription.STATUS_ACTIVE,
            )
            pmt_up = Payment.objects.create(
                gym=demo_gym,
                member=m_up,
                plan=plan_trainer_monthly,
                payer_type=Payment.PAYER_TYPE_MEMBER,
                amount_etb=Decimal("2000.00"),
                gross_amount_etb=Decimal("3500.00"),
                credit_amount_etb=Decimal("1500.00"),
                method=Payment.METHOD_CASH,
                status=Payment.STATUS_CONFIRMED,
                confirmed_by=staff_users["manager"],
            )
            create_receipt_for_payment(pmt_up, staff_users["manager"])
            trainer_clients.append((m_up, trainer1_obj))
            update_member_status(m_up, today=today)

            # 36..90: Active members across standard and trainer plans
            for u, m, idx in members_created[35:]:
                # Assign half to trainer plans
                is_trainer = idx % 2 == 0
                assigned_plan = (
                    plan_trainer_monthly
                    if is_trainer
                    else (
                        plan_standard_quarterly
                        if idx % 3 == 0
                        else plan_standard_monthly
                    )
                )
                start_d = today - timedelta(days=(idx % 20) + 1)
                end_d = today + timedelta(days=30 + (idx % 60))

                sub = MemberSubscription.objects.create(
                    gym=demo_gym,
                    member=m,
                    plan=assigned_plan,
                    start_date=start_d,
                    end_date=end_d,
                    status=MemberSubscription.STATUS_ACTIVE,
                )

                # Payment method variation
                pay_method = (
                    Payment.METHOD_CASH
                    if idx % 2 == 0
                    else Payment.METHOD_BANK_TRANSFER
                )
                pmt = Payment.objects.create(
                    gym=demo_gym,
                    member=m,
                    plan=assigned_plan,
                    payer_type=Payment.PAYER_TYPE_MEMBER,
                    amount_etb=assigned_plan.price_etb,
                    method=pay_method,
                    channel="cbe" if pay_method == Payment.METHOD_BANK_TRANSFER else "",
                    bank_reference=(
                        f"MOCK-FT{idx:08d}"
                        if pay_method == Payment.METHOD_BANK_TRANSFER
                        else None
                    ),
                    status=Payment.STATUS_CONFIRMED,
                    confirmed_by=(
                        staff_users["reception"]
                        if idx % 2 == 0
                        else staff_users["owner"]
                    ),
                )
                create_receipt_for_payment(pmt, staff_users["reception"])
                update_member_status(m, today=today)

                if is_trainer:
                    target_trainer = trainer1_obj if idx % 4 == 0 else trainer2_obj
                    trainer_clients.append((m, target_trainer))

            # 11. Create trainer assignments, fitness profiles, body metrics, and training plans
            monday = today - timedelta(days=today.weekday())
            for m, tr in trainer_clients:
                TrainerAssignment.objects.create(
                    gym=demo_gym,
                    trainer=tr,
                    member=m,
                    assigned_by=staff_users["manager"],
                )

                # Body Metrics
                BodyMetrics.objects.create(
                    gym=demo_gym,
                    member=m,
                    weight_kg=Decimal("74.50"),
                    height_cm=Decimal("178.00"),
                    measurements={"neck_cm": 38, "waist_cm": 84, "hip_cm": 98},
                    recorded_by=tr.user,
                )

                # Fitness Profile
                FitnessProfile.objects.create(
                    gym=demo_gym,
                    member=m,
                    goal="strength",
                    fitness_level="intermediate",
                    health_limitations=["none"],
                    equipment_access=["barbell", "dumbbells", "cable_machine"],
                    training_days_per_week=4,
                    session_length_minutes=60,
                    dietary_notes=["none"],
                    other_dietary="Observes traditional fasting seasons.",
                )

                # Approved Weekly Training Plan
                plan_json = {
                    "focus": "upper_body",
                    "sessions": [
                        {
                            "name": "Session A (Upper Strength)",
                            "exercises": [
                                {
                                    "name": "Barbell Bench Press",
                                    "sets": 4,
                                    "reps": "8-10",
                                    "rpe": 8,
                                    "rest_seconds": 90,
                                },
                                {
                                    "name": "Incline Dumbbell Press",
                                    "sets": 3,
                                    "reps": "10-12",
                                    "rpe": 7,
                                    "rest_seconds": 60,
                                },
                                {
                                    "name": "Cable Lat Pulldown",
                                    "sets": 4,
                                    "reps": "10-12",
                                    "rpe": 8,
                                    "rest_seconds": 75,
                                },
                                {
                                    "name": "Dumbbell Lateral Raises",
                                    "sets": 3,
                                    "reps": "15",
                                    "rpe": 8,
                                    "rest_seconds": 45,
                                },
                            ],
                            "notes": "Maintain controlled tempo on bench press.",
                        },
                        {
                            "name": "Session B (Lower & Core)",
                            "exercises": [
                                {
                                    "name": "Barbell Squats",
                                    "sets": 4,
                                    "reps": "8",
                                    "rpe": 8,
                                    "rest_seconds": 120,
                                },
                                {
                                    "name": "Romanian Deadlifts",
                                    "sets": 3,
                                    "reps": "10",
                                    "rpe": 7,
                                    "rest_seconds": 90,
                                },
                                {
                                    "name": "Walking Lunges",
                                    "sets": 3,
                                    "reps": "12 per leg",
                                    "rpe": 8,
                                    "rest_seconds": 60,
                                },
                                {
                                    "name": "Hanging Knee Raises",
                                    "sets": 3,
                                    "reps": "15",
                                    "rpe": 7,
                                    "rest_seconds": 45,
                                },
                            ],
                            "notes": "Keep brace tight through squat descent.",
                        },
                    ],
                    "nutrition_guidance": "High protein recovery meals: eggs, lean beef, roasted chickpeas (kolo), and lentil stew (misir wot). Ensure at least 3 liters of water daily.",
                }

                TrainingPlan.objects.create(
                    gym=demo_gym,
                    member=m,
                    week_start_date=monday,
                    draft_number=1,
                    status=TrainingPlan.STATUS_APPROVED,
                    generated_by_model="mock-gemini-flash",
                    equipment_source="complete registry list",
                    plan_data=plan_json,
                    focus_this_week=["upper_body"],
                    approved_by=tr.user,
                    approved_at=now - timedelta(days=2),
                )

            # 12. Seed Bank Receipt Review Queue items
            # (a) One payment pending review
            pending_review_user, pending_review_member, _ = members_created[0]
            Payment.objects.create(
                gym=demo_gym,
                member=pending_review_member,
                plan=plan_standard_monthly,
                payer_type=Payment.PAYER_TYPE_MEMBER,
                amount_etb=plan_standard_monthly.price_etb,
                method=Payment.METHOD_BANK_TRANSFER,
                channel="cbe",
                bank_reference="FT2611069901",
                review_photo="demo_receipt_sample.png",
                transfer_screenshot="demo_receipt_sample.png",
                status=Payment.STATUS_PENDING_REVIEW,
            )

            # (b) One declined review
            rejected_user, rejected_member, _ = members_created[1]
            Payment.objects.create(
                gym=demo_gym,
                member=rejected_member,
                plan=plan_standard_monthly,
                payer_type=Payment.PAYER_TYPE_MEMBER,
                amount_etb=plan_standard_monthly.price_etb,
                method=Payment.METHOD_BANK_TRANSFER,
                channel="telebirr",
                bank_reference="FT2611069902",
                review_photo="demo_receipt_unclear.png",
                transfer_screenshot="demo_receipt_unclear.png",
                status=Payment.STATUS_DECLINED,
                review_decision="declined",
                review_decided_by=staff_users["manager"],
                review_decided_at=now - timedelta(days=1),
            )

            # 13. Seed Equipment with purchase prices and total investment
            equipment_data = [
                (
                    "Commercial Treadmill Pro",
                    "cardio_machines",
                    4,
                    Decimal("220000.00"),
                    CONDITION_GOOD,
                ),
                (
                    "Olympic Power Rack",
                    "squat_rack",
                    3,
                    Decimal("85000.00"),
                    CONDITION_GOOD,
                ),
                (
                    "Olympic Barbell 20kg",
                    "barbell",
                    6,
                    Decimal("18000.00"),
                    CONDITION_GOOD,
                ),
                (
                    "Rubber Hex Dumbbell Set 2.5-30kg",
                    "dumbbells",
                    1,
                    Decimal("145000.00"),
                    CONDITION_GOOD,
                ),
                (
                    "Dual Adjustable Pulley Cable Machine",
                    "cable_machine",
                    2,
                    Decimal("160000.00"),
                    CONDITION_GOOD,
                ),
                (
                    "Adjustable Incline Flat Bench",
                    "bench",
                    5,
                    Decimal("22000.00"),
                    CONDITION_GOOD,
                ),
                (
                    "Stationary Spin Bike",
                    "cardio_machines",
                    3,
                    Decimal("45000.00"),
                    CONDITION_OUT_OF_SERVICE,
                ),
            ]

            for name, cat, qty, price, cond in equipment_data:
                Equipment.objects.create(
                    gym=demo_gym,
                    name=name,
                    category=cat,
                    quantity=qty,
                    condition=cond,
                    purchase_date=today - timedelta(days=180),
                    unit_purchase_price_etb=price,
                )

            # 14. Seed Expenses and one voided expense
            Expense.objects.create(
                gym=demo_gym,
                category=Expense.CATEGORY_RENT,
                amount_etb=Decimal("65000.00"),
                note="Monthly commercial facility rent for Bole branch.",
                incurred_on=today - timedelta(days=5),
                logged_by=staff_users["owner"],
            )
            Expense.objects.create(
                gym=demo_gym,
                category=Expense.CATEGORY_SALARIES,
                amount_etb=Decimal("55000.00"),
                note="Staff payroll for trainers and desk staff.",
                incurred_on=today - timedelta(days=5),
                logged_by=staff_users["owner"],
            )
            Expense.objects.create(
                gym=demo_gym,
                category=Expense.CATEGORY_UTILITIES,
                amount_etb=Decimal("12500.00"),
                note="Electric power and water utility bill.",
                incurred_on=today - timedelta(days=12),
                logged_by=staff_users["manager"],
            )
            Expense.objects.create(
                gym=demo_gym,
                category=Expense.CATEGORY_MAINTENANCE,
                amount_etb=Decimal("8000.00"),
                note="Cable replacement and treadmill belt lubrication.",
                incurred_on=today - timedelta(days=18),
                logged_by=staff_users["manager"],
            )

            # Voided expense
            Expense.objects.create(
                gym=demo_gym,
                category=Expense.CATEGORY_SUPPLIES,
                amount_etb=Decimal("15000.00"),
                note="Cleaning supplies order duplicate entry.",
                incurred_on=today - timedelta(days=20),
                logged_by=staff_users["manager"],
                is_void=True,
                voided_at=now - timedelta(days=19),
                voided_by=staff_users["owner"],
                void_reason="Duplicate transaction logged in error; corrected on official receipt.",
            )

            # 15. Seed Group Classes and Bookings
            spin_session = ClassSession.objects.create(
                gym=demo_gym,
                title=CLASS_TITLE_SPINNING,
                trainer=trainer1_obj,
                start_time=now + timedelta(hours=2),
                end_time=now + timedelta(hours=3),
                duration_minutes=60,
                capacity=15,
                status=SESSION_STATUS_SCHEDULED,
            )
            yoga_session = ClassSession.objects.create(
                gym=demo_gym,
                title=CLASS_TITLE_YOGA,
                trainer=trainer2_obj,
                start_time=now + timedelta(days=1, hours=4),
                end_time=now + timedelta(days=1, hours=5),
                duration_minutes=60,
                capacity=20,
                status=SESSION_STATUS_SCHEDULED,
            )
            ClassSession.objects.create(
                gym=demo_gym,
                title=CLASS_TITLE_CROSSFIT,
                trainer=trainer1_obj,
                start_time=now + timedelta(days=2, hours=3),
                end_time=now + timedelta(days=2, hours=4),
                duration_minutes=60,
                capacity=12,
                status=SESSION_STATUS_SCHEDULED,
            )

            # Add bookings for active members
            for _, m, _ in members_created[35:45]:
                ClassBooking.objects.create(
                    gym=demo_gym,
                    session=spin_session,
                    member=m,
                    booked_by=m.user,
                    status=BOOKING_STATUS_BOOKED,
                )

            for _, m, _ in members_created[45:53]:
                ClassBooking.objects.create(
                    gym=demo_gym,
                    session=yoga_session,
                    member=m,
                    booked_by=m.user,
                    status=BOOKING_STATUS_BOOKED,
                )

            # 16. Seed Attendance (past 30 days + ~25 check-ins today)
            att_rows = []
            for d in range(1, 30):
                checkin_date = today - timedelta(days=d)
                # Pick 8-15 random members per day
                for _, m, idx in members_created[35:50]:
                    if (d + idx) % 2 == 0:
                        att_rows.append(
                            Attendance(
                                gym=demo_gym,
                                member=m,
                                date=checkin_date,
                                status=Attendance.STATUS_CHECKED_IN,
                                method=Attendance.METHOD_QR,
                            )
                        )

            # Check-ins today
            for _, m, idx in members_created[35:60]:
                is_manual = idx % 3 == 0
                att_rows.append(
                    Attendance(
                        gym=demo_gym,
                        member=m,
                        date=today,
                        status=Attendance.STATUS_CHECKED_IN,
                        method=(
                            Attendance.METHOD_MANUAL_OVERRIDE
                            if is_manual
                            else Attendance.METHOD_QR
                        ),
                        is_override=is_manual,
                        recorded_by=staff_users["reception"] if is_manual else None,
                        override_reason=(
                            "Member forgot phone pass at front desk"
                            if is_manual
                            else ""
                        ),
                    )
                )

            Attendance.objects.bulk_create(att_rows)

            # 17. Seed Gym Notice Board announcements
            GymNotice.objects.create(
                gym=demo_gym,
                title="Welcome to the FitGate Demo Environment!",
                body=(
                    "Welcome to our live showcase gym. Explore member management, QR check-ins, "
                    "trainer client assignments, automated AI training plans, and operational reports."
                ),
                posted_by=staff_users["owner"],
            )
            GymNotice.objects.create(
                gym=demo_gym,
                title="Spinning & Yoga Schedule for This Week",
                body=(
                    "New group fitness class sessions are now available for booking: "
                    "Morning Spinning with Dawit and Sunset Yoga with Tigist. Reserve your spot early!"
                ),
                posted_by=staff_users["manager"],
            )

            # Update final counter sequence
            counter.last_receipt_number = receipt_seq
            counter.save(update_fields=["last_receipt_number"])

        # Summary output (plain text, formatted nicely)
        self.stdout.write(self.style.SUCCESS("\nFitGate Demo Gym successfully seeded!"))
        self.stdout.write("  Subdomain: demo")
        self.stdout.write("  Tier: Growth (All flags enabled)")
        self.stdout.write(f"  Members seeded: {len(members_created)}")
        self.stdout.write(f"  Receipts generated: {receipt_seq}")
        self.stdout.write("  Classes scheduled: 3")
        self.stdout.write(f"  Attendance logs: {len(att_rows)}")
        self.stdout.write("\nStaff Accounts (Password: from DEMO_PASSWORD):")
        self.stdout.write("  - Owner:     owner@demo.local")
        self.stdout.write("  - Manager:   manager@demo.local")
        self.stdout.write("  - Reception: reception@demo.local")
        self.stdout.write("  - Trainer 1: trainer1@demo.local")
        self.stdout.write("  - Trainer 2: trainer2@demo.local")
        self.stdout.write("  - Member:    member1@demo.local ... member90@demo.local\n")
