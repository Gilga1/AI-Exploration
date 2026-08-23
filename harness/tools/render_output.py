from __future__ import annotations

import io
import json
from typing import Any, Literal

from pydantic import BaseModel, Field

from harness.core.context import RunContext
from harness.core.models import ExecutionMode, ToolSpec
from harness.registry import register_tool


class RenderOutputInput(BaseModel):
    data: list[dict[str, Any]] | dict[str, Any]
    format: Literal["table", "narrative", "chart", "json"] = "table"
    title: str = ""
    chart_config: dict[str, Any] = Field(
        default_factory=dict,
        description="Chart settings: x_field, y_field, chart_type (bar|line)",
    )
    narrative_template: str | None = Field(
        default=None,
        description="Optional template for narrative output using {field} placeholders",
    )


class RenderOutputResult(BaseModel):
    format: str
    title: str
    content: str | None = None
    table: list[dict[str, Any]] | None = None
    json_data: dict[str, Any] | list[dict[str, Any]] | None = None
    artifact_url: str | None = None
    artifact_kind: str | None = None


@register_tool
class RenderOutputTool:
    spec = ToolSpec(
        name="render_output",
        description=(
            "Render analysis results as table, narrative, chart image, or JSON. "
            "Chart output is stored as an artifact."
        ),
        capability_tags=["analytics", "render", "chart", "output"],
        input_schema=RenderOutputInput,
        output_schema=RenderOutputResult,
        side_effects=True,
        execution_mode=ExecutionMode.IN_PROCESS,
    )

    async def run(self, args: RenderOutputInput, *, context: RunContext) -> RenderOutputResult:
        rows = _as_rows(args.data)

        if args.format == "json":
            return RenderOutputResult(
                format="json",
                title=args.title,
                json_data=args.data,
            )

        if args.format == "table":
            return RenderOutputResult(
                format="table",
                title=args.title,
                table=rows,
                content=_table_markdown(rows, args.title),
            )

        if args.format == "narrative":
            content = _render_narrative(rows, args.title, args.narrative_template)
            return RenderOutputResult(format="narrative", title=args.title, content=content, table=rows)

        if args.format == "chart":
            chart_bytes = _render_chart_png(rows, args.chart_config, args.title)
            artifact = await context.store_artifact(
                chart_bytes,
                kind="chart_png",
                metadata={"title": args.title, **args.chart_config},
            )
            return RenderOutputResult(
                format="chart",
                title=args.title,
                table=rows,
                artifact_url=artifact.get("url"),
                artifact_kind="chart_png",
                content=f"Chart generated: {artifact.get('url')}",
            )

        raise ValueError(f"Unsupported format: {args.format}")


def _as_rows(data: list[dict[str, Any]] | dict[str, Any]) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("rows", "records", "cohorts", "anomalies", "metrics"):
            if key in data and isinstance(data[key], list):
                return data[key]
        return [data]
    return []


def _table_markdown(rows: list[dict[str, Any]], title: str) -> str:
    if not rows:
        return f"# {title}\n\nNo data."
    headers = list(rows[0].keys())
    lines = [f"# {title}" if title else "# Results", ""]
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
    for row in rows[:50]:
        lines.append("| " + " | ".join(str(row.get(h, "")) for h in headers) + " |")
    if len(rows) > 50:
        lines.append(f"\n_Showing 50 of {len(rows)} rows._")
    return "\n".join(lines)


def _render_narrative(
    rows: list[dict[str, Any]],
    title: str,
    template: str | None,
) -> str:
    if template:
        context = rows[0] if rows else {}
        try:
            return template.format(**context, title=title, row_count=len(rows))
        except KeyError:
            pass
    if not rows:
        return f"{title}: no results."
    top = rows[0]
    preview = json.dumps(top, default=str)[:500]
    return f"{title}: analyzed {len(rows)} row(s). Top result: {preview}"


def _render_chart_png(rows: list[dict[str, Any]], chart_config: dict[str, Any], title: str) -> bytes:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise ImportError(
            "Chart rendering requires matplotlib. Install with: pip install matplotlib"
        ) from exc

    x_field = chart_config.get("x_field") or (list(rows[0].keys())[0] if rows else "x")
    y_field = chart_config.get("y_field") or (list(rows[0].keys())[1] if rows and len(rows[0]) > 1 else "y")
    chart_type = chart_config.get("chart_type", "bar")
    limit = int(chart_config.get("limit", 20))

    labels = [str(row.get(x_field, "")) for row in rows[:limit]]
    values = [float(str(row.get(y_field, 0)).replace(",", "").replace("$", "") or 0) for row in rows[:limit]]

    fig, ax = plt.subplots(figsize=(10, 5))
    if chart_type == "line":
        ax.plot(labels, values, marker="o")
    else:
        ax.bar(labels, values)
    ax.set_title(title or "Chart")
    ax.set_xlabel(x_field)
    ax.set_ylabel(y_field)
    plt.xticks(rotation=45, ha="right")
    fig.tight_layout()

    buffer = io.BytesIO()
    fig.savefig(buffer, format="png")
    plt.close(fig)
    return buffer.getvalue()
