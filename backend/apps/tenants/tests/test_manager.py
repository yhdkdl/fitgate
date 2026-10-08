"""Unit tests for TenantManager, TenantQuerySet, and TenantAwareModel isolation."""

import pytest
from django.core.exceptions import ValidationError
from django.db import connection, models

from apps.tenants.context import reset_current_tenant, set_current_tenant
from apps.tenants.models import GymTenant, TenantAwareModel


class DummyTenantModel(TenantAwareModel):
    """Concrete model for testing TenantAwareModel and TenantManager."""

    name = models.CharField(max_length=100)

    class Meta:
        app_label = "tenants"


@pytest.fixture(scope="module", autouse=True)
def create_dummy_table(django_db_setup, django_db_blocker):
    """Create and tear down database table for DummyTenantModel once for the module."""
    with django_db_blocker.unblock():
        with connection.schema_editor() as editor:
            editor.create_model(DummyTenantModel)
    yield
    with django_db_blocker.unblock():
        with connection.schema_editor() as editor:
            editor.delete_model(DummyTenantModel)


@pytest.mark.django_db
class TestTenantManagerIsolation:
    """Test tenant query scoping and prevention of cross-tenant leakage."""

    @pytest.fixture
    def seeded_tenants(self):
        """Seed two distinct tenants and their associated items."""
        tenant_a = GymTenant.objects.create(name="Tenant Alpha", subdomain="alpha")
        tenant_b = GymTenant.objects.create(name="Tenant Beta", subdomain="beta")

        item_a1 = DummyTenantModel.objects.create(gym=tenant_a, name="Alpha Item 1")
        item_a2 = DummyTenantModel.objects.create(gym=tenant_a, name="Alpha Item 2")
        item_b1 = DummyTenantModel.objects.create(gym=tenant_b, name="Beta Item 1")

        return {
            "tenant_a": tenant_a,
            "tenant_b": tenant_b,
            "items_a": [item_a1, item_a2],
            "items_b": [item_b1],
        }

    def test_tenant_manager_scopes_to_active_tenant_without_caller_filter(
        self, seeded_tenants
    ):
        """
        Verify that querying through TenantManager without explicit gym_id filter
        returns only the current tenant's rows, proving zero cross-tenant leakage.
        """
        tenant_a = seeded_tenants["tenant_a"]
        tenant_b = seeded_tenants["tenant_b"]

        # Scope context to Tenant Alpha
        token_a = set_current_tenant(tenant_a)
        try:
            results_a = list(DummyTenantModel.objects.all())
            assert len(results_a) == 2
            assert all(item.gym == tenant_a for item in results_a)
            assert {item.name for item in results_a} == {
                "Alpha Item 1",
                "Alpha Item 2",
            }
            # Beta item must NOT leak into Tenant Alpha query
            assert not any(item.gym == tenant_b for item in results_a)
        finally:
            reset_current_tenant(token_a)

        # Switch context to Tenant Beta
        token_b = set_current_tenant(tenant_b)
        try:
            results_b = list(DummyTenantModel.objects.all())
            assert len(results_b) == 1
            assert results_b[0].name == "Beta Item 1"
            assert results_b[0].gym == tenant_b
            # Alpha items must NOT leak into Tenant Beta query
            assert not any(item.gym == tenant_a for item in results_b)
        finally:
            reset_current_tenant(token_b)

    def test_all_objects_bypasses_tenant_scoping(self, seeded_tenants):
        """Verify all_objects returns records across all tenants regardless of context."""
        tenant_a = seeded_tenants["tenant_a"]
        token = set_current_tenant(tenant_a)
        try:
            all_items = list(DummyTenantModel.all_objects.all())
            assert len(all_items) == 3
        finally:
            reset_current_tenant(token)

    def test_unscoped_method_bypasses_tenant_scoping(self, seeded_tenants):
        """Verify .unscoped() on manager returns all records."""
        tenant_a = seeded_tenants["tenant_a"]
        token = set_current_tenant(tenant_a)
        try:
            unscoped_items = list(DummyTenantModel.objects.unscoped().all())
            assert len(unscoped_items) == 3
        finally:
            reset_current_tenant(token)

    def test_tenant_manager_fails_closed_when_no_tenant_in_context(
        self, seeded_tenants
    ):
        """
        Verify that querying without an active tenant context fails closed (returns empty queryset),
        preventing any unintentional data leakage across tenants.
        """
        token = set_current_tenant(None)
        try:
            scoped_items = list(DummyTenantModel.objects.all())
            assert len(scoped_items) == 0

            # Explicit unscoped bypass still returns all rows for administrative usage
            unscoped_items = list(DummyTenantModel.objects.unscoped().all())
            assert len(unscoped_items) == 3

            all_items = list(DummyTenantModel.all_objects.all())
            assert len(all_items) == 3
        finally:
            reset_current_tenant(token)

    def test_queryset_has_no_unscoped_method(self):
        """Verify TenantQuerySet has no unscoped() method to prevent silent no-ops."""
        qs = DummyTenantModel.objects.all()
        assert not hasattr(qs, "unscoped")
        with pytest.raises(AttributeError):
            getattr(qs, "unscoped")()

    def test_auto_assigns_gym_from_context_on_save(self, seeded_tenants):
        """Verify TenantAwareModel automatically assigns gym from context on save()."""
        tenant_a = seeded_tenants["tenant_a"]
        token = set_current_tenant(tenant_a)
        try:
            new_item = DummyTenantModel(name="Auto Assigned Item")
            new_item.save()
            assert new_item.gym == tenant_a
        finally:
            reset_current_tenant(token)

    def test_save_raises_validation_error_when_no_tenant_context_and_no_gym(
        self,
    ):
        """Verify .save() fails closed and raises ValidationError if no tenant context or gym is set."""
        token = set_current_tenant(None)
        try:
            item = DummyTenantModel(name="Orphan Item")
            with pytest.raises(ValidationError) as exc_info:
                item.save()
            assert "Tenant context or explicit gym assignment is required" in str(
                exc_info.value
            )
        finally:
            reset_current_tenant(token)

    def test_save_raises_validation_error_on_mismatched_gym(self, seeded_tenants):
        """Verify .save() fails closed and raises ValidationError when gym contradicts active context."""
        tenant_a = seeded_tenants["tenant_a"]
        tenant_b = seeded_tenants["tenant_b"]

        token = set_current_tenant(tenant_a)
        try:
            item = DummyTenantModel(gym=tenant_b, name="Cross Tenant Item")
            with pytest.raises(ValidationError) as exc_info:
                item.save()
            assert "Cannot assign or modify record for a different tenant" in str(
                exc_info.value
            )
        finally:
            reset_current_tenant(token)

    def test_save_succeeds_with_explicit_matching_gym(self, seeded_tenants):
        """Verify .save() succeeds when explicit gym matches the active tenant context."""
        tenant_a = seeded_tenants["tenant_a"]
        token = set_current_tenant(tenant_a)
        try:
            item = DummyTenantModel(gym=tenant_a, name="Explicit Matching Item")
            item.save()
            assert item.gym == tenant_a
        finally:
            reset_current_tenant(token)

    def test_bulk_create_auto_assigns_gym_from_context(self, seeded_tenants):
        """Verify bulk_create automatically assigns current tenant when gym is omitted."""
        tenant_a = seeded_tenants["tenant_a"]
        token = set_current_tenant(tenant_a)
        try:
            items = [
                DummyTenantModel(name="Bulk Item 1"),
                DummyTenantModel(name="Bulk Item 2"),
            ]
            created = DummyTenantModel.objects.bulk_create(items)
            assert len(created) == 2
            assert all(item.gym == tenant_a for item in created)
            # Confirmed in database query
            persisted = list(
                DummyTenantModel.objects.filter(name__startswith="Bulk Item")
            )
            assert len(persisted) == 2
            assert all(item.gym == tenant_a for item in persisted)
        finally:
            reset_current_tenant(token)

    def test_bulk_create_raises_validation_error_when_no_tenant_context_and_missing_gym(
        self,
    ):
        """Verify bulk_create fails closed with ValidationError when no tenant in context and no gym."""
        token = set_current_tenant(None)
        try:
            items = [DummyTenantModel(name="Orphan Bulk Item")]
            with pytest.raises(ValidationError) as exc_info:
                DummyTenantModel.objects.bulk_create(items)
            assert "Tenant context or explicit gym assignment is required" in str(
                exc_info.value
            )
        finally:
            reset_current_tenant(token)

    def test_bulk_create_raises_validation_error_on_mismatched_gym(
        self, seeded_tenants
    ):
        """Verify bulk_create fails closed with ValidationError when gym contradicts active tenant context."""
        tenant_a = seeded_tenants["tenant_a"]
        tenant_b = seeded_tenants["tenant_b"]

        token = set_current_tenant(tenant_a)
        try:
            items = [
                DummyTenantModel(gym=tenant_a, name="Valid Tenant A Item"),
                DummyTenantModel(gym=tenant_b, name="Invalid Tenant B Item"),
            ]
            with pytest.raises(ValidationError) as exc_info:
                DummyTenantModel.objects.bulk_create(items)
            assert "Cannot assign or modify record for a different tenant" in str(
                exc_info.value
            )
        finally:
            reset_current_tenant(token)

    def test_bulk_create_succeeds_with_explicit_matching_gym(self, seeded_tenants):
        """Verify bulk_create succeeds when explicit gym matches the active tenant context."""
        tenant_a = seeded_tenants["tenant_a"]
        token = set_current_tenant(tenant_a)
        try:
            items = [
                DummyTenantModel(gym=tenant_a, name="Explicit Bulk 1"),
                DummyTenantModel(gym=tenant_a, name="Explicit Bulk 2"),
            ]
            created = DummyTenantModel.objects.bulk_create(items)
            assert len(created) == 2
            assert all(item.gym == tenant_a for item in created)
        finally:
            reset_current_tenant(token)

    def test_bulk_create_accepts_generator_and_creates_all_rows(self, seeded_tenants):
        """Verify bulk_create consumes and persists a generator without silent data loss."""
        tenant_a = seeded_tenants["tenant_a"]
        token = set_current_tenant(tenant_a)
        try:
            gen = (DummyTenantModel(name=f"Gen Item {i}") for i in range(3))
            created = DummyTenantModel.objects.bulk_create(gen)
            assert len(created) == 3
            assert all(item.gym == tenant_a for item in created)

            persisted = list(
                DummyTenantModel.objects.filter(name__startswith="Gen Item")
            )
            assert len(persisted) == 3
            assert {item.name for item in persisted} == {
                "Gen Item 0",
                "Gen Item 1",
                "Gen Item 2",
            }
        finally:
            reset_current_tenant(token)

    def test_bulk_create_generator_raises_for_mismatched_gym(self, seeded_tenants):
        """Verify bulk_create raises ValidationError when a generator yields a record for another gym."""
        tenant_a = seeded_tenants["tenant_a"]
        tenant_b = seeded_tenants["tenant_b"]
        token = set_current_tenant(tenant_a)
        try:

            def mismatched_generator():
                yield DummyTenantModel(gym=tenant_a, name="Gen Valid 1")
                yield DummyTenantModel(gym=tenant_b, name="Gen Invalid 2")

            with pytest.raises(ValidationError) as exc_info:
                DummyTenantModel.objects.bulk_create(mismatched_generator())
            assert "Cannot assign or modify record for a different tenant" in str(
                exc_info.value
            )
        finally:
            reset_current_tenant(token)
