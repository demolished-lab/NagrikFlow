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


# ================= round-4 remediation (re-audit at 8e57023) ================

def test_build_task_catalog_fallback_when_all_search_urls_filtered(client, user,
                                                                   monkeypatch):
    """Search returning ONLY non-government URLs must fall through to the
    curated catalog instead of 400ing."""
    from fastapi import HTTPException
    from app import main as M
    import app.jobs as J

    monkeypatch.setattr(M.discovermod, "discover",
                        lambda q, max_results=8: [
                            {"url": "https://ugly.example/listing"}])

    def gate(url):
        if "ugly.example" in url:
            raise HTTPException(400, "not a government source")
        return url

    monkeypatch.setattr(M, "_validate_fetch_url", gate)
    monkeypatch.setattr(J, "run_build", lambda engine, jid: None)

    r = client.post("/build-task", headers=user["headers"], json={
        "task": "udyam registration"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["discovery"] == "catalog"
    assert body["urls_found"] > 0


def test_heuristic_uday_audit_quotes_free_paperless_and_link():
    """The re-audit's quoted Udyam text must yield ₹0 + paperless detail and
    the real application link — never a docs step or a help/grievance URL."""
    from app import worker as W
    text = ("Udyam (MSME) Registration is Free of Cost and paperless. "
            "No documents or proof are required for registering an MSME. "
            "Only Adhaar Number will be enough for registration. "
            "Apply at https://udyamregistration.gov.in/UdyamRegistration.aspx "
            "Need help? https://champions.gov.in/grievance or "
            "https://udyamregistration.gov.in/faq")
    steps = W.heuristic_extract(text, "https://udyamregistration.gov.in/")
    assert "docs" not in [s["id"] for s in steps]
    apply = next(s for s in steps if s["id"] == "apply")
    assert apply["fee"] == "₹0"
    assert "Free of cost" in apply["detail"]
    assert "Paperless" in apply["detail"]
    assert apply["link"] == \
        "https://udyamregistration.gov.in/UdyamRegistration.aspx"


def test_heuristic_doc_mention_without_requirement_verb_is_dropped():
    from app import worker as W
    text = "The portal accepts PAN as identity proof and uses Aadhaar for eKYC."
    steps = W.heuristic_extract(text, "https://example.gov.in/scheme")
    assert "docs" not in [s["id"] for s in steps]
    apply = next(s for s in steps if s["id"] == "apply")
    assert apply["link"] == "https://example.gov.in/scheme"  # source fallback


def test_guarded_redirect_blocks_internal_hop(monkeypatch):
    from app import worker as W
    monkeypatch.delenv("SSRF_PROBE", raising=False)
    monkeypatch.setattr(W, "_probe_target_ok",
                        lambda u: False if "internal" in u else True)
    handler = W._GuardedRedirect()
    req = W.urllib.request.Request("https://ok.example/")
    with pytest.raises(W._BadRedirect):
        handler.redirect_request(req, None, 302, "Found", None,
                                 "https://internal.corp.local/x")
    # dev/sim opt-out still works for localhost fixture servers
    monkeypatch.setenv("SSRF_PROBE", "0")
    out = handler.redirect_request(req, None, 302, "Found", None,
                                   "https://internal.corp.local/x")
    assert out is not None and out.full_url == "https://internal.corp.local/x"


def test_job_claim_is_exactly_once(client):
    from app import jobs as J
    from app import main as M
    from app.models import Job
    with Session(M.engine) as s:
        j = Job(kind="build", payload="{}")
        s.add(j)
        s.commit()
        s.refresh(j)
        jid = j.id
    try:
        assert J.claim(M.engine, jid) is True
        assert J.claim(M.engine, jid) is False  # second dispatcher loses
        with Session(M.engine) as s:
            row = s.get(Job, jid)
            assert row.status == "running"
            assert row.lease_until is not None
            assert row.worker_id
        with Session(M.engine) as s:  # finished jobs are never claimable
            row = s.get(Job, jid)
            row.status = "failed"
            s.add(row)
            s.commit()
        assert J.claim(M.engine, jid) is False
    finally:
        with Session(M.engine) as s:
            row = s.get(Job, jid)
            if row:
                s.delete(row)
                s.commit()


def test_poll_once_lease_semantics(client, monkeypatch):
    from app import jobs as J
    from app import main as M
    from app.models import Job
    dispatched = []
    monkeypatch.setattr(J, "_dispatch_thread",
                        lambda engine, jid, kind: dispatched.append((jid, kind)))
    now = datetime.now(timezone.utc)
    rows = {}
    with Session(M.engine) as s:
        rows["queued"] = Job(kind="agent", payload="{}")
        rows["live"] = Job(kind="recheck", status="running", payload="{}",
                           lease_until=now + timedelta(minutes=10))
        rows["dead"] = Job(kind="hermes", status="running", payload="{}",
                           lease_until=now - timedelta(minutes=1))
        rows["expired"] = Job(kind="build", payload="{}",
                              created_at=now - timedelta(hours=25))
        for j in rows.values():
            s.add(j)
        s.commit()
        for j in rows.values():
            s.refresh(j)
        ids = {k: j.id for k, j in rows.items()}
    try:
        J.poll_once(M.engine)
        assert (ids["queued"], "agent") in dispatched
        assert (ids["dead"], "hermes") in dispatched       # expired lease revived
        assert (ids["live"], "recheck") not in dispatched  # live lease untouched
        assert (ids["expired"], "build") not in dispatched
        with Session(M.engine) as s:
            assert s.get(Job, ids["live"]).status == "running"
            assert s.get(Job, ids["dead"]).status == "queued"
            assert s.get(Job, ids["expired"]).status == "failed"
    finally:
        with Session(M.engine) as s:
            for jid in ids.values():
                row = s.get(Job, jid)
                if row:
                    s.delete(row)
            s.commit()


def test_recover_orphans_leaves_live_leases_alone(client, monkeypatch):
    from app import jobs as J
    from app import main as M
    from app.models import Job
    dispatched = []
    monkeypatch.setattr(J, "_dispatch_thread",
                        lambda engine, jid, kind: dispatched.append(jid))
    with Session(M.engine) as s:
        j = Job(kind="build", status="running", payload="{}",
                lease_until=datetime.now(timezone.utc) + timedelta(minutes=10))
        s.add(j)
        s.commit()
        s.refresh(j)
        jid = j.id
    try:
        J.recover_orphans(M.engine)
        with Session(M.engine) as s:
            assert s.get(Job, jid).status == "running"  # other instance's work
        assert jid not in dispatched
    finally:
        with Session(M.engine) as s:
            row = s.get(Job, jid)
            if row:
                s.delete(row)
                s.commit()


def test_taskmap_slug_unique_index_enforced(client):
    from sqlalchemy.exc import IntegrityError
    _seed_map("uq-round4", GOOD_GRAPH)
    with pytest.raises(IntegrityError):
        _seed_map("uq-round4", GOOD_GRAPH)
    from app import main as M
    from app.models import TaskMap
    with Session(M.engine) as s:
        for row in s.exec(select(TaskMap).where(
                TaskMap.slug == "uq-round4")).all():
            s.delete(row)
        s.commit()


def test_account_delete_erases_drafts_anonymizes_verified(client, user, admin):
    from app import main as M
    from app.models import Progress, TaskMap, User
    now = datetime.now(timezone.utc)
    with Session(M.engine) as s:
        who = s.exec(select(User).where(User.email == user["email"])).first()
        uid = who.id
        other = s.exec(select(User).where(
            User.email == "demo@civic.test")).first()
        aid = other.id if other else 0
        s.add(Progress(user_id=aid, map_slug="draft-round4", step_id="a"))
        s.commit()
    _seed_map("draft-round4", GOOD_GRAPH, created_by=uid)
    _seed_map("verified-round4", GOOD_GRAPH, created_by=uid, verified_at=now)
    try:
        r = client.delete("/me/account", headers=user["headers"])
        assert r.status_code == 200, r.text
        with Session(M.engine) as s:
            assert s.exec(select(TaskMap).where(
                TaskMap.slug == "draft-round4")).first() is None
            kept = s.exec(select(TaskMap).where(
                TaskMap.slug == "verified-round4")).first()
            assert kept is not None and kept.created_by == 0
            assert s.exec(select(Progress).where(
                Progress.map_slug == "draft-round4")).first() is None
    finally:
        with Session(M.engine) as s:
            for slug in ("draft-round4", "verified-round4"):
                for row in s.exec(select(TaskMap).where(
                        TaskMap.slug == slug)).all():
                    s.delete(row)
            s.commit()


def test_telegram_webhook_fail_closed_without_secret(monkeypatch):
    from app import telegram_validate as T
    monkeypatch.delenv("CIVIC_DEV", raising=False)
    monkeypatch.delenv("ALLOW_DEV_SECRET", raising=False)
    monkeypatch.setattr(T, "_TELEGRAM_SECRET", "")
    with pytest.raises(ValueError, match="not configured"):
        T.check(None)
    monkeypatch.setenv("CIVIC_DEV", "1")  # dev tolerates an unset secret
    T.check(None)
    monkeypatch.setattr(T, "_TELEGRAM_SECRET", "s3cr3t")  # prod: must match
    T.check("s3cr3t")
    with pytest.raises(ValueError, match="invalid"):
        T.check("wrong")


def test_build_task_quota_returns_429(client, user, monkeypatch):
    from app import main as M
    from app.models import Job, User
    with Session(M.engine) as s:
        who = s.exec(select(User).where(User.email == user["email"])).first()
        uid = who.id
        for _ in range(3):  # default JOB_MAX_ACTIVE_PER_USER = 3
            s.add(Job(kind="build", created_by=uid, payload="{}"))
        s.commit()
    try:
        r = client.post("/build-task", headers=user["headers"],
                        json={"task": "udyam registration"})
        assert r.status_code == 429, r.text
    finally:
        with Session(M.engine) as s:
            for j in s.exec(select(Job).where(Job.created_by == uid)).all():
                s.delete(j)
            s.commit()


def test_build_task_field_length_caps(client, user):
    r = client.post("/build-task", headers=user["headers"],
                    json={"task": "x" * 600})
    assert r.status_code == 422
    r = client.post("/build-task", headers=user["headers"],
                    json={"task": "udyam", "city": "y" * 120})
    assert r.status_code == 422


def test_progress_and_notification_unique_indexes(client, user):
    from sqlalchemy.exc import IntegrityError
    from app import main as M
    from app.models import Notification, Progress, User
    with Session(M.engine) as s:
        who = s.exec(select(User).where(User.email == user["email"])).first()
        uid = who.id
        s.add(Progress(user_id=uid, map_slug="idx-round4", step_id="a"))
        s.commit()
        with pytest.raises(IntegrityError):
            s.add(Progress(user_id=uid, map_slug="idx-round4", step_id="a"))
            s.commit()
        s.rollback()
        s.add(Notification(user_id=uid, reference="dup-ref", title="t"))
        s.commit()
        with pytest.raises(IntegrityError):
            s.add(Notification(user_id=uid, reference="dup-ref", title="t2"))
            s.commit()
        s.rollback()
        for row in s.exec(select(Progress).where(Progress.user_id == uid)).all():
            s.delete(row)
        for row in s.exec(select(Notification).where(
                Notification.user_id == uid)).all():
            s.delete(row)
        s.commit()


def test_migrate_recovers_old_db_missing_new_columns(tmp_path):
    """A real-world DB at versions 1-6 has taskmap without created_by.
    m007's ORM SELECT used to crash boot there — the column safety net only
    ran AFTER the migration loop. It must run before it too."""
    from sqlalchemy import create_engine, inspect, text
    from app.migrate import SchemaVersion, migrate

    engine = create_engine(f"sqlite:///{tmp_path}/old.db")
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE taskmap (id INTEGER PRIMARY KEY, slug VARCHAR,"
            " title VARCHAR, city VARCHAR, graph_json TEXT,"
            " verified_at TIMESTAMP, source_urls TEXT)"))
    SchemaVersion.__table__.create(engine, checkfirst=True)
    with Session(engine) as s:
        for v in range(1, 7):
            s.add(SchemaVersion(version=v))
        s.commit()

    migrate(engine)  # must not raise

    cols = {c["name"] for c in inspect(engine).get_columns("taskmap")}
    assert "created_by" in cols
    with Session(engine) as s:
        applied = {r.version for r in s.exec(select(SchemaVersion)).all()}
    assert 7 in applied  # m007 completed once the columns existed
    engine.dispose()
