"""Edge: headers, body cap, 404 shape, dashboard latency sanity."""


def test_security_headers_and_404(client):
    r = client.get("/health")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert client.get("/nope-nothing-here").status_code == 404
    assert client.get("/nope-nothing-here").json() == {"detail": "not found"}


def test_body_cap(client):
    big = {"email": "x@y.co", "password": "p" * (2 * 1024 * 1024)}
    r = client.post("/auth/register", json=big)
    assert r.status_code == 413


def test_dashboard_latency(client, user):
    import time
    ts = []
    for _ in range(20):
        t0 = time.time()
        assert client.get("/me/dashboard", headers=user["headers"]).status_code == 200
        ts.append((time.time() - t0) * 1000)
    ts.sort()
    p95 = ts[int(len(ts) * 0.95) - 1]
    print(f"\ndashboard p95: {p95:.0f}ms")
    assert p95 < 1000
