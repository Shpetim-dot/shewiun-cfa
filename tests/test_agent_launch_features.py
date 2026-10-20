from fastapi.testclient import TestClient

from app import main


def _setup(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "IS_VERCEL", False)
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "review-features.db")
    main._RATE_BUCKETS.clear()


def _create_review(client):
    response = client.post("/api/review/agent-launch/assess", json={"answers": {
        "tools": [{"name": "Read-only metrics", "access": "read", "credentials": "service account"}],
        "business_actions": ["No external or irreversible actions"],
        "controls": ["Agent identity separate from user identity", "Kill switch", "Audit logging"],
        "untrusted_inputs": [],
        "isolation": "Yes",
        "environment": "Pilot",
    }})
    assert response.status_code == 200, response.text
    token = response.json()["share_url"].rsplit("/", 1)[1]
    return response.json(), token


def test_email_unlock_requires_explicit_consent_and_returns_memo(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    with TestClient(main.app) as client:
        _, token = _create_review(client)
        denied = client.post("/api/review/agent-launch/unlock", json={
            "share_token": token, "email": "person@example.com", "consent": False
        })
        assert denied.status_code == 400
        unlocked = client.post("/api/review/agent-launch/unlock", json={
            "share_token": token, "email": "person@example.com", "consent": True
        })
        assert unlocked.status_code == 200
        assert "decision" in unlocked.json()
        assert unlocked.json()["decision"]["verdict"]


def test_authorization_test_request_is_saved_for_admin_review(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    with TestClient(main.app) as client:
        _, token = _create_review(client)
        response = client.post("/api/review/agent-launch/authorization-test-request", json={
            "share_token": token,
            "name": "Test User",
            "email": "test@example.com",
            "company": "Example GmbH",
            "role": "Platform Engineering",
            "use_case": "Test authorization boundaries for an internal read/write agent.",
            "consent": True,
        })
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "received"
        assert response.json()["delivery"] == "stored_only"
        requests = client.get("/api/review/agent-launch/admin/requests")
        assert requests.status_code == 200
        assert requests.json()[0]["request"]["email"] == "test@example.com"


def test_review_analytics_and_retention_endpoint_are_secret_protected(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    monkeypatch.setenv("CRON_SECRET", "c" * 48)
    with TestClient(main.app) as client:
        _create_review(client)
        event = client.post("/api/review/agent-launch/event", json={"event_name": "page_view", "metadata": {"source": "test"}, "analytics_consent": True})
        assert event.status_code == 200
        summary = client.get("/api/review/agent-launch/admin/analytics?days=30")
        assert summary.status_code == 200
        assert summary.json()["submissions"] >= 1
        assert client.get("/api/maintenance/retention").status_code == 403
        cleanup = client.get("/api/maintenance/retention", headers={"Authorization": "Bearer " + "c" * 48})
        assert cleanup.status_code == 200
        assert cleanup.json()["retention_days"] == 90
