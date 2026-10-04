"""Thread-safe and async-safe tenant context management via contextvars."""

import contextvars
from typing import Optional

_current_tenant: contextvars.ContextVar[Optional[object]] = contextvars.ContextVar(
    "current_tenant", default=None
)


def get_current_tenant() -> Optional[object]:
    """Return the current tenant from the active context."""
    return _current_tenant.get()


def set_current_tenant(tenant: Optional[object]) -> contextvars.Token:
    """Set the current tenant in the active context and return reset token."""
    return _current_tenant.set(tenant)


def reset_current_tenant(token: contextvars.Token) -> None:
    """Reset the current tenant using the provided token."""
    _current_tenant.reset(token)
