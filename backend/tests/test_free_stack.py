"""Free-stack sprint coverage (2026-10-04): evidence snapshots + change
diffs, schema.org/JSON-LD extraction, Common Crawl CDX discovery lane,
India catalog seeds, and the env-gated free-tier LLM lanes."""
import json

from sqlmodel import Session, select

GOOD_GRAPH = {"nodes": [
    {"id": "a", "type": "action", "title": "Step A", "detail": "",
     "url": "", "fee": ""},
], "edges": []}


# ---------------------------- evidence store -------------------------------

def test_snapshot_roundtrip_and_pruning():
    from app import evidence as E
    from app import main as M
    from app.models import SourceSnapshot

    slug = "ev-prune-test"
    for i in range(E.KEEP_PER_URL + 3):
        E.save_snapshot(M.engine, slug, "https://x.gov.in/a",
                        text=f"version {i}", tier="trafilatura")
    with Session(M.engine) as s:
        rows = s.exec(select(SourceSnapshot).where(
            SourceSnapshot.map_slug == slug)).all()
    assert len(rows) == E.KEEP_PER_URL  # history depth enforced
    latest = E.latest_snapshot(M.engine, slug, "https://x.gov.in/a")
    assert latest is not None
    assert latest.text == f"version {E.KEEP_PER_URL + 2}"  # newest kept
    assert latest.content_hash == E.norm_hash(latest.text)


def test_diff_texts_shows_material_change():
    from app import evidence as E
    old = "Shops registration fee is Rs. 500. Submit Form A."
    new = "Shops registration fee is Rs. 750. Submit Form A."
    d = E.diff_texts(old, new)
    assert d.startswith("---") or "-+" in d or d.startswith("@@") is False
    assert "500" in d and "750" in d
    assert any(line.startswith("-") and "500" in line
               for line in d.splitlines() if line[:1] in "-+")
    assert len(d) <= E.DIFF_CAP


def test_record_and_list_changes():
    from app import evidence as E
    from app import main as M
    from app.models import ChangeEvent

    slug = "ev-change-test"
    with Session(M.engine) as s:
        for row in s.exec(select(ChangeEvent).where(
                ChangeEvent.map_slug == slug)).all():
            s.delete(row)
        s.commit()
    ev = E.record_change(M.engine, slug, "https://b.gov.in/x",
                         "old fee 300", "new fee 900", "h1", "h2")
    assert ev.diff and "300" in ev.diff and "900" in ev.diff
    listed = E.list_changes(M.engine, slug)
    assert listed[0]["url"] == "https://b.gov.in/x"
    assert listed[0]["old_hash"] == "h1"


def test_save_snapshots_bulk_ignores_junk():
    from app import evidence as E
    from app import main as M

    slug = "ev-bulk-test"
    n = E.save_snapshots(M.engine, slug, [
        {"url": "https://c.gov.in/", "text": "hello", "tier": "trafilatura",
         "html": "<html></html>"},
        {"url": "", "text": "no url"},       # skipped
        {"url": "https://d.gov.in/", "text": ""},  # skipped
        "not-a-dict",                        # skipped
    ])
    assert n == 1
    row = E.latest_snapshot(M.engine, slug, "https://c.gov.in/")
    assert row is not None and row.text == "hello"
    assert row.raw_hash  # html hashed


# ------------------------ watch: change detection --------------------------

def _seed_watch_map(slug, url, *, content_hash, verified=False):
    from app import main as M
    from app.models import TaskMap, utcnow
    with Session(M.engine) as s:
        s.add(TaskMap(slug=slug, title=f"Map {slug}",
                      graph_json=json.dumps(GOOD_GRAPH),
                      source_urls=json.dumps([{"url": url, "ok": True}]),
                      content_hash=content_hash,
                      verified_at=utcnow() if verified else None,
                      created_by=0))
        s.commit()


def test_recheck_records_readable_diff(monkeypatch):
    from app import evidence as E
    from app import main as M
    from app import watch as W
    from app.models import ChangeEvent, TaskMap

    slug, url = "watch-diff-test", "https://watch.gov.in/page"
    _seed_watch_map(slug, url, content_hash="stale-hash", verified=True)
    E.save_snapshot(M.engine, slug, url, text="Fee is Rs. 500 on this page")

    monkeypatch.setattr("app.worker.cascade_fetch",
                        lambda u: ("Fee is Rs. 750 on this page",
                                   "trafilatura"))
    out = W.recheck(M.engine, slug)
    assert out[0]["changed"] is True
    assert out[0]["diffs"] == 1
    with Session(M.engine) as s:
        m = s.exec(select(TaskMap).where(TaskMap.slug == slug)).first()
        assert m.verified_at is None  # trust revoked
        evs = s.exec(select(ChangeEvent).where(
            ChangeEvent.map_slug == slug)).all()
    assert len(evs) == 1
    assert "500" in evs[0].diff and "750" in evs[0].diff
    latest = E.latest_snapshot(M.engine, slug, url)
    assert latest.content_hash == E.norm_hash("Fee is Rs. 750 on this page")


def test_first_recheck_is_baseline_no_event(monkeypatch):
    from app import evidence as E
    from app import main as M
    from app import watch as W
    from app.models import ChangeEvent, TaskMap

    slug, url = "watch-baseline-test", "https://base.gov.in/page"
    _seed_watch_map(slug, url, content_hash="")  # never hashed = baseline
    E.save_snapshot(M.engine, slug, url, text="old wording")

    monkeypatch.setattr("app.worker.cascade_fetch",
                        lambda u: ("brand new wording", "trafilatura"))
    out = W.recheck(M.engine, slug)
    assert out[0]["note"] == "first baseline stored"
    assert out[0]["changed"] is False
    with Session(M.engine) as s:
        m = s.exec(select(TaskMap).where(TaskMap.slug == slug)).first()
        assert m.content_hash  # baseline established
        assert s.exec(select(ChangeEvent).where(
            ChangeEvent.map_slug == slug)).all() == []
    assert E.latest_snapshot(M.engine, slug, url).text == "brand new wording"


def test_fingerprint_backward_compatible(monkeypatch):
    """Aggregate hash format is unchanged (16-char per-url hash or ERR tag),
    so pre-existing baselines keep comparing correctly."""
    from app import watch as W
    url = "https://fp.gov.in/x"
    monkeypatch.setattr("app.worker.cascade_fetch",
                        lambda u: ("Some official page text", "trafilatura"))
    h1, statuses = W.fingerprint([url])
    h2, _ = W.fingerprint([url])
    assert h1 == h2 and len(h1) == 24
    assert statuses[0]["ok"] is True and statuses[0]["tier"] == "trafilatura"
    assert len(statuses[0]["hash"]) == 16

    monkeypatch.setattr("app.worker.cascade_fetch",
                        lambda u: (_raise(RuntimeError("down"))))
    h3, st3 = W.fingerprint([url])
    assert h3 != h1
    assert st3[0]["ok"] is False


def _raise(exc):
    raise exc


# ----------------------- schema.org / JSON-LD facts ------------------------

JSONLD_HTML = """
<html><head>
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "GovernmentService",
  "name": "Shops and Establishments Registration",
  "description": "Register a new shop or commercial establishment with the municipal authority.",
  "provider": {"@type": "Organization", "name": "Municipal Corporation"},
  "offers": {"@type": "Offer", "price": "500", "priceCurrency": "INR"},
  "url": "https://www.mcgm.gov.in/apply/shops"
}
</script></head><body></body></html>
"""


def test_service_facts_from_jsonld():
    from app import semantics as S
    facts = S.service_facts(JSONLD_HTML, "https://www.mcgm.gov.in/")
    assert facts["name"] == "Shops and Establishments Registration"
    assert facts["fee"] == "₹500"
    assert facts["provider"] == "Municipal Corporation"
    assert facts["application_url"] == "https://www.mcgm.gov.in/apply/shops"
    assert facts["description"].startswith("Register a new shop")


def test_service_facts_zero_price_is_free_and_junk_tolerant():
    from app import semantics as S
    facts = S.service_facts(
        '<script type="application/ld+json">{"@type":"Service",'
        '"name":"Udyam","offers":{"price":0,"priceCurrency":"INR"}}'
        '</script><script type="application/ld+json">{broken', "u")
    assert facts["fee"] == "₹0"
    empty = S.service_facts("", "u")
    assert empty["name"] == ""  # never raises on absence


def test_facts_to_step_and_link_safety():
    from app import semantics as S
    facts = {"name": "Trade Licence", "description": "Renew your licence",
             "fee": "₹750", "provider": "BMC", "supplies": "AADHAAR",
             "application_url": "https://www.mcgm.gov.in/apply"}
    step = S.facts_to_step(facts, "https://www.mcgm.gov.in/")
    assert step["title"] == "Trade Licence" and step["fee"] == "₹750"
    assert "AADHAAR" in step["detail"]
    assert S.facts_to_step({"name": ""}, "u") is None


def test_build_map_uses_structured_facts_when_extraction_empty(monkeypatch):
    from app import worker as W
    url = "https://udyam.example.gov.in/"
    monkeypatch.setattr(W, "cascade_fetch_full",
                        lambda u: ("Registration page text.", "trafilatura", u))
    monkeypatch.setattr(W, "_llm_extract_full",
                        lambda t, u, k: ([], "heuristic", "no llm"))
    monkeypatch.setattr(W, "llm_infer_edges", lambda task, nodes: [])
    W._RAW_HTML[url] = JSONLD_HTML  # simulates the tier-1 capture

    out = W.build_map("register a shop", [url])
    assert out["sources"][0]["facts"]["name"].startswith("Shops")
    ids = {n["id"] for n in out["nodes"]}
    assert "service" in ids
    node = next(n for n in out["nodes"] if n["id"] == "service")
    assert node["fee"] == "₹500"
    # link from JSON-LD must pass the gov/same-host gate
    assert node["link"] == "https://www.mcgm.gov.in/apply/shops"
    # evidence payload for the snapshot store
    assert out["snapshots"][0]["html"] == JSONLD_HTML
    assert out["snapshots"][0]["text"] == "Registration page text."


# ------------------------ Common Crawl CDX lane ----------------------------

CDX_HEADER_BODY = '''["urlkey","timestamp","url","mime","status"]
["in,gov,mcgm)/trade/license.pdf","20260101","https://www.mcgm.gov.in/trade/license.pdf","application/pdf","200"]
["in,gov,mcgm)/grievance","20260101","https://www.mcgm.gov.in/grievance/complaint","text/html","200"]
["in,gov,mcgm)/old","20260101","http://www.mcgm.gov.in/old-page","text/html","200"]
["com,ugly)/","20260101","https://ugly.example/x","text/html","200"]'''


def test_parse_cdx_shapes():
    from app import discover as D
    urls = D._parse_cdx(CDX_HEADER_BODY)
    assert urls == [
        "https://www.mcgm.gov.in/trade/license.pdf",
        "https://www.mcgm.gov.in/grievance/complaint",
        "http://www.mcgm.gov.in/old-page",
        "https://ugly.example/x",
    ]
    # JSON-object lines and TSV lines too
    assert D._parse_cdx('{"url": "https://a.gov.in/1"}\n') == \
        ["https://a.gov.in/1"]
    assert D._parse_cdx("tk\t20260101\thttps://a.gov.in/2\ttext/html") == \
        ["https://a.gov.in/2"]
    assert D._parse_cdx("") == []


def test_cdx_task_urls_filters_to_gov_https_relevant(monkeypatch):
    from app import discover as D
    monkeypatch.setenv("CIVIC_CDX", "1")
    monkeypatch.setattr(D, "_cc_index", lambda: "CC-MAIN-2026-38")
    monkeypatch.setattr(D, "_cc_get", lambda u, timeout=20: CDX_HEADER_BODY)

    out = D.cdx_task_urls(
        "trade licence registration",
        ["https://www.mcgm.gov.in/", "https://ugly.example/"])
    assert out == ["https://www.mcgm.gov.in/trade/license.pdf"]
    # grievance path has no task token, http and non-gov dropped


def test_cdx_lane_disabled_by_env(monkeypatch):
    from app import discover as D
    monkeypatch.setenv("CIVIC_CDX", "0")
    calls = []
    monkeypatch.setattr(D, "_cc_get",
                        lambda *a, **k: calls.append(a) or "")
    assert D.cdx_urls("www.mcgm.gov.in") == []
    assert D.cdx_task_urls("anything", ["https://www.mcgm.gov.in/"]) == []
    assert calls == []


def test_build_task_discovery_falls_through_to_cdx(client, user, monkeypatch):
    import app.jobs as J
    from app import main as M
    monkeypatch.setenv("CIVIC_CDX", "1")
    monkeypatch.setattr(M.discovermod, "discover", lambda q, max_results=8: [])
    monkeypatch.setattr(M.discovermod, "cdx_task_urls",
                        lambda q, seeds: ["https://udyamregistration.gov.in/deep"])
    monkeypatch.setattr(M, "_validate_fetch_url", lambda u: u)
    monkeypatch.setattr(J, "run_build", lambda engine, jid: None)

    r = client.post("/build-task", headers=user["headers"], json={
        "task": "udyam registration"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["discovery"] == "cdx"
    assert body["urls_found"] == 1


# --------------------------- India catalog seeds ---------------------------

def test_catalog_india_seeds_are_gov_https():
    from urllib.parse import urlparse

    from app import catalog as C
    got = C.fallback_sources("register a shop in mumbai", max_urls=5)
    assert "https://www.mcgm.gov.in/" in got
    assert any("aaplesarkar" in u for u in got)
    got2 = C.fallback_sources("birth certificate in delhi", max_urls=5)
    assert any("edistrict.delhi.gov.in" in u for u in got2)
    for u in got + got2:
        p = urlparse(u)
        assert p.scheme == "https"
        assert p.hostname.endswith(".gov.in")


def test_catalog_existing_entries_unchanged():
    from app import catalog as C
    assert C.fallback_sources("gst tax filing", max_urls=1) == \
        ["https://www.gst.gov.in/"]


# --------------------------- free-tier LLM lanes ---------------------------

def test_free_lanes_configured_from_env(monkeypatch):
    from app import llm as L
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    assert L.free_lanes() == []

    monkeypatch.setenv("GROQ_API_KEY", "g-key")
    monkeypatch.setenv("GROQ_MODEL", "")
    lanes = L.free_lanes()
    assert len(lanes) == 1
    label, base, model, key = lanes[0]
    assert label == "groq" and key == "g-key"
    assert base.endswith("/v1") and model  # default model when env empty


def test_gemini_lane_strips_router_style_model_prefix(monkeypatch):
    from app import llm as L
    monkeypatch.setenv("GEMINI_API_KEY", "g-key")
    monkeypatch.setenv("GEMINI_MODEL", "gemini/gemini-3.1-pro-preview")
    assert L.free_lanes()[0][2] == "gemini-3.1-pro-preview"  # bare id


def test_complete_walks_free_lane_before_ollama(monkeypatch):
    from app import llm as L
    monkeypatch.setenv("GROQ_API_KEY", "g-key")
    monkeypatch.setattr(L, "BYNARA_KEY", "")
    monkeypatch.setattr(L, "OFFLINE_ONLY", False)
    seen = {}

    def fake_chat(base, model, prompt, key="", temperature=0.2,
                  max_tokens=400):
        seen.update({"base": base, "model": model, "key": key})
        return "structured reply"

    monkeypatch.setattr(L, "_chat", fake_chat)
    text, via = L.complete("prompt", role="extract")
    assert text == "structured reply"
    assert via.startswith("groq/")
    assert seen["base"] == "https://api.groq.com/openai/v1"
    assert seen["key"] == "g-key"


def test_complete_falls_through_broken_free_lane(monkeypatch):
    from app import llm as L
    for key in ("GEMINI_API_KEY", "GROQ_API_KEY", "OPENROUTER_API_KEY",
                "GEMINI_MODEL", "GROQ_MODEL", "OPENROUTER_MODEL"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("GROQ_API_KEY", "g-key")
    monkeypatch.setattr(L, "BYNARA_KEY", "")
    monkeypatch.setattr(L, "OFFLINE_ONLY", False)
    monkeypatch.setattr(L, "OLLAMA_MODEL", "local-model")

    def fake_chat(base, model, prompt, key="", temperature=0.2,
                  max_tokens=400):
        if "groq" in base:
            raise RuntimeError("quota")
        return "local reply"

    monkeypatch.setattr(L, "_chat", fake_chat)
    text, via = L.complete("prompt")
    assert text == "local reply" and via == "ollama/local-model"


# --------------------------- changes endpoint ------------------------------

def test_changes_endpoint_visibility_and_payload(client, user):
    from app import evidence as E
    from app import main as M
    from app.models import TaskMap, User

    slug = "changes-endpoint-test"
    with Session(M.engine) as s:
        who = s.exec(select(User).where(User.email == user["email"])).first()
        s.add(TaskMap(slug=slug, title="Draft", created_by=who.id,
                      graph_json=json.dumps(GOOD_GRAPH)))
        s.commit()
    E.record_change(M.engine, slug, "https://x.gov.in/f",
                    "fee 100", "fee 200", "a", "b")

    r = client.get(f"/task/{slug}/changes", headers=user["headers"])
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["count"] == 1
    assert "100" in body["changes"][0]["diff"]
    assert body["changes"][0]["created_at"]

    stranger = client.post("/auth/register", json={
        "email": "changes-stranger@t.co", "password": "pw123456"}).json()
    r2 = client.get(f"/task/{slug}/changes",
                    headers={"Authorization": f"Bearer {stranger['token']}"})
    assert r2.status_code == 404  # unverified draft: no existence leak
