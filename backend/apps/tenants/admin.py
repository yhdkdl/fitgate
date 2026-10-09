"""Django admin registration for tenant models."""

from django.contrib import admin

from apps.tenants.models import GymConfig, GymTenant


class GymConfigInline(admin.StackedInline):
    model = GymConfig
    can_delete = False
    verbose_name_plural = "Configuration"


@admin.register(GymTenant)
class GymTenantAdmin(admin.ModelAdmin):
    list_display = ("name", "subdomain", "status", "tier", "currency", "created_at")
    list_filter = ("status", "tier", "currency")
    search_fields = ("name", "subdomain")
    inlines = [GymConfigInline]


@admin.register(GymConfig)
class GymConfigAdmin(admin.ModelAdmin):
    list_display = (
        "gym",
        "has_trainer_module",
        "has_ai_plans",
        "has_analytics",
        "has_group_classes",
        "has_multi_branch",
        "freeze_days_allowed",
    )
