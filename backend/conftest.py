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


_TEST_TENANT_CREDENTIALS_KEY = "test_fernet_secret_key_32_bytes!"
os.environ["TENANT_CREDENTIALS_KEY"] = _TEST_TENANT_CREDENTIALS_KEY


@pytest.fixture(autouse=True)
def tenant_credentials_test_key(settings):
    """Configure test encryption key in test environment only and restore on teardown."""
    settings.TENANT_CREDENTIALS_KEY = _TEST_TENANT_CREDENTIALS_KEY
    yield
    settings.TENANT_CREDENTIALS_KEY = _TEST_TENANT_CREDENTIALS_KEY


try:
    from django.db.backends.base.operations import BaseDatabaseOperations

    _orig_execute_sql_flush = BaseDatabaseOperations.execute_sql_flush

    def _safe_execute_sql_flush(self, sql_list):
        """
        Disable accounts_auditlog immutability trigger around execute_sql_flush
        so TransactionTestCase post-teardown table flushes can succeed cleanly.
        Never embedded in database migrations.
        """
        try:
            with self.connection.cursor() as cursor:
                cursor.execute("ALTER TABLE accounts_auditlog DISABLE TRIGGER ALL;")
        except Exception:
            pass
        try:
            return _orig_execute_sql_flush(self, sql_list)
        finally:
            try:
                with self.connection.cursor() as cursor:
                    cursor.execute("ALTER TABLE accounts_auditlog ENABLE TRIGGER ALL;")
            except Exception:
                pass

    BaseDatabaseOperations.execute_sql_flush = _safe_execute_sql_flush
except Exception:
    pass
