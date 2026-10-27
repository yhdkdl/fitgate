"""Production settings for FitGate (cPanel Passenger WSGI deployment)."""

from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from django.db.backends.postgresql.features import DatabaseFeatures

from .base import *
from .hosts import build_allowed_hosts

# Allow PostgreSQL 13.x for Yegara cPanel production host (runs PostgreSQL 13.23)
DatabaseFeatures.minimum_database_version = (13,)

DEBUG = False
DOCS_PUBLIC = False

# Allowed hosts strictly restricted to the platform apex host and every subdomain of DOMAIN.
# No wildcards (*).
ALLOWED_HOSTS = build_allowed_hosts(
    DOMAIN,
    env.list("ALLOWED_HOSTS", default=[]),
)
CSRF_TRUSTED_ORIGINS = [f"https://{DOMAIN}", f"https://*.{DOMAIN}"]

# The SPA is served from the same host, so no external CORS origins are needed by default.
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = []

# Database - fails fast if DATABASE_URL is missing
DATABASES = {"default": env.db("DATABASE_URL")}

# In production on Yegara cPanel, Redis is unconfirmed.
# If REDIS_URL is provided, use it; otherwise fallback to LocMem or Database cache.
if "REDIS_URL" in env:
    CACHES["default"] = env.cache_url("REDIS_URL")
else:
    CACHES["default"] = {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "fitgate-prod-cache",
    }

# HTTPS & Security Headers
# Host terminates HTTPS directly and sends no X-Forwarded-* headers (wsgi.url_scheme is https).
# Do NOT set SECURE_PROXY_SSL_HEADER.
SECURE_PROXY_SSL_HEADER = None

# Certificate safeguard: do not force HTTPS redirect or HSTS globally until AutoSSL certificates
# are confirmed for each gym domain (handled via TenantSubdomainMiddleware).
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

# cPanel UAPI Subdomain Provisioning
# In production, CPANEL_USE_MOCK has NO default and fails fast if missing.
CPANEL_USE_MOCK = env.bool("CPANEL_USE_MOCK")
if not CPANEL_USE_MOCK:
    CPANEL_HOST = env("CPANEL_HOST")
    CPANEL_USERNAME = env("CPANEL_USERNAME")
    CPANEL_API_TOKEN = env("CPANEL_API_TOKEN")
    CPANEL_ROOT_DOMAIN = env("CPANEL_ROOT_DOMAIN")
    CPANEL_SUBDOMAIN_DOCROOT = env("CPANEL_SUBDOMAIN_DOCROOT")
else:
    CPANEL_HOST = env.str("CPANEL_HOST", default="")
    CPANEL_USERNAME = env.str("CPANEL_USERNAME", default="")
    CPANEL_API_TOKEN = env.str("CPANEL_API_TOKEN", default="")
    CPANEL_ROOT_DOMAIN = env.str("CPANEL_ROOT_DOMAIN", default="")
    CPANEL_SUBDOMAIN_DOCROOT = env.str("CPANEL_SUBDOMAIN_DOCROOT", default="")

# Secrets & Asymmetric Encryption Keys - fails fast with NO defaults
TENANT_CREDENTIALS_KEY = env("TENANT_CREDENTIALS_KEY")
QR_JWT_PRIVATE_KEY = env("QR_JWT_PRIVATE_KEY")
QR_JWT_PUBLIC_KEY = env("QR_JWT_PUBLIC_KEY")

# Email - fails fast if unset in production (supports Brevo on 587 and Resend on 465)
EMAIL_BACKEND = env.str(
    "EMAIL_BACKEND", default="django.core.mail.backends.smtp.EmailBackend"
)
EMAIL_HOST = env("EMAIL_HOST")
EMAIL_PORT = env.int("EMAIL_PORT")
EMAIL_HOST_USER = env("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD")
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS")
EMAIL_USE_SSL = env.bool("EMAIL_USE_SSL")

if EMAIL_USE_TLS and EMAIL_USE_SSL:
    raise ImproperlyConfigured("EMAIL_USE_TLS and EMAIL_USE_SSL cannot both be True.")

DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL")

# Email Safety & Brevo Webhook - fails fast with NO defaults in production
EMAIL_STRICT_MODE = env.bool("EMAIL_STRICT_MODE")
BREVO_WEBHOOK_SECRET = env("BREVO_WEBHOOK_SECRET")
EMAIL_ALLOWED_RECIPIENTS = [
    r.strip().lower()
    for r in env.list("EMAIL_ALLOWED_RECIPIENTS", default=[])
    if r.strip()
]
EMAIL_HOURLY_CAP_PER_GYM = env.int("EMAIL_HOURLY_CAP_PER_GYM", default=100)
EMAIL_HOURLY_CAP_PLATFORM = env.int("EMAIL_HOURLY_CAP_PLATFORM", default=500)

# Files & Persistent Storage outside release folder and public_html
MEDIA_ROOT = Path(env("MEDIA_ROOT"))
MEDIA_ROOT.mkdir(parents=True, exist_ok=True)

# Static Files - Whitenoise storage and direct serving of built React SPA
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}
WHITENOISE_ROOT = str(FRONTEND_DIST_DIR) if FRONTEND_DIST_DIR.exists() else None

# Production Logging - Rotating file in LOG_DIR and stderr, with sensitive data scrubbed
LOG_DIR = Path(env("LOG_DIR"))
LOG_DIR.mkdir(parents=True, exist_ok=True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "sensitive_data_filter": {
            "()": "fitgate.logging_filters.SensitiveDataFilter",
        },
    },
    "formatters": {
        "verbose": {
            "format": "[{asctime}] {levelname} {name} {process:d} {thread:d} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "filters": ["sensitive_data_filter"],
            "formatter": "verbose",
        },
        "rotating_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(LOG_DIR / "fitgate.log"),
            "maxBytes": 10 * 1024 * 1024,  # 10 MB
            "backupCount": 5,
            "filters": ["sensitive_data_filter"],
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console", "rotating_file"],
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console", "rotating_file"],
            "level": "INFO",
            "propagate": False,
        },
        "apps": {
            "handlers": ["console", "rotating_file"],
            "level": "INFO",
            "propagate": False,
        },
    },
}
