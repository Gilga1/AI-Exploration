from __future__ import annotations

from typing import Any


TEMPLATE_IDS = ("line_temporal", "bar_categorical", "kpi_card", "grouped_bar")


def build_visualization_package(
    result_package: dict[str, Any],
    metric_id: str,
) -> dict[str, Any] | None:
    rows = result_package.get("rows", [])
    columns = result_package.get("columns", [])
    if not rows or not columns:
        return None

    template_id = _select_template(rows, columns)
    chart = _build_chart(template_id, rows, columns, metric_id)
    if not chart:
        return None

    return {
        "charts": [chart],
        "recommended_chart_id": chart["id"],
    }


def build_chart_spec(
    rows: list[dict[str, Any]], columns: list[str], metric_id: str
) -> dict[str, Any] | None:
    package = {"rows": rows, "columns": columns}
    viz = build_visualization_package(package, metric_id)
    if not viz or not viz.get("charts"):
        return None
    chart = viz["charts"][0]
    return {
        "library": chart.get("library", "vega-lite"),
        "metric_id": metric_id,
        "template_id": chart.get("template_id"),
        "spec": chart.get("spec"),
    }


def _select_template(rows: list[dict[str, Any]], columns: list[str]) -> str:
    numeric_cols = _numeric_columns(rows, columns)
    dim_cols = [c for c in columns if c not in numeric_cols]
    time_col = _time_column(dim_cols, rows)

    if len(rows) == 1 and numeric_cols:
        return "kpi_card"
    if time_col and len(numeric_cols) == 1 and len(rows) > 1:
        return "line_temporal"
    if len(numeric_cols) >= 2:
        return "grouped_bar"
    if dim_cols and numeric_cols:
        return "bar_categorical"
    return "bar_categorical"


def _build_chart(
    template_id: str,
    rows: list[dict[str, Any]],
    columns: list[str],
    metric_id: str,
) -> dict[str, Any] | None:
    numeric_cols = _numeric_columns(rows, columns)
    dim_cols = [c for c in columns if c not in numeric_cols]
    if not numeric_cols:
        return None

    data = rows
    title = f"Chart for {metric_id}"
    spec: dict[str, Any]

    if template_id == "kpi_card":
        metric_col = numeric_cols[0]
        value = rows[0].get(metric_col)
        spec = {
            "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
            "data": {"values": [{"value": value, "label": metric_col}]},
            "mark": {"type": "text", "fontSize": 42},
            "encoding": {
                "text": {"field": "value", "type": "quantitative"},
            },
        }
    elif template_id == "line_temporal":
        x_col = _time_column(dim_cols, rows) or dim_cols[0]
        y_col = numeric_cols[0]
        spec = {
            "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
            "data": {"values": data},
            "mark": "line",
            "encoding": {
                "x": {"field": x_col, "type": _vega_type(x_col, rows)},
                "y": {"field": y_col, "type": "quantitative"},
            },
        }
    elif template_id == "grouped_bar":
        x_col = dim_cols[0] if dim_cols else columns[0]
        spec = {
            "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
            "data": {"values": data},
            "mark": "bar",
            "encoding": {
                "x": {"field": x_col, "type": _vega_type(x_col, rows)},
                "y": {"field": numeric_cols[0], "type": "quantitative"},
                "color": {"field": numeric_cols[1], "type": "quantitative"},
            },
        }
    else:
        x_col = dim_cols[0] if dim_cols else columns[0]
        y_col = numeric_cols[0]
        spec = {
            "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
            "data": {"values": data},
            "mark": "bar",
            "encoding": {
                "x": {"field": x_col, "type": _vega_type(x_col, rows)},
                "y": {"field": y_col, "type": "quantitative"},
            },
        }

    return {
        "id": "primary",
        "template_id": template_id,
        "title": title,
        "library": "vega-lite",
        "spec": spec,
    }


def _numeric_columns(rows: list[dict[str, Any]], columns: list[str]) -> list[str]:
    return [
        c
        for c in columns
        if any(isinstance(row.get(c), (int, float)) for row in rows)
    ]


def _time_column(dim_cols: list[str], rows: list[dict[str, Any]]) -> str | None:
    for col in dim_cols:
        if _looks_temporal(col, rows):
            return col
    return None


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
