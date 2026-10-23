"""Deterministic, explainable checks for Agent Launch Review v1.

These rules are a self-assessment aid, not a security test or certification.
Each finding points to the answer field that triggered it.
"""
from __future__ import annotations

from typing import Any

PLAYBOOK_VERSION = "1.0.0"


def _selected(value: Any, *choices: str) -> bool:
    if isinstance(value, list):
        return any(item in choices for item in value)
    return value in choices


def evaluate_agent_launch(answers: dict[str, Any]) -> dict[str, Any]:
    """Evaluate questionnaire answers without calling a model or external service."""
    tools = answers.get("tools") or []
    if not isinstance(tools, list):
        tools = []
    controls = answers.get("controls") or []
    untrusted = answers.get("untrusted_inputs") or []
    actions = answers.get("business_actions") or []

    write_tools = [
        tool for tool in tools
        if isinstance(tool, dict) and str(tool.get("access", "")).lower() in {"write", "read/write", "read_write"}
    ]
    payment_write = any(
        isinstance(tool, dict)
        and str(tool.get("access", "")).lower() in {"write", "read/write", "read_write"}
        and any(term in str(tool.get("name", "")).lower() for term in ("payment", "transfer", "payout"))
        for tool in tools
    ) or _selected(actions, "Payments", "Refunds")

    findings: list[dict[str, Any]] = []

    def add(rule_id: str, severity: str, title: str, detail: str, field: str) -> None:
        findings.append({
            "id": rule_id,
            "severity": severity,
            "title": title,
            "detail": detail,
            "triggered_by": {"field": field, "answer": answers.get(field)},
            "basis": "User-provided answer",
        })

    human_approval = _selected(controls, "Human approval before consequential actions")
    amount_limits = _selected(controls, "Rate or amount limits")
    separate_identity = _selected(controls, "Agent identity separate from user identity")
    kill_switch = _selected(controls, "Kill switch")
    audit_logging = _selected(controls, "Audit logging")
    isolation = answers.get("isolation", "Unknown")

    if payment_write and not human_approval:
        add("ALR-001", "critical", "Financial write actions lack human approval",
            "The answers indicate payment/refund capability without an implemented human approval gate. Keep these actions disabled until an approval control is in place and tested.",
            "controls")
    if payment_write and not amount_limits:
        add("ALR-002", "high", "No amount or rate limits reported",
            "Financial actions are reported, but no implemented rate or amount limits were selected.",
            "controls")
    if any(str(tool.get("credentials", "")).lower() in {"user credentials", "users own credentials", "user's own credentials", "end-user credentials"} for tool in tools if isinstance(tool, dict)):
        add("ALR-003", "high", "Agent identity boundary is unclear",
            "At least one tool may use end-user credentials. Confirm credential ownership and scope.",
            "tools")
    elif write_tools and not separate_identity:
        add("ALR-003", "high", "Separate agent identity not reported",
            "Write-capable tools are listed, but a separate agent identity was not selected as implemented.",
            "controls")
    if not kill_switch:
        add("ALR-004", "high", "Kill switch not reported",
            "No implemented mechanism to stop agent execution was selected. Define and test a way to halt ongoing and queued actions.",
            "controls")
    if _selected(untrusted, "Emails", "Web content", "Tickets", "Documents", "Tool/API outputs", "User prompts") and write_tools and isolation != "Yes":
        add("ALR-005", "critical", "Untrusted input can reach write-capable tools without confirmed isolation",
            "Untrusted content and write access are both reported, while isolation is not confirmed as complete. Test prompt-injection and confused-deputy paths before enabling writes.",
            "isolation")
    if not audit_logging:
        add("ALR-006", "high", "Audit logging not reported",
            "No implemented audit logging was selected. Record tool calls, decisions, identities, timestamps, and outcomes.",
            "controls")
    if answers.get("environment") == "Production" and _selected(controls, "None of these", "Unknown"):
        add("ALR-007", "high", "Production controls are unknown or absent",
            "The environment is marked Production while controls are reported as unknown or absent. Confirm the actual control state before launch.",
            "controls")
    if not tools:
        add("ALR-008", "medium", "Tool inventory is missing",
            "No structured tool entries were provided. List each reachable API/tool, access mode, scope, credential type, and limit.",
            "tools")

    severity_rank = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    findings.sort(key=lambda item: severity_rank[item["severity"]])
    if any(f["severity"] == "critical" for f in findings):
        preliminary_status = "No-Go pending critical controls"
    elif any(f["severity"] == "high" for f in findings):
        preliminary_status = "Conditional review"
    elif findings:
        preliminary_status = "Review required"
    else:
        preliminary_status = "No rule findings from supplied answers"

    return {
        "playbook": "agent-launch",
        "playbook_version": PLAYBOOK_VERSION,
        "assessment_type": "deterministic_self_assessment",
        "disclaimer": "This is a structured self-assessment based on user-provided answers. It is not a security test, audit, or certification.",
        "preliminary_status": preliminary_status,
        "findings": findings,
        "finding_count": len(findings),
        "note": "No model was called. A lack of findings does not prove an agent is safe to launch.",
    }
