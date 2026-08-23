from pydantic import BaseModel, Field

from harness.core.context import RunContext
from harness.core.models import ExecutionMode, ToolSpec
from harness.registry import register_tool
from harness.analytics.schema import connector_schema, document_key_field


class IndexFetchDocumentInput(BaseModel):
    connector: str = Field(description="Registered Azure AI Search connector")
    document_id: str = Field(description="Document key value, e.g. Contact Global ID")
    id_field: str | None = Field(
        default=None,
        description="Override key field; defaults to connector schema document_key_field",
    )


class IndexFetchDocumentOutput(BaseModel):
    document: dict
    found: bool


@register_tool
class IndexFetchDocumentTool:
    spec = ToolSpec(
        name="index_fetch_document",
        description="Fetch a single document from an Azure AI Search index by document key.",
        capability_tags=["search", "retrieval", "azure", "document"],
        input_schema=IndexFetchDocumentInput,
        output_schema=IndexFetchDocumentOutput,
        side_effects=False,
        execution_mode=ExecutionMode.IN_PROCESS,
    )

    async def run(self, args: IndexFetchDocumentInput, *, context: RunContext) -> IndexFetchDocumentOutput:
        connector = context.connectors.get(args.connector)
        if connector is None:
            raise ValueError(f"Connector {args.connector!r} not found")

        schema = connector_schema(connector)
        key_field = document_key_field(schema, args.id_field)

        if hasattr(connector, "get_document"):
            document = await connector.get_document(args.document_id, key_field=key_field)
        else:
            from harness.core.models import QuerySpec

            result = await connector.query(
                QuerySpec(
                    filters={
                        "query": "*",
                        "filter": f"{key_field} eq '{args.document_id}'",
                        "top": 1,
                    },
                    limit=1,
                )
            )
            document = result.rows[0] if result.rows else None

        if not document:
            return IndexFetchDocumentOutput(document={}, found=False)
        return IndexFetchDocumentOutput(document=document, found=True)
