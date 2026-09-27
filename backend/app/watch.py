"""Night watchman: re-fetch map sources, compare content hashes.

Changed page -> map auto-unverified + linked users alerted (Telegram if
linked, else in-app flag via verified=None). Deterministic: sha256 of
normalized fetched text. Run via /admin/recheck or a cron hitting it.
"""
import hashlib
import json
import re
from datetime import datetime, timezone

from sqlmodel import Session, select

from . import worker as workermod
from .obs import warn
from .models import Progress, TaskMap, User


def _norm(text: str) -> str:
    text = re.sub(r"\s+", " ", (text or "").lower())
    return text.strip()


def fingerprint(urls: list[str]) -> tuple[str, list[dict]]:
    """Return (sha256, per-url status). Failures hash as 'ERR:…' so a dead
    page also counts as change (never silently trust)."""
    parts, statuses = [], []
    for url in urls:
        try:
            text, tier = workermod.cascade_fetch(url)
            h = hashlib.sha256(_norm(text).encode()).hexdigest()[:16]
            parts.append(f"{url}={h}")
            statuses.append({"url": url, "ok": True, "tier": tier, "hash": h})
        except Exception as e:
            parts.append(f"{url}=ERR:{str(e)[:60]}")
            statuses.append({"url": url, "ok": False, "error": str(e)[:120]})
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:24], statuses


def recheck(engine, slug: str | None = None) -> list[dict]:
    """Recheck one map or all. Returns per-map {slug, changed, ...}."""
    out = []
    with Session(engine) as s:
        maps = s.exec(select(TaskMap).where(
            TaskMap.slug == slug) if slug else select(TaskMap)).all()
        for m in maps:
            urls = [u for u in json.loads(m.source_urls)
                    if isinstance(u, str)] or \
                   [s2.get("url") for s2 in json.loads(m.source_urls)
                    if isinstance(s2, dict)]
            new_hash, statuses = fingerprint(urls)
            changed = bool(m.content_hash) and new_hash != m.content_hash
            m.checked_at = datetime.now(timezone.utc)
            note = "first baseline stored"
            if not m.content_hash:
                m.content_hash = new_hash
            elif changed:
                m.verified_at = None  # trust revoked until human re-stamps
                note = "CHANGED — verification revoked"
            s.add(m)
            s.commit()
            alerted = 0
            if changed:
                users = {p.user_id for p in s.exec(
                    select(Progress).where(Progress.map_slug == m.slug)).all()}
                try:
                    from . import alerts as alertsmod
                except Exception as e:
                    alertsmod = None
                    warn("watch", "alerts module unavailable, "
                         "change notice not sent", error=e)
                for uid in users:
                    u = s.get(User, uid)
                    if not (u and u.telegram_chat):
                        continue
                    try:
                        alertsmod.portal_changed(u.telegram_chat, m.title, m.slug)
                        alerted += 1
                    except Exception as e:
                        warn("watch", "change alert send failed",
                             slug=m.slug, user_id=uid, error=e)
            out.append({"slug": m.slug, "changed": changed, "note": note,
                        "hash": new_hash, "alerted": alerted,
                        "sources": statuses})
    return out
