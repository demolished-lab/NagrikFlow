"""Night watchman: re-fetch map sources, compare content hashes.

Changed page -> map auto-unverified + linked users alerted (Telegram if
linked, else in-app flag via verified=None). Deterministic: sha256 of
normalized fetched text. Run via /admin/recheck or a cron hitting it.

Evidence layer: every fetch is compared against the stored SourceSnapshot
for that source. A material difference records a ChangeEvent with a
readable unified diff (what actually moved), then refreshes the snapshot —
so admins review *deltas*, not mystery revocations. The map's first recheck
is a baseline: snapshots refresh, no events fire.
"""
import hashlib
import json

from sqlmodel import Session, select

from . import evidence as evidencemod
from . import worker as workermod
from .models import Progress, TaskMap, User
from .obs import warn


def _fetch_all(urls: list[str]) -> list[dict]:
    """Cascade-fetch every source once. Per row: {url, ok, tier|error,
    text, hash} (text/hash only on success)."""
    rows = []
    for url in urls:
        try:
            text, tier = workermod.cascade_fetch(url)
            rows.append({"url": url, "ok": True, "tier": tier, "text": text,
                         "hash": evidencemod.norm_hash(text)})
        except Exception as e:
            rows.append({"url": url, "ok": False, "error": str(e)[:120]})
    return rows


def _aggregate(urls: list[str], rows: list[dict]) -> str:
    """Composite map hash: same construction as before the evidence layer
    (per-url 16-char hash or ERR tag, joined) — existing baselines stay valid."""
    parts = []
    for row in rows:
        if row.get("ok"):
            parts.append(f"{row['url']}={row['hash'][:16]}")
        else:
            parts.append(f"{row['url']}=ERR:{str(row.get('error', ''))[:60]}")
    # every url participates even if a fetch row is missing entirely
    seen = {r["url"] for r in rows}
    for u in urls:
        if u not in seen:
            parts.append(f"{u}=ERR:missing")
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:24]


def _statuses(rows: list[dict]) -> list[dict]:
    out = []
    for row in rows:
        if row.get("ok"):
            out.append({"url": row["url"], "ok": True, "tier": row["tier"],
                        "hash": row["hash"][:16]})
        else:
            out.append({"url": row["url"], "ok": False,
                        "error": row.get("error", "")})
    return out


def fingerprint(urls: list[str]) -> tuple[str, list[dict]]:
    """Return (sha256, per-url status). Failures hash as 'ERR:…' so a dead
    page also counts as change (never silently trust)."""
    rows = _fetch_all(urls)
    return _aggregate(urls, rows), _statuses(rows)


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
            rows = _fetch_all(urls)
            new_hash = _aggregate(urls, rows)
            statuses = _statuses(rows)
            first = not m.content_hash
            changed = bool(m.content_hash) and new_hash != m.content_hash
            m.checked_at = evidencemod.utcnow()
            note = "first baseline stored"
            if first:
                m.content_hash = new_hash
            elif changed:
                m.verified_at = None  # trust revoked until human re-stamps
                note = "CHANGED — verification revoked"
            s.add(m)
            s.commit()
            events = 0
            for row in rows:
                if not row.get("ok"):
                    continue  # dead source: aggregate ERR tag already flagged
                try:
                    prior = evidencemod.latest_snapshot(engine, m.slug,
                                                        row["url"])
                    if prior is None:
                        evidencemod.save_snapshot(
                            engine, m.slug, row["url"], text=row["text"],
                            final_url=row["url"], tier=row["tier"])
                    elif prior.content_hash != row["hash"]:
                        if not first:
                            evidencemod.record_change(
                                engine, m.slug, row["url"], prior.text,
                                row["text"], prior.content_hash, row["hash"])
                            events += 1
                        evidencemod.save_snapshot(
                            engine, m.slug, row["url"], text=row["text"],
                            final_url=prior.final_url or row["url"],
                            tier=row["tier"])
                except Exception as e:
                    warn("watch", "evidence update failed",
                         slug=m.slug, url=row["url"], error=e)
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
                        "diffs": events,
                        "sources": statuses})
    return out
