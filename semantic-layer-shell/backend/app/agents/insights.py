from __future__ import annotations

import json
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from pydantic import BaseModel, Field

from app.llm.client import LLMClient

logger = logging.getLogger(__name__)


class InsightEvidence(BaseModel):
    type: str = "aggregation"
    column: str | None = None
    function: str | None = None
    value: Any = None


class StructuredInsight(BaseModel):
    id: str
    text: str
    evidence: InsightEvidence | dict[str, Any] = Field(default_factory=dict)


class StructuredInsightsResult(BaseModel):
    headline: str = ""
    insights: list[StructuredInsight] = Field(default_factory=list)
    follow_ups: list[str] = Field(default_factory=list)


def build_result_package(
    *,
    question: str,
    metric_id: str,
    rows: list[dict[str, Any]],
    columns: list[str],
    analysis: dict[str, Any],
    provenance: dict[str, Any] | None = None,
    business_rules: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "question": question,
        "metric_id": metric_id,
        "rows": rows,
        "columns": columns,
        "row_count": len(rows),
        "analysis": analysis,
        "column_profiles": analysis.get("columns", {}),
        "provenance": provenance or {},
        "business_rules": business_rules or [],
    }


def generate_structured_insights(
    llm: LLMClient,
    result_package: dict[str, Any],
) -> dict[str, Any]:
    rows = result_package.get("rows", [])
    analysis = result_package.get("analysis", {})
    metric_id = result_package.get("metric_id", "")
    question = result_package.get("question", "")

    if not llm.enabled:
        return _heuristic_structured_insights(result_package)

    preview_rows = rows[: min(len(rows), llm.settings.max_result_rows)]
    try:
        result = llm._chat_json(
            system=(
                "You analyze query results for business users. Return JSON with keys: headline, "
                "insights (list of {id, text, evidence}), follow_ups (list). "
                "Every numeric claim in insights must include evidence with type, column, function, value "
                "computed from the provided rows or column profiles."
            ),
            user=(
                f"Question: {question}\nMetric: {metric_id}\n"
                f"Row count: {len(rows)}\n"
                f"Columns: {result_package.get('columns', [])}\n"
                f"Column profiles: {json.dumps(analysis.get('columns', {}), default=str)}\n"
                f"Rows: {json.dumps(preview_rows, default=str)}"
            ),
            model_cls=StructuredInsightsResult,
        )
        payload = result.model_dump()
        payload["llm"] = True
        return payload
    except Exception as exc:
        logger.warning("Structured insights failed, using heuristic: %s", exc)
        return _heuristic_structured_insights(result_package)


def _heuristic_structured_insights(result_package: dict[str, Any]) -> dict[str, Any]:
    analysis = result_package.get("analysis", {})
    row_count = analysis.get("row_count", len(result_package.get("rows", [])))
    cols = analysis.get("columns", {})
    numeric = [c for c, stats in cols.items() if stats.get("type") == "numeric"]
    insights: list[dict[str, Any]] = []
    headline = f"Query returned {row_count} row(s)."

    if numeric:
        col = numeric[0]
        stats = cols[col]
        total = stats.get("sum")
        if total is not None:
            headline = f"Total {col} is {total} across {row_count} row(s)."
            insights.append(
                {
                    "id": "ins-1",
                    "text": headline,
                    "evidence": {
                        "type": "aggregation",
                        "column": col,
                        "function": "sum",
                        "value": total,
                    },
                }
            )
        else:
            insights.append(
                {
                    "id": "ins-1",
                    "text": (
                        f"{col} ranges from {stats.get('min')} to {stats.get('max')} "
                        f"with mean {stats.get('mean', 0):.2f}."
                    ),
                    "evidence": {
                        "type": "profile",
                        "column": col,
                        "function": "range",
                        "value": stats,
                    },
                }
            )

    return {
        "headline": headline,
        "insights": insights,
        "follow_ups": [],
        "llm": False,
    }


def generate_insights(
    llm: LLMClient,
    question: str,
    metric_id: str,
    analysis: dict[str, Any],
    rows: list[dict[str, Any]],
    *,
    provenance: dict[str, Any] | None = None,
    business_rules: list[str] | None = None,
) -> dict[str, Any]:
    package = build_result_package(
        question=question,
        metric_id=metric_id,
        rows=rows,
        columns=list(analysis.get("columns", {}).keys()) if analysis.get("columns") else [],
        analysis=analysis,
        provenance=provenance,
        business_rules=business_rules,
    )
    return generate_structured_insights(llm, package)


def run_post_sql_agents(
    llm: LLMClient,
    result_package: dict[str, Any],
    metric_id: str,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    from app.agents.visualization import build_visualization_package

    with ThreadPoolExecutor(max_workers=2) as executor:
        insights_future = executor.submit(generate_structured_insights, llm, result_package)
        viz_future = executor.submit(build_visualization_package, result_package, metric_id)
        return insights_future.result(), viz_future.result()
