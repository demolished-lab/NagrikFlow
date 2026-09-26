"""Auth: register/login/lockout/OTP. Converted from tool-call/sec_check.py."""
from unittest.mock import patch


def test_register_and_login(client):
    assert client.post("/auth/register", json={
        "email": "a@t.co", "password": "pw123456"}).status_code == 200
    assert client.post("/auth/register", json={
        "email": "a@t.co", "password": "pw123456"}).status_code == 409
    r = client.post("/auth/login", json={"email": "a@t.co", "password": "pw123456"})
    assert r.status_code == 200 and "token" in r.json()
    assert client.post("/auth/login", json={
        "email": "a@t.co", "password": "nope"}).status_code == 401


def test_lockout(client):
    client.post("/auth/register", json={"email": "v@t.co", "password": "rightpass"})
    for _ in range(5):
        assert client.post("/auth/login", json={
            "email": "v@t.co", "password": "wrong"}).status_code == 401
    r = client.post("/auth/login", json={"email": "v@t.co", "password": "rightpass"})
    assert r.status_code == 423


def test_otp_roundtrip(client):
    from app import security as S
    old = S.LIMITS["/auth/otp"]
    S.LIMITS["/auth/otp"] = (20, 600)
    try:
        client.post("/auth/register", json={"email": "o@t.co", "password": "pw123456"})
        assert client.post("/auth/otp/request", json={"email": "o@t.co"}).json() == {"ok": True}
        assert client.post("/auth/otp/request", json={"email": "ghost@t.co"}).json() == {"ok": True}
        with patch("secrets.randbelow", return_value=111111):
            client.post("/auth/otp/request", json={"email": "o@t.co"})
        assert client.post("/auth/otp/verify", json={
            "email": "o@t.co", "code": "000000"}).status_code == 401
        assert client.post("/auth/otp/verify", json={
            "email": "o@t.co", "code": "211111"}).status_code == 200
        assert client.post("/auth/otp/verify", json={
            "email": "o@t.co", "code": "211111"}).status_code == 401
    finally:
        S.LIMITS["/auth/otp"] = old


def test_rate_limit_trips(client):
    from app import security as S
    old = S.LIMITS["default"]
    S.LIMITS["default"] = (3, 60)
    try:
        codes = [client.get("/health").status_code for _ in range(5)]
    finally:
        S.LIMITS["default"] = old
    assert codes[0] == 200 and codes[-1] == 429
