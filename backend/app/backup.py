"""Backups: online SQLite snapshot to disk + retention.

Default dir E:\\backups\\civic (healthy VHDX, off the C: drain); override
BACKUP_DIR. Keeps BACKUP_KEEP latest (default 7). Postgres path: pg_dump to
same dir layout when DATABASE_URL is postgresql (documented, needs server).
"""
import os
import sqlite3
from datetime import datetime
from pathlib import Path

BACKUP_DIR = Path(os.environ.get("BACKUP_DIR", r"E:\backups\civic"))
BACKUP_KEEP = int(os.environ.get("BACKUP_KEEP", "7"))


def db_path(engine) -> Path:
    url = str(engine.url)
    assert url.startswith("sqlite:///"), "backups v1 support sqlite only"
    return Path(url.replace("sqlite:///", "")).resolve()


def run(engine, dest_dir: Path | None = None) -> dict:
    dest = Path(dest_dir or BACKUP_DIR)
    dest.mkdir(parents=True, exist_ok=True)
    src = db_path(engine)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out = dest / f"civic-{stamp}.db"
    with sqlite3.connect(src) as s1, sqlite3.connect(out) as s2:
        s1.backup(s2)
    kept = sorted(dest.glob("civic-*.db"))
    for old in kept[:-BACKUP_KEEP]:
        old.unlink()
    return {"file": str(out), "bytes": out.stat().st_size,
            "kept": len(list(dest.glob('civic-*.db')))}


def listing(dest_dir: Path | None = None) -> list[dict]:
    dest = Path(dest_dir or BACKUP_DIR)
    if not dest.exists():
        return []
    return [{"file": p.name, "bytes": p.stat().st_size,
             "at": datetime.fromtimestamp(p.stat().st_mtime).isoformat()}
            for p in sorted(dest.glob("civic-*.db"), reverse=True)]
