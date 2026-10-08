"""Host resolution helper for FitGate settings."""

from collections.abc import Iterable

from django.core.exceptions import ImproperlyConfigured


def build_allowed_hosts(
    domain: str,
    env_hosts: Iterable[str] | None = None,
    extra: Iterable[str] = (),
) -> list[str]:
    """
    Build a de-duplicated ALLOWED_HOSTS list.

    Always begins with [domain, f".{domain}"], followed by extra hosts,
    followed additively by env_hosts. Raises ImproperlyConfigured if '*' appears anywhere.
    """
    if not domain:
        raise ImproperlyConfigured("DOMAIN must be specified for ALLOWED_HOSTS.")

    raw_env_hosts = list(env_hosts) if env_hosts is not None else []
    raw_extra = list(extra)

    candidates: list[str] = [domain, f".{domain}"] + raw_extra + raw_env_hosts

    for host in candidates:
        if host == "*":
            raise ImproperlyConfigured(
                "Wildcard '*' is not permitted in ALLOWED_HOSTS."
            )

    return list(dict.fromkeys(candidates))
