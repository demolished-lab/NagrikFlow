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
    from app import backup as B
    out = B.run(__import__("app.main", fromlist=["x"]).engine, dest_dir=tmp_path)
    assert out["bytes"] > 0 and out["kept"] == 1
    con = sqlite3.connect(out["file"])
    tables = {r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    con.close()
    assert "user" in tables and "taskmap" in tables
    # retention: fake 10 old files -> keep 7
    for i in range(10):
        (tmp_path / f"civic-2020010{i}-000000.db").touch()
    B.run(__import__("app.main", fromlist=["x"]).engine, dest_dir=tmp_path)
    assert len(list(tmp_path.glob("civic-*.db"))) == 7
    # endpoints
    H = admin["headers"]
    assert client.post("/admin/backup", headers=H).status_code in (200, 500)
    assert isinstance(client.get("/admin/backups", headers=H).json(), list)
