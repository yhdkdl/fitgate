"""
Logging filter for sanitizing sensitive data (tokens, passwords, Authorization headers, QR codes).
"""

import logging
import re

# Patterns to match sensitive parameters or header values
SENSITIVE_PATTERNS = [
    # Authorization header: Bearer <token>
    (re.compile(r"(Bearer\s+)[A-Za-z0-9\-_.]+", re.IGNORECASE), r"\1[REDACTED]"),
    # cPanel Auth: cpanel username:<token>
    (
        re.compile(r"(cpanel\s+[A-Za-z0-9-_]+:)[A-Za-z0-9-_]+", re.IGNORECASE),
        r"\1[REDACTED]",
    ),
    # Password parameters: password="...", 'password': '...', password=...
    (
        re.compile(
            r"(['\"]?(?:password|passwd|secret|api_token|token|key)['\"]?\s*[:=]\s*['\"]?)[^'\"\s,;&]+(['\"]?)",
            re.IGNORECASE,
        ),
        r"\1[REDACTED]\2",
    ),
    # JWT compact tokens: eyJ...
    (
        re.compile(r"eyJ[A-Za-z0-9-_=]+\.[A-Za-z0-9-_=]+\.[A-Za-z0-9-_=]+"),
        "[REDACTED_JWT]",
    ),
]


def sanitize_sensitive_string(text: str) -> str:
    """Scrub sensitive patterns from a string message."""
    if not isinstance(text, str):
        return text
    scrubbed = text
    for pattern, replacement in SENSITIVE_PATTERNS:
        scrubbed = pattern.sub(replacement, scrubbed)
    return scrubbed


class SensitiveDataFilter(logging.Filter):
    """
    Log filter that redacts passwords, tokens, Authorization headers,
    and JWT / QR code tokens from log messages and their arguments.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            if record.args:
                # Format the message with arguments first, then scrub secrets
                formatted = record.getMessage()
                record.msg = sanitize_sensitive_string(formatted)
                record.args = ()
            elif isinstance(record.msg, str):
                record.msg = sanitize_sensitive_string(record.msg)
        except Exception:
            pass
        return True
