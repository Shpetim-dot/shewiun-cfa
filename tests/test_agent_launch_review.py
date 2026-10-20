from app.agent_launch_rules import evaluate_agent_launch
from fastapi.testclient import TestClient

from app import main


def test_payment_write_without_human_approval_is_critical():
    result = evaluate_agent_launch({
        "tools": [{"name": "Payments API", "access": "write", "credentials": "service account"}],
        "business_actions": ["Payments"],
        "controls": ["Audit logging", "Kill switch"],
        "untrusted_inputs": [],
        "isolation": "Yes",
    })
    finding = next(f for f in result["findings"] if f["id"] == "ALR-001")
    assert finding["severity"] == "critical"
    assert finding["triggered_by"]["field"] == "controls"
    assert result["preliminary_status"] == "No-Go pending critical controls"


def test_untrusted_content_and_write_tools_without_isolation_is_critical():
    result = evaluate_agent_launch({
        "tools": [{"name": "CRM API", "access": "write", "credentials": "service account"}],
        "business_actions": ["Messages to customers"],
        "controls": ["Human approval before consequential actions", "Agent identity separate from user identity", "Kill switch", "Audit logging"],
        "untrusted_inputs": ["Emails", "Tool/API outputs"],
        "isolation": "Unknown",
    })
    finding = next(f for f in result["findings"] if f["id"] == "ALR-005")
    assert finding["severity"] == "critical"
    assert finding["triggered_by"]["field"] == "isolation"


def test_no_write_tools_does_not_raise_identity_finding():
    result = evaluate_agent_launch({
        "tools": [{"name": "Read-only metrics", "access": "read", "credentials": "service account"}],
        "business_actions": ["No external or irreversible actions"],
        "controls": ["Agent identity separate from user identity", "Kill switch", "Audit logging"],
        "untrusted_inputs": ["User prompts"],
        "isolation": "Yes",
        "environment": "Pilot",
    })
    assert not any(f["id"] == "ALR-003" for f in result["findings"])
    assert result["assessment_type"] == "deterministic_self_assessment"
    assert "not a security test" in result["disclaimer"]


def test_public_assess_endpoint_is_rules_only(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "agent-launch-test.db")
    with TestClient(main.app) as client:
        response = client.post("/api/review/agent-launch/assess", json={"answers": {
            "tools": [{"name": "Payments API", "access": "write", "credentials": "service account"}],
            "business_actions": ["Payments"],
            "controls": [],
            "untrusted_inputs": [],
            "isolation": "Unknown",
        }})
        assert response.status_code == 200
        data = response.json()
        assert data["assessment_type"] == "deterministic_self_assessment"
        assert data["finding_count"] >= 1
        assert any(f["id"] == "ALR-001" for f in data["findings"])
        assert "No model was called" in data["note"]


def test_public_assess_endpoint_caps_payload_size():
    with TestClient(main.app) as client:
        response = client.post("/api/review/agent-launch/assess", json={"answers": {"purpose": "x" * 21000}})
        assert response.status_code == 413


def test_agent_launch_route_serves_questionnaire():
    with TestClient(main.app) as client:
        response = client.get("/review/agent-launch")
        assert response.status_code == 200
        assert "Self-assessment only" in response.text
        assert 'name="business_actions"' in response.text
