"""Hermes worker rebuild: improved Telegram bot with webhook fallback.

The previous worker used long-polling only. This rebuild adds:
- Webhook mode (preferred for production behind Cloudflare Tunnel)
- Long-polling fallback when webhook is not configured
- Automatic reconnection with exponential backoff
- Rate limiting protection against Telegram API limits
- Error handling for common failure modes
"""
import asyncio
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
API = f"https://api.telegram.org/bot{TOKEN}" if TOKEN else ""
WEBHOOK_URL = os.environ.get("TELEGRAM_WEBHOOK_URL", "")
POLLING_TIMEOUT = int(os.environ.get("TELEGRAM_POLLING_TIMEOUT", "50"))
POLLING_INTERVAL = float(os.environ.get("TELEGRAM_POLLING_INTERVAL", "1.0"))
MAX_RECONNECT_DELAY = 60.0

logger = logging.getLogger(__name__)


def _import_app():
    """Lazy import app.main to avoid circular imports."""
    import app.main as M
    return M


# Reuse logic from hermes.py (imported)
from app.hermes import route as hermes_route


async def send_message(chat_id: str, text: str, session: httpx.AsyncClient = None) -> dict:
    """Send message via Telegram Bot API."""
    if session is None:
        async with httpx.AsyncClient(timeout=30) as s:
            r = await s.post(f"{API}/sendMessage", json={"chat_id": chat_id, "text": text})
            r.raise_for_status()
            data = r.json()
    else:
        r = await session.post(f"{API}/sendMessage", json={"chat_id": chat_id, "text": text})
        r.raise_for_status()
        data = r.json()
    return {"ok": True, "message_id": data["result"]["message_id"]}


async def set_webhook(session: httpx.AsyncClient):
    """Configure webhook if URL is set."""
    if not WEBHOOK_URL:
        return
    r = await session.post(f"{API}/setWebhook", json={
        "url": WEBHOOK_URL,
        "max_connections": 40,
        "allowed_updates": ["message"],
    })
    r.raise_for_status()
    result = r.json()
    if not result.get("ok"):
        logger.warning(f"Failed to set webhook: {result}")
    else:
        logger.info(f"Webook set to {WEBHOOK_URL}")


async def get_updates(offset: int = 0, timeout: int = POLLING_TIMEOUT,
                      session: httpx.AsyncClient = None) -> list:
    """Get updates from Telegram."""
    url = f"{API}/getUpdates"
    params = {"offset": offset, "timeout": timeout, "allowed_updates": ["message"]}
    if session:
        r = await session.get(url, params=params, timeout=timeout + 10)
    else:
        async with httpx.AsyncClient() as s:
            r = await s.get(url, params=params, timeout=timeout + 10)
    r.raise_for_status()
    return r.json().get("result", [])


async def long_poll_loop():
    """Main polling loop with automatic reconnection."""
    offset = 0
    reconnect_delay = 1.0
    async with httpx.AsyncClient() as client:
        await set_webhook(client)
        logger.info("Hermes worker started in polling mode")
        while True:
            try:
                updates = await get_updates(offset, POLLING_TIMEOUT, client)
                reconnect_delay = 1.0  # reset on success
                for update in updates:
                    offset = max(offset, update.get("update_id", 0) + 1)
                    msg = update.get("message", {})
                    chat_id = str(msg.get("chat", {}).get("id", ""))
                    text = msg.get("text", "")
                    if chat_id and text:
                        reply = hermes_route(chat_id, text)
                        try:
                            await send_message(chat_id, reply, client)
                        except Exception as e:
                            logger.error(f"Failed to send message: {e}")
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    retry_after = int(e.response.headers.get("retry-after", 5))
                    logger.warning(f"Rate limited by Telegram, waiting {retry_after}s")
                    await asyncio.sleep(retry_after)
                else:
                    logger.error(f"HTTP error: {e}")
                    await asyncio.sleep(min(reconnect_delay * 2, MAX_RECONNECT_DELAY))
            except Exception as e:
                logger.error(f"Polling error: {e}")
                await asyncio.sleep(min(reconnect_delay * 2, MAX_RECONNECT_DELAY))
            reconnect_delay = min(reconnect_delay * 1.5, MAX_RECONNECT_DELAY)


def main():
    if not TOKEN:
        print("TELEGRAM_BOT_TOKEN unset — worker refuses to start.")
        raise SystemExit(1)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    if WEBHOOK_URL:
        logger.info(f"Running in webhook mode: {WEBHOOK_URL}")
        # Webhook mode is handled by FastAPI /hooks/telegram endpoint
        # This branch is for standalone webhook processing
        print("Webhook mode: receive POST to /hooks/telegram endpoint.")
        raise SystemExit(0)
    else:
        asyncio.run(long_poll_loop())


if __name__ == "__main__":
    main()
