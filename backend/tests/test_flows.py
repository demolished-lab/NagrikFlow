"""Personalization + admin desk. Converted from sim/persona scripts."""
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
