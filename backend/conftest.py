"""Pytest root configuration and fixtures."""

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
