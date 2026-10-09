"""Factory pattern implementation for role-specific dashboard configurations."""

from apps.accounts.models import User


def dashboard_config_for(user: User) -> dict:
    """
    Factory that returns role-specific dashboard configuration for a user.

    Raises ValueError if user role is unrecognized.
    """
    role = getattr(user, "role", None)
    if not role:
        raise ValueError("User has no role defined.")

    configs = {
        User.ROLE_SUPER_ADMIN: {
            "role": User.ROLE_SUPER_ADMIN,
            "title": "Platform Administration",
            "widgets": [
                {"id": "tenant_summary", "title": "Tenants Overview"},
                {"id": "platform_revenue", "title": "Platform Revenue"},
                {"id": "system_health", "title": "System Health"},
                {"id": "notices", "title": "Platform Notices"},
            ],
            "navigation": [
                {"label": "Gyms", "path": "/platform/gyms"},
                {"label": "Subscriptions", "path": "/platform/subscriptions"},
                {"label": "Reports", "path": "/platform/reports"},
                {"label": "Super Admins", "path": "/platform/super-admins"},
            ],
        },
        User.ROLE_OWNER: {
            "role": User.ROLE_OWNER,
            "title": "Gym Owner Dashboard",
            "widgets": [
                {"id": "active_members", "title": "Active Members"},
                {"id": "daily_checkins", "title": "Today's Check-ins"},
                {"id": "monthly_revenue", "title": "Monthly Revenue"},
                {"id": "expiring_memberships", "title": "Expiring Memberships"},
            ],
            "navigation": [
                {"label": "Overview", "path": "/dashboard"},
                {"label": "Members", "path": "/members"},
                {"label": "Staff", "path": "/staff"},
                {"label": "Plans", "path": "/plans"},
                {"label": "Finances", "path": "/finances"},
                {"label": "Settings", "path": "/settings"},
            ],
        },
        User.ROLE_MANAGER: {
            "role": User.ROLE_MANAGER,
            "title": "Gym Manager Dashboard",
            "widgets": [
                {"id": "active_members", "title": "Active Members"},
                {"id": "daily_checkins", "title": "Today's Check-ins"},
                {"id": "expiring_memberships", "title": "Expiring Memberships"},
            ],
            "navigation": [
                {"label": "Overview", "path": "/dashboard"},
                {"label": "Members", "path": "/members"},
                {"label": "Staff", "path": "/staff"},
                {"label": "Plans", "path": "/plans"},
                {"label": "Classes", "path": "/classes"},
            ],
        },
        User.ROLE_TRAINER: {
            "role": User.ROLE_TRAINER,
            "title": "Trainer Dashboard",
            "widgets": [
                {"id": "assigned_clients", "title": "Assigned Clients"},
                {"id": "pending_plans", "title": "Pending Plan Reviews"},
                {"id": "today_schedule", "title": "Today's Schedule"},
            ],
            "navigation": [
                {"label": "Clients", "path": "/clients"},
                {"label": "Training Plans", "path": "/plans"},
                {"label": "Availability", "path": "/availability"},
                {"label": "Messages", "path": "/messages"},
            ],
        },
        User.ROLE_RECEPTION: {
            "role": User.ROLE_RECEPTION,
            "title": "Front Desk Reception",
            "widgets": [
                {"id": "checkin_scanner", "title": "QR Check-in Scanner"},
                {"id": "today_attendance", "title": "Today's Attendance"},
                {"id": "recent_cash_payments", "title": "Recent Payments"},
            ],
            "navigation": [
                {"label": "Check-in", "path": "/checkin"},
                {"label": "Register Member", "path": "/members/register"},
                {"label": "Payments", "path": "/payments"},
            ],
        },
        User.ROLE_MEMBER: {
            "role": User.ROLE_MEMBER,
            "title": "Member Portal",
            "widgets": [
                {"id": "my_qr_code", "title": "My Check-in QR"},
                {"id": "active_subscription", "title": "Active Plan"},
                {"id": "my_plan", "title": "Training & Nutrition Plan"},
                {"id": "attendance_streak", "title": "Attendance Streak"},
            ],
            "navigation": [
                {"label": "Home", "path": "/home"},
                {"label": "Check-in QR", "path": "/qr"},
                {"label": "My Plan", "path": "/my-plan"},
                {"label": "Messages", "path": "/messages"},
                {"label": "Profile", "path": "/profile"},
            ],
        },
    }

    if role not in configs:
        raise ValueError(f"Unknown user role: {role}")

    return configs[role]
