"""Backups: SQLite online snapshot or Postgres pg_dump + retention +
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
from urllib.parse import urlparse

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
    url = str(engine.url).replace("postgresql+psycopg://", "postgresql://")
    p = urlparse(url)
    password = p.password or ""
    host = p.hostname or "localhost"
    port = f":{p.port}" if p.port else ""
    clean = f"postgresql://{p.username or ''}@{host}{port}{p.path}"
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
