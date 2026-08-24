from typing import Any

from pydantic import BaseModel, Field

from harness.core.context import RunContext
from harness.core.models import ExecutionMode, ToolSpec
from harness.registry import register_tool
from harness.analytics.lib import flatten_collection


class FlattenCollectionInput(BaseModel):
    document: dict[str, Any] = Field(description="Parent index document containing nested collections")
    collection: str = Field(description="Nested collection field name, e.g. DETAILS_FTSALES")
    date_field: str | None = Field(default=None, description="Date field inside collection items")
    date_from: str | None = None
    date_to: str | None = None
    filters: dict[str, Any] = Field(default_factory=dict)
    parent_fields: list[str] = Field(
        default_factory=list,
        description="Parent document fields to copy onto each flattened row",
    )


class FlattenCollectionOutput(BaseModel):
    records: list[dict[str, Any]]
    row_count: int


@register_tool
class FlattenCollectionTool:
    spec = ToolSpec(
        name="flatten_collection",
        description=(
            "Explode a nested collection array from an index document into flat rows "
            "for downstream aggregation and analysis."
        ),
        capability_tags=["analytics", "transform", "etl"],
        input_schema=FlattenCollectionInput,
        output_schema=FlattenCollectionOutput,
        side_effects=False,
        execution_mode=ExecutionMode.IN_PROCESS,
    )

    async def run(self, args: FlattenCollectionInput, *, context: RunContext) -> FlattenCollectionOutput:
        records = flatten_collection(
            args.document,
            args.collection,
            date_field=args.date_field,
            date_from=args.date_from,
            date_to=args.date_to,
            filters=args.filters,
            parent_fields=args.parent_fields,
        )
        return FlattenCollectionOutput(records=records, row_count=len(records))
