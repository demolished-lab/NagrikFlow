"""Exception-transparency coverage (2026-09-27 audit directive):

Every failure / exception / unexpected behavior must be
1. logged as a structured one-line warning (obs.warn), and
2. surfaced to the user in API payloads, job results or HTTP responses —
   and where possible fixed (e.g. extract fallbacks store their reason).

Never a silent `except: pass` on a path that degrades user-visible output.
"""
import json
import logging

from sqlmodel import Session

GOOD_NODE = {"id": "a", "type": "action", "title": "Apply",
             "detail": "d", "url": "", "fee": ""}


def test_warn_emits_json_line(caplog):
    from app.obs import warn
    with caplog.at_level(logging.WARNING, logger="civic"):
        warn("scope-x", "something broke", error=ValueError("bad"),
             url="https://x.gov.in/")
    lines = [r.getMessage() for r in caplog.records
             if r.levelname == "WARNING"]
    assert lines, "warn() must emit a WARNING log"
    data = json.loads(lines[-1])
    assert data["level"] == "warning"
    assert data["scope"] == "scope-x"
    assert data["msg"] == "something broke"
    assert "bad" in data["error"]
    assert data["url"] == "https://x.gov.in/"


def test_llm_extract_falls_back_with_logged_reason(monkeypatch, caplog):
    from app import worker

    def boom(prompt, max_tokens=400):
        raise RuntimeError("router down")

    monkeypatch.setattr(worker.llmmod, "_chat_raw", boom)
    with caplog.at_level(logging.WARNING, logger="civic"):
        steps, lane, err = worker._llm_extract_full(
            "Registration is free of cost. Apply now.", "https://x.gov.in/", "t")
    assert lane == "heuristic"
    assert "router down" in err          # reason survives for the API payload
    assert steps and steps[0]["id"] == "apply"   # fallback still works
    assert any("rules fallback" in r.getMessage() for r in caplog.records)


def test_llm_extract_unparseable_reply_falls_back(monkeypatch, caplog):
    from app import worker
    monkeypatch.setattr(
        worker.llmmod, "_chat_raw",
        lambda p, max_tokens=400: ("I cannot help with that.", "m"))
    with caplog.at_level(logging.WARNING, logger="civic"):
        _steps, lane, err = worker._llm_extract_full(
            "gov page text", "https://x.gov.in/", "t")
    assert lane == "heuristic"
    assert "unparseable" in err
    assert any("rules fallback" in r.getMessage() for r in caplog.records)


def test_llm_extract_requests_large_output(monkeypatch):
    """Extract replies must not be truncated: a mid-JSON cut used to fail
    parse silently and drop to one-node heuristic maps."""
    from app import worker
    seen = {}

    def fake(prompt, max_tokens=400):
        seen["max_tokens"] = max_tokens
        return (('[{"id":"a","type":"action","title":"Apply",'
                 '"detail":"d","fee":"","link":""}]'), "m")

    monkeypatch.setattr(worker.llmmod, "_chat_raw", fake)
    steps, lane, err = worker._llm_extract_full("text", "https://x.gov.in/", "t")
    assert seen["max_tokens"] == 2000
    assert lane == "llm" and err == ""
    assert steps[0]["title"] == "Apply"


def test_build_map_records_lane_and_error(monkeypatch):
    from app import worker
    monkeypatch.setattr(
        worker, "cascade_fetch_full",
        lambda u: ("Registration is free of cost. Apply now.",
                   "trafilatura", u))

    def no_llm(prompt, max_tokens=400):
        raise RuntimeError("no llm")

    monkeypatch.setattr(worker.llmmod, "_chat_raw", no_llm)
    out = worker.build_map("task", ["https://udyam.example.gov.in/"])
    src = out["sources"][0]
    assert src["extract"] == "heuristic"
    assert "no llm" in src["llm_error"]


def test_source_warnings_surface_failures():
    from app.packet import source_warnings
    warns = source_warnings([
        {"url": "https://mca.gov.in/", "ok": False,
         "error": "all fetch tiers failed (403)"},
        {"url": "https://udyamregistration.gov.in/", "ok": True,
         "extract": "heuristic", "llm_error": "LLM unavailable: timeout"},
        {"url": "https://gst.gov.in/", "ok": True, "extract": "llm"},
        "https://legacy.gov.in/",
    ])
    assert len(warns) == 2, warns
    assert "mca.gov.in could not be fetched" in warns[0]
    assert "403" in warns[0]
    assert "rules, not the AI model" in warns[1]
    assert "timeout" in warns[1]


def test_map_payloads_carry_warnings(client, user):
    """GET /maps/{slug} and GET /task/{slug} must tell the citizen when a
    source was unreachable or extraction degraded."""
    from datetime import datetime, timezone

    import app.main as M
    from app.models import TaskMap
    slug = "warn-seed-map"
    sources = [
        {"url": "https://mca.gov.in/", "ok": False, "error": "blocked"},
        {"url": "https://udyamregistration.gov.in/", "ok": True,
         "extract": "llm", "tier": "trafilatura", "guides": []},
    ]
    with Session(M.engine) as s:
        s.add(TaskMap(slug=slug, title="Warn map", city="Pune",
                      state="MH", graph_json=json.dumps(
                          {"nodes": [GOOD_NODE], "edges": []}),
                      source_urls=json.dumps(sources),
                      verified_at=datetime.now(timezone.utc)))
        s.commit()
    for path in (f"/maps/{slug}", f"/task/{slug}"):
        r = client.get(path, headers=user["headers"])
        assert r.status_code == 200, (path, r.text)
        warnings = r.json()["warnings"]
        assert any("mca.gov.in could not be fetched" in w
                   for w in warnings), warnings


def test_readyz_reports_job_poller_state(client):
    r = client.get("/readyz")
    assert r.status_code == 200, r.text
    assert "job_poller" in r.json()["checks"]


def test_otp_send_failure_is_visible_to_the_user(client, user, monkeypatch):
    """A failed OTP email must not answer ok:true — the user would wait
    for a code that never comes."""
    import app.notify as notify_mod

    def boom(*a, **k):
        raise RuntimeError("smtp down")

    monkeypatch.setattr(notify_mod, "send", boom)
    r = client.post("/auth/otp/request", json={"email": user["email"]})
    assert r.status_code == 502, r.text
    assert "could not be sent" in r.json()["detail"]


def test_otp_send_success_still_ok(client, user):
    r = client.post("/auth/otp/request", json={"email": user["email"]})
    assert r.status_code == 200, r.text
    assert r.json()["ok"] is True


def test_poller_status_flag_defaults_for_tests():
    from app import jobs
    assert jobs.POLLER_STATUS["disabled"] is True  # conftest sets JOB_POLLER=0
