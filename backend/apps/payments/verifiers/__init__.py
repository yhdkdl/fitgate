"""Bank receipt verifiers package and factory."""

from django.conf import settings

from apps.payments.verifiers.base import (
    BankReceiptVerificationResult,
    BankReceiptVerifier,
)
from apps.payments.verifiers.mock import MockBankReceiptVerifier


def get_bank_receipt_verifier() -> BankReceiptVerifier:
    """
    Factory returning the configured bank receipt verifier.
    Uses MockBankReceiptVerifier if:
    - BANK_RECEIPT_VERIFIER_USE_MOCK is True, or
    - RECEIPT_VERIFICATION_ENABLED is False, or
    - in testing environments.
    Otherwise uses DirectChekiVerifier.
    """
    use_mock = getattr(settings, "BANK_RECEIPT_VERIFIER_USE_MOCK", True)
    is_enabled = getattr(settings, "RECEIPT_VERIFICATION_ENABLED", False)

    if use_mock or not is_enabled:
        return MockBankReceiptVerifier()

    from apps.payments.verifiers.direct_cheki import DirectChekiVerifier

    return DirectChekiVerifier()


__all__ = [
    "BankReceiptVerificationResult",
    "BankReceiptVerifier",
    "MockBankReceiptVerifier",
    "get_bank_receipt_verifier",
]
