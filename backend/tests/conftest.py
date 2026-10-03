import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)  # noqa: SIM115 - sqlite needs the path after close
_tmp.close()
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_tmp.name}")  # CI may preset Postgres
os.environ["ALLOW_DEV_SECRET"] = "1"
os.environ["LINK_PROBE"] = "0"  # tests must never hit the network
os.environ["JOB_POLLER"] = "0"  # no background dispatch racing test job rows
os.environ["RECOVER_JOBS"] = "0"  # recovery also dispatches — off for tests
os.environ["CIVIC_CDX"] = "0"  # Common Crawl archive lane is network — off

import pytest
from fastapi.testclient import TestClient

import app.main as M
from app import security as S

_counter = [0]


def _unique(prefix: str) -> str:
    _counter[0] += 1
    return f"{prefix}{_counter[0]}@t.co"


@pytest.fixture()
def client():
    S.reset_store()
    with TestClient(M.app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture()
def user(client):
    email = _unique("u")
    r = client.post("/auth/register", json={
        "email": email, "password": "pw123456", "name": "U"})
    assert r.status_code == 200, r.text
    tok = r.json()["token"]
    return {"headers": {"Authorization": f"Bearer {tok}"}, "token": tok,
            "email": email}


@pytest.fixture()
def admin(client):
    body = {"email": "demo@civic.test", "password": "demo1234"}
    r = client.post("/auth/register", json=body)
    if r.status_code == 409:  # already seeded by an earlier test: log in
        r = client.post("/auth/login", json=body)
    assert r.status_code == 200, r.text
    tok = r.json()["token"]
    return {"headers": {"Authorization": f"Bearer {tok}"}, "token": tok}
