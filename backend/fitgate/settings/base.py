"""Base settings for FitGate project."""

from datetime import timedelta
from pathlib import Path

import environ

from .hosts import build_allowed_hosts

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Initialize environment parser
env = environ.Env()

# Look for .env in project root or current working dir if present
ENV_PATH = BASE_DIR.parent / ".env"
if ENV_PATH.exists():
    environ.Env.read_env(str(ENV_PATH))
elif (BASE_DIR / ".env").exists():
    environ.Env.read_env(str(BASE_DIR / ".env"))

SECRET_KEY = env("DJANGO_SECRET_KEY")
DOMAIN = env("DOMAIN")
JWT_SIGNING_KEY = env("JWT_SIGNING_KEY")

# JWT Lifetimes & Lockout (configurable settings)
JWT_ACCESS_TOKEN_LIFETIME = timedelta(minutes=15)
JWT_REFRESH_TOKEN_LIFETIME = timedelta(days=7)
LOGIN_LOCKOUT_MINUTES = 15

# Password reset settings (Sprint 3)
PASSWORD_RESET_TOKEN_MINUTES = 60
PASSWORD_RESET_COOLDOWN_SECONDS = 120
PUBLIC_URL_SCHEME = "https"

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
]


MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
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

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

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


# drf-spectacular configuration
SPECTACULAR_SETTINGS = {
    "TITLE": "FitGate API",
    "DESCRIPTION": "Multi-tenant Gym Management Platform API for Ethiopian Gyms",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
}
