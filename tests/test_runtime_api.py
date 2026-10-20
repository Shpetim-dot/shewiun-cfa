import time

from fastapi.testclient import TestClient

from app import main


def test_runtime_council_run_is_durable_and_completes(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "runtime-test.db")
    monkeypatch.setenv("CFA_MODEL_API_KEY", "test-key")
    monkeypatch.setenv("CFA_MODEL_NAME", "test-model")
    async def fake_model_reply(role, topic, context):
        return f"{role} reviewed: {topic}"
    monkeypatch.setattr(main, "model_reply", fake_model_reply)

    with TestClient(main.app) as client:
        created = client.post("/api/runtime/runs", json={
            "topic": "Choose the next CFA backend milestone",
            "roles": ["Strategist", "Skeptic", "Builder"],
            "rounds": 1,
        })
        assert created.status_code == 202
        run_id = created.json()["id"]

        deadline = time.time() + 5
        run = None
        while time.time() < deadline:
            response = client.get(f"/api/runtime/runs/{run_id}")
            assert response.status_code == 200
            run = response.json()
            if run["status"] in {"completed", "failed", "cancelled"}:
                break
            time.sleep(0.05)

        assert run is not None
        assert run["status"] == "completed", run
        assert run["state"]["next_index"] == 4
        assert run["result"]["mode"] == "live"
        assert len(run["result"]["transcript"]) == 4
        assert any(event["event_type"] == "run.completed" for event in run["events"])

        history = client.get("/api/runtime/runs")
        assert history.status_code == 200
        assert any(item["id"] == run_id for item in history.json())



def test_runtime_rejects_missing_model_without_fabricating_result(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "no-model.db")
    monkeypatch.delenv("CFA_MODEL_API_KEY", raising=False)
    monkeypatch.delenv("CFA_MODEL_NAME", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with TestClient(main.app) as client:
        response = client.post("/api/runtime/runs", json={"topic": "Should we ship this?"})
        assert response.status_code == 503
        assert "No model configured" in response.json()["detail"]
        assert client.get("/api/runtime/runs").json() == []


def test_direct_council_uses_free_fallback_without_model(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "no-model-council.db")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("CFA_MODEL_API_KEY", raising=False)
    monkeypatch.delenv("CFA_MODEL_NAME", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("CFA_DATABASE_URL", raising=False)
    with TestClient(main.app) as client:
        response = client.post("/api/council", json={"topic": "Should we ship this?"})
        assert response.status_code == 200
        assert response.json()["mode"] == "local-free"
        assert any(item["role"] == "Synthesizer" for item in response.json()["transcript"])



def test_gemini_free_tier_is_detected_and_security_headers_are_set(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.delenv("CFA_MODEL_API_KEY", raising=False)
    monkeypatch.delenv("CFA_MODEL_NAME", raising=False)
    with TestClient(main.app) as client:
        health = client.get("/api/health")
        assert health.status_code == 200
        assert health.json()["model_configured"] is True
        assert health.json()["model_provider"] == "Google Gemini API"
        assert health.json()["model_name"] == "gemini-2.5-flash"
        assert health.json()["free_agent_available"] is True
        assert health.headers["x-content-type-options"] == "nosniff"
        assert health.headers["x-frame-options"] == "DENY"
        assert health.headers["content-security-policy"].find("frame-ancestors 'none'") >= 0
