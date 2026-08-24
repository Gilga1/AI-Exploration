from typing import Any

from pydantic import BaseModel, Field

from harness.core.context import RunContext
from harness.core.models import ExecutionMode, ToolSpec
from harness.registry import register_tool
from harness.analytics.lib import aggregate_records


class AggregateDataInput(BaseModel):
    records: list[dict[str, Any]]
    group_by: list[str] = Field(description="Dimension fields to group by")
    measures: dict[str, str] = Field(
        description="Measure field to aggregation mapping, e.g. {'Sales in dollar': 'sum'}"
    )
    sort_by: str | None = None
    sort_desc: bool = True
    limit: int | None = Field(default=None, ge=1, le=1000)


class AggregateDataOutput(BaseModel):
    rows: list[dict[str, Any]]
    row_count: int


@register_tool
class AggregateDataTool:
    spec = ToolSpec(
        name="aggregate_data",
        description="GROUP BY aggregation over flat records with configurable dimensions and measures.",
        capability_tags=["analytics", "aggregate", "sql-like"],
        input_schema=AggregateDataInput,
        output_schema=AggregateDataOutput,
        side_effects=False,
        execution_mode=ExecutionMode.IN_PROCESS,
    )

    async def run(self, args: AggregateDataInput, *, context: RunContext) -> AggregateDataOutput:
        rows = aggregate_records(
            args.records,
            group_by=args.group_by,
            measures=args.measures,
            sort_by=args.sort_by,
            sort_desc=args.sort_desc,
            limit=args.limit,
        )
        return AggregateDataOutput(rows=rows, row_count=len(rows))
