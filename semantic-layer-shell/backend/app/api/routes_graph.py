from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.routes_registry import get_staged_registry
from app.auth.rbac import require_scope
from app.config.settings import get_settings
from app.graph.discovery import GraphDiscovery
from app.graph.neo4j_client import get_neo4j_client
from app.graph.resolver import GraphResolver
from app.registry.ingestor import RegistryIngestor
from app.registry.models import RegistryDocument
from app.registry.validator import validate_staged_registry

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
    staged = get_staged_registry()
    updated: RegistryDocument | None = None
    documents: list[RegistryDocument] = []

    for doc in staged.documents:
        if doc.metadata.id == node_id:
            data = doc.model_dump()
            metadata_updates = {
                k: v for k, v in patch.properties.items() if k in ("name", "description", "owner", "status", "tags", "synonyms")
            }
            data["metadata"].update(metadata_updates)
            updated = doc.model_validate(data)
            documents.append(updated)
        else:
            documents.append(doc)

    if not updated:
        raise HTTPException(status_code=404, detail=f"Node {node_id!r} not found in staged registry")

    from app.registry.models import StagedRegistry

    new_staged = StagedRegistry(documents=documents, source_files=staged.source_files)
    validation = validate_staged_registry(new_staged)
    if not validation.passed:
        raise HTTPException(status_code=422, detail=validation.model_dump())

    settings = get_settings()
    client = get_neo4j_client()
    if client.connect():
        ingestor = RegistryIngestor(client, settings.embedding_dimensions)
        version_id = ingestor.publish(new_staged)
        return {"id": node_id, "updated": patch.properties, "status": "published", "graph_version_id": version_id}

    return {"id": node_id, "updated": patch.properties, "status": "validated", "graph_version_id": None}


@router.get("/search")
async def search_graph(q: str, user: dict = Depends(require_scope("graph.read"))) -> list[dict[str, Any]]:
    del user
    client = get_neo4j_client()
    discovery = GraphDiscovery(client)
    return discovery.search(q)
