from pydantic import BaseModel, Field

from harness.core.context import RunContext
from harness.core.models import ExecutionMode, ToolSpec
from harness.registry import register_tool
from harness.analytics.schema import connector_schema, lookup_profile


class IndexLookupInput(BaseModel):
    connector: str = Field(description="Registered Azure AI Search connector for entity resolution")
    query: str | None = Field(default=None, description="Free-text search query")
    filters: dict[str, str] = Field(
        default_factory=dict,
        description="Field equality filters, e.g. advisor_name, email, territory",
    )
    top: int = Field(default=5, ge=1, le=20)


class IndexLookupMatch(BaseModel):
    document_id: str
    score: float | None = None
    fields: dict = Field(default_factory=dict)


class IndexLookupOutput(BaseModel):
    matches: list[IndexLookupMatch]
    resolved_id: str | None = None
    summary: str


@register_tool
class IndexLookupTool:
    spec = ToolSpec(
        name="index_lookup",
        description=(
            "Resolve an entity to its document ID using a configured lookup index. "
            "Reads lookup field mappings from the connector schema.yaml."
        ),
        capability_tags=["search", "lookup", "entity-resolution", "azure"],
        input_schema=IndexLookupInput,
        output_schema=IndexLookupOutput,
        side_effects=False,
        execution_mode=ExecutionMode.IN_PROCESS,
    )

    async def run(self, args: IndexLookupInput, *, context: RunContext) -> IndexLookupOutput:
        connector = context.connectors.get(args.connector)
        if connector is None:
            raise ValueError(f"Connector {args.connector!r} not found")

        schema = connector_schema(connector)
        profile = lookup_profile(schema)
        id_field = profile.get("id_field") or schema.get("document_key_field") or "id"
        search_text = args.query or "*"

        if hasattr(connector, "lookup"):
            result = await connector.lookup(
                search_text=search_text,
                filters=args.filters,
                top=args.top,
            )
        else:
            from harness.core.models import QuerySpec

            result = await connector.query(
                QuerySpec(filters={"query": search_text, "top": args.top}, limit=args.top)
            )

        matches: list[IndexLookupMatch] = []
        for row in result.rows:
            doc_id = str(row.get(id_field) or row.get("id") or "")
            matches.append(
                IndexLookupMatch(
                    document_id=doc_id,
                    score=row.get("@search.score"),
                    fields={
                        k: v
                        for k, v in row.items()
                        if not k.startswith("@") and k not in ("content",)
                    },
                )
            )

        resolved_id = matches[0].document_id if matches else None
        summary = (
            f"Resolved {len(matches)} match(es); top ID={resolved_id!r}"
            if matches
            else "No matches found"
        )
        return IndexLookupOutput(matches=matches, resolved_id=resolved_id, summary=summary)
