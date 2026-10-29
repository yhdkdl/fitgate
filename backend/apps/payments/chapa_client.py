"""HTTP Client for Chapa Payment Gateway API."""

import json
import logging
import re
import ssl
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional, Tuple

from django.conf import settings

logger = logging.getLogger(__name__)

CHAPA_API_BASE = "https://api.chapa.co/v1"


class ChapaAPIError(Exception):
    """Raised when Chapa API returns an error or fails to respond."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        data: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.data = data or {}


class ChapaClient:
    """Wrapper for Chapa API operations."""

    def __init__(self, secret_key: str):
        self.secret_key = secret_key

    def _request(
        self,
        endpoint: str,
        method: str = "GET",
        data: Optional[Dict[str, Any]] = None,
        timeout: int = 15,
    ) -> Dict[str, Any]:
        url = f"{CHAPA_API_BASE}/{endpoint.lstrip('/')}"
        headers = {
            "Authorization": f"Bearer {self.secret_key}",
            "Accept": "application/json",
            "User-Agent": "FitGate-Payment-Service/1.0",
        }
        encoded_data = None
        if data is not None:
            headers["Content-Type"] = "application/json"
            encoded_data = json.dumps(data).encode("utf-8")

        req = urllib.request.Request(
            url=url,
            data=encoded_data,
            headers=headers,
            method=method,
        )

        ctx = ssl.create_default_context()
        try:
            with urllib.request.urlopen(req, context=ctx, timeout=timeout) as resp:
                resp_bytes = resp.read()
                return json.loads(resp_bytes.decode("utf-8"))
        except urllib.error.HTTPError as exc:
            status_code = exc.code
            try:
                err_body = exc.read().decode("utf-8")
                err_data = json.loads(err_body)
                err_msg = err_data.get("message") or f"HTTP {status_code}"
            except Exception:
                err_data = {}
                err_msg = f"HTTP {status_code}"
            logger.warning("Chapa API HTTP error on %s: %s", endpoint, err_msg)
            raise ChapaAPIError(
                err_msg, status_code=status_code, data=err_data
            ) from exc
        except urllib.error.URLError as exc:
            logger.warning(
                "Chapa API network/URL error on %s: %s", endpoint, exc.reason
            )
            raise ChapaAPIError(f"Network error: {exc.reason}") from exc
        except TimeoutError as exc:
            logger.warning("Chapa API timeout on %s", endpoint)
            raise ChapaAPIError("Connection timed out.") from exc
        except Exception as exc:
            logger.warning("Unexpected error communicating with Chapa API: %s", exc)
            raise ChapaAPIError("Unexpected error contacting payment gateway.") from exc

    def initialize_transaction(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Call POST /transaction/initialize to create a checkout session.
        Returns the checkout response containing checkout_url.
        """
        if getattr(settings, "CHAPA_USE_MOCK", False):
            customization = payload.get("customization") or {}
            title = customization.get("title")
            if title and len(title) > 16:
                raise ChapaAPIError(
                    "The customization.title must not exceed 16 characters.",
                    status_code=400,
                    data={
                        "customization.title": [
                            "The customization.title must not exceed 16 characters."
                        ]
                    },
                )
            if title and not re.match(r"^[a-zA-Z0-9\s\-_.]+$", title):
                raise ChapaAPIError(
                    "The customization.title may only contain letters, numbers, hyphens, underscores, spaces, and dots.",
                    status_code=400,
                    data={
                        "customization.title": [
                            "The customization.title may only contain letters, numbers, hyphens, underscores, spaces, and dots."
                        ]
                    },
                )
            desc = customization.get("description")
            if desc and not re.match(r"^[a-zA-Z0-9\s\-_.]+$", desc):
                raise ChapaAPIError(
                    "The customization.description may only contain letters, numbers, hyphens, underscores, spaces, and dots.",
                    status_code=400,
                    data={
                        "customization.description": [
                            "The customization.description may only contain letters, numbers, hyphens, underscores, spaces, and dots."
                        ]
                    },
                )
            first_name = payload.get("first_name")
            if first_name and len(first_name) > 35:
                raise ChapaAPIError(
                    "The first_name must not exceed 35 characters.",
                    status_code=400,
                    data={
                        "first_name": ["The first_name must not exceed 35 characters."]
                    },
                )
            last_name = payload.get("last_name")
            if last_name and len(last_name) > 35:
                raise ChapaAPIError(
                    "The last_name must not exceed 35 characters.",
                    status_code=400,
                    data={
                        "last_name": ["The last_name must not exceed 35 characters."]
                    },
                )
            tx_ref = payload.get("tx_ref", "tx-mock")
            if tx_ref and len(tx_ref) > 50:
                raise ChapaAPIError(
                    "The tx_ref must not exceed 50 characters.",
                    status_code=400,
                    data={"tx_ref": ["The tx_ref must not exceed 50 characters."]},
                )
            phone = payload.get("phone_number")
            if phone and not (
                re.match(r"^(09|07)\d{8}$", phone)
                or (phone.isdigit() and 9 <= len(phone) <= 15)
            ):
                raise ChapaAPIError(
                    "The phone_number format is invalid.",
                    status_code=400,
                    data={"phone_number": ["The phone_number format is invalid."]},
                )
            amount = payload.get("amount")
            if not amount:
                raise ChapaAPIError("The amount field is required.", status_code=400)
            currency = payload.get("currency")
            if currency not in ("ETB", "USD"):
                raise ChapaAPIError("The currency is invalid.", status_code=400)
            email = payload.get("email")
            if not email or "@" not in email:
                raise ChapaAPIError(
                    "The email field must be a valid email address.", status_code=400
                )

            return {
                "message": "Hosted Link (mocked)",
                "status": "success",
                "data": {
                    "checkout_url": f"https://checkout.chapa.co/checkout/payment/mock-{tx_ref}",
                    "tx_ref": tx_ref,
                },
            }

        resp = self._request("transaction/initialize", method="POST", data=payload)
        if resp.get("status") != "success":
            raise ChapaAPIError(
                resp.get("message", "Transaction initialization failed."), data=resp
            )
        return resp

    def verify_transaction(self, tx_ref: str) -> Dict[str, Any]:
        """
        Call GET /transaction/verify/{tx_ref} to verify transaction status server-side.
        """
        if getattr(settings, "CHAPA_USE_MOCK", False):
            return {
                "message": "Payment details (mocked)",
                "status": "success",
                "data": {
                    "status": "success",
                    "tx_ref": tx_ref,
                },
            }

        return self._request(
            f"transaction/verify/{urllib.parse.quote(tx_ref)}", method="GET"
        )

    def test_connection(self) -> Tuple[bool, str]:
        """
        Test if the API credentials are valid.
        Calls GET /banks endpoint.
        """
        if getattr(settings, "CHAPA_USE_MOCK", False):
            return True, "Simulated (mock mode): not checked with Chapa"

        try:
            resp = self._request("banks", method="GET", timeout=10)
            if resp.get("status") == "success" or "data" in resp:
                return True, "Chapa connection verified successfully."
            return False, "Chapa rejected the key."
        except ChapaAPIError as exc:
            if exc.status_code in (401, 403):
                return False, "Chapa rejected the key."
            return False, "Could not reach Chapa."
        except Exception:
            return False, "Could not reach Chapa."
