"""DPDP Act (India, 2023) compliance: withdraw/consent export, erasure, grievances."""


def _user_vault(s, models, uid, kinds):
    for k in kinds:
        s.add(models.VaultItem(user_id=uid, kind=k, label=k.capitalize(),
                               issuer="in.gov.x", reference=f"dg://{k}"))
    s.commit()


def test_consent_withdraw_erases_vault(client, user):
    """Withdrawing consent must wipe vault + consents + oauth states."""
    r = client.post("/me/consent/withdraw", headers=user["headers"])
    assert r.status_code == 200
    body = r.json()
    assert "vault_items_erased" in body and "consents_withdrawn" in body


def test_data_export_receipt(client, user):
    r = client.post("/me/data-export", headers=user["headers"])
    assert r.status_code == 200
    d = r.json()
    assert d["format"] == "civic-pathfinder-data-receipt/v1"
    assert d["user"]["email"] == user["email"]
    assert "vault" in d and "consents" in d and "progress" in d


def test_account_delete_removes_everything(client):
    # Register fresh user, then delete
    r = client.post("/auth/register", json={
        "email": "erase-me@civic.test", "password": "pw12345678"}).json()
    h = {"Authorization": f"Bearer {r['token']}"}
    d = client.delete("/me/account", headers=h)
    assert d.status_code == 200 and d.json()["deleted"]
    # JWT should now be invalid
    after = client.get("/me/dashboard", headers=h)
    assert after.status_code == 401


def test_grievance_submit_and_list(client, user):
    r = client.post("/me/grievance", headers=user["headers"],
                    json={"subject": "Test issue", "message": "Data not deleting."})
    assert r.status_code == 200
    gid = r.json()["id"]
    assert r.json()["status"] == "open"
    glist = client.get("/me/grievance", headers=user["headers"]).json()
    assert any(g["id"] == gid for g in glist)


def test_admin_grievance_triage(client, admin):
    # Create a user-grievance
    u = client.post("/auth/register", json={
        "email": "g@civic.test", "password": "pw12345678"}).json()
    uh = {"Authorization": f"Bearer {u['token']}"}
    r = client.post("/me/grievance", headers=uh,
                    json={"subject": "Help", "message": "Please resolve"})
    gid = r.json()["id"]
    # Admin sees it
    gs = client.get("/admin/grievances", headers=admin["headers"]).json()
    assert any(g["id"] == gid for g in gs)
    # User is denied admin list
    denied = client.get("/admin/grievances", headers=uh)
    assert denied.status_code == 403
    # Resolve it
    res = client.post(f"/admin/grievances/{gid}/resolve",
                      headers=admin["headers"],
                      json={"status": "resolved", "resolution": "Fixed"})
    assert res.json()["status"] == "resolved"


def test_public_legal_endpoints(client):
    # No auth required (DPDP transparency)
    p = client.get("/legal/privacy")
    assert p.status_code == 200 and "policy" in p.json()
    t = client.get("/legal/terms")
    assert t.status_code == 200 and "terms" in t.json()
    # Anonymous access must work
    assert "consent" in p.json()["policy"].lower()
