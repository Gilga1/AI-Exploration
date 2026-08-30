from __future__ import annotations

from typing import Any


def build_chart_spec(
    rows: list[dict[str, Any]], columns: list[str], metric_id: str
) -> dict[str, Any] | None:
    if not rows or not columns:
        return None

    numeric_cols = [
        c
        for c in columns
        if any(isinstance(row.get(c), (int, float)) for row in rows)
    ]
    dim_cols = [c for c in columns if c not in numeric_cols]

    if not numeric_cols:
        return None

    y_col = numeric_cols[0]
    x_col = dim_cols[0] if dim_cols else None

    chart_type = "line" if _looks_temporal(x_col, rows) else "bar"
    data = rows[:100]

    return {
        "library": "vega-lite",
        "metric_id": metric_id,
        "spec": {
            "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
            "description": f"Auto chart for {metric_id}",
            "data": {"values": data},
            "mark": chart_type,
            "encoding": {
                "x": {"field": x_col or columns[0], "type": _vega_type(x_col or columns[0], rows)},
                "y": {"field": y_col, "type": "quantitative"},
            },
        },
    }


def _looks_temporal(col: str | None, rows: list[dict[str, Any]]) -> bool:
    if not col:
        return False
    if "date" in col.lower() or col.endswith("_at"):
        return True
    sample = next((row.get(col) for row in rows if row.get(col) is not None), None)
    return isinstance(sample, str) and ("-" in sample or "/" in sample)


def _vega_type(col: str, rows: list[dict[str, Any]]) -> str:
    if _looks_temporal(col, rows):
        return "temporal"
    sample = next((row.get(col) for row in rows if row.get(col) is not None), None)
    if isinstance(sample, (int, float)):
        return "quantitative"
    return "nominal"
