import asyncio
import json

from app import agent_launch_runtime as runtime


def test_review_persists_result_and_private_token(tmp_path, monkeypatch):
    monkeypatch.delenv("CFA_MODEL_API_KEY", raising=False)
    result = asyncio.run(runtime.create_review(tmp_path / "reviews.db", {
        "tools": [{"name": "Payments API", "access": "write", "credentials": "service account"}],
        "business_actions": ["Payments"],
        "controls": ["Audit logging"],
        "untrusted_inputs": [],
        "isolation": "Unknown",
        "environment": "Production",
    }))
    assert result["model_configured"] is False
    assert result["decision"]["verdict"] == "No-Go"
    assert "not a security test" in result["disclaimer"]
    token = result["share_url"].rsplit("/", 1)[1]
    saved = runtime.get_review_by_token(tmp_path / "reviews.db", token)
    assert saved["id"] == result["id"]
    assert saved["decision"]["verdict"] == "No-Go"


def test_model_synthesis_cannot_override_critical_rule():
    memo = {"verdict": "Go", "recommendation": "Launch now", "key_risks": []}
    findings = [{"id": "ALR-001", "severity": "critical", "title": "Payment approval missing"}]
    enforced = runtime._enforce_rules(memo, findings)
    assert enforced["verdict"] == "No-Go"
    assert "critical control gaps" in enforced["recommendation"]


def test_review_deletion_removes_saved_result(tmp_path, monkeypatch):
    monkeypatch.delenv("CFA_MODEL_API_KEY", raising=False)
    path = tmp_path / "reviews.db"
    result = asyncio.run(runtime.create_review(path, {"tools": [], "controls": []}))
    token = result["share_url"].rsplit("/", 1)[1]
    assert runtime.delete_review(path, result["id"])
    assert runtime.get_review_by_token(path, token) is None


def test_review_provider_not_configured_is_explicit(tmp_path, monkeypatch):
    monkeypatch.delenv("CFA_MODEL_API_KEY", raising=False)
    monkeypatch.delenv("CFA_MODEL_NAME", raising=False)
    result = asyncio.run(runtime.create_review(tmp_path / "reviews.db", {"tools": []}))
    assert result["model_configured"] is False
    assert result["perspectives"] == {}
    assert result["decision"]["confidence"]["level"] == "Limited"
