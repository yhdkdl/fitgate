import logging
import os
from typing import Any, Dict, List, Tuple

from django.conf import settings
from django.core.exceptions import ValidationError

from apps.core.validators import validate_telegram_channel

logger = logging.getLogger(__name__)

# In-memory mock storage for dev and test inspections
MOCK_SENT_MESSAGES: List[Dict[str, Any]] = []


def clear_mock_messages():
    """Clear mock delivery log (useful for test isolation)."""
    MOCK_SENT_MESSAGES.clear()


def get_mock_messages() -> List[Dict[str, Any]]:
    """Get all mock delivered messages."""
    return list(MOCK_SENT_MESSAGES)


def send_telegram_channel_message(channel: str, message: str) -> Tuple[bool, str]:
    """
    Send an announcement message to a public Telegram channel (@channel_name).

    Returns:
        (success: bool, note_or_error: str)

    Fails gracefully: missing token, unconfigured channel, or Telegram API errors
    never raise unhandled exceptions and never block in-app notice publication.
    """
    if not channel:
        return False, "Telegram channel is not configured for this gym."

    try:
        cleaned_channel = validate_telegram_channel(channel)
    except ValidationError as exc:
        msg = exc.messages[0] if hasattr(exc, "messages") else str(exc)
        return False, msg

    use_mock = (
        getattr(settings, "TELEGRAM_USE_MOCK", True)
        or getattr(settings, "ENVIRONMENT", "development") in ("development", "test")
        or os.getenv("TELEGRAM_USE_MOCK", "true").lower() in ("true", "1", "yes")
    )

    if use_mock:
        logger.info(
            "Mock Telegram delivery to %s: %s",
            cleaned_channel,
            message[:80] + ("..." if len(message) > 80 else ""),
        )
        MOCK_SENT_MESSAGES.append(
            {
                "channel": cleaned_channel,
                "message": message,
            }
        )
        return True, "Broadcast recorded via development mock sender."

    bot_token = (
        getattr(settings, "TELEGRAM_BOT_TOKEN", None)
        or os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    )
    if not bot_token:
        return False, "Telegram bot token is not configured on the server."

    # Production network delivery
    try:
        import requests

        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            "chat_id": cleaned_channel,
            "text": message,
            "parse_mode": "Markdown",
        }
        resp = requests.post(url, json=payload, timeout=5)
        if resp.status_code == 200:
            return True, "Broadcast sent to Telegram channel."
        return False, f"Telegram API error ({resp.status_code}): {resp.text}"
    except Exception as exc:
        logger.warning(
            "Failed to deliver Telegram broadcast to %s: %s", cleaned_channel, exc
        )
        return False, f"Network error delivering to Telegram: {exc}"
