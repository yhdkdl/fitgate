"""Shared validation rules for FitGate backend."""

import datetime
import re
from decimal import Decimal, InvalidOperation
from typing import Optional, Union

from django.core.exceptions import ValidationError
from django.core.validators import EmailValidator

# Phone validator
# Allowed chars: digits, optional leading +, spaces, hyphens
PHONE_ALLOWED_CHARS_REGEX = re.compile(r"^\+?[0-9\s\-]+$")


def validate_and_normalize_phone(value: str) -> str:
    """
    Validate phone number characters and normalize Ethiopian or international numbers.

    Rules:
    - Only digits, one optional leading +, spaces and dashes.
    - Letters are rejected.
    - Ethiopian numbers:
      - Formats: +251911223344, 0911223344, 0711223344, +251711223344, 251911223344, 251711223344
      - Normalized to ONE standard form: +251 followed by 9 digits (+2519XXXXXXXX or +2517XXXXXXXX)
    - Other international numbers:
      - 9 to 15 digits accepted, formatted with leading +
    """
    if not value or not isinstance(value, str):
        raise ValidationError("Phone number is required.")

    trimmed = value.strip()
    if not trimmed:
        raise ValidationError("Phone number cannot be empty.")

    if not PHONE_ALLOWED_CHARS_REGEX.match(trimmed):
        raise ValidationError(
            "Phone number can only contain digits, an optional leading +, spaces, and hyphens."
        )

    # Check for leading +
    has_plus = trimmed.startswith("+")
    # Extract only digits
    digits = re.sub(r"\D", "", trimmed)

    # Check total digit count
    if len(digits) < 9 or len(digits) > 15:
        raise ValidationError("Phone number must contain between 9 and 15 digits.")

    # Check for Ethiopian number forms:
    # 1. Starts with 251 and next digit is 9 or 7:
    if digits.startswith("251"):
        eth_suffix = digits[3:]
        if len(eth_suffix) != 9:
            raise ValidationError(
                "Ethiopian phone numbers must be 9 digits after +251 (e.g. +251911223344 or 0911223344)."
            )
        if not (eth_suffix.startswith("9") or eth_suffix.startswith("7")):
            raise ValidationError(
                "Ethiopian mobile numbers must start with 9 or 7 (e.g. +251911223344 or 0911223344)."
            )
        return f"+251{eth_suffix}"

    # 2. Local Ethiopian formats: 09XXXXXXXX (10 digits) or 07XXXXXXXX (10 digits)
    if digits.startswith("09") or digits.startswith("07"):
        if len(digits) != 10:
            raise ValidationError(
                "Ethiopian phone numbers must be 10 digits when starting with 0 (e.g. 0911223344 or 0711223344)."
            )
        return f"+251{digits[1:]}"

    # 3. Local 9-digit Ethiopian formats: 9XXXXXXXX or 7XXXXXXXX (9 digits)
    if (digits.startswith("9") or digits.startswith("7")) and len(digits) == 9:
        return f"+251{digits}"

    # Non-Ethiopian international numbers
    if has_plus:
        return f"+{digits}"
    return f"+{digits}"


def validate_name(value: str, field_name: str = "Name") -> str:
    """
    Validate names (full name, gym name, contact person).

    Rules:
    - Letters of any script (Amharic included).
    - Spaces, apostrophes, hyphens, dots allowed.
    - No digits allowed.
    - 2 to 100 characters.
    - Trimmed, not only spaces.
    """
    if not value or not isinstance(value, str):
        raise ValidationError(f"{field_name} is required.")

    trimmed = value.strip()
    if len(trimmed) < 2:
        raise ValidationError(f"{field_name} must be at least 2 characters.")
    if len(trimmed) > 100:
        raise ValidationError(f"{field_name} cannot exceed 100 characters.")

    has_letter = False
    for char in trimmed:
        if char.isdigit():
            raise ValidationError(f"{field_name} cannot contain digits.")
        if char.isalpha():
            has_letter = True
        elif char in " '-.":
            continue
        else:
            raise ValidationError(
                f"{field_name} can only contain letters, spaces, apostrophes, hyphens, and dots."
            )

    if not has_letter:
        raise ValidationError(f"{field_name} must contain letters.")

    return trimmed


RESERVED_TEST_DOMAINS = {
    "example.com",
    "example.org",
    "example.net",
    "example.edu",
    "localhost",
    "invalid",
    "test",
    "local",
}

RESERVED_TEST_TLDS = (
    ".test",
    ".invalid",
    ".localhost",
    ".local",
    ".example",
)


def is_reserved_test_domain(domain: str) -> bool:
    """Return True if domain is an RFC-reserved test or documentation domain."""
    d = domain.strip().lower()
    if d in RESERVED_TEST_DOMAINS:
        return True
    return any(d.endswith(tld) for tld in RESERVED_TEST_TLDS)


def check_domain_dns_accepts_mail(domain: str, timeout: float = 2.0) -> None:
    """
    Checks if domain exists in DNS with a short timeout.
    Definite non-existence (NXDOMAIN) raises ValidationError.
    If lookup itself times out or has a network/DNS error, log warning and accept.
    """
    import logging
    import socket

    logger = logging.getLogger(__name__)

    try:
        orig_timeout = socket.getdefaulttimeout()
        socket.setdefaulttimeout(timeout)
        try:
            socket.getaddrinfo(domain, None)
        finally:
            socket.setdefaulttimeout(orig_timeout)
    except socket.gaierror as e:
        err_msg = str(e).lower()
        if (
            (hasattr(socket, "EAI_NONAME") and e.errno == socket.EAI_NONAME)
            or "name or service not known" in err_msg
            or "nodename nor servname provided" in err_msg
            or "getaddrinfo failed" in err_msg
            or e.errno in (-2, 11001, 8)
        ):
            raise ValidationError("Domain does not exist or cannot accept mail.")
        logger.warning(
            "DNS lookup failed for domain %s (network error), accepting without blocking: %s",
            domain,
            e,
        )
    except (socket.timeout, TimeoutError, OSError) as e:
        logger.warning(
            "DNS lookup timed out or had network error for domain %s, accepting without blocking: %s",
            domain,
            e,
        )


_email_validator = EmailValidator(message="Enter a valid email address.")


def validate_email_address(
    value: str,
    is_public_registration: bool = False,
    is_lenient: bool = False,
) -> str:
    """
    Validate email address format, length up to 254 chars, and store lowercase.

    Under EMAIL_STRICT_MODE:
    - Blocks reserved test domains with 'Use a real email address'.
    - Blocks disposable domains for public registration.
    - Performs fast DNS check (unless is_lenient is True).
    """
    from django.conf import settings

    from apps.accounts.disposable_domains import DISPOSABLE_EMAIL_DOMAINS

    if not value or not isinstance(value, str):
        raise ValidationError("Email address is required.")

    trimmed = value.strip().lower()
    if len(trimmed) > 254:
        raise ValidationError("Email address cannot exceed 254 characters.")

    _email_validator(trimmed)

    domain = trimmed.split("@")[-1].strip()
    strict_mode = getattr(settings, "EMAIL_STRICT_MODE", False)

    if strict_mode:
        if is_reserved_test_domain(domain):
            raise ValidationError("Use a real email address")

        if is_public_registration and domain in DISPOSABLE_EMAIL_DOMAINS:
            raise ValidationError(
                "Disposable email addresses are not allowed. Please use a permanent email address."
            )

        if not is_lenient:
            check_domain_dns_accepts_mail(domain)
    else:
        if is_public_registration and domain in DISPOSABLE_EMAIL_DOMAINS:
            raise ValidationError(
                "Disposable email addresses are not allowed. Please use a permanent email address."
            )

    return trimmed


def validate_weight(value: Union[Decimal, float, int, str]) -> Decimal:
    """Weight must be between 20.00 and 400.00 kg, max 2 decimals."""
    try:
        val = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValidationError("Weight must be a valid number.")

    if val.as_tuple().exponent < -2:
        raise ValidationError("Weight cannot have more than 2 decimal places.")
    if val < Decimal("20.00") or val > Decimal("400.00"):
        raise ValidationError("Weight must be between 20 and 400 kg.")
    return val


def validate_height(value: Union[Decimal, float, int, str]) -> Decimal:
    """Height must be between 50.00 and 260.00 cm, max 2 decimals."""
    try:
        val = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValidationError("Height must be a valid number.")

    if val.as_tuple().exponent < -2:
        raise ValidationError("Height cannot have more than 2 decimal places.")
    if val < Decimal("50.00") or val > Decimal("260.00"):
        raise ValidationError("Height must be between 50 and 260 cm.")
    return val


def validate_waist(
    value: Optional[Union[Decimal, float, int, str]],
) -> Optional[Decimal]:
    """Waist must be between 40.00 and 200.00 cm, max 2 decimals."""
    if value is None or value == "":
        return None
    try:
        val = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValidationError("Waist must be a valid number.")

    if val.as_tuple().exponent < -2:
        raise ValidationError("Waist cannot have more than 2 decimal places.")
    if val < Decimal("40.00") or val > Decimal("200.00"):
        raise ValidationError("Waist circumference must be between 40 and 200 cm.")
    return val


def validate_neck(
    value: Optional[Union[Decimal, float, int, str]],
) -> Optional[Decimal]:
    """Neck must be between 20.00 and 80.00 cm, max 2 decimals."""
    if value is None or value == "":
        return None
    try:
        val = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValidationError("Neck must be a valid number.")

    if val.as_tuple().exponent < -2:
        raise ValidationError("Neck cannot have more than 2 decimal places.")
    if val < Decimal("20.00") or val > Decimal("80.00"):
        raise ValidationError("Neck circumference must be between 20 and 80 cm.")
    return val


def validate_hip(value: Optional[Union[Decimal, float, int, str]]) -> Optional[Decimal]:
    """Hip must be between 40.00 and 220.00 cm, max 2 decimals."""
    if value is None or value == "":
        return None
    try:
        val = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValidationError("Hip must be a valid number.")

    if val.as_tuple().exponent < -2:
        raise ValidationError("Hip cannot have more than 2 decimal places.")
    if val < Decimal("40.00") or val > Decimal("220.00"):
        raise ValidationError("Hip circumference must be between 40 and 220 cm.")
    return val


def validate_chest(
    value: Optional[Union[Decimal, float, int, str]],
) -> Optional[Decimal]:
    """Chest must be between 50.00 and 200.00 cm, max 2 decimals."""
    if value is None or value == "":
        return None
    try:
        val = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValidationError("Chest must be a valid number.")

    if val.as_tuple().exponent < -2:
        raise ValidationError("Chest cannot have more than 2 decimal places.")
    if val < Decimal("50.00") or val > Decimal("200.00"):
        raise ValidationError("Chest circumference must be between 50 and 200 cm.")
    return val


def validate_bicep(
    value: Optional[Union[Decimal, float, int, str]],
) -> Optional[Decimal]:
    """Bicep must be between 15.00 and 80.00 cm, max 2 decimals."""
    if value is None or value == "":
        return None
    try:
        val = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValidationError("Bicep must be a valid number.")

    if val.as_tuple().exponent < -2:
        raise ValidationError("Bicep cannot have more than 2 decimal places.")
    if val < Decimal("15.00") or val > Decimal("80.00"):
        raise ValidationError("Bicep circumference must be between 15 and 80 cm.")
    return val


def validate_thigh(
    value: Optional[Union[Decimal, float, int, str]],
) -> Optional[Decimal]:
    """Thigh must be between 30.00 and 120.00 cm, max 2 decimals."""
    if value is None or value == "":
        return None
    try:
        val = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValidationError("Thigh must be a valid number.")

    if val.as_tuple().exponent < -2:
        raise ValidationError("Thigh cannot have more than 2 decimal places.")
    if val < Decimal("30.00") or val > Decimal("120.00"):
        raise ValidationError("Thigh circumference must be between 30 and 120 cm.")
    return val


def validate_calf(
    value: Optional[Union[Decimal, float, int, str]],
) -> Optional[Decimal]:
    """Calf must be between 20.00 and 80.00 cm, max 2 decimals."""
    if value is None or value == "":
        return None
    try:
        val = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValidationError("Calf must be a valid number.")

    if val.as_tuple().exponent < -2:
        raise ValidationError("Calf cannot have more than 2 decimal places.")
    if val < Decimal("20.00") or val > Decimal("80.00"):
        raise ValidationError("Calf circumference must be between 20 and 80 cm.")
    return val


def validate_resting_heart_rate(
    value: Optional[Union[int, str, float]],
) -> Optional[int]:
    """Resting heart rate must be a whole number between 30 and 220 bpm."""
    if value is None or value == "":
        return None
    try:
        s = str(value).strip()
        val = int(s)
        if float(s) != val:
            raise ValueError
    except (TypeError, ValueError):
        raise ValidationError("Resting heart rate must be a whole number.")

    if val < 30 or val > 220:
        raise ValidationError("Resting heart rate must be between 30 and 220 bpm.")
    return val


def validate_body_fat_percentage(
    value: Optional[Union[Decimal, float, int, str]],
) -> Optional[Decimal]:
    """Body fat % must be between 2.00 and 70.00 %, max 2 decimals."""
    if value is None or value == "":
        return None
    try:
        val = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValidationError("Body fat percentage must be a valid number.")

    if val.as_tuple().exponent < -2:
        raise ValidationError(
            "Body fat percentage cannot have more than 2 decimal places."
        )
    if val < Decimal("2.00") or val > Decimal("70.00"):
        raise ValidationError("Body fat percentage must be between 2 and 70 %.")
    return val


def validate_payment_amount(value: Union[Decimal, float, int, str]) -> Decimal:
    """Payment amount must be greater than 0 with at most 2 decimals and <= 10,000,000 ETB."""
    try:
        val = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValidationError("Payment amount must be a valid number.")

    if val.as_tuple().exponent < -2:
        raise ValidationError("Payment amount cannot have more than 2 decimal places.")
    if val <= Decimal("0"):
        raise ValidationError("Payment amount must be greater than 0.")
    if val > Decimal("10000000.00"):
        raise ValidationError("Payment amount cannot exceed 10,000,000 ETB.")
    return val


def clamp_page_size(
    value: Union[int, str, None], default: int = 20, max_size: int = 100
) -> int:
    """Clamp page size to range 1 to 100."""
    if value is None or value == "":
        return default
    try:
        val = int(value)
    except (ValueError, TypeError):
        return default

    if val < 1:
        return 1
    if val > max_size:
        return max_size
    return val


def validate_date_of_birth(value: Union[datetime.date, str]) -> datetime.date:
    """Date of birth cannot be in the future and not older than 120 years."""
    if isinstance(value, str):
        try:
            val = datetime.date.fromisoformat(value)
        except ValueError:
            raise ValidationError("Date of birth must be a valid date (YYYY-MM-DD).")
    elif isinstance(value, datetime.date):
        val = value
    else:
        raise ValidationError("Date of birth must be a valid date.")

    today = datetime.date.today()
    if val > today:
        raise ValidationError("Date of birth cannot be in the future.")

    # 120 years ago
    earliest_date = datetime.date(today.year - 120, today.month, today.day)
    if val < earliest_date:
        raise ValidationError("Date of birth cannot be older than 120 years.")
    return val


def validate_date_range(
    from_date: Optional[Union[datetime.date, str]],
    to_date: Optional[Union[datetime.date, str]],
) -> None:
    """Validate that from_date is not after to_date."""
    if not from_date or not to_date:
        return

    def parse_d(d):
        if isinstance(d, str):
            return datetime.date.fromisoformat(d)
        return d

    try:
        f = parse_d(from_date)
        t = parse_d(to_date)
    except (ValueError, TypeError):
        return

    if f > t:
        raise ValidationError("From date cannot be after to date.")


def validate_text_length(
    value: str,
    min_len: int = 1,
    max_len: int = 500,
    field_name: str = "Text",
) -> str:
    """Trim text and validate length within min_len and max_len."""
    if value is None:
        if min_len > 0:
            raise ValidationError(f"{field_name} is required.")
        return ""

    trimmed = str(value).strip()
    if len(trimmed) < min_len:
        raise ValidationError(
            f"{field_name} must be at least {min_len} character{'s' if min_len != 1 else ''}."
        )
    if len(trimmed) > max_len:
        raise ValidationError(f"{field_name} cannot exceed {max_len} characters.")
    return trimmed


VALID_GOALS = ["fat_loss", "muscle_gain", "strength", "endurance", "general_fitness"]
VALID_FITNESS_LEVELS = ["beginner", "intermediate", "advanced"]
VALID_SESSION_LENGTHS = [30, 45, 60, 90]


def validate_goal(value: str) -> str:
    """Validate goal selection against allowed choices."""
    if not value or not str(value).strip():
        raise ValidationError("Goal is required.")
    val = str(value).strip().lower()
    if val not in VALID_GOALS:
        raise ValidationError(
            f"Invalid goal: '{val}'. Must be one of {', '.join(VALID_GOALS)}."
        )
    return val


def validate_fitness_level(value: str) -> str:
    """Validate self-reported / trainer-assessed fitness level."""
    if not value or not str(value).strip():
        raise ValidationError("Fitness level is required.")
    val = str(value).strip().lower()
    if val not in VALID_FITNESS_LEVELS:
        raise ValidationError(
            f"Invalid fitness level: '{val}'. Must be one of {', '.join(VALID_FITNESS_LEVELS)}."
        )
    return val


def validate_training_days_per_week(value: Union[int, str]) -> int:
    """Validate training days per week (whole number 2 to 6)."""
    try:
        val = int(value)
    except (ValueError, TypeError):
        raise ValidationError("Training days must be a whole number between 2 and 6.")
    if val < 2 or val > 6:
        raise ValidationError("Training days must be a whole number between 2 and 6.")
    return val


def validate_session_length(value: Union[int, str]) -> int:
    """Validate session length (30, 45, 60, or 90 minutes)."""
    try:
        val = int(value)
    except (ValueError, TypeError):
        raise ValidationError("Session length must be 30, 45, 60, or 90 minutes.")
    if val not in VALID_SESSION_LENGTHS:
        raise ValidationError("Session length must be 30, 45, 60, or 90 minutes.")
    return val


def validate_dietary_notes(value: Optional[str]) -> str:
    """Validate optional dietary notes up to 1000 characters."""
    if not value:
        return ""
    val = str(value).strip()
    if len(val) > 1000:
        raise ValidationError("Dietary notes cannot exceed 1000 characters.")
    return val


def validate_trainer_note_for_week(value: Optional[str]) -> str:
    """Validate optional weekly focus note up to 500 characters."""
    if not value:
        return ""
    val = str(value).strip()
    if len(val) > 500:
        raise ValidationError("Trainer note cannot exceed 500 characters.")
    return val


def validate_rejection_reason(value: str) -> str:
    """Validate required rejection reason between 5 and 500 characters."""
    if not value or not str(value).strip():
        raise ValidationError("Reason must be between 5 and 500 characters.")
    val = str(value).strip()
    if len(val) < 5 or len(val) > 500:
        raise ValidationError("Reason must be between 5 and 500 characters.")
    return val


def validate_checkin_score(value: Union[int, str], field_name: str = "Score") -> int:
    """Validate check-in score between 1 and 5."""
    try:
        val = int(value)
    except (ValueError, TypeError):
        raise ValidationError(f"{field_name} must be an integer between 1 and 5.")
    if val < 1 or val > 5:
        raise ValidationError(f"{field_name} must be an integer between 1 and 5.")
    return val
