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
