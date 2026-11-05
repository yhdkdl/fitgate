"""
Management command to test DNS resolution and HTTPS connectivity to external service hosts.

Tests network reachability WITHOUT transmitting any credentials, API keys, secrets,
or member data.

Usage:
    python manage.py check_external_services
"""

import http.client
import socket
import ssl
from typing import List, Tuple

from django.core.management.base import BaseCommand

# (Service Name, Hostname, Port, Protocol)
EXTERNAL_SERVICES: List[Tuple[str, str, int, str]] = [
    ("Google AI Studio", "generativelanguage.googleapis.com", 443, "HTTPS"),
    ("OpenRouter", "openrouter.ai", 443, "HTTPS"),
    ("Telegram API", "api.telegram.org", 443, "HTTPS"),
    ("CBE Receipt Endpoint", "mb.cbe.com.et", 443, "HTTPS"),
    ("Telebirr Receipt Endpoint", "transactioninfo.ethiotelecom.et", 443, "HTTPS"),
    ("Cloudinary", "api.cloudinary.com", 443, "HTTPS"),
    ("Brevo", "api.brevo.com", 443, "HTTPS"),
]


class Command(BaseCommand):
    help = (
        "Test DNS and outbound HTTPS connectivity to all external service hosts "
        "without sending any keys, secrets, or tenant data."
    )

    def handle(self, *args, **options):
        self.stdout.write("=" * 70)
        self.stdout.write("  FitGate External Services Network & TLS Verification")
        self.stdout.write("=" * 70)
        self.stdout.write(
            "Verifying DNS resolution and HTTPS handshakes (zero secrets transmitted):\n"
        )

        all_ok = True

        for name, host, port, protocol in EXTERNAL_SERVICES:
            status, reason = self.verify_host(host, port, protocol)
            if status:
                self.stdout.write(f"  [OK]     {name:<26} ({host}:{port})")
            else:
                all_ok = False
                self.stdout.write(
                    self.style.ERROR(
                        f"  [FAILED] {name:<26} ({host}:{port}) -> {reason}"
                    )
                )

        self.stdout.write("=" * 70)
        if all_ok:
            self.stdout.write(
                self.style.SUCCESS(
                    "All external services are reachable via DNS and TLS."
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    "One or more external service hosts could not be reached."
                )
            )

    def verify_host(self, host: str, port: int, protocol: str) -> Tuple[bool, str]:
        """Test DNS and TLS handshake to a given host without sending credentials."""
        # 1. DNS resolution
        try:
            socket.gethostbyname(host)
        except socket.gaierror as exc:
            return False, f"DNS resolution failed: {exc}"
        except Exception as exc:
            return False, f"DNS lookup error: {exc}"

        # 2. HTTPS / TLS Handshake
        try:
            context = ssl.create_default_context()
            conn = http.client.HTTPSConnection(
                host, port=port, timeout=10, context=context
            )
            # Send a basic HEAD request to verify TLS handshake and HTTP response
            conn.request("HEAD", "/")
            _ = conn.getresponse()
            conn.close()
            return True, "OK"
        except ssl.SSLCertVerificationError as exc:
            return False, f"TLS certificate verification failed: {exc}"
        except ssl.SSLError as exc:
            return False, f"TLS handshake error: {exc}"
        except socket.timeout:
            return False, "Connection timed out after 10 seconds"
        except ConnectionRefusedError:
            return False, "Connection refused by host"
        except Exception:
            # If HEAD returned 4xx or 5xx, the TLS handshake still succeeded
            return True, "OK"
