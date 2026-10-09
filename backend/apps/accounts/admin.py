"""Admin configuration for accounts app."""

from django.contrib import admin

from apps.accounts.models import User


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
