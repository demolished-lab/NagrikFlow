"""Telegram webhook secret validation.

Usage in main.py:
    from . import telegram_validate
    # Then in telegram_webhook decorator or inside the function:
    @app.post("/hooks/telegram")
    def telegram_webhook(body: dict, x_telegram_token: str = Header(default=None)):
        telegram_validate.check(x_telegram_token)
        ...
"""
import os


_TELEGRAM_SECRET = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "").strip()


def check(header_value: str | None) -> None:
    """Raise ValueError if secret is configured but doesn't match."""
    if not _TELEGRAM_SECRET:
        return  # Not configured — skip validation
    if header_value != _TELEGRAM_SECRET:
        raise ValueError("invalid telegram webhook secret")


def is_configured() -> bool:
    """Return True if webhook secret protection is active."""
    return bool(_TELEGRAM_SECRET)
