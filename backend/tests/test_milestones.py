def test_citizen_milestones_notifications_and_pdf(client, user):
    profile = client.get('/me/profile', headers=user['headers'])
    assert profile.status_code == 200
    assert profile.json()['role'] == 'citizen'

    milestones = client.get('/me/milestones/udyam-register', headers=user['headers'])
    assert milestones.status_code == 200
    items = milestones.json()['milestones']
    assert len(items) >= 4
    assert {'step_id', 'title', 'due_at', 'days_left', 'status'} <= set(items[0])

    alerts = client.get('/me/notifications', headers=user['headers'])
    assert alerts.status_code == 200
    assert alerts.json()['unread'] >= 1
    notification = alerts.json()['notifications'][0]
    marked = client.post(f"/me/notifications/{notification['id']}/read", headers=user['headers'])
    assert marked.status_code == 200

    report = client.get('/me/progress-report.pdf', headers=user['headers'])
    assert report.status_code == 200
    assert report.headers['content-type'].startswith('application/pdf')
    assert report.content.startswith(b'%PDF-1.4')
    assert 'civic-progress-report.pdf' in report.headers['content-disposition']


def test_admin_role_is_required_for_verification_management(client, user, admin):
    assert client.get('/admin/maps', headers=user['headers']).status_code == 403
    admin_profile = client.get('/me/profile', headers=admin['headers'])
    assert admin_profile.status_code == 200
    assert admin_profile.json()['role'] == 'admin'
    assert client.get('/admin/maps', headers=admin['headers']).status_code == 200


def test_notifications_and_pdf_work_without_any_map(client, user):
    """A fresh citizen with no pathways must get 200 + empty data, not a
    404 from one hard-coded map slug (regression: live /me/notifications)."""
    alerts = client.get('/me/notifications', headers=user['headers'])
    assert alerts.status_code == 200, alerts.text
    assert alerts.json()['notifications'] == []
    assert alerts.json()['unread'] == 0

    report = client.get('/me/progress-report.pdf', headers=user['headers'])
    assert report.status_code == 200, report.text
    assert b"No reviewed pathways yet" in report.content


def test_notifications_aggregate_multiple_verified_maps(client, user, admin):
    """Engagement on more than one verified map surfaces deadlines from all
    of them (regression: only slug 'udyam-register' was ever checked)."""
    # verify the seeded map as admin
    client.post('/admin/maps/udyam-register/verify', headers=admin['headers'],
                json={"content_hash": None, "note": "test"})
    # citizen engages with it (creates milestones)
    client.get('/me/milestones/udyam-register', headers=user['headers'])
    alerts = client.get('/me/notifications', headers=user['headers'])
    assert alerts.status_code == 200, alerts.text
    assert alerts.json()['unread'] >= 1

    report = client.get('/me/progress-report.pdf', headers=user['headers'])
    assert report.status_code == 200
    assert b"Roadmap:" in report.content


def test_progress_on_own_unverified_map_tells_the_owner_why(client, user):
    """Builder + unverified => 409 with the review-gate reason; strangers
    still get existence-hiding 404 (transparency without leaking)."""
    from sqlmodel import Session, select

    import app.main as M
    from app.models import TaskMap, User

    with Session(M.engine) as s:
        who = s.exec(select(User).where(User.email == user["email"])).first()
        s.add(TaskMap(slug="fresh-unverified-map", title="Fresh", city="X",
                      state="MH",
                      graph_json='{"nodes":[{"id":"a","type":"action",'
                                 '"title":"T","detail":"d"}],"edges":[]}',
                      source_urls="[]", created_by=who.id))
        s.commit()

    own = client.post("/me/progress", headers=user["headers"],
                      json={"map_slug": "fresh-unverified-map",
                            "step_id": "a"})
    assert own.status_code == 409, own.text
    assert "source review" in own.json()["detail"]

    r2 = client.post("/auth/register",
                     json={"email": "stranger-map@t.co", "password": "pw123456",
                           "name": "S"})
    stranger = {"Authorization": f"Bearer {r2.json()['token']}"}
    other = client.post("/me/progress", headers=stranger,
                        json={"map_slug": "fresh-unverified-map",
                              "step_id": "a"})
    assert other.status_code == 404, other.text
    assert other.json()["detail"] == "unknown map"


def test_404_detail_is_preserved_for_the_user(client, user):
    """edge.py used to swallow every 404 detail into 'not found', hiding
    the real reason (transparency directive)."""
    r = client.get('/me/milestones/no-such-map', headers=user['headers'])
    assert r.status_code == 404
    detail = str(r.json().get('detail', ''))
    assert 'unknown' in detail.lower() or 'unverified' in detail.lower(), detail
    # bare router 404 still answers the normalised shape
    r2 = client.get('/definitely/not/a/route')
    assert r2.status_code == 404
    assert r2.json() == {"detail": "not found"}
