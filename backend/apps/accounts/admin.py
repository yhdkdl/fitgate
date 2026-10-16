"""Admin configuration for accounts app."""

from django.contrib import admin

from apps.accounts.models import AuditLog, User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    """
    User admin configuration for Super Admins on the apex domain.

    Uses User.all_objects so Super Admin can manage accounts across all gyms.
    """

    list_display = ("email", "role", "gym", "is_active", "created_at")
    list_filter = ("role", "is_active")
    search_fields = ("email",)
    ordering = ("-created_at",)

    def get_queryset(self, request):
        """Use all_objects to access users across all tenant scopes."""
        return self.model.all_objects.get_queryset()


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """
    Append-only Audit Log viewer for Super Admins in Django admin.
    Strictly read-only: add, change, and delete permissions are disabled.
    """

    list_display = (
        "timestamp",
        "action_type",
        "affected_record_type",
        "affected_record_id",
        "actor",
        "gym",
    )
    list_filter = ("action_type", "affected_record_type", "gym")
    search_fields = (
        "action_type",
        "affected_record_type",
        "affected_record_id",
        "actor__email",
    )
    ordering = ("-timestamp",)
    readonly_fields = [
        "id",
        "gym",
        "actor",
        "action_type",
        "affected_record_type",
        "affected_record_id",
        "timestamp",
        "metadata",
    ]

    def get_queryset(self, request):
        """Use all_objects to inspect audit rows across all tenants and apex."""
        return self.model.all_objects.get_queryset()

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
