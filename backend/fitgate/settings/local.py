"""Local development settings for FitGate."""

from pathlib import Path

from .base import *
from .hosts import build_allowed_hosts

DEBUG = env.bool("DEBUG", default=True)
DOCS_PUBLIC = env.bool("DOCS_PUBLIC", default=True)

DEV_TUNNEL_HOST = env.str("DEV_TUNNEL_HOST", default="").strip().lower()
if DEV_TUNNEL_HOST.startswith("http://"):
    DEV_TUNNEL_HOST = DEV_TUNNEL_HOST[7:]
elif DEV_TUNNEL_HOST.startswith("https://"):
    DEV_TUNNEL_HOST = DEV_TUNNEL_HOST[8:]
DEV_TUNNEL_HOST = DEV_TUNNEL_HOST.split("/")[0].split(":")[0].strip()

_extra_hosts = ["localhost", "127.0.0.1", "backend"]
if DEV_TUNNEL_HOST and DEV_TUNNEL_HOST not in _extra_hosts:
    _extra_hosts.append(DEV_TUNNEL_HOST)

ALLOWED_HOSTS = build_allowed_hosts(
    DOMAIN,
    env.list("ALLOWED_HOSTS", default=[]),
    extra=tuple(_extra_hosts),
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
EMAIL_BACKEND = env.str(
    "EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend"
)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="webmaster@localhost")
EMAIL_HOST = env.str("EMAIL_HOST", default="localhost")
EMAIL_PORT = env.int("EMAIL_PORT", default=25)
EMAIL_HOST_USER = env.str("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env.str("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=False)
EMAIL_USE_SSL = env.bool("EMAIL_USE_SSL", default=False)

# cPanel UAPI settings (mocked by default in dev)
CPANEL_USE_MOCK = env.bool("CPANEL_USE_MOCK", default=True)
CPANEL_HOST = env.str("CPANEL_HOST", default="")
CPANEL_USERNAME = env.str("CPANEL_USERNAME", default="")
CPANEL_API_TOKEN = env.str("CPANEL_API_TOKEN", default="")
CPANEL_ROOT_DOMAIN = env.str("CPANEL_ROOT_DOMAIN", default="localhost")
CPANEL_SUBDOMAIN_DOCROOT = env.str(
    "CPANEL_SUBDOMAIN_DOCROOT", default="public_html/fitgate"
)

# Optional PostgreSQL 13 override for pre-release validation runs against PG 13 containers
if env.bool("ALLOW_POSTGRES_13", default=False):
    from django.db.backends.postgresql.features import DatabaseFeatures

    DatabaseFeatures.minimum_database_version = (13,)

# Media & Logging
MEDIA_ROOT = Path(env("MEDIA_ROOT", default=str(BASE_DIR / "media")))
LOG_DIR = Path(env("LOG_DIR", default=str(BASE_DIR / "logs")))

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

# Tenant payment credentials encryption key (no default secret in code per AGENT.md rule 14)
TENANT_CREDENTIALS_KEY = env("TENANT_CREDENTIALS_KEY")
