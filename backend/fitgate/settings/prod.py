"""Production settings for FitGate (cPanel Passenger WSGI deployment)."""

from .base import *
from .hosts import build_allowed_hosts

DEBUG = False

ALLOWED_HOSTS = build_allowed_hosts(
    DOMAIN,
    env.list("ALLOWED_HOSTS", default=[]),
)

DATABASES = {"default": env.db("DATABASE_URL")}

# In production on Yegara cPanel, Redis is unconfirmed.
# If REDIS_URL is provided, use it; otherwise fallback to LocMem or Database cache.
if "REDIS_URL" in env:
    CACHES = {"default": env.cache_url("REDIS_URL")}
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "fitgate-prod-cache",
        }
    }

# HTTPS & Security Headers
# Note: cPanel AutoSSL may have an issuance window; see Sprint 4 & Sprint 38
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS")
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS")

# Email - Configured via environment in production
if "EMAIL_BACKEND" in env:
    EMAIL_BACKEND = env("EMAIL_BACKEND")
else:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
