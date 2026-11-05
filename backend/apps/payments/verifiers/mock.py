"""Mock bank receipt verifier for development and automated test suites."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Optional

from apps.payments.verifiers.base import (
    BankReceiptVerificationResult,
    BankReceiptVerifier,
)


class MockBankReceiptVerifier(BankReceiptVerifier):
    """
    Deterministic mock bank receipt verifier.
    Used in development and all automated test suites to avoid external network calls.
    """

    def verify(
        self,
        bank: str,
        reference: str,
        expected_amount: Optional[Decimal] = None,
        receiving_accounts: Optional[list[str]] = None,
        **kwargs: Any,
    ) -> BankReceiptVerificationResult:
        bank_clean = (bank or "cbe").lower().strip()
        ref_upper = (reference or "").strip().upper()
        now = datetime.now(timezone.utc)

        target_receiver = (
            receiving_accounts[0] if receiving_accounts else "1000123456789"
        )
        amt = expected_amount if expected_amount is not None else Decimal("1500.00")

        # 1. Could not check / error simulation
        if (
            "TIMEOUT" in ref_upper
            or "ERROR" in ref_upper
            or "FAIL" in ref_upper
            or "NOTFOUND" in ref_upper
        ):
            return BankReceiptVerificationResult(
                status=BankReceiptVerificationResult.STATUS_COULD_NOT_CHECK,
                bank=bank_clean,
                reference=reference,
                error_message="Upstream bank verification service timed out or was unreachable.",
                raw={"mock": True, "reason": "simulated_upstream_error"},
            )

        # 2. Mismatch simulation
        if "MISMATCH" in ref_upper:
            # Simulate genuine bank receipt but with amount difference
            mismatched_amount = (
                amt - Decimal("1000.00")
                if amt > Decimal("1000.00")
                else amt + Decimal("500.00")
            )
            msg = f"Receipt shows {mismatched_amount:.2f} ETB. Plan price is {amt:.2f} ETB. Not accepted."
            return BankReceiptVerificationResult(
                status=BankReceiptVerificationResult.STATUS_MISMATCH,
                bank=bank_clean,
                reference=reference,
                amount=mismatched_amount,
                currency="ETB",
                receiver_account=target_receiver,
                receiver_name="FitGate Fitness Gym",
                sender_account="1000987654321",
                sender_name="Abebe Bikila",
                transaction_date=now - timedelta(hours=2),
                error_message=msg,
                raw={"mock": True, "reason": "simulated_mismatch"},
            )

        # 3. Default: Verified
        return BankReceiptVerificationResult(
            status=BankReceiptVerificationResult.STATUS_VERIFIED,
            bank=bank_clean,
            reference=reference,
            amount=amt,
            currency="ETB",
            receiver_account=target_receiver,
            receiver_name="FitGate Fitness Gym",
            sender_account="1000987654321",
            sender_name="Abebe Bikila",
            transaction_date=now - timedelta(hours=1),
            raw={"mock": True, "reason": "simulated_verified"},
        )
