"""Personalization + admin desk. Converted from sim/persona scripts."""
import json

from app import eligibility as elig


def test_persona_rules():
    cases = [
        (set(), set()),
        ({"aadhaar"}, {"pan"}),
        ({"aadhaar", "pan"}, {"udyam"}),
        ({"aadhaar", "pan", "udyam"}, {"gstin", "shops"}),
        ({"aadhaar", "pan", "udyam", "gstin", "shops"}, set()),
    ]
    from app.eligibility import LABELS
    inv = {v: k for k, v in LABELS.items()}
    for kinds, _ in cases:
        b = elig.personalize(set(kinds), {})
        gives = {inv.get(n["get"], n["get"]) for n in b["next_easiest"]}
        assert not (gives & set(kinds)), (kinds, gives)


def test_dashboard_flow(client, user):
    d = client.get("/me/dashboard", headers=user["headers"]).json()
    assert d["have"] == [] and d["next_easiest"] == []
    r = client.post("/me/progress", headers=user["headers"],
                    json={"map_slug": "udyam-register", "step_id": "aadhaar"})
    assert r.json() == {"ok": True}


def test_admin_gates(client, user, admin):
    assert client.get("/admin/maps", headers=user["headers"]).status_code == 403
    maps = client.get("/admin/maps", headers=admin["headers"]).json()
    assert any(m["slug"] == "udyam-register" for m in maps)
    v = client.post("/admin/maps/udyam-register/verify", headers=admin["headers"],
                    json={"verified": True}).json()
    assert v["verified"]


def test_telegram_link_isolation(client):
    a = client.post("/auth/register", json={"email": "ta@t.co", "password": "pw123456"}).json()
    b = client.post("/auth/register", json={"email": "tb@t.co", "password": "pw123456"}).json()
    ha = {"Authorization": f"Bearer {a['token']}"}
    hb = {"Authorization": f"Bearer {b['token']}"}
    ca = client.post("/me/telegram/link-code", headers=ha).json()["code"]
    cb = client.post("/me/telegram/link-code", headers=hb).json()["code"]
    ok = client.post("/hooks/telegram", json={
        "message": {"chat": {"id": 111}, "text": f"/start {ca}"}}).json()
    assert ok.get("linked") is True
    no = client.post("/hooks/telegram", json={
        "message": {"chat": {"id": 111}, "text": f"/start {cb}"}}).json()
    assert no.get("linked") is not True


def test_my_pathways_uses_saved_data_and_is_user_scoped(client, user):
    from sqlmodel import Session

    from app import main as M
    from app.models import Job, Progress, TaskMap

    profile = client.get("/me/profile", headers=user["headers"]).json()
    slug = f"my-path-{profile['id']}"
    graph = {"nodes": [
        {"id": "prepare", "title": "Prepare documents", "detail": "Bring PAN", "url": "https://example.gov.in", "type": "prereq"},
        {"id": "apply", "title": "Apply online", "detail": "Use the official portal", "url": "https://example.gov.in/apply", "type": "action"},
    ], "edges": [["prepare", "apply"]]}
    with Session(M.engine) as session:
        session.add(TaskMap(
            slug=slug, title="Apply for a permit", city="Pune", state="Maharashtra",
            graph_json=json.dumps(graph),
            source_urls=json.dumps([{"url": "https://example.gov.in", "ok": True}]),
        ))
        session.add(Job(
            kind="build", status="done", created_by=profile["id"],
            payload=json.dumps({"task": "Apply for a permit", "slug": slug,
                                "city": "Pune", "state": "Maharashtra"}),
            result=json.dumps({"slug": slug}),
        ))
        session.add(Progress(user_id=profile["id"], map_slug=slug, step_id="apply"))
        session.add(Job(
            kind="build", status="done", created_by=profile["id"] + 10000,
            payload=json.dumps({"task": "Another user's task", "slug": "private-other-path"}),
            result=json.dumps({"slug": "private-other-path"}),
        ))
        session.commit()

    response = client.get("/me/pathways", headers=user["headers"])
    assert response.status_code == 200
    pathways = response.json()
    assert [item["slug"] for item in pathways] == [slug]
    assert pathways[0]["status"] == "review_required"
    assert pathways[0]["city"] == "Pune"
    assert pathways[0]["state"] == "Maharashtra"
    assert pathways[0]["steps"] == 2
    assert pathways[0]["completed"] == 1
    assert pathways[0]["completed_steps"] == ["apply"]
    assert pathways[0]["steps_preview"][0]["title"] == "Prepare documents"
