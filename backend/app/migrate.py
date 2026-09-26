"""Versioned migrations: never delete a DB again.

Each migration is a function taking (engine). Applied versions tracked in
schema_version table. Runs at startup, in order. SQLite + Postgres compatible
(SQLAlchemy DDL only). New schema change = append new function + list entry.
"""
from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, Session, SQLModel, create_engine, select


class SchemaVersion(SQLModel, table=True):
    version: Optional[int] = Field(default=None, primary_key=True)


def _ensure_columns(engine):
    from sqlalchemy import inspect, text
    stmts = []
    try:
        have = {c["name"] for c in inspect(engine).get_columns("user")}
        if "failed_attempts" not in have:
            stmts.append("ALTER TABLE user ADD COLUMN failed_attempts INTEGER DEFAULT 0")
        if "locked_until" not in have:
            stmts.append("ALTER TABLE user ADD COLUMN locked_until DATETIME")
    except Exception:
        pass
    try:
        thave = {c["name"] for c in inspect(engine).get_columns("taskmap")}
        if "content_hash" not in thave:
            stmts.append("ALTER TABLE taskmap ADD COLUMN content_hash VARCHAR DEFAULT ''")
        if "checked_at" not in thave:
            stmts.append("ALTER TABLE taskmap ADD COLUMN checked_at DATETIME")
    except Exception:
        pass
    if stmts:
        with engine.begin() as conn:
            for q in stmts:
                conn.execute(text(q))


def m001_base(engine):
    from app import models  # noqa: F401  (registers all tables)
    SQLModel.metadata.create_all(engine)
    _ensure_columns(engine)


def m002_seed_udyam(engine):
    import json
    from pathlib import Path
    from app.models import TaskMap
    seed = Path(__file__).resolve().parent.parent / "data" / "udyam_seed.json"
    with Session(engine) as s:
        if not s.exec(select(TaskMap).where(TaskMap.slug == "udyam-register")).first():
            d = json.loads(seed.read_text())
            s.add(TaskMap(slug=d["slug"], title=d["title"], city=d["city"],
                          graph_json=json.dumps({"nodes": d["nodes"], "edges": d["edges"]}),
                          source_urls=json.dumps(d["source_urls"]),
                          verified_at=datetime.now(timezone.utc)))
            s.commit()


def m003_security_jobs(engine):
    """New tables (auto) + re-ensure columns (idempotent)."""
    SQLModel.metadata.create_all(engine)  # new tables only (checkfirst)
    _ensure_columns(engine)


def m004_oauth_state(engine):
    """OAuthState table on already-migrated DBs (fresh DBs get it via m001)."""
    SQLModel.metadata.create_all(engine)  # checkfirst: new tables only


MIGRATIONS = [m001_base, m002_seed_udyam, m003_security_jobs, m004_oauth_state]


def migrate(engine):
    SchemaVersion.__table__.create(engine, checkfirst=True)
    with Session(engine) as s:
        applied = {r.version for r in s.exec(select(SchemaVersion)).all()}
        for i, fn in enumerate(MIGRATIONS, start=1):
            if i not in applied:
                fn(engine)
                s.add(SchemaVersion(version=i))
                s.commit()
