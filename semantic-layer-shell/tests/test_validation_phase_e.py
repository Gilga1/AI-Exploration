import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.agents.response_composer import compose_response
from app.agents.validator import load_validation_policy, run_validation
from app.registry.validation_rules import evaluate_rule

REGISTRY_DIR = Path(__file__).resolve().parents[1] / "registry"


def test_load_validation_policy_for_net_flow_ratio():
    policy = load_validation_policy("net_flow_ratio")
    assert policy is not None
    assert policy["id"] == "net_flow_ratio_validation"
    assert len(policy["rules"]) >= 4


def test_row_count_rule_fails_on_empty_rows():
    result = evaluate_rule(
        {"id": "rows_returned", "type": "row_count", "min": 1, "severity": "high"},
        {"rows": [], "row_count": 0},
    )
    assert result["passed"] is False


def test_entity_resolution_rule_fails_on_not_found():
    result = evaluate_rule(
        {
            "id": "entity_resolved",
            "type": "entity_resolution",
            "expect": "exactly_one",
            "severity": "high",
        },
        {
            "entity_resolutions": [
                {"entity_type": "product", "status": "not_found"},
            ]
        },
    )
    assert result["passed"] is False


def test_ratio_bounds_rule():
    result = evaluate_rule(
        {
            "id": "ratio_bounds",
            "type": "ratio_bounds",
            "severity": "medium",
            "params": {"column": "metric_value", "min": -1.0, "max": 1.0},
        },
        {"rows": [{"metric_value": 0.5}, {"metric_value": 1.5}]},
    )
    assert result["passed"] is False


def test_run_validation_overall_confidence_low_on_high_severity_failure():
    policy = load_validation_policy("net_flow_ratio")
    validation = run_validation(
        policy,
        result_package={"rows": [], "columns": [], "row_count": 0},
        insights={"insights": [{"id": "ins-1", "text": "test", "evidence": {}}]},
        entity_resolutions=[],
        dimensions=[],
    )
    assert validation["overall_confidence"] == "low"
    assert validation["rules_evaluated"] >= 1
    assert any(not f["passed"] for f in validation["findings"])


def test_compose_response_includes_validation_and_data():
    payload = compose_response(
        question="ratio?",
        insights={"headline": "Test", "insights": [{"id": "ins-1", "text": "ok"}], "follow_ups": []},
        charts={"charts": [], "recommended_chart_id": None},
        validation={
            "overall_confidence": "medium",
            "policy_id": "net_flow_ratio_validation",
            "rules_evaluated": 3,
            "rules_passed": 2,
            "findings": [],
            "insight_labels": [{"insight_id": "ins-1", "confidence": "medium", "reasons": []}],
        },
        rows=[{"metric_value": 1}],
        columns=["metric_value"],
        provenance={"metric_id": "net_flow_ratio"},
    )
    assert payload["headline"] == "Test"
    assert payload["validation"]["overall_confidence"] == "medium"
    assert payload["data"]["row_count"] == 1
    assert payload["insights"][0]["confidence"] == "medium"
