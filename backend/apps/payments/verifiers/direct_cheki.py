"""Direct bank receipt verifier using open-source Python package cheki in DIRECT mode."""

import logging
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Optional

import requests

from apps.payments.verifiers.base import (
    BankReceiptVerificationResult,
    BankReceiptVerifier,
)

logger = logging.getLogger(__name__)


def _normalize_account_num(acc: Optional[str]) -> str:
    if not acc:
        return ""
    # Strip non-digits for Ethiopian accounts/phones
    return re.sub(r"\D", "", acc)


class DirectChekiVerifier(BankReceiptVerifier):
    """
    Direct mode verifier using cheki[direct].
    Reaches only bank endpoints (mb.cbe.com.et, transactioninfo.ethiotelecom.et).
    Never transmits receipt references or account numbers to cheki.et or any third party.
    """

    TIMEOUT_SECONDS = 8

    def verify(
        self,
        bank: str,
        reference: str,
        expected_amount: Optional[Decimal] = None,
        receiving_accounts: Optional[list[str]] = None,
        **kwargs: Any,
    ) -> BankReceiptVerificationResult:
        bank_clean = (bank or "").lower().strip()
        ref_clean = (reference or "").strip()

        try:
            import cheki  # noqa: F401
            from cheki.banks import VERIFIERS
        except ImportError as exc:
            logger.warning("cheki[direct] is not installed or available: %s", exc)
            return BankReceiptVerificationResult(
                status=BankReceiptVerificationResult.STATUS_COULD_NOT_CHECK,
                bank=bank_clean,
                reference=ref_clean,
                error_message="Bank verification service library is unavailable.",
            )

        if bank_clean not in VERIFIERS:
            return BankReceiptVerificationResult(
                status=BankReceiptVerificationResult.STATUS_COULD_NOT_CHECK,
                bank=bank_clean,
                reference=ref_clean,
                error_message=f"Bank '{bank_clean}' is not supported by direct verification.",
            )

        verifier_cls = VERIFIERS[bank_clean]
        verifier = verifier_cls()

        # Monkey-patch verifier timeout to 8s
        orig_get = verifier._get

        def _timed_get(url: str, **get_kwargs: Any) -> requests.Response:
            get_kwargs.setdefault("timeout", self.TIMEOUT_SECONDS)
            return orig_get(url, **get_kwargs)

        verifier._get = _timed_get

        try:
            res = verifier.verify(ref_clean, **kwargs)
        except Exception as exc:
            logger.info(
                "Direct cheki verification failed for %s (%s): %s",
                bank_clean,
                ref_clean,
                exc,
            )
            return BankReceiptVerificationResult(
                status=BankReceiptVerificationResult.STATUS_COULD_NOT_CHECK,
                bank=bank_clean,
                reference=ref_clean,
                error_message=str(exc),
            )

        if not res or not getattr(res, "exists", False):
            return BankReceiptVerificationResult(
                status=BankReceiptVerificationResult.STATUS_COULD_NOT_CHECK,
                bank=bank_clean,
                reference=ref_clean,
                error_message="Receipt not found on bank service.",
                raw=getattr(res, "raw", {}),
            )

        # Receipt was found by the bank! Now check amount, receiving account, and 7-day date window
        res_amount = None
        if getattr(res, "amount", None) is not None:
            try:
                res_amount = Decimal(str(res.amount))
            except Exception:
                res_amount = None

        res_receiver_acc = _normalize_account_num(getattr(res, "receiver_account", ""))
        res_date = getattr(res, "transaction_date", None)
        if isinstance(res_date, datetime) and res_date.tzinfo is None:
            res_date = res_date.replace(tzinfo=timezone.utc)

        now = datetime.now(timezone.utc)
        seven_days_ago = now - timedelta(days=7)

        # 1. Amount match check
        amount_matches = expected_amount is None or (
            res_amount is not None and res_amount == expected_amount
        )

        # 2. Receiving account match check
        account_matches = True
        if receiving_accounts:
            norm_receivers = [
                _normalize_account_num(a) for a in receiving_accounts if a
            ]
            # Match if res_receiver_acc is in configured accounts or suffix matches
            account_matches = any(
                res_receiver_acc == na
                or (len(na) >= 8 and res_receiver_acc.endswith(na[-8:]))
                or (len(res_receiver_acc) >= 8 and na.endswith(res_receiver_acc[-8:]))
                for na in norm_receivers
            )

        # 3. 7-day date window check
        date_matches = True
        if res_date:
            date_matches = seven_days_ago <= res_date <= now + timedelta(days=1)

        if amount_matches and account_matches and date_matches:
            return BankReceiptVerificationResult(
                status=BankReceiptVerificationResult.STATUS_VERIFIED,
                bank=bank_clean,
                reference=ref_clean,
                amount=res_amount,
                currency=getattr(res, "currency", "ETB") or "ETB",
                receiver_account=getattr(res, "receiver_account", None),
                receiver_name=getattr(res, "receiver_name", None),
                sender_account=getattr(res, "sender_account", None),
                sender_name=getattr(res, "sender_name", None),
                transaction_date=res_date,
                raw=getattr(res, "raw", {}),
            )

        # Mismatch detected: genuine bank receipt, but amount, account, or date differs
        reasons = []
        if not amount_matches:
            reasons.append(
                f"Receipt shows {res_amount} ETB. Plan price is {expected_amount} ETB."
            )
        if not account_matches:
            reasons.append(
                "Receiving account does not match gym's configured bank accounts."
            )
        if not date_matches:
            reasons.append("Receipt date is older than 7 days.")

        mismatch_msg = " ".join(reasons) + " Not accepted."
        return BankReceiptVerificationResult(
            status=BankReceiptVerificationResult.STATUS_MISMATCH,
            bank=bank_clean,
            reference=ref_clean,
            amount=res_amount,
            currency=getattr(res, "currency", "ETB") or "ETB",
            receiver_account=getattr(res, "receiver_account", None),
            receiver_name=getattr(res, "receiver_name", None),
            sender_account=getattr(res, "sender_account", None),
            sender_name=getattr(res, "sender_name", None),
            transaction_date=res_date,
            error_message=mismatch_msg,
            raw=getattr(res, "raw", {}),
        )
