from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.graph.neo4j_client import Neo4jClient
from app.registry.parser import parse_registry_directory
from app.registry.validation_rules import evaluate_rule

CONFIDENCE_ORDER = {"low": 0, "medium": 1, "high": 2}


def load_validation_policy(
    metric_id: str, client: Neo4jClient | None = None
) -> dict[str, Any] | None:
    if client and client.is_connected:
        rows = client.run(
            """
            MATCH (m:Metric {id: $metric_id})-[:HAS_VALIDATION_POLICY]->(p:ValidationPolicy)
            RETURN p
            LIMIT 1
            """,
            {"metric_id": metric_id},
        )
        if rows:
            policy = dict(rows[0]["p"])
            for key in ("rules", "applies_to"):
                val = policy.get(key)
                if isinstance(val, str):
                    try:
                        policy[key] = json.loads(val)
                    except json.JSONDecodeError:
                        policy[key] = []
            return {
                "id": policy.get("id"),
                "name": policy.get("name"),
                "description": policy.get("description"),
                "confidence_aggregation": policy.get("confidence_aggregation", "min"),
                "rules": policy.get("rules", []),
            }

    registry_dir = Path(__file__).resolve().parents[3] / "registry"
    if not registry_dir.exists():
        return None

    staged = parse_registry_directory(registry_dir)
    metric_policy_id: str | None = None
    for doc in staged.documents:
        if doc.kind == "metric" and doc.metadata.id == metric_id:
            metric_policy_id = doc.spec.validation_policy  # type: ignore[union-attr]
            break

    policy_doc = None
    for doc in staged.documents:
        if doc.kind != "validation_policy":
            continue
        if metric_policy_id and doc.metadata.id == metric_policy_id:
            policy_doc = doc
            break
        applies = doc.spec.applies_to  # type: ignore[union-attr]
        if any(t.get("ref") == metric_id and t.get("kind", "metric") == "metric" for t in applies):
            policy_doc = doc
            break

    if not policy_doc:
        return None

    return {
        "id": policy_doc.metadata.id,
        "name": policy_doc.metadata.name,
        "description": policy_doc.metadata.description,
        "confidence_aggregation": policy_doc.spec.confidence_aggregation,  # type: ignore[union-attr]
        "rules": policy_doc.spec.rules,  # type: ignore[union-attr]
    }


def run_validation(
    policy: dict[str, Any] | None,
    *,
    result_package: dict[str, Any],
    insights: dict[str, Any],
    entity_resolutions: list[dict[str, Any]] | None = None,
    entity_filters: list[dict[str, Any]] | None = None,
    resolved_time: dict[str, Any] | None = None,
    dimensions: list[str] | None = None,
) -> dict[str, Any]:
    rules = (policy or {}).get("rules") or []
    context = {
        "rows": result_package.get("rows", []),
        "columns": result_package.get("columns", []),
        "row_count": result_package.get("row_count", len(result_package.get("rows", []))),
        "analysis": result_package.get("analysis", {}),
        "entity_resolutions": entity_resolutions or [],
        "entity_filters": entity_filters or [],
        "resolved_time": resolved_time or {},
        "dimensions": dimensions or [],
    }

    findings: list[dict[str, Any]] = []
    for rule in rules:
        if rule.get("enabled") is False:
            continue
        findings.append(evaluate_rule(rule, context))

    passed_count = sum(1 for f in findings if f.get("passed"))
    overall = _overall_confidence(findings)
    insight_labels = _label_insights(insights, findings, overall)

    return {
        "policy_id": (policy or {}).get("id"),
        "overall_confidence": overall,
        "rules_evaluated": len(findings),
        "rules_passed": passed_count,
        "findings": findings,
        "insight_labels": insight_labels,
    }


def _overall_confidence(findings: list[dict[str, Any]]) -> str:
    if not findings:
        return "high"

    failed_high = [f for f in findings if not f.get("passed") and f.get("severity") == "high"]
    failed_medium = [f for f in findings if not f.get("passed") and f.get("severity") == "medium"]

    if failed_high:
        return "low"
    if failed_medium:
        return "medium"
    return "high"


def _label_insights(
    insights: dict[str, Any],
    findings: list[dict[str, Any]],
    overall: str,
) -> list[dict[str, Any]]:
    labels: list[dict[str, Any]] = []
    passed_rules = [f["rule_id"] for f in findings if f.get("passed")]
    failed_rules = [f["rule_id"] for f in findings if not f.get("passed")]

    for item in insights.get("insights", []):
        has_evidence = bool(item.get("evidence"))
        confidence = overall
        if overall == "high" and not has_evidence:
            confidence = "medium"
        reasons = []
        if passed_rules:
            reasons.append(f"passed rules: {', '.join(passed_rules[:3])}")
        if failed_rules:
            reasons.append(f"failed rules: {', '.join(failed_rules[:3])}")
        if has_evidence:
            reasons.append("evidence present")
        labels.append(
            {
                "insight_id": item.get("id"),
                "confidence": confidence,
                "reasons": reasons,
            }
        )
    return labels


def apply_insight_labels(insights: dict[str, Any], validation: dict[str, Any]) -> dict[str, Any]:
    label_index = {
        entry.get("insight_id"): entry.get("confidence")
        for entry in validation.get("insight_labels", [])
    }
    updated = dict(insights)
    enriched: list[dict[str, Any]] = []
    for item in insights.get("insights", []):
        copy = dict(item)
        if item.get("id") in label_index:
            copy["confidence"] = label_index[item["id"]]
        enriched.append(copy)
    updated["insights"] = enriched
    return updated
