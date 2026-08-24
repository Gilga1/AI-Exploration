from typing import Any

from pydantic import BaseModel, Field

from harness.core.context import RunContext
from harness.core.models import ExecutionMode, ToolSpec
from harness.registry import register_tool
from harness.analytics.lib import compute_metrics


class ComputeDerivedMetricsInput(BaseModel):
    records: list[dict[str, Any]]
    metrics: list[dict[str, Any]] = Field(
        description=(
            "Metric definitions. Supported types: ratio, share_of_total. "
            "Example: {name: wallet_share, type: ratio, numerator_field: Sales in dollar, "
            "denominator_field: INDAUM}"
        )
    )


class ComputeDerivedMetricsOutput(BaseModel):
    metrics: list[dict[str, Any]]


@register_tool
class ComputeDerivedMetricsTool:
    spec = ToolSpec(
        name="compute_derived_metrics",
        description="Compute derived metrics such as wallet share and market share from aggregated data.",
        capability_tags=["analytics", "metrics", "derived"],
        input_schema=ComputeDerivedMetricsInput,
        output_schema=ComputeDerivedMetricsOutput,
        side_effects=False,
        execution_mode=ExecutionMode.IN_PROCESS,
    )

    async def run(
        self, args: ComputeDerivedMetricsInput, *, context: RunContext
    ) -> ComputeDerivedMetricsOutput:
        metrics = compute_metrics(args.records, args.metrics)
        return ComputeDerivedMetricsOutput(metrics=metrics)
