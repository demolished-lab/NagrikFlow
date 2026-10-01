r"""Backups: SQLite online snapshot or Postgres pg_dump + retention +
optional S3-compatible cloud upload (AWS S3 / Cloudflare R2 / MinIO).

Local dir: BACKUP_DIR (default E:\backups\civic), keeps BACKUP_KEEP newest
per database format. Cloud: set BACKUP_S3_BUCKET + BACKUP_S3_KEY_ID +
BACKUP_S3_SECRET (optionally BACKUP_S3_ENDPOINT/REGION/PREFIX) and every run
uploads after the local snapshot; failures are reported, never fatal.
Postgres needs pg_dump on PATH (postgresql-client).
"""
import os
import shutil
import sqlite3
import subprocess
from datetime import datetime
from pathlib import Path

from sqlalchemy.engine import make_url

BACKUP_DIR = Path(os.environ.get("BACKUP_DIR", r"E:\backups\civic"))
BACKUP_KEEP = int(os.environ.get("BACKUP_KEEP", "7"))

S3_KEYS = ("BACKUP_S3_ENDPOINT", "BACKUP_S3_BUCKET", "BACKUP_S3_KEY_ID",
           "BACKUP_S3_SECRET", "BACKUP_S3_REGION", "BACKUP_S3_PREFIX")


def s3_configured() -> bool:
    e = {k: os.environ.get(k, "").strip() for k in S3_KEYS}
    return bool(e["BACKUP_S3_BUCKET"] and e["BACKUP_S3_KEY_ID"] and e["BACKUP_S3_SECRET"])


def upload(path: Path) -> dict:
    if not s3_configured():
        return {"uploaded": False, "reason": "s3 not configured"}
    try:
        import boto3
        from botocore.config import Config as BotoConfig
        e = {k: os.environ.get(k, "").strip() for k in S3_KEYS}
        client = boto3.client(
            "s3",
            endpoint_url=e["BACKUP_S3_ENDPOINT"] or None,
            region_name=e["BACKUP_S3_REGION"] or "us-east-1",
            aws_access_key_id=e["BACKUP_S3_KEY_ID"],
            aws_secret_access_key=e["BACKUP_S3_SECRET"],
            config=BotoConfig(signature_version="s3v4"),
        )
        key = "/".join(x for x in (e["BACKUP_S3_PREFIX"].strip("/"), path.name) if x)
        client.upload_file(str(path), e["BACKUP_S3_BUCKET"], key)
        return {"uploaded": True, "bucket": e["BACKUP_S3_BUCKET"], "key": key}
    except Exception as ex:
        return {"uploaded": False, "error": str(ex)[:200]}


def db_path(engine) -> Path:
    url = str(engine.url)
    assert url.startswith("sqlite:///"), "db_path is sqlite-only; use run()"
    return Path(url.replace("sqlite:///", "")).resolve()


def _pg_dump(engine, out: Path) -> None:
    pg = shutil.which("pg_dump")
    if not pg:
        raise RuntimeError("pg_dump not found on PATH (install postgresql-client)")
    u = engine.url
    if not hasattr(u, "password"):
        u = make_url(str(u))
    password = u.password or ""
    host = u.host or "localhost"
    port = f":{u.port}" if u.port else ""
    clean = f"postgresql://{u.username or ''}@{host}{port}/{u.database or ''}"
    env = dict(os.environ)
    if password:
        env["PGPASSWORD"] = password  # keep the password off the argv
    r = subprocess.run([pg, clean, "-Fc", "-f", str(out)],
                       capture_output=True, text=True, timeout=600, env=env)
    if r.returncode != 0:
        raise RuntimeError(f"pg_dump failed: {(r.stderr or '')[:200]}")


def run(engine, dest_dir: Path | None = None) -> dict:
    dest = Path(dest_dir or BACKUP_DIR)
    dest.mkdir(parents=True, exist_ok=True)
    url = str(engine.url)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    if url.startswith("sqlite"):
        src = db_path(engine)
        out = dest / f"civic-{stamp}.db"
        with sqlite3.connect(src) as s1, sqlite3.connect(out) as s2:
            s1.backup(s2)
        pattern = "civic-*.db"
    elif url.startswith("postgres"):
        out = dest / f"civic-{stamp}.dump"
        _pg_dump(engine, out)
        pattern = "civic-*.dump"
    else:
        raise AssertionError(f"unsupported database for backup: {url.split(':')[0]}")
    kept = sorted(dest.glob(pattern))
    for old in kept[:-BACKUP_KEEP]:
        old.unlink()
    result = {"file": str(out), "bytes": out.stat().st_size,
              "kept": len(list(dest.glob(pattern)))}
    result.update(upload(out))
    return result


def listing(dest_dir: Path | None = None) -> list[dict]:
    dest = Path(dest_dir or BACKUP_DIR)
    if not dest.exists():
        return []
    files = list(dest.glob("civic-*.db")) + list(dest.glob("civic-*.dump"))
    return [{"file": p.name, "bytes": p.stat().st_size,
             "at": datetime.fromtimestamp(p.stat().st_mtime).isoformat()}
            for p in sorted(files, key=lambda x: x.stat().st_mtime, reverse=True)]


def validate(path: Path) -> dict:
    """Integrity-check a backup file before trusting it for a restore."""
    path = Path(path)
    if path.suffix == ".db":
        try:
            uri = path.resolve().as_uri() + "?mode=ro"
            with sqlite3.connect(uri, uri=True) as c:
                ok = c.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        except sqlite3.Error:
            ok = False  # corrupt / non-database bytes raise instead of "not ok"
        return {"valid": bool(ok), "check": "sqlite integrity_check"}
    if path.suffix == ".dump":
        pg = shutil.which("pg_restore")
        if not pg:
            raise RuntimeError("pg_restore not found on PATH (postgresql-client)")
        r = subprocess.run([pg, "--list", str(path)], capture_output=True,
                           text=True, timeout=120)
        entries = len([l for l in (r.stdout or "").splitlines() if l.strip()])
        return {"valid": r.returncode == 0 and entries > 0,
                "check": "pg_restore --list", "entries": entries}
    raise ValueError(f"unknown backup type: {path.suffix or path.name}")


def restore(engine, path, confirm: bool = False) -> dict:
    """Restore a backup into the database DATABASE_URL points at.

    SQLite: validates, then replaces the DB file in place (in-process pooled
    connections are disposed first; STOP the running server before restoring
    — a second process would keep serving the old inode).
    Postgres: validates, then pg_restore --clean --if-exists into the target
    (run while the app is stopped or in maintenance mode).
    An existing SQLite target requires confirm=True (CLI: --yes).
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(str(path))
    verdict = validate(path)
    if not verdict["valid"]:
        raise RuntimeError(f"backup failed validation: {verdict}")
    url = str(engine.url)
    if url.startswith("sqlite"):
        target = db_path(engine)
        if target.exists() and not confirm:
            raise RuntimeError(
                f"target DB exists ({target}); confirm=True / --yes to overwrite")
        engine.dispose()  # close pooled handles so the copy can proceed
        if target == path.resolve():
            return {"restored": True, "file": path.name,
                    "target": str(target), "note": "same file, nothing to copy"}
        shutil.copy2(path, target)
        # stale WAL/SHM sidecars would replay old pages onto the new file
        for side in ("-wal", "-shm"):
            Path(str(target) + side).unlink(missing_ok=True)
        return {"restored": True, "file": path.name, "target": str(target),
                **{k: verdict[k] for k in ("check", "valid")}}
    if url.startswith("postgres"):
        pg = shutil.which("pg_restore")
        if not pg:
            raise RuntimeError("pg_restore not found on PATH (postgresql-client)")
        u = engine.url
        if not hasattr(u, "password"):
            u = make_url(str(u))
        password = u.password or ""
        host = u.host or "localhost"
        port = f":{u.port}" if u.port else ""
        clean = f"postgresql://{u.username or ''}@{host}{port}/{u.database or ''}"
        env = dict(os.environ)
        if password:
            env["PGPASSWORD"] = password  # keep the password off the argv
        r = subprocess.run([pg, "--clean", "--if-exists", "-d", clean,
                            str(path)], capture_output=True, text=True,
                           timeout=1800, env=env)
        if r.returncode != 0:
            raise RuntimeError(f"pg_restore failed: {(r.stderr or '')[:300]}")
        return {"restored": True, "file": path.name, "target": host,
                **{k: verdict[k] for k in ("check", "valid")}}
    raise AssertionError(f"unsupported database for restore: {url.split(':')[0]}")


def main(argv=None) -> int:
    """CLI: python -m app.backup {run|list|restore FILE [--yes]} (from backend/)."""
    import argparse
    import json
    import sys
    p = argparse.ArgumentParser(
        prog="python -m app.backup",
        description="Backup / list / restore civic-pathfinder databases")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("run", help="take a new backup (with retention + S3 upload)")
    sub.add_parser("list", help="list local backups, newest first")
    pr = sub.add_parser("restore", help="restore a backup into DATABASE_URL")
    pr.add_argument("file", help="path to civic-*.db / civic-*.dump")
    pr.add_argument("--yes", action="store_true",
                    help="confirm overwriting an existing SQLite database")
    a = p.parse_args(argv)

    from sqlmodel import create_engine
    url = os.environ.get("DATABASE_URL", "sqlite:///./civic.db")
    kw = {"connect_args": {"check_same_thread": False}} \
        if url.startswith("sqlite") else {}
    engine = create_engine(url, **kw)
    try:
        if a.cmd == "run":
            print(json.dumps(run(engine), indent=2))
        elif a.cmd == "list":
            print(json.dumps(listing(), indent=2))
        else:
            print(json.dumps(restore(engine, Path(a.file), confirm=a.yes),
                             indent=2))
    except Exception as ex:
        print(f"error: {ex}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
