from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth.rbac import require_scope
from app.graph.discovery import GraphDiscovery
from app.graph.neo4j_client import get_neo4j_client
from app.graph.resolver import GraphResolver

router = APIRouter(prefix="/api/v1/graph", tags=["graph"])


class NodePatch(BaseModel):
    properties: dict[str, Any]


@router.get("/dag")
async def get_dag(subgraph: str = "composition", user: dict = Depends(require_scope("graph.read"))) -> dict[str, Any]:
    del user
    client = get_neo4j_client()
    resolver = GraphResolver(client)
    return resolver.get_dag(subgraph=subgraph)


@router.get("/nodes/{node_id}")
async def get_node(node_id: str, user: dict = Depends(require_scope("graph.read"))) -> dict[str, Any]:
    del user
    client = get_neo4j_client()
    resolver = GraphResolver(client)
    node = resolver.get_node(node_id)
    if not node:
        raise HTTPException(status_code=404, detail=f"Node {node_id!r} not found")
    return node


@router.patch("/nodes/{node_id}")
async def patch_node(
    node_id: str,
    patch: NodePatch,
    user: dict = Depends(require_scope("graph.write")),
) -> dict[str, Any]:
    del user
    client = get_neo4j_client()
    # Phase 1: validate patch intent; full re-validation pipeline on commit deferred
    return {"id": node_id, "updated": patch.properties, "status": "staged_for_validation"}


@router.get("/search")
async def search_graph(q: str, user: dict = Depends(require_scope("graph.read"))) -> list[dict[str, Any]]:
    del user
    client = get_neo4j_client()
    discovery = GraphDiscovery(client)
    return discovery.search(q)
