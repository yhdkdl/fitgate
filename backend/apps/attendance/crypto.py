"""Asymmetric cryptography and JWT operations for QR check-in."""

import hashlib
from typing import Tuple

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
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


def generate_rsa_keypair(key_size: int = 2048) -> Tuple[str, str]:
    """Generate an RSA keypair and return (private_pem, public_pem) as strings."""
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=key_size,
    )
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


def get_rsa_private_key_pem() -> str:
    """
    Retrieve RSA private key PEM from settings.QR_JWT_PRIVATE_KEY.
    Fails fast if unset. No runtime auto-generation permitted.
    """
    config_key = getattr(settings, "QR_JWT_PRIVATE_KEY", None)
    if config_key and str(config_key).strip():
        return str(config_key).strip()

    raise QRTokenCryptoError("QR_JWT_PRIVATE_KEY is not configured.")


def get_rsa_public_key_pem() -> str:
    """
    Retrieve RSA public key PEM from settings.QR_JWT_PUBLIC_KEY.
    Fails fast if unset. No runtime auto-generation permitted.
    """
    config_key = getattr(settings, "QR_JWT_PUBLIC_KEY", None)
    if config_key and str(config_key).strip():
        return str(config_key).strip()

    raise QRTokenCryptoError("QR_JWT_PUBLIC_KEY is not configured.")


def hash_token(token: str) -> str:
    """Compute SHA-256 hex digest of a token string."""
    return hashlib.sha256(token.strip().encode("utf-8")).hexdigest()


def sign_qr_payload(payload: dict) -> str:
    """Sign payload using RS256 with the configured private key."""
    private_pem = get_rsa_private_key_pem()
    return jwt.encode(payload, private_pem, algorithm="RS256")


def verify_qr_jwt(token: str) -> dict:
    """
    Verify and decode RS256 token using the configured public key.

    Enforces zero clock leeway.
    Raises TokenExpiredError if expired.
    Raises InvalidTokenError if tampered or invalid.
    """
    public_pem = get_rsa_public_key_pem()
    try:
        payload = jwt.decode(
            token,
            public_pem,
            algorithms=["RS256"],
            options={"verify_exp": True, "require": ["exp"]},
            leeway=0,
        )
        return payload
    except jwt.ExpiredSignatureError as e:
        raise TokenExpiredError("Token has expired.") from e
    except jwt.PyJWTError as e:
        raise InvalidTokenError(f"Invalid token signature: {e}") from e
