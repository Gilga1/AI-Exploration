from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.agents.nodes import QueryPipeline
from app.agents.streaming import stream_query_events
from app.auth.rbac import require_scope
from app.graph.neo4j_client import get_neo4j_client
from app.graph.resolver import GraphResolver
from app.sql_gen.assembler import SQLAssembler

router = APIRouter(tags=["query"])


class QueryRequest(BaseModel):
    question: str
    metric_id: str | None = None


class SqlPreviewRequest(BaseModel):
    metric_id: str
    parameters: dict[str, str] = Field(default_factory=dict)
    dimensions: list[str] = Field(default_factory=list)


class SqlExecuteRequest(BaseModel):
    sql_hash: str
    metric_id: str


@router.post("/api/v1/query/stream")
async def query_stream(body: QueryRequest, user: dict = Depends(require_scope("query"))):
    del user

    async def event_generator():
        async for line in stream_query_events(body.question, metric_id=body.metric_id):
            yield line

    return StreamingResponse(event_generator(), media_type="application/x-ndjson")


@router.post("/api/v1/query")
async def query_sync(body: QueryRequest, user: dict = Depends(require_scope("query"))) -> dict[str, Any]:
    del user
    events: list[dict[str, Any]] = []
    async for line in stream_query_events(body.question, metric_id=body.metric_id):
        import json

        events.append(json.loads(line))
    return {"events": events}


@router.post("/api/v1/sql/preview")
async def sql_preview(body: SqlPreviewRequest, user: dict = Depends(require_scope("sql.preview"))) -> dict[str, Any]:
    del user
    client = get_neo4j_client()
    resolver = GraphResolver(client)
    subgraph = resolver.resolve_metric(body.metric_id)
    if not subgraph:
        return {"error": f"metric {body.metric_id!r} not found"}

    assembler = SQLAssembler()
    assembled = assembler.assemble(subgraph, parameters=body.parameters, dimensions=body.dimensions)
    return {
        "metric_id": assembled.metric_id,
        "sql": assembled.sql,
        "sql_hash": assembled.sql_hash,
        "graph_version_id": assembled.graph_version_id,
        "node_ids": assembled.node_ids,
        "edge_ids": assembled.edge_ids,
        "provenance": assembled.provenance,
    }


@router.post("/api/v1/sql/execute")
async def sql_execute(body: SqlExecuteRequest, user: dict = Depends(require_scope("query"))) -> dict[str, Any]:
    del user
    # Phase 1: re-resolve and verify hash before execution
    client = get_neo4j_client()
    resolver = GraphResolver(client)
    subgraph = resolver.resolve_metric(body.metric_id)
    if not subgraph:
        return {"error": f"metric {body.metric_id!r} not found"}

    assembler = SQLAssembler()
    assembled = assembler.assemble(subgraph)
    if assembled.sql_hash != body.sql_hash:
        return {"error": "sql_hash mismatch — preview again before execute"}

    from app.warehouse.snowflake_client import SnowflakeClient

    rows, columns = SnowflakeClient().execute(assembled.sql)
    return {
        "sql_hash": assembled.sql_hash,
        "row_count": len(rows),
        "rows": rows,
        "columns": columns,
    }
