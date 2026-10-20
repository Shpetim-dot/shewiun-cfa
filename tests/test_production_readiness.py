import time

from fastapi.testclient import TestClient

from app import main


def _configure_production(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "IS_VERCEL", True)
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "production-test.db")
    main._RATE_BUCKETS.clear()


def test_production_workspace_fails_closed_without_auth_secrets(monkeypatch, tmp_path):
    _configure_production(monkeypatch, tmp_path)
    monkeypatch.delenv("CFA_ACCESS_PASSWORD", raising=False)
    monkeypatch.delenv("CFA_SESSION_SECRET", raising=False)
    with TestClient(main.app) as client:
        status = client.get("/api/auth/status")
        assert status.status_code == 200
        assert status.json()["required"] is True
        assert status.json()["configured"] is False
        blocked = client.get("/api/projects")
        assert blocked.status_code == 503
        assert "CFA_ACCESS_PASSWORD" in blocked.json()["detail"]


def test_configured_workspace_requires_login_and_accepts_signed_session(monkeypatch, tmp_path):
    _configure_production(monkeypatch, tmp_path)
    monkeypatch.setenv("CFA_ACCESS_PASSWORD", "correct-horse-battery-staple")
    monkeypatch.setenv("CFA_SESSION_SECRET", "s" * 48)
    with TestClient(main.app, base_url="https://testserver") as client:
        assert client.get("/api/projects").status_code == 401
        login = client.post("/api/auth/login", json={"password": "correct-horse-battery-staple"})
        assert login.status_code == 200
        assert "cfa_session" in client.cookies
        assert client.get("/api/projects").status_code == 200
        created = client.post(
            "/api/projects",
            headers={"Origin": "https://testserver"},
            json={"name": "Private workspace test", "description": "Temporary test record"},
        )
        assert created.status_code == 200
        assert client.post(
            "/api/projects",
            headers={"Origin": "https://attacker.example"},
            json={"name": "Cross-origin attempt", "description": ""},
        ).status_code == 403
        assert client.post("/api/auth/logout").status_code == 200
        assert client.get("/api/projects").status_code == 401


def test_auth_rejects_wrong_password_and_reports_readiness_blockers(monkeypatch, tmp_path):
    _configure_production(monkeypatch, tmp_path)
    monkeypatch.setenv("CFA_ACCESS_PASSWORD", "correct-horse-battery-staple")
    monkeypatch.setenv("CFA_SESSION_SECRET", "x" * 48)
    with TestClient(main.app) as client:
        assert client.post("/api/auth/login", json={"password": "wrong-password"}).status_code == 401
        health = client.get("/api/health")
        data = health.json()
        assert data["production_ready"] is False
        assert data["storage_persistent"] is False
        assert data["distributed_rate_limits"] is False
        assert "persistent PostgreSQL storage is not configured" in data["readiness_blockers"]
        assert health.headers["x-content-type-options"] == "nosniff"
        assert health.headers["x-frame-options"] == "DENY"


def test_agent_launch_public_assessment_remains_available(monkeypatch, tmp_path):
    _configure_production(monkeypatch, tmp_path)
    monkeypatch.delenv("CFA_ACCESS_PASSWORD", raising=False)
    monkeypatch.delenv("CFA_SESSION_SECRET", raising=False)
    with TestClient(main.app) as client:
        response = client.post("/api/review/agent-launch/assess", json={"answers": {"tools": []}})
        assert response.status_code == 200
        assert response.json()["assessment_type"] == "deterministic_self_assessment"
