from __future__ import annotations

from typing import Any

from app.agents.validator import apply_insight_labels
from app.config.settings import get_settings


def compose_response(
    *,
    question: str,
    insights: dict[str, Any],
    charts: dict[str, Any] | None,
    validation: dict[str, Any],
    rows: list[dict[str, Any]],
    columns: list[str],
    provenance: dict[str, Any],
    narrative: str | None = None,
) -> dict[str, Any]:
    labeled_insights = apply_insight_labels(insights, validation)
    max_rows = get_settings().max_result_rows

    payload: dict[str, Any] = {
        "headline": labeled_insights.get("headline", ""),
        "insights": labeled_insights.get("insights", []),
        "follow_ups": labeled_insights.get("follow_ups", []),
        "charts": (charts or {}).get("charts", []),
        "recommended_chart_id": (charts or {}).get("recommended_chart_id"),
        "validation": {
            "overall_confidence": validation.get("overall_confidence"),
            "policy_id": validation.get("policy_id"),
            "rules_evaluated": validation.get("rules_evaluated"),
            "rules_passed": validation.get("rules_passed"),
            "findings": validation.get("findings", []),
        },
        "data": {
            "columns": columns,
            "rows": rows,
            "row_count": len(rows),
            "truncated": len(rows) >= max_rows,
        },
        "provenance": provenance,
    }
    if narrative:
        payload["narrative"] = narrative
    payload["question"] = question
    return payload
