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

# QR Check-in RS256 Dev Keypair Fallback (if unset in local .env)
_DEV_QR_PRIVATE_KEY = (
    "-----BEGIN PRIVATE KEY-----\n"
    "MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQC0yXO5D33eE3qL\n"
    "n6u3oSS+9CN8ChJGM0Fv+bo6M/maaO52aqkgdMwpE3u5dk8tbT1EyBE2f0j34MFV\n"
    "g986Pr/7KqGYaSZ50VY/BaYJxZWTkY3LxVjp/xHVf5sePQ3BtXtdfdBUy01MMXN/\n"
    "BqOxMQ3lqgPa5EeJNdukvEXxSbayk/7Mt0i9MYXzvlp6GnQcOc40rxHdDgjESvGY\n"
    "ieJ3JltpMxIpI8NzWbWbstp233sW3uwOLx61o0MAxopmkYUQ2oQ1uxP09oMeigic\n"
    "TNZuGv2kz6RwbrOYwxDTvXRWI1z0f84bFW0vRqX2qcJ4kv5mgFKIhr6YvcQsIjbF\n"
    "5BFZ3yeHAgMBAAECggEAL+/IzRXEALo2gMZGUIschLuUmyPKg628mLXlgOBeO2i+\n"
    "bkzK6q29otilMmCiDwALwmywT7yBeySv7v5oFvgjjLRZo+Ghz6RH068qPyYSis4K\n"
    "BLGf6W/2aR+MYIC84JPAEeK19n3v0Ze9Mb3vcqD4t+CUZBqqs0HCK1S20QuEM6Zj\n"
    "SPVu57+nzIhxwgvSRQ+MmDuvkIwGnPl72QrFOVFFPWpYCyxn0xV1qYsNtIdyh+Ed\n"
    "I0lxzwKJkquUdCr3rUTQZ/8/WnodRbxf9Yyv7xDg5+R7J00z+oOuBoAD7A9czgWh\n"
    "G8wJikYdhIvxLbTmPRU81kiHdd0cCQWTqnRhtS+nWQKBgQDbv7m/z6Uj30V0gWjl\n"
    "W8aRRnxtIwUDyuHs27t3UJIIRJ5wknhFub0doZbxgliYPDr+K/6XVJJQnmt9tetz\n"
    "EXSkzKL66kukXjpmAgVlgryQwGi+De6vbhxhb9JkpiqZMaOqhpC9U+JWjXiSueOa\n"
    "tq53hAHYC8es72Fls/3d7uUHOQKBgQDSnE/SHL9xRd8Ulwz+Gl4h8BYzFT7EAeqW\n"
    "HAe+NsyP6m7w1mKdC3bTSWgTmEg7O2dBqgYV3WHBnKOszDwm1upWZrSQudtzmjo8\n"
    "CMtIWho17n6tHHP2LPgR3JW8iII6Za7UacHmR1YGBciDtpxqcQibZ+iSVqbhRA0U\n"
    "c8S+JxDkvwKBgDF0Q3xcYcDh9YKTwSSk89or78Kr9+vzk8a3aMggVM0RjEqvW+vt\n"
    "MhdiD1NIz2FrZKdhBUnPWaJVFMHU2CksS4DvINqxMdbK8f+VAtvmgUNeWfQztHy8\n"
    "nhx7ivDlyH5zgm7VG+vP3gc2jWUP+p4N8NOq3LNfa0+LC/NUf5Sbt+VZAoGAdmVd\n"
    "EfcLQDhRQhfwO+DCzj1TnX/x+upA4AX97FaOBNF7cHR0l2hcckav9WQEJxgr4eQc\n"
    "66m6TMcr0/Y0Unk63zt5gmqZDZHD7v/al1/foDXkjJiUL+3zvsbMfmIXI5EKCWsy\n"
    "j6vGljgmErVTlRraBdMSEUIZKkXBPKAgF+2KN60CgYEAiBhzG99kYaTqnBm3znOr\n"
    "9zOSSG/EqR4ecRGm+yi6jFQK+zCvv2cTZDbBaQiyIsd/jphHq94WORVekbqHMmKX\n"
    "WC6KombleUg0DqFbsum/DAZ2ZArtGYE2dfY64zdd8ob8Yw7mm2sZgToWjZRjcDer\n"
    "/STe66sgxgzcWPi48blVhbk=\n"
    "-----END PRIVATE KEY-----"
)
_DEV_QR_PUBLIC_KEY = (
    "-----BEGIN PUBLIC KEY-----\n"
    "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAtMlzuQ993hN6i5+rt6Ek\n"
    "vvQjfAoSRjNBb/m6OjP5mmjudmqpIHTMKRN7uXZPLW09RMgRNn9I9+DBVYPfOj6/\n"
    "+yqhmGkmedFWPwWmCcWVk5GNy8VY6f8R1X+bHj0NwbV7XX3QVMtNTDFzfwajsTEN\n"
    "5aoD2uRHiTXbpLxF8Um2spP+zLdIvTGF875aehp0HDnONK8R3Q4IxErxmInidyZb\n"
    "aTMSKSPDc1m1m7Ladt97Ft7sDi8etaNDAMaKZpGFENqENbsT9PaDHooInEzWbhr9\n"
    "pM+kcG6zmMMQ0710ViNc9H/OGxVtL0al9qnCeJL+ZoBSiIa+mL3ELCI2xeQRWd8n\nhwIDAQAB\n"
    "-----END PUBLIC KEY-----"
)

if not QR_JWT_PRIVATE_KEY:
    QR_JWT_PRIVATE_KEY = env.str("QR_JWT_PRIVATE_KEY", default=_DEV_QR_PRIVATE_KEY)
if not QR_JWT_PUBLIC_KEY:
    QR_JWT_PUBLIC_KEY = env.str("QR_JWT_PUBLIC_KEY", default=_DEV_QR_PUBLIC_KEY)
