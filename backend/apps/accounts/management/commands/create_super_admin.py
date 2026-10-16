"""Management command to bootstrap the initial Super Admin account."""

import os

from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import User


class Command(BaseCommand):
    """
    Bootstrap the initial platform Super Admin account.

    Reads SUPERADMIN_EMAIL and SUPERADMIN_PASSWORD from the environment.
    Fails clearly if either variable is missing.
    Idempotent: if any Super Admin exists, exits 0 without modifying anything.
    Sets must_change_password = True.
    """

    help = (
        "Bootstrap the initial platform Super Admin account from environment variables."
    )

    def handle(self, *args, **options):
        # 1. Idempotency check: if any Super Admin already exists, do nothing
        if User.all_objects.filter(role=User.ROLE_SUPER_ADMIN).exists():
            self.stdout.write(
                self.style.SUCCESS(
                    "Super Admin already exists. Idempotent check satisfied."
                )
            )
            return

        # 2. Read environment variables (no defaults, fail fast)
        email = os.environ.get("SUPERADMIN_EMAIL")
        password = os.environ.get("SUPERADMIN_PASSWORD")

        if not email or not email.strip():
            raise CommandError("SUPERADMIN_EMAIL environment variable is required.")

        if not password or not password.strip():
            raise CommandError("SUPERADMIN_PASSWORD environment variable is required.")

        from django.contrib.auth.password_validation import validate_password
        from django.core.exceptions import ValidationError

        try:
            validate_password(password, user=None)
        except ValidationError as exc:
            raise CommandError(f"Password validation error: {list(exc.messages)}")

        normalized_email = email.strip().lower()

        # 3. Create Super Admin with must_change_password = True
        from django.db import transaction

        from apps.accounts.services import record_audit_log

        with transaction.atomic():
            user = User.objects.create_superuser(
                email=normalized_email,
                password=password,
                must_change_password=True,
            )
            record_audit_log(
                action_type="super_admin_created",
                affected_record_type="User",
                affected_record_id=str(user.id),
                actor=user,
                gym=None,
                metadata={"source": "bootstrap_command", "email": normalized_email},
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Super Admin '{normalized_email}' successfully bootstrapped."
            )
        )
