"""Asymmetric cryptography and compact JWT operations for QR check-in (Ed25519 / EdDSA)."""

import base64
import hashlib
import uuid
from typing import Tuple, Union

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
from django.conf import settings


class QRTokenCryptoError(Exception):
    """Base exception for QR token crypto operations."""

    pass


class TokenExpiredError(QRTokenCryptoError):
    """Raised when QR token has exceeded its expiration window."""

    pass


class InvalidTokenError(QRTokenCryptoError):
    """Raised when QR token signature is invalid, tampered with, or malformed."""

    pass


def uuid_to_compact_id(val: Union[uuid.UUID, str]) -> str:
    """Encode a UUID into a compact 22-character base64url string without padding."""
    if isinstance(val, str):
        val = uuid.UUID(val)
    return base64.urlsafe_b64encode(val.bytes).rstrip(b"=").decode("ascii")


def compact_id_to_uuid(val: str) -> uuid.UUID:
    """Decode a 22-character base64url string or standard 36-char string to UUID."""
    val_str = str(val).strip()
    if len(val_str) == 22:
        padded = val_str + "=" * (-len(val_str) % 4)
        return uuid.UUID(bytes=base64.urlsafe_b64decode(padded))
    return uuid.UUID(val_str)


def generate_ed25519_keypair(*args, **kwargs) -> Tuple[str, str]:
    """Generate an Ed25519 keypair and return (private_pem, public_pem) as strings."""
    private_key = ed25519.Ed25519PrivateKey.generate()
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")

    public_pem = (
        private_key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode("utf-8")
    )
    return private_pem, public_pem


# Backward-compatible alias
generate_rsa_keypair = generate_ed25519_keypair


def get_ed25519_private_key_pem() -> str:
    """
    Retrieve Ed25519 private key PEM from settings.QR_JWT_PRIVATE_KEY.

    Fails fast if unset. Validates that the configured key is an Ed25519 private key.
    Converts literal "\\n" escapes back to newlines while preserving multi-line PEM.
    """
    config_key = getattr(settings, "QR_JWT_PRIVATE_KEY", None)
    if not config_key or not str(config_key).strip():
        raise QRTokenCryptoError("QR_JWT_PRIVATE_KEY is not configured.")

    pem_str = str(config_key).strip().replace("\\n", "\n")
    try:
        loaded_key = serialization.load_pem_private_key(
            pem_str.encode("utf-8"), password=None
        )
        if not isinstance(loaded_key, ed25519.Ed25519PrivateKey):
            raise QRTokenCryptoError(
                "Configured QR_JWT_PRIVATE_KEY is not an Ed25519 key. "
                "Please run python manage.py generate_qr_dev_keys to generate an Ed25519 keypair."
            )
    except QRTokenCryptoError:
        raise
    except Exception as e:
        raise QRTokenCryptoError(
            f"Configured QR_JWT_PRIVATE_KEY is invalid or malformed: {e}. "
            "Please run python manage.py generate_qr_dev_keys to generate an Ed25519 keypair."
        ) from e

    return pem_str


# Backward-compatible alias
get_rsa_private_key_pem = get_ed25519_private_key_pem


def get_ed25519_public_key_pem() -> str:
    """
    Retrieve Ed25519 public key PEM from settings.QR_JWT_PUBLIC_KEY.

    Fails fast if unset. Validates that the configured key is an Ed25519 public key.
    Converts literal "\\n" escapes back to newlines while preserving multi-line PEM.
    """
    config_key = getattr(settings, "QR_JWT_PUBLIC_KEY", None)
    if not config_key or not str(config_key).strip():
        raise QRTokenCryptoError("QR_JWT_PUBLIC_KEY is not configured.")

    pem_str = str(config_key).strip().replace("\\n", "\n")
    try:
        loaded_key = serialization.load_pem_public_key(pem_str.encode("utf-8"))
        if not isinstance(loaded_key, ed25519.Ed25519PublicKey):
            raise QRTokenCryptoError(
                "Configured QR_JWT_PUBLIC_KEY is not an Ed25519 key. "
                "Please run python manage.py generate_qr_dev_keys to generate an Ed25519 keypair."
            )
    except QRTokenCryptoError:
        raise
    except Exception as e:
        raise QRTokenCryptoError(
            f"Configured QR_JWT_PUBLIC_KEY is invalid or malformed: {e}. "
            "Please run python manage.py generate_qr_dev_keys to generate an Ed25519 keypair."
        ) from e

    return pem_str


# Backward-compatible alias
get_rsa_public_key_pem = get_ed25519_public_key_pem


def hash_token(token: str) -> str:
    """Compute SHA-256 hex digest of a token string."""
    return hashlib.sha256(token.strip().encode("utf-8")).hexdigest()


def sign_qr_payload(payload: dict) -> str:
    """Sign compact payload using EdDSA (Ed25519) with the configured private key."""
    private_pem = get_ed25519_private_key_pem()
    return jwt.encode(
        payload,
        private_pem,
        algorithm="EdDSA",
        headers={"typ": "fg-qr"},
    )


def verify_qr_jwt(token: str) -> dict:
    """
    Verify and decode EdDSA token using the configured public key.

    Enforces:
    - Algorithm strictly pinned to EdDSA (never accepts RS256, HS256, none, etc.)
    - Required 'exp' claim with zero clock leeway
    - Raises TokenExpiredError if expired.
    - Raises InvalidTokenError if tampered, wrong algorithm, or invalid.
    """
    public_pem = get_ed25519_public_key_pem()
    try:
        unverified_header = jwt.get_unverified_header(token)
        if unverified_header.get("alg") != "EdDSA":
            raise InvalidTokenError(
                f"Invalid algorithm '{unverified_header.get('alg')}'. Only EdDSA is permitted."
            )
        if unverified_header.get("typ") not in ("fg-qr", "qr_checkin"):
            raise InvalidTokenError(
                f"Invalid token type '{unverified_header.get('typ')}'. Only 'fg-qr' is permitted."
            )

        payload = jwt.decode(
            token,
            public_pem,
            algorithms=["EdDSA"],
            options={"verify_exp": True, "require": ["exp"]},
            leeway=0,
        )
        return payload
    except jwt.ExpiredSignatureError as e:
        raise TokenExpiredError("Token has expired.") from e
    except (jwt.PyJWTError, InvalidTokenError) as e:
        raise InvalidTokenError(f"Invalid token signature: {e}") from e
