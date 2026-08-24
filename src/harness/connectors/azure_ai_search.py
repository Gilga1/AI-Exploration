from __future__ import annotations

import asyncio
from typing import Any

from harness.config.models import ConnectorConfig
from harness.core.models import QueryResult, QuerySpec


class AzureAISearchConnector:
    """Azure AI Search vector / hybrid index connector."""

    def __init__(self, config: ConnectorConfig) -> None:
        self._config = config
        self._client = None

    @property
    def name(self) -> str:
        return self._config.name

    @property
    def kind(self) -> str:
        return "vector_index"

    def _build_client(self):
        try:
            from azure.core.credentials import AzureKeyCredential
            from azure.search.documents import SearchClient
        except ImportError as exc:
            raise ImportError(
                "Azure AI Search requires azure-search-documents. "
                "Install with: pip install -r requirements-azure.txt"
            ) from exc

        endpoint = self._config.extra.get("endpoint") or self._config.host
        index_name = self._config.extra.get("index_name") or self._config.database
        api_key = self._config.password or self._config.extra.get("api_key")

        if not endpoint or not index_name or not api_key:
            raise ValueError(
                f"Connector {self.name!r} requires endpoint, index_name, and api_key"
            )

        return SearchClient(
            endpoint=endpoint,
            index_name=index_name,
            credential=AzureKeyCredential(api_key),
        )

    async def connect(self) -> None:
        self._client = await asyncio.to_thread(self._build_client)

    async def health_check(self) -> bool:
        if self._client is None:
            await self.connect()
        assert self._client is not None

        def _check():
            list(self._client.search(search_text="*", top=1))

        await asyncio.to_thread(_check)
        return True

    async def query(self, spec: QuerySpec) -> QueryResult:
        if self._client is None:
            await self.connect()
        assert self._client is not None

        search_text = spec.filters.get("query") or spec.sql or "*"
        top = spec.limit or int(spec.filters.get("top", 5))
        filter_expr = spec.filters.get("filter")

        def _search():
            results = self._client.search(
                search_text=search_text,
                filter=filter_expr,
                top=top,
            )
            return [dict(doc) for doc in results]

        rows = await asyncio.to_thread(_search)
        return QueryResult(rows=rows)

    def as_retriever(self) -> dict[str, Any]:
        return {
            "connector": self.name,
            "kind": "vector_index",
            "provider": "azure_ai_search",
            "index": self._config.extra.get("index_name") or self._config.database,
            "schema": self._config.extra.get("schema", {}),
        }

    async def semantic_search(self, query: str, *, top: int = 5, filter_expr: str | None = None) -> QueryResult:
        return await self.query(
            QuerySpec(filters={"query": query, "top": top, "filter": filter_expr}, limit=top)
        )

    async def get_document(self, document_id: str, *, key_field: str | None = None) -> dict[str, Any] | None:
        """Fetch a single document by key. Uses schema document_key_field when key_field is omitted."""
        if self._client is None:
            await self.connect()
        assert self._client is not None

        schema = self._config.extra.get("schema") or {}
        resolved_key = key_field or schema.get("document_key_field") or "id"

        def _get():
            try:
                return dict(self._client.get_document(key=document_id))
            except Exception:
                # Fallback: filter search when get_document key differs from stored field name
                filter_expr = f"{resolved_key} eq '{document_id}'"
                results = list(
                    self._client.search(search_text="*", filter=filter_expr, top=1)
                )
                return dict(results[0]) if results else None

        return await asyncio.to_thread(_get)

    async def lookup(
        self,
        *,
        search_text: str = "*",
        filters: dict[str, str] | None = None,
        top: int = 5,
        filter_expr: str | None = None,
    ) -> QueryResult:
        """Entity resolution lookup with optional field equality filters."""
        if filter_expr is None and filters:
            parts = [f"{field} eq '{value}'" for field, value in filters.items() if value]
            filter_expr = " and ".join(parts) if parts else None
        return await self.query(
            QuerySpec(
                filters={"query": search_text, "top": top, "filter": filter_expr},
                limit=top,
            )
        )
