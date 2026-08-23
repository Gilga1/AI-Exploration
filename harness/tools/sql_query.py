from pydantic import BaseModel, Field

from harness.core.context import RunContext
from harness.core.models import ExecutionMode, QuerySpec, ToolSpec
from harness.registry import register_tool


class SqlQueryInput(BaseModel):
    connector: str = Field(description="Registered connector name, e.g. sales_postgres or analytics_snowflake")
    sql: str = Field(description="Parameterized SQL query to execute")
    limit: int = Field(default=100, ge=1, le=1000)


class SqlQueryOutput(BaseModel):
    rows: list[dict]
    row_count: int


@register_tool
class SqlQueryTool:
    spec = ToolSpec(
        name="sql_query",
        description="Execute a read-only SQL query against a registered Postgres or Snowflake connector.",
        capability_tags=["sql", "data", "postgres", "snowflake"],
        input_schema=SqlQueryInput,
        output_schema=SqlQueryOutput,
        side_effects=True,
        requires_approval=True,
        execution_mode=ExecutionMode.IN_PROCESS,
    )

    async def run(self, args: SqlQueryInput, *, context: RunContext) -> SqlQueryOutput:
        connector = context.connectors.get(args.connector)
        if connector is None:
            raise ValueError(
                f"Connector {args.connector!r} not found. "
                f"Available: {sorted(context.connectors.keys())}"
            )
        if connector.kind not in ("postgres", "snowflake"):
            raise ValueError(f"Connector {args.connector!r} is not a SQL connector (kind={connector.kind})")

        result = await connector.query(QuerySpec(sql=args.sql, limit=args.limit))
        return SqlQueryOutput(rows=result.rows, row_count=len(result.rows))
