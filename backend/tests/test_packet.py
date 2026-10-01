"""Path-workflow packet: source meta (final URL/tier/guides), packet JSON,
Markdown download, Telegram delivery, and the hermes path_packet tool."""
import json
from datetime import datetime, timezone

from sqlmodel import Session, select

GOOD_GRAPH = {"nodes": [
    {"id": "docs", "type": "prereq", "title": "Gather documents",
     "detail": "Mentioned on source: PAN, Aadhaar", "url": "https://x.gov.in/",
     "fee": ""},
    {"id": "pay", "type": "payment", "title": "Pay fee",
     "detail": "Pay online", "url": "https://x.gov.in/", "link": "",
     "fee": "₹0"},
    {"id": "apply", "type": "action", "title": "Apply on official portal",
     "detail": "Free of cost (stated on the official page).",
     "url": "https://x.gov.in/",
     "link": "https://x.gov.in/registration", "fee": "₹0"},
], "edges": [["docs", "pay"], ["pay", "apply"]]}

RICH_SOURCES = [
    {"url": "https://x.gov.in/page", "ok": True, "tier": "trafilatura",
     "final_url": "https://x.gov.in/en/page",
     "guides": [{"url": "https://x.gov.in/guidelines.pdf",
                 "title": "guidelines.pdf"}],
     "fetched_at": datetime.now(timezone.utc).isoformat()},
    "https://legacy.gov.in/",  # legacy list[str] entry still normalizes
    {"url": "https://dead.gov.in/", "ok": False, "error": "timeout"},
]


def _seed(slug, *, created_by=0, verified=True, sources=None):
    from app import main as M
    from app.models import TaskMap
    with Session(M.engine) as s:
        s.add(TaskMap(slug=slug, title=f"Map {slug}", city="Hyderabad",
                      state="Telangana", service_type="Business & Trade",
                      graph_json=json.dumps(GOOD_GRAPH),
                      source_urls=json.dumps(sources if sources is not None
                                             else RICH_SOURCES),
                      created_by=created_by,
                      verified_at=datetime.now(timezone.utc) if verified
                      else None))
        s.commit()


def _cleanup(slug):
    from app import main as M
    from app.models import TaskMap
    with Session(M.engine) as s:
        for row in s.exec(select(TaskMap).where(TaskMap.slug == slug)).all():
            s.delete(row)
        s.commit()


# ------------------------------ source meta --------------------------------

def test_extract_guides_picks_official_docs_not_help_pages():
    from app import worker as W
    text = ("Handbook: https://x.gov.in/msme-handbook.pdf "
            "Guidelines https://x.gov.in/guidelines "
            "Citizen charter https://x.gov.in/charter "
            "Grievance https://x.gov.in/grievance-cell "
            "Random https://ugly.example/file.pdf "
            "Central scheme https://gst.gov.in/scheme-brochure.pdf")
    guides = W.extract_guides(text, "https://x.gov.in/page")
    urls = [g["url"] for g in guides]
    assert "https://x.gov.in/msme-handbook.pdf" in urls
    assert "https://x.gov.in/guidelines" in urls
    assert "https://gst.gov.in/scheme-brochure.pdf" in urls  # cross-host gov ok
    assert not any("grievance" in u for u in urls)
    assert not any("ugly.example" in u for u in urls)
    assert all(g["title"] for g in guides)


def test_build_map_sources_carry_final_url_and_guides(monkeypatch):
    from app import worker as W
    text = ("Apply at https://dept.gov.in/apply "
            "Read https://dept.gov.in/guidebook.pdf")
    monkeypatch.setattr(W, "cascade_fetch_full",
                        lambda url: (text, "obscura",
                                     "https://dept.gov.in/en/apply"))
    monkeypatch.setattr(W, "llm_extract", lambda t, url, task: [])
    monkeypatch.setattr(W, "_llm_extract_full",
                        lambda t, url, task: ([], "llm", ""))
    monkeypatch.setattr(W, "llm_infer_edges", lambda task, nodes: [])
    monkeypatch.setattr(W, "verify_links", lambda nodes: None)
    result = W.build_map("udyam registration", ["https://dept.gov.in/page"])
    src = next(s for s in result["sources"] if s.get("ok"))
    assert src["tier"] == "obscura"
    assert src["final_url"] == "https://dept.gov.in/en/apply"
    assert any(g["url"] == "https://dept.gov.in/guidebook.pdf"
               for g in src["guides"])


# ------------------------------- packet API --------------------------------

def test_packet_json_shape(client):
    _seed("packet-shape")
    try:
        r = client.get("/task/packet-shape/packet",
                       headers={"Authorization": "Bearer " +
                                _token_for(client)})
        assert r.status_code == 200, r.text
        p = r.json()
        assert p["slug"] == "packet-shape"
        assert [s["order"] for s in p["steps"]] == [1, 2, 3]
        assert p["steps"][2]["prereqs"] == ["pay"]
        assert p["checklist"] == ["Aadhaar", "PAN"]
        assert "₹0" in p["fees"]
        assert p["steps"][2]["link"] == "https://x.gov.in/registration"
        assert p["sources"][0]["final_url"] == "https://x.gov.in/en/page"
        assert p["sources"][1]["url"] == "https://legacy.gov.in/"
        assert p["sources"][2]["ok"] is False
        assert any(g["url"].endswith("guidelines.pdf") for g in p["guides"])
        assert p["counts"]["steps"] == 3
    finally:
        _cleanup("packet-shape")


def _token_for(client) -> str:
    """Register a throwaway user and return their bearer token."""
    r = client.post("/auth/register", json={
        "email": f"pkt{datetime.now(timezone.utc).microsecond}@t.co",
        "password": "pw123456", "name": "P"})
    assert r.status_code == 200, r.text
    return r.json()["token"]


def test_packet_markdown_download(client):
    _seed("packet-md")
    try:
        token = _token_for(client)
        r = client.get("/task/packet-md/packet.md",
                       headers={"Authorization": "Bearer " + token})
        assert r.status_code == 200, r.text
        assert "markdown" in r.headers.get("content-type", "")
        assert "packet-md-packet.md" in r.headers.get(
            "content-disposition", "")
        body = r.text
        assert "# Map packet-md — path workflow packet" in body
        assert "## Document checklist" in body
        assert "## Official sources" in body
        assert "https://x.gov.in/en/page" in body  # final redirect URL
        assert "redirects to:" in body
        assert "guidelines.pdf" in body
    finally:
        _cleanup("packet-md")


def test_packet_scoping_hides_unverified_maps(client):
    _seed("packet-privacy", created_by=999999, verified=False)
    try:
        token = _token_for(client)
        r = client.get("/task/packet-privacy/packet",
                       headers={"Authorization": "Bearer " + token})
        assert r.status_code == 404
        r = client.get("/task/packet-privacy/packet.md",
                       headers={"Authorization": "Bearer " + token})
        assert r.status_code == 404
    finally:
        _cleanup("packet-privacy")


def test_deliver_packet_requires_chat_then_sends(client, user, monkeypatch):
    from app import main as M
    from app.models import User
    monkeypatch.delenv("CIVIC_TELEGRAM_CHAT_ID", raising=False)
    _seed("packet-deliver")
    try:
        # unlinked account, no fallback -> 400
        r = client.post("/task/packet-deliver/deliver", headers=user["headers"])
        assert r.status_code == 400, r.text

        # operator fallback chat id -> delivered (console transport in tests)
        monkeypatch.setenv("CIVIC_TELEGRAM_CHAT_ID", "7083579202")
        r = client.post("/task/packet-deliver/deliver", headers=user["headers"])
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["sent"] is True
        assert body["chat_id"] == "7083579202"
        assert body["via"] == "console"

        # linked account chat wins over the fallback
        with Session(M.engine) as s:
            who = s.exec(select(User).where(
                User.email == user["email"])).first()
            who.telegram_chat = "5551234"
            s.add(who)
            s.commit()
        r = client.post("/task/packet-deliver/deliver", headers=user["headers"])
        assert r.status_code == 200
        assert r.json()["chat_id"] == "5551234"
    finally:
        _cleanup("packet-deliver")


def test_hermes_path_packet_tool(client):
    from app import hermes_core as HC
    assert "path_packet" in HC.TOOLS
    out = HC.TOOLS["path_packet"]["_fn"](slug="no-such-map")
    assert "error" in out
    _seed("packet-tool")
    try:
        out = HC.TOOLS["path_packet"]["_fn"](slug="packet-tool")
        assert out.get("slug") == "packet-tool"
        assert out["counts"]["steps"] == 3
        assert "# Map packet-tool — path workflow packet" in out["markdown"]
    finally:
        _cleanup("packet-tool")
