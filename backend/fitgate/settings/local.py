"""Local development settings for FitGate."""

from .base import *
from .hosts import build_allowed_hosts

DEBUG = env.bool("DEBUG", default=True)

ALLOWED_HOSTS = build_allowed_hosts(
    DOMAIN,
    env.list("ALLOWED_HOSTS", default=[]),
    extra=("localhost", "127.0.0.1", "backend"),
)

TENANT_EXTRA_PLATFORM_HOSTS = ["localhost", "127.0.0.1", "backend", "testserver"]
PUBLIC_URL_SCHEME = "http"
PUBLIC_PORT = env.str("PUBLIC_PORT", default="5173")


DATABASES = {
    "default": env.db(
        "DATABASE_URL",
        default="postgres://postgres:postgres@postgres:5432/fitgate_dev",
    )
}

# Cache - Redis for local dev container
CACHES["default"] = env.cache_url(
    "REDIS_URL",
    default="redis://redis:6379/1",
)

# CORS / CSRF for local dev
CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOWED_ORIGINS = env.list(
    "CORS_ALLOWED_ORIGINS",
    default=["http://localhost:5173", "http://127.0.0.1:5173"],
)
CSRF_TRUSTED_ORIGINS = env.list(
    "CSRF_TRUSTED_ORIGINS",
    default=[
        "http://localhost:5173",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ],
)

# Email - Console backend for local development
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="webmaster@localhost")

# QR Check-in Ed25519 Dev Keypair Fallback (if unset in local .env)
_DEV_QR_PRIVATE_KEY = (
    "-----BEGIN PRIVATE KEY-----\n"
    "MC4CAQAwBQYDK2VwBCIEIDN8SQhCAypGZ7rE54JMyzslbG/e3bn19bBXujZZykkJ\n"
    "-----END PRIVATE KEY-----"
)
_DEV_QR_PUBLIC_KEY = (
    "-----BEGIN PUBLIC KEY-----\n"
    "MCowBQYDK2VwAyEAK6VBortsZz8Wi+nutcLI/nFBAlBDxX9/mdhcdditoTY=\n"
    "-----END PUBLIC KEY-----"
)

if not QR_JWT_PRIVATE_KEY:
    QR_JWT_PRIVATE_KEY = env.str("QR_JWT_PRIVATE_KEY", default=_DEV_QR_PRIVATE_KEY)
if not QR_JWT_PUBLIC_KEY:
    QR_JWT_PUBLIC_KEY = env.str("QR_JWT_PUBLIC_KEY", default=_DEV_QR_PUBLIC_KEY)
