"""Base settings for FitGate project."""

import os
from datetime import timedelta
from pathlib import Path

import environ

from .hosts import build_allowed_hosts

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Initialize environment parser
env = environ.Env()

# Look for explicit environment file path or standard external locations
FITGATE_ENV_FILE = os.environ.get("FITGATE_ENV_FILE")
if FITGATE_ENV_FILE and Path(FITGATE_ENV_FILE).exists():
    environ.Env.read_env(FITGATE_ENV_FILE)
else:
    home_env = Path.home() / "fitgate_env" / ".env"
    parent_env = BASE_DIR.parent.parent / "fitgate_env" / ".env"
    if home_env.exists():
        environ.Env.read_env(str(home_env))
    elif parent_env.exists():
        environ.Env.read_env(str(parent_env))
    elif (BASE_DIR.parent / ".env").exists():
        environ.Env.read_env(str(BASE_DIR.parent / ".env"))
    elif (BASE_DIR / ".env").exists():
        environ.Env.read_env(str(BASE_DIR / ".env"))

SECRET_KEY = env("SECRET_KEY", default=env.str("DJANGO_SECRET_KEY", default=""))
if not SECRET_KEY:
    SECRET_KEY = env("SECRET_KEY")
DOMAIN = env("DOMAIN")
JWT_SIGNING_KEY = env("JWT_SIGNING_KEY", default=SECRET_KEY)

# JWT Lifetimes & Lockout (configurable settings)
JWT_ACCESS_TOKEN_LIFETIME = timedelta(minutes=15)
JWT_REFRESH_TOKEN_LIFETIME = timedelta(days=7)
LOGIN_LOCKOUT_MINUTES = 15

# Password reset settings (Sprint 3)
PASSWORD_RESET_TOKEN_MINUTES = 60
PASSWORD_RESET_COOLDOWN_SECONDS = 120
PUBLIC_URL_SCHEME = "https"
PUBLIC_PORT = env.str("PUBLIC_PORT", default="")

# Multi-tenancy platform hosts (empty by default in production)
TENANT_EXTRA_PLATFORM_HOSTS: list[str] = []

# Allowed hosts derived from DOMAIN without wildcard
ALLOWED_HOSTS = build_allowed_hosts(DOMAIN)

# Custom User Model
AUTH_USER_MODEL = "accounts.User"

# Application definition
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third party apps
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "drf_spectacular",
    # FitGate apps
    "apps.tenants.apps.TenantsConfig",
    "apps.accounts.apps.AccountsConfig",
    "apps.payments.apps.PaymentsConfig",
    "apps.memberships.apps.MembershipsConfig",
    "apps.attendance.apps.AttendanceConfig",
]


MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "apps.tenants.middleware.TenantSubdomainMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "fitgate.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "fitgate.wsgi.application"
ASGI_APPLICATION = "fitgate.asgi.application"

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
        "OPTIONS": {
            "user_attributes": ("email", "full_name"),
        },
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {
            "min_length": 10,
        },
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Africa/Addis_Ababa"
USE_I18N = True
USE_TZ = True

# Static & Media files
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

FRONTEND_DIST_DIR = BASE_DIR.parent / "frontend" / "dist"
STATICFILES_DIRS = [FRONTEND_DIST_DIR] if FRONTEND_DIST_DIR.exists() else []

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

# Cloudinary / File Storage settings (Sprint 4b)
CLOUDINARY_CLOUD_NAME = env.str("CLOUDINARY_CLOUD_NAME", default="")
CLOUDINARY_API_KEY = env.str("CLOUDINARY_API_KEY", default="")
CLOUDINARY_API_SECRET = env.str("CLOUDINARY_API_SECRET", default="")
MAX_UPLOAD_SIZE_BYTES = 2 * 1024 * 1024  # 2 MB limit per SPEC §4b

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Cache configuration (database cache for rate limiting / non-Redis environments)
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "fitgate-default-cache",
    },
    "db_cache": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "fitgate_cache_table",
    },
}

# Django REST Framework
REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "apps.accounts.authentication.FitGateJWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "apps.accounts.permissions.RequirePasswordChanged",
        "rest_framework.permissions.IsAuthenticated",
    ),
}

# SimpleJWT configuration
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": JWT_ACCESS_TOKEN_LIFETIME,
    "REFRESH_TOKEN_LIFETIME": JWT_REFRESH_TOKEN_LIFETIME,
    "SIGNING_KEY": JWT_SIGNING_KEY,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "AUTH_HEADER_NAME": "HTTP_AUTHORIZATION",
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}

# QR Check-in Asymmetric Token Configuration (Sprint 8)
QR_JWT_PRIVATE_KEY = env.str("QR_JWT_PRIVATE_KEY", default="")
QR_JWT_PUBLIC_KEY = env.str("QR_JWT_PUBLIC_KEY", default="")
QR_TOKEN_WINDOW_SECONDS = 90


# drf-spectacular configuration
SPECTACULAR_SETTINGS = {
    "TITLE": "FitGate API",
    "DESCRIPTION": "Multi-tenant Gym Management Platform API for Ethiopian Gyms",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "ENUM_NAME_OVERRIDES": {
        "GymStatusEnum": "apps.tenants.models.GymTenant.STATUS_CHOICES",
        "DemoRequestStatusEnum": "apps.tenants.models.DemoRequest.STATUS_CHOICES",
        "PaymentStatusEnum": "apps.payments.models.Payment.STATUS_CHOICES",
        "UserRoleEnum": "apps.accounts.models.User.ROLE_CHOICES",
    },
}

# API documentation permissions (overridden in local.py / prod.py)
DOCS_PUBLIC = False
