import time

from fastapi.testclient import TestClient

from app import main


def test_runtime_council_run_is_durable_and_completes(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "runtime-test.db")
    monkeypatch.setenv("CFA_MODEL_API_KEY", "test-key")
    monkeypatch.setenv("CFA_MODEL_NAME", "test-model")
\n    async def fake_model_reply(role, topic, context):
        return f"{role} reviewed: {topic}"
\n    monkeypatch.setattr(main, "model_reply", fake_model_reply)

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
    with TestClient(main.app) as client:
        response = client.post("/api/runtime/runs", json={"topic": "Should we ship this?"})
        assert response.status_code == 503
        assert "No model configured" in response.json()["detail"]
        assert client.get("/api/runtime/runs").json() == []


def test_direct_council_rejects_missing_model(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "no-model-council.db")
    monkeypatch.delenv("CFA_MODEL_API_KEY", raising=False)
    monkeypatch.delenv("CFA_MODEL_NAME", raising=False)
    with TestClient(main.app) as client:
        response = client.post("/api/council", json={"topic": "Should we ship this?"})
        assert response.status_code == 503
        assert "No model configured" in response.json()["detail"]
