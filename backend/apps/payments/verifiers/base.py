"""Base interface and data structures for bank receipt verification."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional


@dataclass
class BankReceiptVerificationResult:
    """Standardized result returned by bank receipt verifiers."""

    STATUS_VERIFIED = "VERIFIED"
    STATUS_COULD_NOT_CHECK = "COULD_NOT_CHECK"
    STATUS_MISMATCH = "MISMATCH"

    status: str
    bank: str
    reference: str
    amount: Optional[Decimal] = None
    currency: str = "ETB"
    receiver_account: Optional[str] = None
    receiver_name: Optional[str] = None
    sender_account: Optional[str] = None
    sender_name: Optional[str] = None
    transaction_date: Optional[datetime] = None
    error_message: Optional[str] = None
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def is_verified(self) -> bool:
        return self.status == self.STATUS_VERIFIED

    @property
    def is_mismatch(self) -> bool:
        return self.status == self.STATUS_MISMATCH

    @property
    def could_not_check(self) -> bool:
        return self.status == self.STATUS_COULD_NOT_CHECK


class BankReceiptVerifier(ABC):
    """Abstract interface for swappable bank receipt verification."""

    @abstractmethod
    def verify(
        self,
        bank: str,
        reference: str,
        expected_amount: Optional[Decimal] = None,
        receiving_accounts: Optional[list[str]] = None,
        **kwargs: Any,
    ) -> BankReceiptVerificationResult:
        """
        Verify a bank transfer receipt reference.

        Args:
            bank: Bank code (e.g. 'cbe', 'telebirr').
            reference: Bank receipt transaction reference or Receipt ID.
            expected_amount: Locked expected payment amount in ETB.
            receiving_accounts: List of normalized receiving accounts for the gym.
            kwargs: Extra parameters (e.g. account suffix for legacy CBE FT refs).

        Returns:
            BankReceiptVerificationResult
        """
        raise NotImplementedError
