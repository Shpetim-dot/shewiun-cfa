import pytest

from app.agent_launch_rules import evaluate_agent_launch


@pytest.mark.parametrize(
    ("answers", "expected_id"),
    [
        ({"tools": [{"name": "Payments API", "access": "write"}], "business_actions": ["Payments"], "controls": ["Kill switch", "Audit logging"]}, "ALR-001"),
        ({"tools": [{"name": "Payout API", "access": "write"}], "business_actions": [], "controls": ["Human approval before consequential actions", "Kill switch", "Audit logging"]}, "ALR-002"),
        ({"tools": [{"name": "CRM API", "access": "write", "credentials": "service account"}], "controls": ["Kill switch", "Audit logging"]}, "ALR-003"),
        ({"tools": [{"name": "Read-only API", "access": "read"}], "controls": ["Audit logging"]}, "ALR-004"),
        ({"tools": [{"name": "CRM API", "access": "write"}], "untrusted_inputs": ["Emails"], "isolation": "Unknown", "controls": ["Human approval before consequential actions", "Agent identity separate from user identity", "Kill switch", "Audit logging"]}, "ALR-005"),
        ({"tools": [{"name": "Read-only API", "access": "read"}], "controls": ["Kill switch"]}, "ALR-006"),
        ({"tools": [{"name": "Read-only API", "access": "read"}], "environment": "Production", "controls": ["Unknown"]}, "ALR-007"),
        ({"tools": [], "controls": ["Kill switch", "Audit logging"]}, "ALR-008"),
    ],
)
def test_eight_rule_eval_cases_are_explainable(answers, expected_id):
    result = evaluate_agent_launch(answers)
    finding = next(item for item in result["findings"] if item["id"] == expected_id)
    assert finding["basis"] == "User-provided answer"
    assert finding["triggered_by"]["field"]
    assert finding["triggered_by"]["field"] in answers or finding["triggered_by"]["field"] in {
        "tools", "controls", "isolation"
    }
    assert result["assessment_type"] == "deterministic_self_assessment"


def test_clean_read_only_case_never_claims_proven_safety():
    result = evaluate_agent_launch({
        "tools": [{"name": "Read-only metrics", "access": "read", "credentials": "service account"}],
        "business_actions": ["No external or irreversible actions"],
        "controls": [
            "Agent identity separate from user identity",
            "Kill switch",
            "Audit logging",
        ],
        "untrusted_inputs": [],
        "isolation": "Yes",
        "environment": "Pilot",
    })
    assert result["finding_count"] == 0
    assert "does not prove" in result["note"]
    assert "not a security test" in result["disclaimer"]
