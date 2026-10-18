"""Pytest root configuration and fixtures."""

import os

import pytest


def pytest_sessionfinish(session, exitstatus):
    """
    Ensure zero tests collected returns exit code 0 (clean success).

    By default, pytest returns exit code 5 (NO_TESTS_COLLECTED).
    This hook ensures the test harness can be cleanly verified before
    tests are written.
    """
    if exitstatus == pytest.ExitCode.NO_TESTS_COLLECTED:
        session.exitstatus = pytest.ExitCode.OK


@pytest.fixture(autouse=True)
def fast_password_hasher(settings):
    """Use fast MD5 password hasher for test execution speed."""
    settings.PASSWORD_HASHERS = [
        "django.contrib.auth.hashers.MD5PasswordHasher",
    ]


_TEST_QR_KEYPAIR = None


def _get_test_qr_keypair():
    global _TEST_QR_KEYPAIR
    if _TEST_QR_KEYPAIR is None:
        from apps.attendance.crypto import generate_ed25519_keypair

        _TEST_QR_KEYPAIR = generate_ed25519_keypair()
    return _TEST_QR_KEYPAIR


# Set in os.environ for prod settings module imports during tests
_keys = _get_test_qr_keypair()
os.environ.setdefault("QR_JWT_PRIVATE_KEY", _keys[0])
os.environ.setdefault("QR_JWT_PUBLIC_KEY", _keys[1])


@pytest.fixture(autouse=True)
def qr_jwt_test_keys(settings):
    """Configure EdDSA test keypair in test settings so runtime auto-generation is not needed."""
    keys = _get_test_qr_keypair()
    settings.QR_JWT_PRIVATE_KEY = keys[0]
    settings.QR_JWT_PUBLIC_KEY = keys[1]


@pytest.fixture
def allow_auditlog_test_flush():
    """
    Fixture for transactional_db tests that need to flush tables.
    Disables accounts_auditlog USER triggers before flush and re-enables after.
    Never embedded in database migrations.
    """
    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute("ALTER TABLE accounts_auditlog DISABLE TRIGGER USER;")
    try:
        yield
    finally:
        with connection.cursor() as cursor:
            cursor.execute("ALTER TABLE accounts_auditlog ENABLE TRIGGER USER;")
