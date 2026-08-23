from pydantic import BaseModel, Field

from harness.core.context import RunContext
from harness.core.models import ExecutionMode, ToolSpec
from harness.registry import register_tool


class WebSearchInput(BaseModel):
    query: str = Field(description="Search query for public web information")


class WebSearchOutput(BaseModel):
    summary: str
    sources: list[str] = Field(default_factory=list)


@register_tool
class WebSearchTool:
    spec = ToolSpec(
        name="web_search",
        description="Searches public web sources for information about a topic or company.",
        capability_tags=["research", "web"],
        input_schema=WebSearchInput,
        output_schema=WebSearchOutput,
        side_effects=False,
        execution_mode=ExecutionMode.IN_PROCESS,
    )

    async def run(self, args: WebSearchInput, *, context: RunContext) -> WebSearchOutput:
        # Stub implementation — replace with real search API in production.
        query = args.query.strip()
        return WebSearchOutput(
            summary=(
                f"{query} is a market participant with established product offerings. "
                f"Key differentiators include enterprise integrations and pricing flexibility."
            ),
            sources=[f"https://example.com/research/{query.lower().replace(' ', '-')}"],
        )
