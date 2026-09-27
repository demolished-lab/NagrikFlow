"""Tests for Telegram webhook secret validation."""
import pytest


def test_health_endpoint(client):
    """Test basic health check."""
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["ok"] is True
    assert "digilocker_env" in r.json()


def test_llm_health_check(client):
    """Test LLM health endpoint returns status structure."""
    r = client.get("/health/llm")
    assert r.status_code == 200
    data = r.json()
    assert "bynara" in data
    assert "ollama" in data
    assert "overall" in data
    assert "timestamp" in data


def test_build_task_requires_login(client):
    """Test that build task endpoint requires authentication."""
    # Without auth - should fail
    r = client.post("/build-task", json={"task": "test task"})
    assert r.status_code == 401
    
    # Register and login
    client.post("/auth/register", json={
        "email": "builder@civic.test",
        "password": "builderpass123"
    })
    login_resp = client.post("/auth/login", json={
        "email": "builder@civic.test",
        "password": "builderpass123"
    })
    token = login_resp.json()["token"]
    
    # With auth - should get past auth check
    headers = {"Authorization": f"Bearer {token}"}
    r = client.post("/build-task", json={"task": "test task"}, headers=headers)
    # Should be 200 (queued), 400 (validation error), or 500 (backend error like no sources)
    # But NOT 401 (should pass auth)
    assert r.status_code not in [401, 403]


def test_telegram_webhook_validates_secret(client):
    """Test that Telegram webhook rejects requests without valid secret."""
    from app import telegram_validate as tval
    
    original_secret = tval._TELEGRAM_SECRET
    tval._TELEGRAM_SECRET = "my-secret-token"
    
    try:
        # Without secret header - should fail
        r = client.post("/hooks/telegram", json={
            "message": {"chat": {"id": "123"}, "text": "/start ABC1234"}
        })
        assert r.status_code == 401
        
        # With wrong secret - should fail
        r = client.post(
            "/hooks/telegram",
            json={"message": {"chat": {"id": "123"}, "text": "/start ABC1234"}},
            headers={"X-Telegram-Bot-Api-Secret-Token": "wrong-secret"}
        )
        assert r.status_code == 401
    finally:
        tval._TELEGRAM_SECRET = original_secret
