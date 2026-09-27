"""Production-hardening tests: nltk guard, Redis rate limiter, health/metrics
endpoints, integration doctor, cloud/Postgres backups."""
import json as _json

from sqlmodel import select


# ---------------- 1. nltk runtime guard (PYSEC-2026-3740) ----------------

def test_nltk_guard_blocks_traversal_and_absolutes():
    from app import nltk_guard as G
    assert G.install() in (True, False)
    assert G.install() is True  # idempotent
    import nltk.data as D
    assert getattr(D.find, "_civic_guarded", False)
    assert G.is_installed()

    for bad in ("tokenizers/../../secrets",
                "corpora/..\\..\\windows\\system32",
                "file:///etc/passwd"):
        try:
            D.find(bad)
        except ValueError as e:
            assert "nltk_guard" in str(e)
        else:
            raise AssertionError(f"guard let through: {bad}")

    import os
    abs_outside = os.path.abspath(os.path.join(os.environ.get("TEMP", r"C:\Temp"), "x"))
    try:
        D.find(abs_outside)
    except ValueError as e:
        assert "nltk_guard" in str(e)
    else:
        raise AssertionError("absolute path outside nltk_data accepted")


def test_nltk_guard_allows_legit_constant_paths():
    from app import nltk_guard as G
    G.install()
    import nltk.data as D
    try:
        D.find("tokenizers/punkt")
    except ValueError as e:
        if "nltk_guard" in str(e):
            raise AssertionError("guard blocked a legitimate corpus path")
    except LookupError:
        pass  # corpus not downloaded here; guard did not interfere


# ---------------- 2. rate limiting: memory + shared Redis ----------------

def test_memory_store_429_with_retry_after(client):
    for i in range(5):
        r = client.post("/auth/otp", json={})
        assert r.status_code != 429, f"request {i+1} unexpectedly limited"
    r = client.post("/auth/otp", json={})
    assert r.status_code == 429
    assert r.headers.get("retry-after") == "600"
    assert "rate limited" in r.json()["detail"]


def test_redis_store_shared_across_workers(client, monkeypatch):
    import fakeredis
    from app import security as S
    from app import security_redis as SR

    fake = fakeredis.FakeStrictRedis()
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setattr(SR, "get_client", lambda: fake)
    S.reset_store()
    try:
        for i in range(5):
            assert client.post("/auth/otp", json={}).status_code != 429
        # simulate a NEW worker process: fresh store, same Redis -> still limited
        S.reset_store()
        assert client.post("/auth/otp", json={}).status_code == 429
    finally:
        S.reset_store()
        SR.reset()


def test_healthz_and_readyz(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"ok": True, "status": "live"}

    r = client.get("/readyz")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["checks"]["database"] == "ok"
    assert body["checks"]["migrations"] == "ok"


def test_readyz_fails_when_redis_configured_but_down(client, monkeypatch):
    from app import security_redis as SR
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setattr(SR, "get_client", lambda: None)
    monkeypatch.setattr(SR, "reset", lambda: None)
    r = client.get("/readyz")
    assert r.status_code == 503
    assert r.json()["checks"]["redis"] == "fail"
    assert r.json()["ok"] is False


# ---------------- 3. Prometheus metrics ----------------

def test_norm_path_bounds_cardinality():
    from app import obs as O
    assert O.norm_path("/auth/login") == "/auth/login"
    assert O.norm_path("/admin/maps/udyam-register/steps") == "/admin/maps/*"
    assert O.norm_path("/task/udyam-register") == "/task/udyam-register"
    assert O.norm_path("/") == "/"


def test_prometheus_endpoint(client):
    client.get("/healthz")  # ensure at least one counted route
    r = client.get("/metrics")
    assert r.status_code == 200
    assert "text/plain" in r.headers["content-type"]
    body = r.text
    assert "civic_http_requests_total" in body
    assert "civic_http_errors_total" in body
    assert "civic_http_request_duration_ms_total" in body
    assert 'route="/healthz"' in body


def test_metrics_token_gate(client, monkeypatch):
    monkeypatch.setenv("METRICS_TOKEN", "sek-metrics")
    assert client.get("/metrics").status_code == 401
    assert client.get("/metrics", headers={"X-Metrics-Token": "wrong"}).status_code == 401
    ok = client.get("/metrics", headers={"Authorization": "Bearer sek-metrics"})
    assert ok.status_code == 200


# ---------------- 4. integration doctor ----------------

def test_admin_integrations_reports_config(client, admin, user, monkeypatch):
    from app import main as M

    async def fake_health():
        return {"overall": "ok"}
    monkeypatch.setattr(M.llmhealth, "health_check", fake_health)

    assert client.get("/admin/integrations",
                      headers=user["headers"]).status_code == 403
    r = client.get("/admin/integrations", headers=admin["headers"])
    assert r.status_code == 200, r.text
    body = r.json()
    for key in ("database", "rate_limiter", "redis", "telegram", "digilocker",
                "llm", "backup", "email", "nltk_guard"):
        assert key in body, key
    # secrets never echoed: only booleans/structure
    assert isinstance(body["telegram"]["bot_token"], bool)
    assert isinstance(body["digilocker"]["client_id"], bool)
    assert isinstance(body["nltk_guard"]["installed"], bool)
    assert "token" not in _json.dumps(body).lower().replace("bot_token", "")
    # no live probe unless requested
    assert body["telegram"]["live"] is None


# ---------------- 5. backups: sqlite / pg / cloud ----------------

def test_backup_sqlite_local(client, tmp_path):
    from app import backup as B
    from app import main as M
    res = B.run(M.engine, dest_dir=tmp_path)
    assert res["bytes"] > 0
    assert res["kept"] <= B.BACKUP_KEEP
    assert res["uploaded"] is False
    assert res["reason"] == "s3 not configured"
    assert B.listing(tmp_path)


def test_backup_pg_dump_command(client, monkeypatch, tmp_path):
    from app import backup as B

    calls = {}

    def fake_which(name):
        return "C:/pg/bin/pg_dump.exe" if name == "pg_dump" else None

    def fake_run(cmd, **kw):
        calls["cmd"] = cmd
        calls["env"] = kw.get("env", {})
        open(cmd[cmd.index("-f") + 1], "wb").write(b"PGDMP")
        class R:
            returncode, stderr = 0, ""
        return R()

    monkeypatch.setattr(B.shutil, "which", fake_which)
    monkeypatch.setattr(B.subprocess, "run", fake_run)

    class FakeEngine:
        url = "postgresql+psycopg://civic:s3cret@db:5432/civic"

    res = B.run(FakeEngine(), dest_dir=tmp_path)
    assert res["bytes"] == 5
    assert res["file"].endswith(".dump")
    argv = " ".join(calls["cmd"])
    assert "s3cret" not in argv                      # password stays off argv
    assert calls["env"].get("PGPASSWORD") == "s3cret"


def test_backup_s3_upload(client, monkeypatch, tmp_path):
    from app import backup as B
    from app import main as M

    uploaded = {}

    class FakeS3:
        def upload_file(self, path, bucket, key):
            uploaded.update({"path": path, "bucket": bucket, "key": key})

    import boto3
    monkeypatch.setattr(boto3, "client", lambda *a, **k: FakeS3())
    monkeypatch.setenv("BACKUP_S3_BUCKET", "civic-backups")
    monkeypatch.setenv("BACKUP_S3_KEY_ID", "kid")
    monkeypatch.setenv("BACKUP_S3_SECRET", "sek")
    monkeypatch.setenv("BACKUP_S3_PREFIX", "prod/")

    res = B.run(M.engine, dest_dir=tmp_path)
    assert res["uploaded"] is True
    assert uploaded["bucket"] == "civic-backups"
    assert uploaded["key"].startswith("prod/")
    assert uploaded["path"] == res["file"]


def test_backup_s3_failure_is_nonfatal(client, monkeypatch, tmp_path):
    from app import backup as B
    from app import main as M

    import boto3

    def boom(*a, **k):
        raise RuntimeError("network down")
    monkeypatch.setattr(boto3, "client", boom)
    monkeypatch.setenv("BACKUP_S3_BUCKET", "b")
    monkeypatch.setenv("BACKUP_S3_KEY_ID", "k")
    monkeypatch.setenv("BACKUP_S3_SECRET", "s")

    res = B.run(M.engine, dest_dir=tmp_path)
    assert res["uploaded"] is False
    assert "network down" in res["error"]
    assert res["bytes"] > 0  # local snapshot still succeeded
