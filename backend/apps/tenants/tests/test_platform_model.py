"""Unit tests for PlatformTenantAwareModel, PlatformTenantManager, and PlatformTenantQuerySet."""

import pytest
from django.core.exceptions import ValidationError
from django.db import connection, models

from apps.accounts.models import User
from apps.tenants.context import reset_current_tenant, set_current_tenant
from apps.tenants.models import GymTenant, PlatformTenantAwareModel


class DummyPlatformModel(PlatformTenantAwareModel):
    """Concrete model for testing PlatformTenantAwareModel and PlatformTenantManager."""

    name = models.CharField(max_length=100)
    role = models.CharField(max_length=20, default="standard")

    class Meta:
        app_label = "tenants"


@pytest.fixture(scope="module", autouse=True)
def create_dummy_platform_table(django_db_setup, django_db_blocker):
    """Create and tear down database table for DummyPlatformModel once for the module."""
    with django_db_blocker.unblock():
        with connection.schema_editor() as editor:
            editor.create_model(DummyPlatformModel)
    yield
    with django_db_blocker.unblock():
        with connection.schema_editor() as editor:
            editor.delete_model(DummyPlatformModel)


@pytest.mark.django_db
class TestPlatformTenantAwareModelIsolation:
    """Test platform-level vs gym tenant isolation and validation rules."""

    @pytest.fixture
    def seeded_platform_data(self):
        """Seed a gym tenant, a platform row, and a gym-scoped row."""
        gym_a = GymTenant.objects.create(name="PowerGym", subdomain="powergym")
        gym_b = GymTenant.objects.create(name="FitZone", subdomain="fitzone")

        # Without tenant context (apex): platform row has gym=None, gym row has explicit gym
        platform_item = DummyPlatformModel.objects.create(
            name="Platform Announcement", gym=None
        )
        gym_a_item = DummyPlatformModel.objects.create(name="PowerGym Item", gym=gym_a)
        gym_b_item = DummyPlatformModel.objects.create(name="FitZone Item", gym=gym_b)

        return {
            "gym_a": gym_a,
            "gym_b": gym_b,
            "platform_item": platform_item,
            "gym_a_item": gym_a_item,
            "gym_b_item": gym_b_item,
        }

    def test_apex_context_shows_only_platform_rows(self, seeded_platform_data):
        """At apex (no tenant context), PlatformTenantManager returns only rows where gym is null."""
        token = set_current_tenant(None)
        try:
            results = list(DummyPlatformModel.objects.all())

            assert seeded_platform_data["platform_item"] in results
            assert seeded_platform_data["gym_a_item"] not in results
            assert seeded_platform_data["gym_b_item"] not in results
            assert len(results) == 1
        finally:
            reset_current_tenant(token)

    def test_gym_context_shows_only_that_gym_rows(self, seeded_platform_data):
        """Inside a gym tenant, PlatformTenantManager returns only rows for that gym."""
        gym_a = seeded_platform_data["gym_a"]
        token = set_current_tenant(gym_a)
        try:
            results = list(DummyPlatformModel.objects.all())
            assert seeded_platform_data["gym_a_item"] in results
            assert seeded_platform_data["platform_item"] not in results
            assert seeded_platform_data["gym_b_item"] not in results
            assert len(results) == 1
        finally:
            reset_current_tenant(token)

    def test_unscoped_and_all_objects_return_all_rows(self, seeded_platform_data):
        """all_objects and .unscoped() return all platform and gym rows unconditionally."""
        gym_a = seeded_platform_data["gym_a"]
        token = set_current_tenant(gym_a)
        try:
            all_objs = list(DummyPlatformModel.all_objects.all())
            unscoped_objs = list(DummyPlatformModel.objects.unscoped().all())

            assert len(all_objs) == 3
            assert len(unscoped_objs) == 3
            assert seeded_platform_data["platform_item"] in all_objs
            assert seeded_platform_data["gym_a_item"] in all_objs
            assert seeded_platform_data["gym_b_item"] in all_objs
        finally:
            reset_current_tenant(token)

    def test_save_in_tenant_context_auto_assigns_tenant_if_empty(
        self, seeded_platform_data
    ):
        """Saving with active tenant and empty gym auto-assigns active tenant."""
        gym_a = seeded_platform_data["gym_a"]
        token = set_current_tenant(gym_a)
        try:
            item = DummyPlatformModel(name="Auto Assigned")
            item.save()
            assert item.gym == gym_a
        finally:
            reset_current_tenant(token)

    def test_save_in_tenant_context_rejects_mismatched_gym(self, seeded_platform_data):
        """Saving with active tenant and mismatched gym raises ValidationError."""
        gym_a = seeded_platform_data["gym_a"]
        gym_b = seeded_platform_data["gym_b"]
        token = set_current_tenant(gym_a)
        try:
            item = DummyPlatformModel(name="Mismatched", gym=gym_b)
            with pytest.raises(
                ValidationError,
                match="Cannot assign or modify record for a different tenant",
            ):
                item.save()
        finally:
            reset_current_tenant(token)

    def test_save_in_tenant_context_rejects_super_admin_role(
        self, seeded_platform_data
    ):
        """Saving a record with role='super_admin' in tenant context raises ValidationError."""
        gym_a = seeded_platform_data["gym_a"]
        token = set_current_tenant(gym_a)
        try:
            item = DummyPlatformModel(name="Invalid Admin", role="super_admin")
            with pytest.raises(
                ValidationError, match="Super Admin cannot belong to a gym"
            ):
                item.save()
        finally:
            reset_current_tenant(token)

    def test_save_without_tenant_context_allows_null_or_explicit_gym(
        self, seeded_platform_data
    ):
        """Without tenant context, both null gym and explicit gym are allowed."""
        token = set_current_tenant(None)
        try:
            item_null = DummyPlatformModel.objects.create(name="Platform Row", gym=None)
            item_explicit = DummyPlatformModel.objects.create(
                name="Apex Created Gym Row", gym=seeded_platform_data["gym_a"]
            )

            assert item_null.gym is None
            assert item_explicit.gym == seeded_platform_data["gym_a"]
        finally:
            reset_current_tenant(token)

    def test_bulk_create_enforces_tenant_rules(self, seeded_platform_data):
        """bulk_create enforces auto-assignment, mismatch rejection, and super_admin rejection."""
        gym_a = seeded_platform_data["gym_a"]
        gym_b = seeded_platform_data["gym_b"]

        token = set_current_tenant(gym_a)
        try:
            # Auto-assigns
            items = [
                DummyPlatformModel(name="Bulk 1"),
                DummyPlatformModel(name="Bulk 2"),
            ]
            created = DummyPlatformModel.objects.bulk_create(items)
            assert all(item.gym == gym_a for item in created)

            # Rejects mismatch
            with pytest.raises(
                ValidationError,
                match="Cannot assign or modify record for a different tenant",
            ):
                DummyPlatformModel.objects.bulk_create(
                    [DummyPlatformModel(name="Bad", gym=gym_b)]
                )

            # Rejects super_admin
            with pytest.raises(
                ValidationError, match="Super Admin cannot belong to a gym"
            ):
                DummyPlatformModel.objects.bulk_create(
                    [DummyPlatformModel(name="Bad Admin", role="super_admin")]
                )
        finally:
            reset_current_tenant(token)

    def test_bulk_create_accepts_generator_and_enforces_rules(
        self, seeded_platform_data
    ):
        """bulk_create handles generator expressions properly and auto-assigns active gym."""
        gym_a = seeded_platform_data["gym_a"]
        token = set_current_tenant(gym_a)
        try:
            generator = (DummyPlatformModel(name=f"Gen Item {i}") for i in range(3))
            created = DummyPlatformModel.objects.bulk_create(generator)
            assert len(created) == 3
            assert all(item.gym == gym_a for item in created)
        finally:
            reset_current_tenant(token)

    def test_user_model_isolation_between_apex_and_gym(self, seeded_platform_data):
        """Verify User model satisfies platform isolation: gym rows never visible at apex, platform rows never in gym."""
        gym_a = seeded_platform_data["gym_a"]
        gym_b = seeded_platform_data["gym_b"]

        super_admin = User.objects.create_superuser(
            email="platform.admin@fitgate.org",
            password="SuperPassword123!",
        )
        owner_a = User.objects.create_user(
            email="owner.a@powergym.com",
            password="OwnerPassword123!",
            role=User.ROLE_OWNER,
            gym=gym_a,
        )

        # 1. At apex (no tenant context)
        token_apex = set_current_tenant(None)
        try:
            apex_users = list(User.objects.all())
            assert super_admin in apex_users
            assert owner_a not in apex_users
        finally:
            reset_current_tenant(token_apex)

        # 2. Inside Gym A
        token_a = set_current_tenant(gym_a)
        try:
            gym_a_users = list(User.objects.all())
            assert owner_a in gym_a_users
            assert super_admin not in gym_a_users
        finally:
            reset_current_tenant(token_a)

        # 3. Inside Gym B
        token_b = set_current_tenant(gym_b)
        try:
            gym_b_users = list(User.objects.all())
            assert len(gym_b_users) == 0
        finally:
            reset_current_tenant(token_b)

        # 4. all_objects sees both
        all_users = list(User.all_objects.all())
        assert super_admin in all_users
        assert owner_a in all_users
