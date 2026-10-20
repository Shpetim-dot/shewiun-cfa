from fastapi.testclient import TestClient

from app import main


def _client(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "IS_VERCEL", False)
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "agents.db")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("CFA_MODEL_API_KEY", raising=False)
    monkeypatch.delenv("CFA_MODEL_NAME", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("CFA_DATABASE_URL", raising=False)
    monkeypatch.delenv("CFA_REQUIRE_AUTH", raising=False)
    main._RATE_BUCKETS.clear()
    return TestClient(main.app)


def test_free_local_planner_runs_without_model_key_and_saves_history(tmp_path, monkeypatch):
    with _client(tmp_path, monkeypatch) as client:
        health = client.get("/api/health")
        assert health.status_code == 200
        agents = client.get("/api/agents").json()
        planner = next(agent for agent in agents if agent["id"] == "local-planner")
        assert planner["provider"] == "Built-in · free"
        result = client.post("/api/agents/run", json={
            "topic": "Plan a small customer research pilot",
            "agent_id": "local-planner",
        })
        assert result.status_code == 200, result.text
        assert result.json()["mode"] == "local-free"
        assert "Proposed next steps" in result.json()["result"]
        assert client.get("/api/council").json()[0]["topic"] == "Plan a small customer research pilot"


def test_custom_agent_can_be_created_selected_and_deleted(tmp_path, monkeypatch):
    with _client(tmp_path, monkeypatch) as client:
        created = client.post("/api/agents", json={
            "name": "Customer Researcher",
            "role": "Research and customer insight synthesis",
            "instructions": "Separate observed evidence from assumptions.",
            "icon": "search",
        })
        assert created.status_code == 200, created.text
        agent = created.json()
        assert agent["custom"] is True
        assert any(row["id"] == agent["id"] for row in client.get("/api/agents").json())
        run = client.post("/api/agents/run", json={
            "topic": "Find the next customer discovery experiment",
            "agent_id": agent["id"],
        })
        assert run.status_code == 200, run.text
        assert "Research" in run.json()["result"] or "customer" in run.json()["result"].lower()
        deleted = client.delete("/api/agents/" + agent["id"])
        assert deleted.status_code == 200
        assert all(row["id"] != agent["id"] for row in client.get("/api/agents").json())


def test_council_has_a_free_fallback_when_model_is_not_configured(tmp_path, monkeypatch):
    with _client(tmp_path, monkeypatch) as client:
        response = client.post("/api/council", json={
            "topic": "Choose an MVP success metric",
            "roles": ["Strategist", "Skeptic", "Builder"],
            "rounds": 1,
        })
        assert response.status_code == 200, response.text
        assert response.json()["mode"] == "local-free"
        assert any(item["role"] == "Synthesizer" for item in response.json()["transcript"])
