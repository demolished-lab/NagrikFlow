"""Regression coverage for the production hardening pass."""
import json

from sqlmodel import Session, select


def test_unverified_maps_are_visible_to_builder_and_admin_only(client, user,
                                                               admin):
    from app import main as M
    from app.models import TaskMap, User

    with Session(M.engine) as s:
        who = s.exec(select(User).where(User.email == user["email"])).first()
        s.add(TaskMap(slug="draft-map", title="Draft", created_by=who.id,
                      graph_json=json.dumps({"nodes": [], "edges": []})))
        s.commit()

    # the builder reads their own unverified draft, flagged unverified
    r = client.get("/maps/draft-map", headers=user["headers"])
    assert r.status_code == 200
    assert r.json()["verified"] is False

    # admins read every map
    assert client.get("/maps/draft-map",
                      headers=admin["headers"]).status_code == 200

    # an unrelated authenticated user gets 404 (no existence leak)
    stranger = client.post("/auth/register",
                           json={"email": "stranger-scoping@t.co",
                                 "password": "pw123456"}).json()
    r = client.get("/maps/draft-map",
                   headers={"Authorization": f"Bearer {stranger['token']}"})
    assert r.status_code == 404


def test_progress_requires_a_real_step(client, user):
    bad_step = client.post(
        "/me/progress",
        headers=user["headers"],
        json={"map_slug": "udyam-register", "step_id": "not-a-real-step"},
    )
    assert bad_step.status_code == 400
    bad_map = client.post(
        "/me/progress",
        headers=user["headers"],
        json={"map_slug": "missing-map", "step_id": "anything"},
    )
    assert bad_map.status_code == 404


def test_admin_builder_rejects_non_government_urls(client, admin):
    response = client.post(
        "/admin/jobs/build",
        headers=admin["headers"],
        json={"task": "probe", "slug": "probe", "urls": ["http://127.0.0.1:8000/internal"]},
    )
    assert response.status_code == 400


def test_cors_preflight_is_explicit(client):
    response = client.options(
        "/me/dashboard",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "Authorization",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
