from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel

from app.auth.rbac import get_current_user, require_scope
from app.config.settings import get_settings
from app.graph.neo4j_client import get_neo4j_client
from app.graph.versioning import GraphVersionManager
from app.registry.ingestor import RegistryIngestor
from app.registry.models import StagedRegistry
from app.registry.parser import parse_yaml_content
from app.registry.validator import validate_staged_registry

router = APIRouter(prefix="/api/v1/registry", tags=["registry"])

_staged_registry = StagedRegistry()


class PublishResponse(BaseModel):
    graph_version_id: str
    document_count: int


@router.post("/upload")
async def upload_registry(
    files: list[UploadFile] = File(...),
    user: dict = Depends(require_scope("registry")),
) -> dict[str, Any]:
    del user
    documents = []
    source_files = []
    for upload in files:
        content = (await upload.read()).decode("utf-8")
        doc = parse_yaml_content(content, source_name=upload.filename or "upload")
        documents.append(doc)
        source_files.append(upload.filename or "upload")

    global _staged_registry
    _staged_registry = StagedRegistry(documents=documents, source_files=source_files)
    return {
        "uploaded": len(documents),
        "ids": [d.metadata.id for d in documents],
    }


@router.post("/validate")
async def validate_registry(user: dict = Depends(require_scope("registry"))) -> dict[str, Any]:
    del user
    global _staged_registry
    if not _staged_registry.documents:
        load_bundled_registry()
    if not _staged_registry.documents:
        raise HTTPException(status_code=400, detail="No staged registry — upload files first")
    result = validate_staged_registry(_staged_registry)
    return result.model_dump()


@router.post("/publish", response_model=PublishResponse)
async def publish_registry(user: dict = Depends(require_scope("registry"))) -> PublishResponse:
    del user
    global _staged_registry
    if not _staged_registry.documents:
        load_bundled_registry()
    if not _staged_registry.documents:
        raise HTTPException(status_code=400, detail="No staged registry — upload files first")

    validation = validate_staged_registry(_staged_registry)
    if not validation.passed:
        raise HTTPException(status_code=422, detail=validation.model_dump())

    settings = get_settings()
    client = get_neo4j_client()
    ingestor = RegistryIngestor(client, settings.embedding_dimensions)
    version_id = ingestor.publish(_staged_registry)

    return PublishResponse(graph_version_id=version_id, document_count=len(_staged_registry.documents))


@router.get("/versions")
async def list_versions(user: dict = Depends(require_scope("registry"))) -> list[dict[str, Any]]:
    del user
    client = get_neo4j_client()
    if client.connect():
        versions = GraphVersionManager(client).list_versions()
        if versions:
            for row in versions:
                if isinstance(row.get("source_ref"), str):
                    try:
                        row["source_ref"] = json.loads(row["source_ref"])
                    except json.JSONDecodeError:
                        pass
            return versions
    return []


@router.post("/rollback/{version_id}")
async def rollback_version(
    version_id: str, user: dict = Depends(require_scope("registry.rollback"))
) -> dict[str, str]:
    del user
    client = get_neo4j_client()
    if not client.connect():
        raise HTTPException(status_code=503, detail="Neo4j not available")
    try:
        return GraphVersionManager(client).rollback(version_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def load_bundled_registry() -> None:
    """Load example registry from disk on startup."""
    global _staged_registry
    registry_dir = Path(__file__).resolve().parents[3] / "registry"
    if not registry_dir.exists():
        return
    from app.registry.parser import parse_registry_directory

    _staged_registry = parse_registry_directory(registry_dir)


def get_staged_registry() -> StagedRegistry:
    if not _staged_registry.documents:
        load_bundled_registry()
    return _staged_registry
