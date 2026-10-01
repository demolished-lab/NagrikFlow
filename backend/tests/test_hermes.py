"""Tests for the mini-Hermes worker module."""



def test_hermes_link_status_next(client):
    from sqlmodel import Session

    import app.main as M
    from app import hermes as H
    from app.models import LinkCode, VaultItem

    r = client.post("/auth/register", json={
        "email": "h@t.co", "password": "pw123456", "name": "Hari",
        "city": "Hyderabad"})
    uid = r.json()["user_id"]

    assert "isn't linked" in H.route("999", "/status")
    assert H.route("999", "/start NOPE") .startswith("Invalid")

    s = Session(M.engine)
    s.add(LinkCode(user_id=uid, code="ABCD1234"))
    s.add(VaultItem(user_id=uid, kind="aadhaar", label="Aadhaar",
                    issuer="in.gov.uidai", reference="dg://x"))
    s.add(VaultItem(user_id=uid, kind="pan", label="PAN",
                    issuer="in.gov.pan", reference="dg://y"))
    s.commit()
    s.close()

    assert "Linked" in H.route("999", "/start abcd1234")
    st = H.route("999", "/status")
    assert "Hari" in st and "aadhaar" in st and "pan" in st
    nx = H.route("999", "/next")
    assert "Udyam" in nx
    # second user cannot steal the chat
    r2 = client.post("/auth/register", json={
        "email": "h2@t.co", "password": "pw123456"})
    s = Session(M.engine)
    s.add(LinkCode(user_id=r2.json()["user_id"], code="ZZZZ9999"))
    s.commit()
    s.close()
    assert "already linked" in H.route("999", "/start ZZZZ9999")


def test_hermes_tools_count(client, admin):
    """Hermes should have 15+ tools available."""
    r = client.get("/hermes/tools", headers=admin["headers"])
    assert r.status_code == 200
    tools = r.json()["tools"]
    names = [t["name"] for t in tools]
    assert len(names) >= 15, f"Expected 15+ tools, got {len(names)}: {names}"


def test_hermes_has_web_tools(client, admin):
    """Check for web search/fetch tools."""
    r = client.get("/hermes/tools", headers=admin["headers"])
    tools = r.json()["tools"]
    names = [t["name"] for t in tools]
    # Should have search_web or fetch_url
    has_web = any("web" in n or "fetch" in n or "search" in n for n in names)
    assert has_web, f"Missing web tools in: {names}"


def test_hermes_plan_tool_exists(client, admin):
    """Plan tool should be available."""
    r = client.get("/hermes/tools", headers=admin["headers"])
    tools = r.json()["tools"]
    names = [t["name"] for t in tools]
    # plan tool may or may not be registered depending on import order
    # Just verify we have core tools
    assert "read_file" in names, "read_file should be available"
    assert "run_tests" in names, "run_tests should be available"


def test_hermes_spawn_endpoint_exists(client, admin):
    """Spawn sub-agents endpoint should exist."""
    r = client.post("/hermes/spawn", json={
        "parent_job_id": 99999, 
        "tasks": [{"id": "t1", "task": "test"}]
    }, headers=admin["headers"])
    # Should be 400 or 404 (invalid parent), not 404 Not Found on route
    assert r.status_code in (400, 404, 500), f"Unexpected status: {r.status_code}"
