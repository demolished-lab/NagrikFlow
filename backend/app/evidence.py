"""Evidence store: immutable source snapshots + readable change diffs.

The claim "government requirement X changed" is worthless without proof.
Every build/recheck appends a SourceSnapshot per source (fetched text, raw
HTML when the tier exposed it, sha256 of both, tier, final URL, timestamp)
and a material change records a capped unified diff in ChangeEvent.

Hash semantics match watch._norm (lowercased, whitespace-collapsed) so the
per-URL content_hash lines up with the aggregate fingerprint. Text rows are
capped — this is evidence for review, not a web archive (warcio/WARC is the
upgrade path; see FREE_RESOURCES.md §7).
"""
import difflib
import hashlib
import re
import textwrap

from sqlmodel import Session, select

from .models import ChangeEvent, SourceSnapshot, utcnow
from .obs import warn

TEXT_CAP = 50_000  # per snapshot row, chars
HTML_CAP = 400_000
DIFF_CAP = 4_000
KEEP_PER_URL = 4  # history depth per (map, url)


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


def norm_hash(text: str) -> str:
    """sha256 (full hex) of the normalized text — same normalization the
    watch fingerprint uses, so snapshot hashes are comparable to it."""
    return hashlib.sha256(_norm(text).encode("utf-8", "replace")).hexdigest()


def raw_hash(data: str) -> str:
    return hashlib.sha256((data or "").encode("utf-8", "replace")).hexdigest()


def diff_texts(old: str, new: str) -> str:
    """Capped unified diff between two page texts. Sentence-per-line when the
    text has no newlines (trafilatura output varies), so reviewers see the
    actual changed requirement, not one 40k-char line."""
    def lines(t: str) -> list[str]:
        base = (t or "").splitlines()
        if len(base) >= 2:
            return base
        wrapped = textwrap.wrap((t or "").strip(), 100) or [""]
        out: list[str] = []
        for chunk in wrapped:
            out.extend(re.split(r"(?<=[.;:])\s{2,}", chunk) or [chunk])
        return out

    diff = "\n".join(difflib.unified_diff(
        lines(old), lines(new), fromfile="previous", tofile="current",
        lineterm=""))
    return diff[:DIFF_CAP]


def save_snapshot(engine, map_slug: str, url: str, *, text: str,
                  final_url: str = "", tier: str = "", html: str = "",
                  content_hash: str = "") -> SourceSnapshot:
    """Append one snapshot row and prune old ones for (slug, url)."""
    text = text or ""
    row = SourceSnapshot(
        map_slug=map_slug, url=url, final_url=final_url or url, tier=tier,
        content_hash=content_hash or norm_hash(text),
        raw_hash=raw_hash(html) if html else "",
        text=text[:TEXT_CAP], html=html[:HTML_CAP],
        retrieved_at=utcnow())
    with Session(engine) as s:
        s.add(row)
        s.commit()
        s.refresh(row)
        old = s.exec(select(SourceSnapshot).where(
            SourceSnapshot.map_slug == map_slug,
            SourceSnapshot.url == url).order_by(
            SourceSnapshot.id.desc())).all()
        for doomed in old[KEEP_PER_URL:]:
            s.delete(doomed)
        s.commit()
        s.refresh(row)
    return row


def save_snapshots(engine, map_slug: str, entries: list[dict]) -> int:
    """Bulk persist build-time snapshots ({url, text, final_url, tier, html})."""
    saved = 0
    for entry in entries or []:
        if (not isinstance(entry, dict) or not entry.get("url")
                or not entry.get("text")):
            continue
        try:
            save_snapshot(engine, map_slug, entry["url"],
                          text=entry.get("text", ""),
                          final_url=entry.get("final_url", ""),
                          tier=entry.get("tier", ""),
                          html=entry.get("html", ""))
            saved += 1
        except Exception as exc:
            # evidence writing must never fail a build
            warn("evidence", "snapshot save failed",
                 map_slug=map_slug, url=entry.get("url", ""), error=exc)
            continue
    return saved


def latest_snapshot(engine, map_slug: str, url: str) -> SourceSnapshot | None:
    with Session(engine) as s:
        return s.exec(select(SourceSnapshot).where(
            SourceSnapshot.map_slug == map_slug,
            SourceSnapshot.url == url).order_by(
            SourceSnapshot.id.desc())).first()


def record_change(engine, map_slug: str, url: str, old_text: str,
                  new_text: str, old_hash: str, new_hash: str) -> ChangeEvent:
    """Store the readable diff for one material source change."""
    ev = ChangeEvent(map_slug=map_slug, url=url, old_hash=old_hash,
                     new_hash=new_hash, diff=diff_texts(old_text, new_text),
                     created_at=utcnow())
    with Session(engine) as s:
        s.add(ev)
        s.commit()
        s.refresh(ev)
    return ev


def list_changes(engine, map_slug: str, limit: int = 20) -> list[dict]:
    """Newest-first change events for a map (review-queue / citizen view)."""
    with Session(engine) as s:
        rows = s.exec(select(ChangeEvent).where(
            ChangeEvent.map_slug == map_slug).order_by(
            ChangeEvent.id.desc()).limit(limit)).all()
    return [{"id": r.id, "url": r.url, "old_hash": r.old_hash,
             "new_hash": r.new_hash, "diff": r.diff,
             "created_at": r.created_at.isoformat() if r.created_at else ""}
            for r in rows]
