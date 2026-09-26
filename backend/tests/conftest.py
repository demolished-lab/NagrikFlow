import os
import sys
import tempfile

sys.path.insert(0, r"C:\Users\Raja\civic-pathfinder\backend")

_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp.name}"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import app.main as M  # noqa: E402
from app import security as S  # noqa: E402

_counter = [0]


def _unique(prefix: str) -> str:
    _counter[0] += 1
    return f"{prefix}{_counter[0]}@t.co"


@pytest.fixture()
def client():
    S._hits.clear()
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
