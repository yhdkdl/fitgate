"""Encryption and credential masking utilities for tenant payment configurations."""

import base64
import logging
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings

logger = logging.getLogger(__name__)


def _get_fernet() -> Fernet:
    """
    Construct a Fernet cipher instance using TENANT_CREDENTIALS_KEY.
    Requires a valid 32-byte secret key or standard 44-character urlsafe-base64 key.
    Refuses to operate with an empty or missing key outside test settings.
    """
    from django.core.exceptions import ImproperlyConfigured

    raw_key = getattr(settings, "TENANT_CREDENTIALS_KEY", "")
    if not raw_key:
        raise ImproperlyConfigured(
            "TENANT_CREDENTIALS_KEY is missing or empty in settings. "
            "A 32-byte secret key is required to encrypt or decrypt tenant credentials."
        )

    if isinstance(raw_key, str):
        key_bytes = raw_key.encode("utf-8")
    elif isinstance(raw_key, bytes):
        key_bytes = raw_key
    else:
        raise ImproperlyConfigured("TENANT_CREDENTIALS_KEY must be a string or bytes.")

    # Attempt to use as-is if already a valid 32-byte base64-encoded Fernet key
    try:
        decoded = base64.urlsafe_b64decode(key_bytes)
        if len(decoded) == 32:
            return Fernet(key_bytes)
    except Exception:
        pass

    # If raw 32-byte string, encode to urlsafe base64
    if len(key_bytes) >= 32:
        normalized_32 = key_bytes[:32]
        fernet_key = base64.urlsafe_b64encode(normalized_32)
        return Fernet(fernet_key)

    raise ImproperlyConfigured(
        "TENANT_CREDENTIALS_KEY must be at least 32 bytes or a valid 44-character urlsafe-base64 key."
    )


def encrypt_credential(plaintext: Optional[str]) -> str:
    """
    Encrypt a plaintext secret credential using Fernet symmetric encryption.
    Returns the ciphertext string to be stored at rest.
    """
    if not plaintext:
        return ""
    fernet = _get_fernet()
    encrypted_bytes = fernet.encrypt(plaintext.strip().encode("utf-8"))
    return encrypted_bytes.decode("ascii")


def decrypt_credential(ciphertext: Optional[str]) -> str:
    """
    Decrypt a Fernet ciphertext string from storage.
    Returns the original plaintext string, or empty string if ciphertext is empty.
    """
    if not ciphertext:
        return ""
    try:
        fernet = _get_fernet()
        decrypted_bytes = fernet.decrypt(ciphertext.encode("ascii"))
        return decrypted_bytes.decode("utf-8")
    except InvalidToken:
        logger.error(
            "Failed to decrypt tenant credential: invalid token or mismatched key."
        )
        return ""
    except Exception as exc:
        from django.core.exceptions import ImproperlyConfigured

        if isinstance(exc, ImproperlyConfigured):
            raise
        logger.error("Unexpected error decrypting credential: %s", exc)
        return ""


def mask_credential(key_str: Optional[str], visible_suffix: int = 4) -> str:
    """
    Mask a credential for safe screen display.
    Example: 'CHAPUBK_TEST-abc123xyz789' -> 'CHAPUBK_TEST-****z789'
    Example: 'CHASECK-secretvalue1234' -> 'CHASECK-****1234'
    """
    if not key_str:
        return ""
    key_str = key_str.strip()
    if "-" in key_str:
        prefix, rest = key_str.split("-", 1)
        if len(rest) <= visible_suffix:
            return f"{prefix}-****"
        return f"{prefix}-****{rest[-visible_suffix:]}"

    if len(key_str) <= visible_suffix:
        return "****"
    return f"****{key_str[-visible_suffix:]}"
