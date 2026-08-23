from pydantic import BaseModel, Field

from harness.core.context import RunContext
from harness.core.models import ExecutionMode, ToolSpec
from harness.registry import register_tool


class AzureSearchInput(BaseModel):
    connector: str = Field(
        default="product_docs_index",
        description="Registered Azure AI Search connector name",
    )
    query: str = Field(description="Semantic or keyword search query")
    top: int = Field(default=5, ge=1, le=20)
    filter: str | None = Field(default=None, description="OData filter expression, e.g. product_line eq 'retirement'")


class AzureSearchHit(BaseModel):
    doc_id: str | None = None
    content: str = ""
    score: float | None = None
    metadata: dict = Field(default_factory=dict)


class AzureSearchOutput(BaseModel):
    summary: str
    hits: list[AzureSearchHit]


@register_tool
class AzureIndexSearchTool:
    spec = ToolSpec(
        name="azure_index_search",
        description="Search an Azure AI Search index for relevant document chunks.",
        capability_tags=["search", "retrieval", "azure", "vector"],
        input_schema=AzureSearchInput,
        output_schema=AzureSearchOutput,
        side_effects=False,
        execution_mode=ExecutionMode.IN_PROCESS,
    )

    async def run(self, args: AzureSearchInput, *, context: RunContext) -> AzureSearchOutput:
        connector = context.connectors.get(args.connector)
        if connector is None:
            raise ValueError(
                f"Connector {args.connector!r} not found. "
                f"Available: {sorted(context.connectors.keys())}"
            )

        if hasattr(connector, "semantic_search"):
            result = await connector.semantic_search(
                args.query, top=args.top, filter_expr=args.filter
            )
        else:
            from harness.core.models import QuerySpec

            result = await connector.query(
                QuerySpec(
                    filters={"query": args.query, "top": args.top, "filter": args.filter},
                    limit=args.top,
                )
            )

        hits: list[AzureSearchHit] = []
        snippets: list[str] = []
        for row in result.rows:
            content = str(row.get("content") or row.get("chunk") or row.get("text") or "")
            snippets.append(content[:300])
            hits.append(
                AzureSearchHit(
                    doc_id=str(row.get("doc_id") or row.get("id") or ""),
                    content=content,
                    score=row.get("@search.score"),
                    metadata={k: v for k, v in row.items() if not k.startswith("@")},
                )
            )

        summary = " ".join(snippets[:3]) if snippets else f"No results for {args.query!r}"
        return AzureSearchOutput(summary=summary[:2000], hits=hits)
