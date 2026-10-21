"""cPanel UAPI client interface and implementations for subdomain provisioning."""

import json
import logging
import ssl
import urllib.error
import urllib.parse
import urllib.request
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Set, Tuple

from django.conf import settings

logger = logging.getLogger(__name__)


class CPanelUAPIError(Exception):
    """Raised when cPanel UAPI operations fail."""

    pass


def derive_domain_hierarchy(domain: str) -> Tuple[str, str]:
    """
    Derive (platform_label, root_domain) from DOMAIN without hardcoding.
    For example:
      'fitgate.tebebtech.com' -> ('fitgate', 'tebebtech.com')
      'fitgate.org'           -> ('', 'fitgate.org')
    """
    domain_parts = domain.strip().split(".")
    if len(domain_parts) > 2:
        platform_label = domain_parts[0]
        root_domain = ".".join(domain_parts[1:])
    else:
        platform_label = ""
        root_domain = domain.strip()
    return platform_label, root_domain


class BaseUAPIClient(ABC):
    """Abstract interface for cPanel UAPI client."""

    @abstractmethod
    def provision_subdomain(self, subdomain: str) -> bool:
        """
        Provision a subdomain DNS record and document root in cPanel.

        Raises CPanelUAPIError if the operation fails.
        """
        pass

    @abstractmethod
    def delete_subdomain(self, subdomain: str) -> bool:
        """
        Delete a subdomain from cPanel.

        Raises CPanelUAPIError if the operation fails.
        """
        pass

    @abstractmethod
    def list_subdomains(self) -> List[Dict[str, Any]]:
        """
        List all subdomains configured on the cPanel account.

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

    def delete_subdomain(self, subdomain: str) -> bool:
        if self.should_fail or subdomain in self.fail_subdomains:
            raise CPanelUAPIError(
                f"Simulated cPanel UAPI error deleting subdomain '{subdomain}'."
            )
        if subdomain in self.provisioned_subdomains:
            self.provisioned_subdomains.remove(subdomain)
        logger.info("[Mock UAPI] Successfully deleted subdomain: %s", subdomain)
        return True

    def list_subdomains(self) -> List[Dict[str, Any]]:
        return [{"domain": sub} for sub in self.provisioned_subdomains]


class CPanelUAPIClient(BaseUAPIClient):
    """
    Live cPanel UAPI client for production deployment.

    Calls cPanel UAPI endpoints via HTTPS port 2083 with cPanel API token.
    Fails fast with NO default fallbacks on credentials.
    """

    def __init__(
        self,
        host: Optional[str] = None,
        username: Optional[str] = None,
        api_token: Optional[str] = None,
        docroot: Optional[str] = None,
    ):
        self.host = host or settings.CPANEL_HOST
        self.username = username or settings.CPANEL_USERNAME
        self.api_token = api_token or settings.CPANEL_API_TOKEN
        self.docroot = docroot or settings.CPANEL_SUBDOMAIN_DOCROOT

    def _call_uapi(
        self,
        module: str,
        function: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if not self.api_token or not self.host or not self.username or not self.docroot:
            raise CPanelUAPIError(
                "cPanel UAPI credentials (CPANEL_HOST, CPANEL_USERNAME, CPANEL_API_TOKEN, CPANEL_SUBDOMAIN_DOCROOT) are incomplete."
            )

        query = urllib.parse.urlencode(params or {})
        url = f"https://{self.host}:2083/execute/{module}/{function}"
        if query:
            url = f"{url}?{query}"

        req = urllib.request.Request(
            url,
            headers={
                "Authorization": f"cpanel {self.username}:{self.api_token}",
                "User-Agent": "FitGate-UAPI-Client",
                "Accept": "application/json",
            },
        )
        ctx = ssl.create_default_context()
        try:
            with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                result = data.get("result", data)
                if result.get("status") != 1 and result.get("status") is not True:
                    errors = result.get("errors", ["Unknown cPanel UAPI error"])
                    raise CPanelUAPIError(f"cPanel UAPI returned failure: {errors}")
                return result
        except Exception as exc:
            if isinstance(exc, CPanelUAPIError):
                raise
            raise CPanelUAPIError(
                f"Failed to communicate with cPanel UAPI: {exc}"
            ) from exc

    def provision_subdomain(self, subdomain: str) -> bool:
        platform_label, root_domain = derive_domain_hierarchy(settings.DOMAIN)
        domain_label = f"{subdomain}.{platform_label}" if platform_label else subdomain

        params = {
            "domain": domain_label,
            "rootdomain": root_domain,
            "dir": self.docroot,
            "disallowdot": 0,
        }
        self._call_uapi("SubDomain", "addsubdomain", params)
        logger.info(
            "Successfully provisioned cPanel subdomain: %s under %s",
            domain_label,
            root_domain,
        )
        return True

    def delete_subdomain(self, subdomain: str) -> bool:
        fqdn = f"{subdomain}.{settings.DOMAIN.strip()}"
        params = {
            "domain": fqdn,
            "disallowdot": 0,
        }
        self._call_uapi("SubDomain", "delsubdomain", params)
        logger.info("Successfully deleted cPanel subdomain: %s", fqdn)
        return True

    def list_subdomains(self) -> List[Dict[str, Any]]:
        result = self._call_uapi("SubDomain", "listsubdomains")
        data = result.get("data", [])
        return data if isinstance(data, list) else []


_global_mock_client = MockCPanelUAPIClient()


def get_uapi_client() -> BaseUAPIClient:
    """Return configured cPanel UAPI client (mock for dev/tests, real for production)."""
    if settings.CPANEL_USE_MOCK:
        return _global_mock_client
    return CPanelUAPIClient()
