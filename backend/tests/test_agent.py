"""Test coverage for Mini-Hermes agent subsystem."""
import json
from pathlib import Path

from sqlmodel import Session, select


def test_agent_tools_schema(client, admin):
    """Agent tools endpoint returns registered tool schemas."""
    r = client.get("/agent/tools", headers=admin["headers"])
    assert r.status_code == 200
    tools = r.json()["tools"]
    names = [t["name"] for t in tools]
    assert "read_file" in names
    assert "write_file" in names
    assert "patch_file" in names
    assert "run_cmd" in names


def test_agent_audit_empty(client, admin):
    """Audit log starts empty or returns entries."""
    r = client.get("/agent/audit?n=10", headers=admin["headers"])
    assert r.status_code == 200
    assert isinstance(r.json()["entries"], list)


def test_agent_run_requires_admin(client):
    """Non-admin cannot trigger agent jobs."""
    r = client.post("/auth/register", json={
        "email": "user@civic.test", "password": "pw12345678"})
    h = {"Authorization": f"Bearer {r.json()['token']}"}
    run = client.post("/agent/run", json={"task": "test", "mode": "auto"}, headers=h)
    assert run.status_code == 403


def test_grievance_model_exists(client):
    """Grievance table is created by migrations."""
    import app.main as M
    from sqlmodel import Session, select
    from app.models import Grievance
    with Session(M.engine) as s:
        count = len(s.exec(select(Grievance)).all())
    assert isinstance(count, int)
