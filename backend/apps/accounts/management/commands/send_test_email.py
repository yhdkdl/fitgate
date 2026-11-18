"""
Management command to verify outbound SMTP email delivery.

Usage:
    python manage.py send_test_email --to recipient@example.com
"""

import sys

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.accounts.email_templates import render_gym_email_html
from apps.accounts.notifications import send_fitgate_email


class Command(BaseCommand):
    help = "Send a test email using production SMTP settings to verify outbound email delivery."

    def add_arguments(self, parser):
        parser.add_argument(
            "--to",
            required=True,
            help="Recipient email address to send the test email to.",
        )

    def handle(self, *args, **options):
        to_email = options["to"].strip()
        host = getattr(settings, "EMAIL_HOST", "NOT CONFIGURED")
        port = getattr(settings, "EMAIL_PORT", "NOT CONFIGURED")
        use_tls = getattr(settings, "EMAIL_USE_TLS", False)
        use_ssl = getattr(settings, "EMAIL_USE_SSL", False)
        from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "NOT CONFIGURED")

        self.stdout.write("=" * 60)
        self.stdout.write("  FitGate SMTP Email Delivery Test")
        self.stdout.write("=" * 60)
        self.stdout.write(f"Connecting to host : {host}:{port}")
        self.stdout.write(
            f"Security mode      : {'STARTTLS (587)' if use_tls else ('SSL/TLS (465)' if use_ssl else 'None')}"
        )
        self.stdout.write(f"Sender address     : {from_email}")
        self.stdout.write(f"Recipient address  : {to_email}")
        self.stdout.write("Sending test message...")

        subject = "FitGate System: SMTP Email Delivery Test"
        message = (
            "Congratulations!\n\n"
            "This test email confirms that your FitGate production SMTP email configuration "
            "is operating correctly on the host.\n\n"
            f"Sent via: {host}:{port}\n"
            "— FitGate Platform System\n"
        )
        html_msg = render_gym_email_html(
            headline="FitGate SMTP Operational Test",
            body_text_or_paragraphs=[
                "Congratulations!",
                "This email confirms that your FitGate SMTP email service is operating properly and connected to your outbound mail server.",
                "All transactional messages, including member invitations, password resets, and renewal notices, will be formatted with this gym-branded layout.",
            ],
            badge_text="OPERATIONAL TEST",
            detail_rows=[
                ("Host Server", f"{host}:{port}"),
                ("Security Mode", "STARTTLS" if use_tls else ("SSL/TLS" if use_ssl else "Plain")),
                ("Sender Address", from_email),
                ("Recipient", to_email),
                ("Status", "VERIFIED"),
            ],
            notice_text="This is an automated delivery test initiated from the management CLI.",
        )

        try:
            send_fitgate_email(
                subject=subject,
                message=message,
                recipient_list=[to_email],
                gym=None,  # Platform level -> "FitGate"
                fail_silently=False,
                html_message=html_msg,
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f"\n[OK] Test email successfully delivered to {to_email} via {host}:{port}."
                )
            )
        except Exception as exc:
            self.stderr.write(
                self.style.ERROR(f"\n[FAILED] Error sending test email: {exc}")
            )
            sys.exit(1)
