"""Versioned migrations: never delete a DB again.

Each migration is a function taking (engine). Applied versions tracked in
schema_version table. Runs at startup, in order. SQLite + Postgres compatible
(SQLAlchemy DDL only). New schema change = append new function + list entry.
"""
import os
from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, Session, SQLModel, create_engine, select


class SchemaVersion(SQLModel, table=True):
    version: Optional[int] = Field(default=None, primary_key=True)


def _ensure_columns(engine):
    from sqlalchemy import inspect, text
    dt = "TIMESTAMP" if engine.dialect.name == "postgresql" else "DATETIME"
    stmts = []
    try:
        have = {c["name"] for c in inspect(engine).get_columns("user")}
        if "failed_attempts" not in have:
            stmts.append("ALTER TABLE user ADD COLUMN failed_attempts INTEGER DEFAULT 0")
        if "locked_until" not in have:
            stmts.append(f"ALTER TABLE user ADD COLUMN locked_until {dt}")
    except Exception:
        pass
    try:
        thave = {c["name"] for c in inspect(engine).get_columns("taskmap")}
        if "content_hash" not in thave:
            stmts.append("ALTER TABLE taskmap ADD COLUMN content_hash VARCHAR DEFAULT ''")
        if "checked_at" not in thave:
            stmts.append(f"ALTER TABLE taskmap ADD COLUMN checked_at {dt}")
        if "state" not in thave:
            stmts.append("ALTER TABLE taskmap ADD COLUMN state VARCHAR DEFAULT ''")
        if "edge_sources" not in thave:
            stmts.append("ALTER TABLE taskmap ADD COLUMN edge_sources TEXT DEFAULT ''")
        if "service_type" not in thave:
            stmts.append("ALTER TABLE taskmap ADD COLUMN service_type VARCHAR DEFAULT ''")
        if "created_by" not in thave:
            stmts.append("ALTER TABLE taskmap ADD COLUMN created_by INTEGER DEFAULT 0")
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


def _seed_graph_hash(graph_json: str) -> str:
    import hashlib
    return hashlib.sha256(graph_json.encode("utf-8")).hexdigest()


def m002_seed_udyam(engine):
    import json
    from pathlib import Path
    from app.models import TaskMap
    seed = Path(__file__).resolve().parent.parent / "data" / "udyam_seed.json"
    with Session(engine) as s:
        if not s.exec(select(TaskMap).where(TaskMap.slug == "udyam-register")).first():
            d = json.loads(seed.read_text())
            graph_json = json.dumps({"nodes": d["nodes"], "edges": d["edges"]})
            s.add(TaskMap(slug=d["slug"], title=d["title"], city=d["city"],
                          graph_json=graph_json,
                          source_urls=json.dumps(d["source_urls"]),
                          verified_at=datetime.now(timezone.utc),
                          content_hash=_seed_graph_hash(graph_json),
                          checked_at=datetime.now(timezone.utc)))
            s.commit()


def m003_security_jobs(engine):
    """New tables (auto) + re-ensure columns (idempotent)."""
    SQLModel.metadata.create_all(engine)  # new tables only (checkfirst)
    _ensure_columns(engine)


def m004_oauth_state(engine):
    """OAuthState table on already-migrated DBs (fresh DBs get it via m001)."""
    SQLModel.metadata.create_all(engine)  # checkfirst: new tables only


def m005_grievances(engine):
    """Grievance table for DPDP Act compliance."""
    SQLModel.metadata.create_all(engine)  # checkfirst: new tables only


def m006_service_type(engine):
    """TaskMap.service_type column: explicit service category from the citizen."""
    SQLModel.metadata.create_all(engine)  # checkfirst: new tables only
    _ensure_columns(engine)


def m007_seed_provenance(engine):
    """Backfill curated-seed provenance (content_hash + checked_at) so the
    admin verify gates pass on DBs seeded before m002 carried it. checked_at =
    migration time = the moment this curation was stamped; a later recheck
    replaces it with a real fetch timestamp."""
    from app.models import TaskMap
    with Session(engine) as s:
        m = s.exec(select(TaskMap).where(TaskMap.slug == "udyam-register")).first()
        if not m:
            return
        changed = False
        if not m.content_hash:
            m.content_hash = _seed_graph_hash(m.graph_json or "")
            changed = True
        if not m.checked_at:
            m.checked_at = datetime.now(timezone.utc)
            changed = True
        if changed:
            s.add(m)
            s.commit()


MIGRATIONS = [m001_base, m002_seed_udyam, m003_security_jobs, m004_oauth_state,
              m005_grievances, m006_service_type, m007_seed_provenance]

# Optionally add PostgreSQL-specific migrations
_DB_URL = os.environ.get("DATABASE_URL", "sqlite:///./civic.db")


def _try_add_pg_migrations(migrations_list):
    """Add pg_trgm/index migrations only when DATABASE_URL points to Postgres."""
    if not (_DB_URL.startswith("postgresql://") or _DB_URL.startswith("postgresql+psycopg://")):
        return
    try:
        from . import migrate_pg as mpg_mod
        migrations_list.append(mpg_mod.m005_postgres)
    except ImportError:
        pass  # migrate_pg.py absent — silently skip PG migration


_try_add_pg_migrations(MIGRATIONS)


def migrate(engine):
    SchemaVersion.__table__.create(engine, checkfirst=True)
    with Session(engine) as s:
        applied = {r.version for r in s.exec(select(SchemaVersion)).all()}
        for i, fn in enumerate(MIGRATIONS, start=1):
            if i not in applied:
                fn(engine)
                s.add(SchemaVersion(version=i))
                s.commit()
    # Idempotent column safety net (service_type etc.) on every boot, so a
    # version-index shift can never skip an ALTER on an existing DB.
    _ensure_columns(engine)
