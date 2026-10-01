"""PostgreSQL migration: add Pg-specific indexes and constraints.

SQLite handles these automatically; Postgres needs explicit support.
Also creates a pg_trgm extension for text search on task titles.
"""
from sqlmodel import text


def m005_postgres(engine):
    """Add Postgres-compatible indexes and search extension."""
    with engine.begin() as conn:
        # Enable pg_trgm for text search (Postgres only — no-op on SQLite)
        try:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS hstore"))
        except Exception:
            pass  # SQLite ignores this

        # Search index on TaskMap title (Postgres full-text + pg_trgm)
        try:
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_taskmap_title_trgm "
                "ON taskmap USING gin(title gin_trgm_ops)"
            ))
        except Exception:
            pass  # Not available on SQLite

        # Unique constraint on link codes (ensure uniqueness at DB level)
        try:
            conn.execute(text(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_linkcode_code_unique "
                "ON linkcode (code)"
            ))
        except Exception:
            pass

        # Partial index: only active OAuth states (not expired)
        try:
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_oauthstate_active "
                "ON oauthstate (created_at) "
                "WHERE created_at > NOW() - INTERVAL '1 hour'"
            ))
        except Exception:
            pass

        # Timestamp indexes for monitoring
        try:
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_vaultitem_user_kind "
                "ON vaultitem (user_id, kind)"
            ))
        except Exception:
            pass


if __name__ == "__main__":
    # python -m app.migrate_pg  (run from backend/)
    # Applies the full versioned migration set for DATABASE_URL; on Postgres
    # that includes m005_postgres above (SQLite DBs run the base migrations).
    import os as _os

    from sqlmodel import create_engine as _create_engine

    from app.migrate import migrate as _migrate

    _url = _os.environ.get("DATABASE_URL", "sqlite:///./civic.db")
    _kw = {"connect_args": {"check_same_thread": False}} \
        if _url.startswith("sqlite") else {}
    _engine = _create_engine(_url, **_kw)
    _migrate(_engine)
    _target = _url.split("@")[-1]
    print(f"migrations applied -> {_target}")

