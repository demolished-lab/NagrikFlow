"""Hermes worker routing (no token needed — logic only)."""
from sqlmodel import Session, select


def test_hermes_link_status_next(client):
    from app import hermes as H
    import app.main as M
    from app.models import LinkCode, User, VaultItem

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
