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

    bot_token = (
        getattr(settings, "TELEGRAM_BOT_TOKEN", None)
        or os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    )

    mock_setting = getattr(settings, "TELEGRAM_USE_MOCK", None)
    mock_env = os.getenv("TELEGRAM_USE_MOCK", "").strip().lower()

    if mock_setting is True or mock_env in ("true", "1", "yes"):
        use_mock = True
    elif mock_setting is False or mock_env in ("false", "0", "no"):
        use_mock = False
    elif not bot_token or getattr(settings, "ENVIRONMENT", "development") == "test":
        use_mock = True
    else:
        use_mock = False

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
        if not bot_token:
            return (
                True,
                "Broadcast recorded via development mock sender (No TELEGRAM_BOT_TOKEN configured in server .env).",
            )
        return (
            True,
            "Broadcast recorded via development mock sender (TELEGRAM_USE_MOCK is enabled).",
        )

    if not bot_token:
        return (
            False,
            "Telegram bot token is not configured on the server. Set TELEGRAM_BOT_TOKEN in .env.",
        )

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

        try:
            err_data = resp.json()
            description = err_data.get("description", resp.text)
        except Exception:
            description = resp.text

        desc_lower = description.lower()
        if resp.status_code == 401:
            return False, "Telegram error: Invalid TELEGRAM_BOT_TOKEN."
        if "chat not found" in desc_lower:
            return (
                False,
                f"Telegram error: Channel {cleaned_channel} not found. Ensure the channel is public and the handle is correct.",
            )
        if (
            "bot is not a member" in desc_lower
            or "not enough rights" in desc_lower
            or "need administrator rights" in desc_lower
            or "administrator" in desc_lower
        ):
            return (
                False,
                f"Telegram error: Your Telegram bot must be added as an Administrator to {cleaned_channel} with 'Post Messages' rights.",
            )

        return False, f"Telegram API error ({resp.status_code}): {description}"
    except Exception as exc:
        logger.warning(
            "Failed to deliver Telegram broadcast to %s: %s", cleaned_channel, exc
        )
        return False, f"Network error delivering to Telegram: {exc}"
