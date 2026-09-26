"""Telegram alerts: due nudges, portal-change pings, OTP fallback channel.

Needs TELEGRAM_BOT_TOKEN + per-user chat id (stored on User.telegram_chat).
Without a token every send degrades to console log — never crashes.
"""
import os

import httpx

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")


def send(chat_id: str, text: str) -> dict:
    if not TOKEN or not chat_id:
        print(f"[alerts:console] to={chat_id or '?'} :: {text[:160]}")
        return {"via": "console"}
    r = httpx.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                   json={"chat_id": chat_id, "text": text}, timeout=30)
    r.raise_for_status()
    return {"via": "telegram", "id": r.json()["result"]["message_id"]}


def portal_changed(chat_id: str, title: str, slug: str) -> dict:
    return send(chat_id, f"⚠️ '{title}' source changed — map '{slug}' needs re-check. "
                         "Open Civic Path Navigator to review before acting.")


def due_soon(chat_id: str, title: str, due: str) -> dict:
    return send(chat_id, f"⏰ Reminder: {title} due {due}. See your dashboard for the step + link.")
