from __future__ import annotations

import asyncio
import os
from typing import Any

from pydantic import BaseModel, Field

from harness.core.context import RunContext
from harness.core.models import ExecutionMode, ToolSpec
from harness.registry import register_tool


class WebSearchInput(BaseModel):
    query: str = Field(description="Search query for public web information")
    limit: int = Field(default=5, ge=1, le=20, description="Max results to return")


class WebSearchResult(BaseModel):
    title: str = ""
    url: str = ""
    snippet: str = ""
    markdown: str | None = None


class WebSearchOutput(BaseModel):
    summary: str
    sources: list[str] = Field(default_factory=list)
    results: list[WebSearchResult] = Field(default_factory=list)


def _firecrawl_api_key() -> str | None:
    return os.environ.get("HARNESS_SECRET_FIRECRAWL_API_KEY") or os.environ.get("FIRECRAWL_API_KEY")


@register_tool
class WebSearchTool:
    spec = ToolSpec(
        name="web_search",
        description="Searches the public web via Firecrawl and returns structured results with optional page content.",
        capability_tags=["research", "web", "firecrawl"],
        input_schema=WebSearchInput,
        output_schema=WebSearchOutput,
        side_effects=False,
        execution_mode=ExecutionMode.IN_PROCESS,
    )

    async def run(self, args: WebSearchInput, *, context: RunContext) -> WebSearchOutput:
        api_key = _firecrawl_api_key()
        if not api_key:
            return _stub_search(args.query)

        return await asyncio.to_thread(_firecrawl_search, args.query, args.limit, api_key)


def _firecrawl_search(query: str, limit: int, api_key: str) -> WebSearchOutput:
    from firecrawl import Firecrawl

    client = Firecrawl(api_key=api_key)
    response = client.search(
        query,
        limit=limit,
        scrape_options={"formats": ["markdown"]},
    )
    results: list[WebSearchResult] = []
    sources: list[str] = []
    snippets: list[str] = []

    for item in response.web or []:
        title = getattr(item, "title", None) or getattr(getattr(item, "metadata", None), "title", "") or ""
        url = getattr(item, "url", None) or getattr(getattr(item, "metadata", None), "url", "") or ""
        description = getattr(item, "description", "") or ""
        markdown = getattr(item, "markdown", None)
        if url:
            sources.append(url)
        snippet = (markdown or description or title)[:500]
        snippets.append(snippet)
        results.append(
            WebSearchResult(title=title, url=url, snippet=description, markdown=markdown)
        )

    summary = " ".join(snippets[:3]) if snippets else f"No web results found for {query!r}."
    return WebSearchOutput(summary=summary[:2000], sources=sources, results=results)


def _stub_search(query: str) -> WebSearchOutput:
    slug = query.lower().replace(" ", "-")
    url = f"https://example.com/research/{slug}"
    return WebSearchOutput(
        summary=(
            f"{query}: market participant with established product offerings. "
            "Key differentiators include enterprise integrations and pricing flexibility. "
            "(stub — set HARNESS_SECRET_FIRECRAWL_API_KEY for live Firecrawl search)"
        ),
        sources=[url],
        results=[WebSearchResult(title=query, url=url, snippet="Stub search result")],
    )
