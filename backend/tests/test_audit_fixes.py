"""Regression coverage for the 2026-09-27 external audit fixes.

Covers: map scoping, OTP lockout + single-active-code, extended erasure,
admin verify graph/provenance gates, job staleness/recovery, Redis limiter
degradation, SSRF guard on the wigolo fetch path, build-task catalog
fallback, pick_link quality, and the paperless docs suppression.
"""
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from sqlmodel import Session, select

GOOD_GRAPH = {"nodes": [
    {"id": "a", "type": "action", "title": "Step A", "detail": "", "url": "", "fee": ""},
    {"id": "b", "type": "prereq", "title": "Step B", "detail": "", "url": "", "fee": ""},
], "edges": [["a", "b"]]}


def _seed_map(slug, graph, *, created_by=0, source_urls=None,
              content_hash="", checked_at=None, verified_at=None):
    from app import main as M
    from app.models import TaskMap
    with Session(M.engine) as s:
        s.add(TaskMap(slug=slug, title=f"Map {slug}",
                      graph_json=json.dumps(graph),
                      source_urls=json.dumps(source_urls or []),
                      content_hash=content_hash, checked_at=checked_at,
                      created_by=created_by, verified_at=verified_at))
        s.commit()


def _verify(client, admin, slug, verified=True):
    return client.post(f"/admin/maps/{slug}/verify", headers=admin["headers"],
                       json={"verified": verified})


# ------------------------------- map scoping -------------------------------

def test_task_endpoint_scopes_unverified_maps(client, user, admin):
    from app import main as M
    from app.models import TaskMap, User
    with Session(M.engine) as s:
        who = s.exec(select(User).where(User.email == user["email"])).first()
        s.add(TaskMap(slug="task-scoping-draft", title="Draft",
                      created_by=who.id, graph_json=json.dumps(GOOD_GRAPH)))
        s.commit()

    assert client.get("/task/task-scoping-draft",
                      headers=user["headers"]).status_code == 200
    assert client.get("/task/task-scoping-draft",
                      headers=admin["headers"]).status_code == 200
    stranger = client.post("/auth/register",
                           json={"email": "task-scoping-stranger@t.co",
                                 "password": "pw123456"}).json()
    r = client.get("/task/task-scoping-draft",
                   headers={"Authorization": f"Bearer {stranger['token']}"})
    assert r.status_code == 404


# --------------------------------- OTP auth --------------------------------

def test_otp_previous_code_is_retired(client):
    from app import security as S
    old = S.LIMITS["/auth/otp"]
    S.LIMITS["/auth/otp"] = (50, 600)
    try:
        client.post("/auth/register",
                    json={"email": "otp-retire@t.co", "password": "pw123456"})
        with patch("secrets.randbelow", return_value=111111):
            client.post("/auth/otp/request", json={"email": "otp-retire@t.co"})
        with patch("secrets.randbelow", return_value=222222):
            client.post("/auth/otp/request", json={"email": "otp-retire@t.co"})
        # first code was retired by the second request
        assert client.post("/auth/otp/verify", json={
            "email": "otp-retire@t.co", "code": "211111"}).status_code == 401
        # only the newest code verifies
        assert client.post("/auth/otp/verify", json={
            "email": "otp-retire@t.co", "code": "322222"}).status_code == 200
    finally:
        S.LIMITS["/auth/otp"] = old


def test_otp_per_account_lockout(client):
    from app import main as M
    from app import security as S
    from app.models import User
    old = S.LIMITS["/auth/otp"]
    S.LIMITS["/auth/otp"] = (50, 600)
    try:
        client.post("/auth/register",
                    json={"email": "otp-lock@t.co", "password": "pw123456"})
        with Session(M.engine) as s:
            u = s.exec(select(User).where(User.email == "otp-lock@t.co")).first()
            u.failed_attempts = S.MAX_FAILS - 1
            s.add(u)
            s.commit()
        with patch("secrets.randbelow", return_value=111111):
            client.post("/auth/otp/request", json={"email": "otp-lock@t.co"})
        # one more miss trips the per-account lock
        assert client.post("/auth/otp/verify", json={
            "email": "otp-lock@t.co", "code": "000000"}).status_code == 401
        with Session(M.engine) as s:
            u = s.exec(select(User).where(User.email == "otp-lock@t.co")).first()
            assert u.locked_until is not None
        # locked: even the correct code is rejected until the lock expires
        assert client.post("/auth/otp/verify", json={
            "email": "otp-lock@t.co", "code": "211111"}).status_code == 423
    finally:
        S.LIMITS["/auth/otp"] = old


# --------------------------------- erasure ---------------------------------

def test_account_delete_erases_extended_rows(client, user):
    from app import main as M
    from app.models import (Grievance, Job, Notification, RoadmapMilestone,
                            User)
    with Session(M.engine) as s:
        who = s.exec(select(User).where(User.email == user["email"])).first()
        uid = who.id
        s.add(RoadmapMilestone(user_id=uid, map_slug="udyam-register",
                               step_id="gst",
                               due_at=datetime.now(timezone.utc)))
        s.add(Notification(user_id=uid, reference="deadline-gst",
                           title="GST deadline"))
        s.add(Grievance(user_id=uid, subject="s", message="m"))
        s.add(Job(kind="build", created_by=uid, payload="{}"))
        s.commit()

    r = client.delete("/me/account", headers=user["headers"])
    assert r.status_code == 200, r.text

    with Session(M.engine) as s:
        assert not s.exec(select(RoadmapMilestone).where(
            RoadmapMilestone.user_id == uid)).all()
        assert not s.exec(select(Notification).where(
            Notification.user_id == uid)).all()
        assert not s.exec(select(Grievance).where(
            Grievance.user_id == uid)).all()
        assert not s.exec(select(Job).where(
            Job.created_by == uid)).all()
        assert s.exec(select(User).where(User.id == uid)).first() is None


# --------------------------- admin verify gates ----------------------------

def test_admin_verify_rejects_broken_graphs(client, admin):
    now = datetime.now(timezone.utc)
    cases = [
        ("verify-empty", {"nodes": [], "edges": []}, "no steps"),
        ("verify-dangling", {"nodes": [{"id": "a"}], "edges": [["a", "zz"]]},
         "unknown step"),
        ("verify-cycle", {"nodes": [{"id": "a"}, {"id": "b"}],
                          "edges": [["a", "b"], ["b", "a"]]}, "cycle"),
    ]
    for slug, graph, needle in cases:
        _seed_map(slug, graph, source_urls=["https://x.gov.in/"],
                  content_hash="h", checked_at=now)
        r = _verify(client, admin, slug)
        assert r.status_code == 400, (slug, r.text)
        assert needle in r.json()["detail"]


def test_admin_verify_requires_fresh_provenance(client, admin):
    now = datetime.now(timezone.utc)
    _seed_map("verify-nosources", GOOD_GRAPH, content_hash="h",
              checked_at=now)
    r = _verify(client, admin, "verify-nosources")
    assert r.status_code == 400
    assert "source_urls" in r.json()["detail"]

    _seed_map("verify-nohash", GOOD_GRAPH,
              source_urls=["https://x.gov.in/"], checked_at=now)
    r = _verify(client, admin, "verify-nohash")
    assert r.status_code == 400
    assert "content_hash" in r.json()["detail"]

    _seed_map("verify-stale", GOOD_GRAPH, source_urls=["https://x.gov.in/"],
              content_hash="h", checked_at=now - timedelta(days=46))
    r = _verify(client, admin, "verify-stale")
    assert r.status_code == 400
    assert "old" in r.json()["detail"]

    _seed_map("verify-good", GOOD_GRAPH, source_urls=["https://x.gov.in/"],
              content_hash="h", checked_at=now)
    r = _verify(client, admin, "verify-good")
    assert r.status_code == 200, r.text
    assert r.json()["verified"]


# ------------------------------- job hygiene -------------------------------

def test_recover_orphans_fails_expired_and_redispatches_fresh(client,
                                                              monkeypatch):
    from app import jobs as J
    from app import main as M
    from app.models import Job

    dispatched = []
    monkeypatch.setattr(J, "_dispatch_thread",
                        lambda engine, jid, kind: dispatched.append((jid, kind)))

    with Session(M.engine) as s:
        stale = Job(kind="build", status="running", payload="{}",
                    created_at=datetime.now(timezone.utc) - timedelta(hours=25))
        fresh = Job(kind="mystery", status="running", payload="{}")
        s.add(stale)
        s.add(fresh)
        s.commit()
        s.refresh(stale)
        s.refresh(fresh)
        stale_id, fresh_id = stale.id, fresh.id

    try:
        J.recover_orphans(M.engine)
        with Session(M.engine) as s:
            stale_j = s.get(Job, stale_id)
            fresh_j = s.get(Job, fresh_id)
            assert stale_j.status == "failed"
            assert "expired" in json.loads(stale_j.result)["error"]
            assert fresh_j.status == "queued"
        assert (fresh_id, "mystery") in dispatched
        assert (stale_id, "build") not in dispatched
    finally:
        with Session(M.engine) as s:
            for jid in (stale_id, fresh_id):
                row = s.get(Job, jid)
                if row:
                    s.delete(row)
            s.commit()


def test_job_status_endpoint_fails_stale_running_job(client, user):
    from app import main as M
    from app.models import Job, User
    with Session(M.engine) as s:
        who = s.exec(select(User).where(User.email == user["email"])).first()
        j = Job(kind="build", status="running", created_by=who.id,
                payload="{}",
                created_at=datetime.now(timezone.utc) - timedelta(hours=2))
        s.add(j)
        s.commit()
        s.refresh(j)
        jid = j.id
    try:
        r = client.get(f"/jobs/{jid}", headers=user["headers"])
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "failed"
        assert "stale" in body["result"]["error"]
    finally:
        with Session(M.engine) as s:
            row = s.get(Job, jid)
            if row:
                s.delete(row)
                s.commit()


# ---------------------------- rate-limit fail mode -------------------------

def test_redis_store_degrades_to_memory(monkeypatch):
    from app.security_redis import RedisStore

    class Boom:
        def lrange(self, *a, **k):
            raise ConnectionError("redis down")

        def pipeline(self):
            raise ConnectionError("redis down")

    store = RedisStore(Boom(), fallback=None)
    assert store.allow("1.2.3.4", "default", 2, 60) is True
    assert store.allow("1.2.3.4", "default", 2, 60) is True
    assert store.allow("1.2.3.4", "default", 2, 60) is False

    monkeypatch.setenv("RATE_LIMIT_FAIL_CLOSED", "1")
    strict = RedisStore(Boom(), fallback=None)
    assert strict.allow("1.2.3.4", "default", 2, 60) is False


# --------------------------------- SSRF ------------------------------------

def test_discover_fetch_text_blocks_non_public(monkeypatch):
    from app import discover as D

    monkeypatch.setattr("app.worker._probe_target_ok", lambda u: False)

    def _no_network(*a, **k):
        raise AssertionError("network path must not be reached")

    monkeypatch.setattr(D, "_run", _no_network)
    with pytest.raises(RuntimeError, match="non-public"):
        D.fetch_text("http://internal.corp.local/x")
    with pytest.raises(RuntimeError, match="scheme"):
        D.fetch_text("ftp://files.example/x")


# --------------------------- build-task resilience -------------------------

def test_build_task_catalog_fallback_when_search_is_empty(client, user,
                                                          monkeypatch):
    from app import main as M
    import app.jobs as J

    monkeypatch.setattr(M.discovermod, "discover", lambda q, max_results=8: [])
    monkeypatch.setattr(M, "_validate_fetch_url", lambda u: u)
    monkeypatch.setattr(J, "run_build", lambda engine, jid: None)

    r = client.post("/build-task", headers=user["headers"], json={
        "task": "register a small business", "city": "Hyderabad",
        "state": "Telangana", "service_type": "Business & Trade"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["discovery"] == "catalog"
    assert body["urls_found"] > 0


def test_build_task_skips_policy_rejected_urls(client, user, monkeypatch):
    from fastapi import HTTPException
    from app import main as M
    import app.jobs as J

    monkeypatch.setattr(M.discovermod, "discover",
                        lambda q, max_results=8: [
                            {"url": "http://127.0.0.1/internal"},
                            {"url": "https://udyamregistration.gov.in/"}])
    seen = []

    def gate(url):
        if "127.0.0.1" in url:
            raise HTTPException(400, "blocked")
        seen.append(url)
        return url

    monkeypatch.setattr(M, "_validate_fetch_url", gate)
    monkeypatch.setattr(J, "run_build", lambda engine, jid: None)

    r = client.post("/build-task", headers=user["headers"], json={
        "task": "udyam registration"})
    assert r.status_code == 200, r.text
    assert r.json()["urls_found"] == 1
    assert seen == ["https://udyamregistration.gov.in/"]


# ------------------------------ link quality -------------------------------

def test_pick_link_prefers_form_over_grievance_pages():
    from app import worker as W
    text = ("Apply: https://udyamregistration.gov.in/UdyamRegistration.aspx "
            "or raise https://udyamregistration.gov.in/grievance-helpdesk "
            "see also https://udyamregistration.gov.in/faq")
    picked = W.pick_link(text, "https://udyamregistration.gov.in/home")
    assert picked == "https://udyamregistration.gov.in/UdyamRegistration.aspx"


def test_pick_link_returns_empty_when_only_bad_links():
    from app import worker as W
    text = ("https://portal.gov.in/complaint "
            "https://portal.gov.in/feedback "
            "https://portal.gov.in/helpdesk")
    assert W.pick_link(text, "https://portal.gov.in/") == ""


def test_pick_link_ignores_hint_words_in_hostname_only():
    from app import worker as W
    # hint "apply" lives only in the cross-host hostname, path is neutral
    text = "Visit https://apply.tn.gov.in/plain"
    assert W.pick_link(text, "https://portal.tn.gov.in/start") == ""


def test_pick_link_accepts_cross_host_with_path_evidence():
    from app import worker as W
    text = "Register at https://gst.gov.in/registration"
    assert W.pick_link(text, "https://udyamregistration.gov.in/home") == \
        "https://gst.gov.in/registration"


# ------------------------- paperless docs heuristic ------------------------

def test_heuristic_extract_suppresses_docs_on_paperless_pages():
    from app import worker as W
    paperless = ("Udyam registration is a paperless process. "
                 "PAN and Aadhaar details are captured online, "
                 "no documents to upload.")
    steps = W.heuristic_extract(paperless, "https://udyamregistration.gov.in/")
    assert [s["id"] for s in steps] == ["apply"]

    normal = "Bring your PAN card and Aadhaar letter to the office."
    steps = W.heuristic_extract(normal, "https://example.gov.in/page")
    assert any(s["id"] == "docs" for s in steps)
