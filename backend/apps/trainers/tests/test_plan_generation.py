from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

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
from apps.trainers.ai.base import AIPlanGenerationError
from apps.trainers.ai.litellm_provider import (
    LiteLLMAIPlanProvider,
    build_user_prompt,
)
from apps.trainers.ai.mock_provider import MockAIPlanProvider
from apps.trainers.models import (
    FitnessProfile,
    TrainerAssignment,
    TrainingPlan,
)
from apps.trainers.services import (
    approve_training_plan,
    edit_training_plan_draft,
    generate_training_plan,
    get_plan_generation_prerequisites,
    reject_training_plan,
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
def assigned_trainer_user(db, gym_tenant):
    return User.objects.create_user(
        email="assigned.trainer@bolehub.com",
        password="TrainerPassword123!",
        gym=gym_tenant,
        role=User.ROLE_TRAINER,
        must_change_password=False,
    )


@pytest.fixture
def unrelated_trainer_user(db, gym_tenant):
    return User.objects.create_user(
        email="unrelated.trainer@bolehub.com",
        password="TrainerPassword123!",
        gym=gym_tenant,
        role=User.ROLE_TRAINER,
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
def super_admin_user(db):
    return User.objects.create_user(
        email="superadmin@fitgate.app",
        password="SuperAdminPassword123!",
        gym=None,
        role=User.ROLE_SUPER_ADMIN,
        must_change_password=False,
    )


@pytest.fixture
def member_user(db, gym_tenant):
    return User.objects.create_user(
        email="member.yonas@bolehub.com",
        password="MemberPassword123!",
        gym=gym_tenant,
        role=User.ROLE_MEMBER,
        must_change_password=False,
    )


@pytest.fixture
def active_member(db, gym_tenant, member_user, assigned_trainer_user):
    plan = MembershipPlan.objects.create(
        gym=gym_tenant,
        name="Personal Training Pro",
        price_etb=Decimal("3500.00"),
        duration_value=1,
        duration_unit=MembershipPlan.DURATION_MONTHS,
        trainer_inclusive=True,
        is_active=True,
    )
    member = Member.objects.create(
        gym=gym_tenant,
        user=member_user,
        full_name="Yonas Alemu",
        phone="+251911002233",
        date_of_birth="1995-05-15",
        gender="male",
        status=Member.STATUS_ACTIVE,
        waiver_accepted_at=timezone.now(),
    )
    MemberSubscription.objects.create(
        gym=gym_tenant,
        member=member,
        plan=plan,
        start_date=timezone.localdate() - timedelta(days=5),
        end_date=timezone.localdate() + timedelta(days=25),
        status=MemberSubscription.STATUS_ACTIVE,
    )
    TrainerAssignment.objects.create(
        gym=gym_tenant,
        member=member,
        trainer=assigned_trainer_user.trainer_profile,
        assigned_at=timezone.now() - timedelta(days=5),
    )
    FitnessProfile.objects.create(
        gym=gym_tenant,
        member=member,
        goal="muscle_gain",
        fitness_level="intermediate",
        health_limitations=["knee"],
        other_limitations="",
        equipment_access=["full_gym"],
        other_equipment="",
        training_days_per_week=3,
        session_length_minutes=60,
        dietary_notes=["orthodox_fasting"],
        other_dietary="",
    )
    BodyMetrics.objects.create(
        gym=gym_tenant,
        member=member,
        recorded_by=assigned_trainer_user,
        weight_kg=Decimal("78.50"),
        height_cm=Decimal("180.00"),
        measurements={"waist_cm": 82.0, "neck_cm": 38.0},
        recorded_at=timezone.now() - timedelta(days=2),
    )
    return member


def authenticate_client(client, user, gym=None):
    tokens = get_tokens_for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
    subdomain = (
        gym.subdomain if gym else (user.gym.subdomain if user.gym else "bolehub")
    )
    if user.role == User.ROLE_SUPER_ADMIN:
        client.defaults["HTTP_HOST"] = "localhost"
    else:
        client.defaults["HTTP_HOST"] = f"{subdomain}.localhost"


# ==============================================================================
# 1. MOCK PROVIDER VALIDITY TESTS
# ==============================================================================


def test_mock_ai_plan_generation_valid_structure(
    db, gym_tenant, active_member, assigned_trainer_user
):
    provider = MockAIPlanProvider()
    plan = generate_training_plan(
        member=active_member,
        gym=gym_tenant,
        acting_user=assigned_trainer_user,
        week_choice="this_week",
        focus_this_week=["legs"],
        trainer_notes="Focus on squat mechanics",
        provider=provider,
    )

    assert plan.status == TrainingPlan.STATUS_PENDING_REVIEW
    assert plan.draft_number == 1
    assert plan.generated_by_model == "mock-ai-v1"
    assert len(plan.plan_data["sessions"]) == 3
    assert plan.plan_data["sessions"][0]["name"] == "Session A"
    assert plan.plan_data["sessions"][1]["name"] == "Session B"
    assert plan.plan_data["sessions"][2]["name"] == "Session C"

    # Ethiopian nutrition & fasting compliance
    nutrition = plan.plan_data["nutrition"]
    assert "guidance" in nutrition
    assert len(nutrition["meal_patterns"]) >= 3
    nutr_json = str(nutrition).lower()
    assert any(
        food in nutr_json
        for food in ["injera", "shiro", "misir", "kik", "gomen", "lentils"]
    )
    assert "kcal" not in nutr_json


# ==============================================================================
# 2. PREREQUISITES & GATEKEEPER TESTS
# ==============================================================================


def test_prerequisites_gatekeeper(db, gym_tenant, active_member):
    prereqs = get_plan_generation_prerequisites(member=active_member, gym=gym_tenant)
    assert prereqs["eligible"] is True
    assert prereqs["missing_requirements"] == []

    # Missing AI plans on gym
    gym_tenant.config.has_ai_plans = False
    gym_tenant.config.save()
    prereqs = get_plan_generation_prerequisites(member=active_member, gym=gym_tenant)
    assert prereqs["eligible"] is False
    assert any("not enabled" in m.lower() for m in prereqs["missing_requirements"])
    gym_tenant.config.has_ai_plans = True
    gym_tenant.config.save()

    # Missing trainer-inclusive subscription
    sub = MemberSubscription.all_objects.filter(member=active_member).first()
    sub.plan.trainer_inclusive = False
    sub.plan.save()
    prereqs = get_plan_generation_prerequisites(member=active_member, gym=gym_tenant)
    assert prereqs["eligible"] is False
    assert any("trainer-inclusive" in m for m in prereqs["missing_requirements"])
    sub.plan.trainer_inclusive = True
    sub.plan.save()

    # Missing active assignment
    assignment = TrainerAssignment.all_objects.filter(member=active_member).first()
    assignment.ended_at = timezone.now()
    assignment.save()
    prereqs = get_plan_generation_prerequisites(member=active_member, gym=gym_tenant)
    assert prereqs["eligible"] is False
    assert any("assigned trainer" in m.lower() for m in prereqs["missing_requirements"])
    assignment.ended_at = None
    assignment.save()

    # Missing measurements
    BodyMetrics.all_objects.filter(member=active_member).delete()
    prereqs = get_plan_generation_prerequisites(member=active_member, gym=gym_tenant)
    assert prereqs["eligible"] is False
    assert any(
        "at least one measurement" in m.lower() for m in prereqs["missing_requirements"]
    )


def test_prerequisites_status_endpoint(
    api_client, gym_tenant, active_member, assigned_trainer_user
):
    authenticate_client(api_client, assigned_trainer_user, gym_tenant)
    url = f"/api/gym/members/{active_member.id}/plans/status/"
    res = api_client.get(url)
    assert res.status_code == 200
    assert res.data["eligible"] is True
    assert res.data["missing_requirements"] == []


# ==============================================================================
# 3. RBAC & TENANT ACCESS TESTS
# ==============================================================================


def test_rbac_plan_access_refusals(
    api_client,
    gym_tenant,
    other_gym_tenant,
    active_member,
    assigned_trainer_user,
    unrelated_trainer_user,
    reception_user,
    super_admin_user,
    member_user,
):
    # Setup pending draft
    provider = MockAIPlanProvider()
    plan = generate_training_plan(
        member=active_member,
        gym=gym_tenant,
        acting_user=assigned_trainer_user,
        provider=provider,
    )

    url_status = f"/api/gym/members/{active_member.id}/plans/status/"
    url_plans = f"/api/gym/members/{active_member.id}/plans/"
    url_detail = f"/api/gym/training-plans/{plan.id}/"

    # 1. Unrelated trainer -> 403 Forbidden
    authenticate_client(api_client, unrelated_trainer_user, gym_tenant)
    assert api_client.get(url_status).status_code == 403
    assert api_client.get(url_plans).status_code == 403
    assert api_client.get(url_detail).status_code == 403

    # 2. Reception -> 403 Forbidden
    authenticate_client(api_client, reception_user, gym_tenant)
    assert api_client.get(url_status).status_code == 403
    assert api_client.get(url_plans).status_code == 403
    assert api_client.get(url_detail).status_code == 403

    # 3. Super Admin -> 403 Forbidden
    authenticate_client(api_client, super_admin_user, gym_tenant)
    assert api_client.get(url_status).status_code == 403
    assert api_client.get(url_plans).status_code == 403
    assert api_client.get(url_detail).status_code == 403

    # 4. Member -> unapproved draft completely hidden
    authenticate_client(api_client, member_user, gym_tenant)
    # Cannot access gym endpoints
    assert api_client.get(url_plans).status_code == 403
    # Member me endpoint returns empty because plan is pending_review
    res_me = api_client.get("/api/members/me/plans/")
    assert res_me.status_code == 200
    assert len(res_me.data) == 0


# ==============================================================================
# 4. RATE LIMITING TESTS
# ==============================================================================


def test_hourly_gym_rate_limit(db, gym_tenant, active_member, assigned_trainer_user):
    provider = MockAIPlanProvider()
    today = timezone.localdate()
    monday = today - timedelta(days=today.weekday())

    # Pre-create 20 plans in the current hour for the gym
    for i in range(20):
        TrainingPlan.all_objects.create(
            gym=gym_tenant,
            member=active_member,
            week_start_date=monday + timedelta(days=7 * (i + 1)),
            draft_number=1,
            status=TrainingPlan.STATUS_PENDING_REVIEW,
            generated_by_model="mock-ai-v1",
            plan_data={
                "sessions": [],
                "nutrition": {"guidance": "", "meal_patterns": []},
            },
        )

    # 21st attempt in the same hour must be refused
    with pytest.raises(Exception) as excinfo:
        generate_training_plan(
            member=active_member,
            gym=gym_tenant,
            acting_user=assigned_trainer_user,
            week_choice="this_week",
            provider=provider,
        )
    assert "Gym rate limit reached" in str(excinfo.value)


# ==============================================================================
# 5. WEEKLY DRAFT LIMIT & REJECTION RULES
# ==============================================================================


def test_weekly_draft_limit_and_rejection_rules(
    db, gym_tenant, active_member, assigned_trainer_user
):
    provider = MockAIPlanProvider()

    # Draft 1
    draft_1 = generate_training_plan(
        member=active_member,
        gym=gym_tenant,
        acting_user=assigned_trainer_user,
        week_choice="this_week",
        provider=provider,
    )
    assert draft_1.draft_number == 1
    assert draft_1.can_reject is True

    # Cannot create a second draft while draft 1 is pending
    with pytest.raises(Exception) as excinfo:
        generate_training_plan(
            member=active_member,
            gym=gym_tenant,
            acting_user=assigned_trainer_user,
            week_choice="this_week",
            provider=provider,
        )
    assert "already pending review" in str(excinfo.value)

    # Reject Draft 1 -> Generates Draft 2
    draft_2 = reject_training_plan(
        plan=draft_1,
        rejection_reasons=["too_hard"],
        other_rejection_reason="",
        acting_user=assigned_trainer_user,
        provider=provider,
    )
    draft_1.refresh_from_db()
    assert draft_1.status == TrainingPlan.STATUS_REJECTED
    assert draft_2.draft_number == 2
    assert draft_2.can_reject is True

    # Reject Draft 2 -> Generates Draft 3
    draft_3 = reject_training_plan(
        plan=draft_2,
        rejection_reasons=["exercises_not_suitable", "other"],
        other_rejection_reason="Lower load for knees",
        acting_user=assigned_trainer_user,
        provider=provider,
    )
    draft_2.refresh_from_db()
    assert draft_2.status == TrainingPlan.STATUS_REJECTED
    assert draft_3.draft_number == 3
    assert draft_3.is_final_draft is True
    assert draft_3.can_reject is False

    # Draft 3 cannot be rejected
    with pytest.raises(Exception) as excinfo:
        reject_training_plan(
            plan=draft_3,
            rejection_reasons=["too_hard"],
            other_rejection_reason="",
            acting_user=assigned_trainer_user,
            provider=provider,
        )
    assert "Draft 3 is the final draft and cannot be rejected" in str(excinfo.value)


# ==============================================================================
# 6. DIRECT EDIT & APPROVAL AUDIT LOGGING
# ==============================================================================


def test_direct_edit_and_approval(
    db, gym_tenant, active_member, assigned_trainer_user, member_user, api_client
):
    provider = MockAIPlanProvider()
    draft = generate_training_plan(
        member=active_member,
        gym=gym_tenant,
        acting_user=assigned_trainer_user,
        provider=provider,
    )

    # Direct edit exercises
    new_data = dict(draft.plan_data)
    new_data["sessions"][0]["exercises"][0]["notes"] = "Custom trainer form cue"
    edited_plan = edit_training_plan_draft(
        plan=draft,
        plan_data=new_data,
        acting_user=assigned_trainer_user,
    )
    assert edited_plan.was_edited is True

    # Audit log check for edit
    edit_log = AuditLog.all_objects.filter(
        gym=gym_tenant, action_type="training_plan_edited"
    ).first()
    assert edit_log is not None

    # Approve plan
    approved_plan = approve_training_plan(
        plan=edited_plan, acting_user=assigned_trainer_user
    )
    assert approved_plan.status == TrainingPlan.STATUS_APPROVED
    assert approved_plan.approved_by == assigned_trainer_user
    assert approved_plan.approved_at is not None

    # Audit log check for approval
    approval_log = AuditLog.all_objects.filter(
        gym=gym_tenant, action_type="training_plan_approved"
    ).first()
    assert approval_log is not None
    assert approval_log.metadata["was_edited"] is True

    # Member now sees approved plan
    authenticate_client(api_client, member_user, gym_tenant)
    res_me = api_client.get("/api/members/me/plans/")
    assert res_me.status_code == 200
    assert len(res_me.data) == 1
    assert res_me.data[0]["id"] == str(approved_plan.id)


# ==============================================================================
# 7. ZERO PII VERIFICATION
# ==============================================================================


def test_zero_pii_in_prompt_context(active_member, gym_tenant):
    from apps.trainers.rules_engine import build_ai_generation_context

    ctx = build_ai_generation_context(
        member=active_member,
        gym=gym_tenant,
        week_start_date=timezone.localdate(),
    )
    user_prompt = build_user_prompt(ctx)

    # Sensitive personal information must never appear
    assert "Yonas" not in user_prompt
    assert "Alemu" not in user_prompt
    assert active_member.phone not in user_prompt
    assert active_member.user.email not in user_prompt
    assert str(active_member.id) not in user_prompt
    assert str(active_member.user.id) not in user_prompt


# ==============================================================================
# 8. FALLBACK & 3-FAILURE RULE
# ==============================================================================


def test_model_fallback_and_three_failure_rule(gym_tenant, active_member, owner_user):
    from apps.trainers.rules_engine import build_ai_generation_context

    ctx = build_ai_generation_context(
        member=active_member,
        gym=gym_tenant,
        week_start_date=timezone.localdate(),
    )
    ctx["gym_id"] = str(gym_tenant.id)

    provider = LiteLLMAIPlanProvider(
        ordered_models=["model-fail-1", "model-fail-2", "model-fail-3"],
        timeout_seconds=5,
    )

    # Mock all three models failing
    with patch.object(
        provider, "_invoke_model", side_effect=Exception("API connection timeout")
    ):
        with pytest.raises(AIPlanGenerationError) as excinfo:
            provider.generate_plan(ctx)
        assert "generation failed, try again later" in str(excinfo.value)

    # Check that owner audit log was created
    audit = AuditLog.all_objects.filter(
        gym=gym_tenant, action_type="ai_plan_generation_failed"
    ).first()
    assert audit is not None
    assert audit.metadata["attempt_count"] == 3

    # Check that owner in-app notification was created
    from apps.accounts.models import Notification

    notif = Notification.all_objects.filter(
        gym=gym_tenant, type="ai_plan_generation_failed"
    ).first()
    assert notif is not None
    assert "failed after 3 attempts" in notif.message


def test_generation_endpoint_returns_clean_503_on_provider_failure(
    api_client, gym_tenant, active_member, assigned_trainer_user
):
    authenticate_client(api_client, assigned_trainer_user, gym_tenant)
    url = f"/api/gym/members/{active_member.id}/plans/"
    with patch("apps.trainers.services.get_default_ai_provider") as mock_prov:
        prov = LiteLLMAIPlanProvider(
            ordered_models=["m1", "m2", "m3"], timeout_seconds=1
        )
        mock_prov.return_value = prov
        with patch.object(
            prov, "_invoke_model", side_effect=Exception("Provider down")
        ):
            res = api_client.post(url, {"week_choice": "this_week"})
            assert res.status_code == 503
            assert res.data["detail"] == "Generation failed, try again later"

    # Failed attempts do not count toward gym's 20/hr rate limit or create any plan
    assert TrainingPlan.all_objects.filter(gym=gym_tenant).count() == 0


def test_missing_date_of_birth_refusal(db, gym_tenant, active_member):
    active_member.date_of_birth = None
    active_member.save()
    prereqs = get_plan_generation_prerequisites(member=active_member, gym=gym_tenant)
    assert prereqs["eligible"] is False
    assert any(
        "date of birth is missing" in m.lower() for m in prereqs["missing_requirements"]
    )


# ==============================================================================
# 8. SPRINT 23 & 24 TESTS: NOTIFICATIONS, GATED DRAFTS, TRAINER CLIENT SCOPE
# ==============================================================================


def test_notification_sent_only_to_right_member_and_only_on_approval(
    api_client, gym_tenant, active_member, assigned_trainer_user
):
    import datetime

    from apps.accounts.models import Notification, User
    from apps.memberships.models import Member
    from apps.trainers.services import (
        approve_training_plan,
        edit_training_plan_draft,
        generate_training_plan,
        reject_training_plan,
    )

    # Second member in the same gym
    user_b = User.objects.create_user(
        email="member_b@test.com",
        password="ValidPassword123!",
        role=User.ROLE_MEMBER,
        gym=gym_tenant,
        full_name="Member B",
    )
    Member.objects.create(
        user=user_b,
        gym=gym_tenant,
        date_of_birth="1995-05-15",
        waiver_accepted_at=timezone.now(),
    )

    today = timezone.localdate()
    monday = today - datetime.timedelta(days=today.weekday())

    from apps.trainers.ai.mock_provider import MockAIPlanProvider

    provider = MockAIPlanProvider()

    # 1. Generation creates a draft: member gets NO notification
    plan_1 = generate_training_plan(
        member=active_member,
        gym=gym_tenant,
        week_choice="this_week",
        acting_user=assigned_trainer_user,
        provider=provider,
    )
    assert Notification.all_objects.filter(recipient=active_member.user).count() == 0
    assert Notification.all_objects.filter(recipient=user_b).count() == 0

    # 2. Editing draft: member gets NO notification
    edit_training_plan_draft(
        plan=plan_1,
        plan_data=plan_1.plan_data,
        acting_user=assigned_trainer_user,
    )
    assert Notification.all_objects.filter(recipient=active_member.user).count() == 0
    assert Notification.all_objects.filter(recipient=user_b).count() == 0

    # 3. Rejecting draft: member gets NO notification, generates draft 2
    draft_2 = reject_training_plan(
        plan=plan_1,
        rejection_reasons=["too_hard"],
        other_rejection_reason="",
        acting_user=assigned_trainer_user,
        provider=provider,
    )
    assert Notification.all_objects.filter(recipient=active_member.user).count() == 0
    assert Notification.all_objects.filter(recipient=user_b).count() == 0

    # 4. Approving draft 2: ONLY active_member gets the notification
    approve_training_plan(plan=draft_2, acting_user=assigned_trainer_user)

    notifs_a = Notification.all_objects.filter(recipient=active_member.user)
    assert notifs_a.count() == 1
    assert (
        notifs_a.first().message
        == f"Your training plan for the week of {monday} is ready."
    )

    # Verify other member got NOTHING
    notifs_b = Notification.all_objects.filter(recipient=user_b)
    assert notifs_b.count() == 0


def test_member_never_sees_drafts(
    api_client, gym_tenant, active_member, assigned_trainer_user
):
    from apps.trainers.ai.mock_provider import MockAIPlanProvider
    from apps.trainers.services import generate_training_plan

    # Create pending draft
    draft = generate_training_plan(
        member=active_member,
        gym=gym_tenant,
        week_choice="this_week",
        acting_user=assigned_trainer_user,
        provider=MockAIPlanProvider(),
    )

    # Member calls approved plans endpoint -> returns empty list
    authenticate_client(api_client, active_member.user, gym_tenant)
    res_me = api_client.get("/api/members/me/plans/")
    assert res_me.status_code == 200
    assert len(res_me.data) == 0

    # Member attempts to access trainer plan management endpoints directly -> 403 Forbidden
    res_direct = api_client.get(f"/api/gym/training-plans/{draft.id}/")
    assert res_direct.status_code == 403

    res_member_plans = api_client.get(f"/api/gym/members/{active_member.id}/plans/")
    assert res_member_plans.status_code == 403


def test_trainer_clients_list_never_contains_another_trainers_clients(
    api_client, gym_tenant, active_member, assigned_trainer_user
):
    from apps.accounts.models import User
    from apps.memberships.models import Member
    from apps.trainers.models import TrainerAssignment
    from apps.trainers.services import generate_training_plan

    # Second trainer user (profile auto-created via signal)
    trainer_user_2 = User.objects.create_user(
        email="trainer2@test.com",
        password="ValidPassword123!",
        role=User.ROLE_TRAINER,
        gym=gym_tenant,
        full_name="Trainer Two",
    )
    trainer_profile_2 = trainer_user_2.trainer_profile

    # Second member assigned to trainer 2
    user_b = User.objects.create_user(
        email="client2@test.com",
        password="ValidPassword123!",
        role=User.ROLE_MEMBER,
        gym=gym_tenant,
        full_name="Client Two",
    )
    member_b = Member.objects.create(
        user=user_b,
        gym=gym_tenant,
        date_of_birth="1994-08-20",
        waiver_accepted_at=timezone.now(),
    )
    TrainerAssignment.objects.create(
        gym=gym_tenant,
        trainer=trainer_profile_2,
        member=member_b,
        assigned_by=assigned_trainer_user,
    )

    from apps.trainers.ai.mock_provider import MockAIPlanProvider

    # Trainer 1 creates a draft for their client
    generate_training_plan(
        member=active_member,
        gym=gym_tenant,
        week_choice="this_week",
        acting_user=assigned_trainer_user,
        provider=MockAIPlanProvider(),
    )

    # Trainer 1 views their clients: sees ONLY active_member with pending_review draft
    authenticate_client(api_client, assigned_trainer_user, gym_tenant)
    res_1 = api_client.get("/api/trainers/me/clients/")
    assert res_1.status_code == 200
    returned_ids_1 = [c["member_id"] for c in res_1.data]
    assert str(active_member.id) in returned_ids_1
    assert str(member_b.id) not in returned_ids_1
    client_a_data = next(
        c for c in res_1.data if c["member_id"] == str(active_member.id)
    )
    assert client_a_data["has_approved_plan_this_week"] is False
    assert client_a_data["plan_status_this_week"] == "pending_review"

    # Trainer 2 views their clients: sees ONLY member_b with no_draft
    authenticate_client(api_client, trainer_user_2, gym_tenant)
    res_2 = api_client.get("/api/trainers/me/clients/")
    assert res_2.status_code == 200
    returned_ids_2 = [c["member_id"] for c in res_2.data]
    assert str(member_b.id) in returned_ids_2
    assert str(active_member.id) not in returned_ids_2
    client_b_data = next(c for c in res_2.data if c["member_id"] == str(member_b.id))
    assert client_b_data["has_approved_plan_this_week"] is False
    assert client_b_data["plan_status_this_week"] == "no_draft"
