"""Hermes worker: Telegram long-poll loop, zero new dependencies (raw httpx).

Polls getUpdates, routes commands through the app's own logic:
- /start CODE  -> calls app link-binder directly (same guards as webhook)
- /status      -> account + vault summary for the linked user
- /next        -> easiest next win from eligibility engine

Run: .venv-civic/Scripts/python -m app.hermes (needs TELEGRAM_BOT_TOKEN;
without it the worker refuses to start — console mode lives in alerts.py).
"""
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
API = f"https://api.telegram.org/bot{TOKEN}" if TOKEN else ""


def handle_start(chat_id: str, code: str) -> str:
    """Same binding rules as POST /hooks/telegram, minus HTTP."""
    from datetime import datetime, timedelta, timezone

    from sqlmodel import Session, select

    import app.main as M
    from app.models import LinkCode, User
    with Session(M.engine) as s:
        link = s.exec(select(LinkCode).where(
            LinkCode.code == code.upper())).first()
        if not link or link.used_at:
            return "Invalid or used code. Generate a fresh one from your dashboard."
        created = link.created_at.replace(tzinfo=timezone.utc) \
            if link.created_at.tzinfo is None else link.created_at
        if datetime.now(timezone.utc) - created > timedelta(minutes=15):
            return "Code expired. Generate a fresh one."
        other = s.exec(select(User).where(User.telegram_chat == chat_id)).first()
        me = s.get(User, link.user_id)
        if other and other.id != me.id:
            return "This chat is already linked to another account."
        me.telegram_chat = chat_id
        link.used_at = datetime.now(timezone.utc)
        s.add(me)
        s.add(link)
        s.commit()
        return ("Linked! You'll get due-date and change pings here. "
                "Try /status and /next.")


def handle_status(chat_id: str) -> str:
    from sqlmodel import Session, select

    import app.main as M
    from app.models import Progress, User, VaultItem
    with Session(M.engine) as s:
        u = s.exec(select(User).where(User.telegram_chat == chat_id)).first()
        if not u:
            return "This chat isn't linked. Send /start YOURCODE from your dashboard."
        docs = s.exec(select(VaultItem).where(VaultItem.user_id == u.id)).all()
        progs = s.exec(select(Progress).where(Progress.user_id == u.id)).all()
        kinds = sorted({d.kind for d in docs})
        return (f"{u.name or 'Citizen'} ({u.city}): holds {', '.join(kinds) or 'nothing yet'}, "
                f"{len(progs)} steps done.")


def handle_next(chat_id: str) -> str:
    from sqlmodel import Session, select

    import app.main as M
    from app import eligibility as elig
    from app.models import User, VaultItem
    with Session(M.engine) as s:
        u = s.exec(select(User).where(User.telegram_chat == chat_id)).first()
        if not u:
            return "This chat isn't linked. Send /start YOURCODE from your dashboard."
        kinds = {d.kind for d in
                 s.exec(select(VaultItem).where(VaultItem.user_id == u.id)).all()}
        b = elig.personalize(kinds, {})
        if not b["next_easiest"]:
            return "Nothing pending — you're all set."
        n = b["next_easiest"][0]
        return f"Easiest next: {n['get']} ({n['effort']}). {n['why']}"


def route(chat_id: str, text: str) -> str:
    parts = (text or "").strip().split()
    cmd = parts[0].lower() if parts else ""
    if cmd == "/start" and len(parts) > 1:
        return handle_start(chat_id, parts[1])
    if cmd == "/status":
        return handle_status(chat_id)
    if cmd == "/next":
        return handle_next(chat_id)
    return ("Commands: /start CODE (link), /status (your holdings), "
            "/next (easiest win). Get CODE from your dashboard.")


def main():
    if not TOKEN:
        print("TELEGRAM_BOT_TOKEN unset — worker refuses to start (use alerts console mode).")
        raise SystemExit(1)
    offset = 0
    print("hermes worker polling…")
    while True:
        try:
            r = httpx.get(f"{API}/getUpdates",
                          params={"offset": offset, "timeout": 50}, timeout=70).json()
            for up in r.get("result", []):
                offset = up["update_id"] + 1
                msg = up.get("message", {})
                chat = str(msg.get("chat", {}).get("id", ""))
                text = msg.get("text", "")
                if chat and text:
                    reply = route(chat, text)
                    httpx.post(f"{API}/sendMessage",
                               json={"chat_id": chat, "text": reply}, timeout=30)
        except Exception as e:
            print("poll error:", str(e)[:160])
            time.sleep(5)


if __name__ == "__main__":
    main()
