"""Ops: secrets rotation, metrics, backups."""
import sqlite3


def test_metrics_collects(client):
    client.get("/health")
    client.get("/health")
    from app import obs as O
    snap = O.snapshot()
    assert snap["/health"]["hits"] >= 2
    assert "avg_ms" in snap["/health"]


def test_backup_roundtrip_to_tmpdir(tmp_path, client, admin):
    import shutil
    import subprocess

    from app import backup as B
    engine = __import__("app.main", fromlist=["x"]).engine
    is_sqlite = str(engine.url).startswith("sqlite")
    out = B.run(engine, dest_dir=tmp_path)
    assert out["bytes"] > 0 and out["kept"] == 1
    if is_sqlite:
        con = sqlite3.connect(out["file"])
        tables = {r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        con.close()
        assert "user" in tables and "taskmap" in tables
        suffix = "db"
    else:
        pg = shutil.which("pg_restore")
        assert pg, "pg_restore needed to verify a pg_dump archive"
        r = subprocess.run([pg, "--list", out["file"]],
                           capture_output=True, text=True, timeout=120)
        assert r.returncode == 0 and "taskmap" in r.stdout, r.stderr[:300]
        suffix = "dump"
    # retention: fake 10 old files -> keep 7
    for i in range(10):
        (tmp_path / f"civic-2020010{i}-000000.{suffix}").touch()
    B.run(engine, dest_dir=tmp_path)
    assert len(list(tmp_path.glob(f"civic-*.{suffix}"))) == 7
    # endpoints
    H = admin["headers"]
    assert client.post("/admin/backup", headers=H).status_code in (200, 500)
    assert isinstance(client.get("/admin/backups", headers=H).json(), list)


def test_backup_validate_and_restore(tmp_path):
    from pathlib import Path

    import pytest
    from sqlalchemy import create_engine
    from sqlmodel import SQLModel

    from app import backup as B
    from app import models  # noqa: F401  (register all tables)

    db = tmp_path / "target.db"
    url = f"sqlite:///{db.as_posix()}"
    engine = create_engine(url)
    SQLModel.metadata.create_all(engine)

    out = B.run(engine, dest_dir=tmp_path)
    backup_file = Path(out["file"])
    assert backup_file != db
    assert B.validate(backup_file)["valid"] is True

    # corrupt files must never pass validation
    bad = tmp_path / "civic-19990101-000000.db"
    bad.write_bytes(b"this is not a database")
    assert B.validate(bad)["valid"] is False

    # an existing target requires explicit confirmation
    db.write_bytes(b"corrupted-but-present")
    engine.dispose()
    with pytest.raises(RuntimeError, match="confirm"):
        B.restore(engine, backup_file, confirm=False)

    r = B.restore(engine, backup_file, confirm=True)
    assert r["restored"] is True and r["valid"] is True
    with sqlite3.connect(db) as c:
        tables = {row[0] for row in c.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
    assert "taskmap" in tables and "user" in tables

    with pytest.raises(FileNotFoundError):
        B.restore(engine, tmp_path / "missing.db", confirm=True)
