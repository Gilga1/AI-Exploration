from __future__ import annotations

from typing import Any

from app.llm.client import LLMClient


def generate_insights(
    llm: LLMClient,
    question: str,
    metric_id: str,
    analysis: dict[str, Any],
    rows: list[dict[str, Any]],
) -> str:
    if not llm.enabled:
        return _heuristic_insights(analysis)

    import json

    try:
        client = llm._get_client()
        response = client.chat.completions.create(
            model=llm.settings.openai_model,
            temperature=0.2,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a data analyst. Given query statistics, provide 2-3 bullet insights. "
                        "Be factual — only reference numbers present in the analysis."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Question: {question}\nMetric: {metric_id}\n"
                        f"Analysis: {json.dumps(analysis, default=str)}\n"
                        f"Sample rows: {json.dumps(rows[:3], default=str)}"
                    ),
                },
            ],
        )
        return response.choices[0].message.content or _heuristic_insights(analysis)
    except Exception:
        return _heuristic_insights(analysis)


def _heuristic_insights(analysis: dict[str, Any]) -> str:
    count = analysis.get("row_count", 0)
    cols = analysis.get("columns", {})
    numeric = [c for c, s in cols.items() if s.get("type") == "numeric"]
    if not numeric:
        return f"Returned {count} rows."
    first = numeric[0]
    stats = cols[first]
    return (
        f"Returned {count} rows. {first}: min={stats.get('min')}, max={stats.get('max')}, "
        f"mean={stats.get('mean', 0):.2f}."
    )
