"""cPanel UAPI client interface and implementations for subdomain provisioning."""

import logging
from abc import ABC, abstractmethod
from typing import List, Optional, Set

from django.conf import settings

logger = logging.getLogger(__name__)


class CPanelUAPIError(Exception):
    """Raised when cPanel UAPI operations fail."""

    pass


class BaseUAPIClient(ABC):
    """Abstract interface for cPanel UAPI client."""

    @abstractmethod
    def provision_subdomain(self, subdomain: str) -> bool:
        """
        Provision a subdomain DNS record and document root in cPanel.

        Raises CPanelUAPIError if the operation fails.
        """
        pass


class MockCPanelUAPIClient(BaseUAPIClient):
    """
    In-memory mock cPanel UAPI client for local development and testing.

    Tracks provisioned subdomains and supports simulated failures for atomicity testing.
    """

    def __init__(
        self,
        should_fail: bool = False,
        fail_subdomains: Optional[Set[str]] = None,
    ):
        self.should_fail = should_fail
        self.fail_subdomains = fail_subdomains or set()
        self.provisioned_subdomains: List[str] = []

    def provision_subdomain(self, subdomain: str) -> bool:
        if self.should_fail or subdomain in self.fail_subdomains:
            raise CPanelUAPIError(
                f"Simulated cPanel UAPI error provisioning subdomain '{subdomain}'."
            )
        self.provisioned_subdomains.append(subdomain)
        logger.info("[Mock UAPI] Successfully provisioned subdomain: %s", subdomain)
        return True


class CPanelUAPIClient(BaseUAPIClient):
    """
    Live cPanel UAPI client for production deployment.

    Calls cPanel UAPI SubDomain/addsubdomain via HTTP with cPanel API token.
    """

    def __init__(
        self,
        host: Optional[str] = None,
        username: Optional[str] = None,
        api_token: Optional[str] = None,
        root_domain: Optional[str] = None,
    ):
        self.host = host or getattr(settings, "CPANEL_HOST", "")
        self.username = username or getattr(settings, "CPANEL_USERNAME", "")
        self.api_token = api_token or getattr(settings, "CPANEL_API_TOKEN", "")
        self.root_domain = root_domain or settings.DOMAIN

    def provision_subdomain(self, subdomain: str) -> bool:
        if not self.api_token or not self.host or not self.username:
            raise CPanelUAPIError(
                "cPanel UAPI credentials (CPANEL_HOST, CPANEL_USERNAME, CPANEL_API_TOKEN) are incomplete."
            )

        import json
        import urllib.error
        import urllib.parse
        import urllib.request

        url = f"https://{self.host}:2083/execute/SubDomain/addsubdomain"
        params = urllib.parse.urlencode(
            {
                "domain": subdomain,
                "rootdomain": self.root_domain,
                "dir": f"public_html/{subdomain}",
            }
        )
        full_url = f"{url}?{params}"

        req = urllib.request.Request(
            full_url,
            headers={
                "Authorization": f"cpanel {self.username}:{self.api_token}",
                "User-Agent": "FitGate-UAPI-Client",
            },
        )

        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if not data.get("status"):
                    errors = data.get("errors", ["Unknown cPanel UAPI error"])
                    raise CPanelUAPIError(f"cPanel UAPI returned failure: {errors}")
                return True
        except Exception as exc:
            if isinstance(exc, CPanelUAPIError):
                raise
            raise CPanelUAPIError(
                f"Failed to communicate with cPanel UAPI: {exc}"
            ) from exc


_global_mock_client = MockCPanelUAPIClient()


def get_uapi_client() -> BaseUAPIClient:
    """Return configured cPanel UAPI client (mock for dev/tests, real for production)."""
    use_mock = getattr(settings, "CPANEL_USE_MOCK", True)
    if use_mock:
        return _global_mock_client
    return CPanelUAPIClient()
