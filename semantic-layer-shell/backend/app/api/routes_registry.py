from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel

from app.auth.rbac import Role, get_current_user, require_scope
from app.config.settings import get_settings
from app.graph.neo4j_client import get_neo4j_client
from app.registry.ingestor import RegistryIngestor
from app.registry.models import StagedRegistry
from app.registry.parser import parse_yaml_content
from app.registry.validator import validate_staged_registry

router = APIRouter(prefix="/api/v1/registry", tags=["registry"])

_staged_registry = StagedRegistry()
_published_versions: list[dict[str, Any]] = []


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
    if not _staged_registry.documents:
        raise HTTPException(status_code=400, detail="No staged registry — upload files first")

    validation = validate_staged_registry(_staged_registry)
    if not validation.passed:
        raise HTTPException(status_code=422, detail=validation.model_dump())

    settings = get_settings()
    client = get_neo4j_client()
    ingestor = RegistryIngestor(client, settings.embedding_dimensions)
    version_id = ingestor.publish(_staged_registry)

    _published_versions.append(
        {
            "id": version_id,
            "document_count": len(_staged_registry.documents),
            "source_files": _staged_registry.source_files,
        }
    )

    return PublishResponse(graph_version_id=version_id, document_count=len(_staged_registry.documents))


@router.get("/versions")
async def list_versions(user: dict = Depends(require_scope("registry"))) -> list[dict[str, Any]]:
    del user
    return _published_versions


@router.post("/rollback/{version_id}")
async def rollback_version(version_id: str, user: dict = Depends(require_scope("registry.rollback"))) -> dict[str, str]:
    del user
    # Phase 1: record intent; full blue-green swap deferred
    return {"status": "rollback_scheduled", "version_id": version_id}


def load_bundled_registry() -> None:
    """Load example registry from disk on startup."""
    global _staged_registry
    registry_dir = Path(__file__).resolve().parents[3] / "registry"
    if not registry_dir.exists():
        return
    from app.registry.parser import parse_registry_directory

    _staged_registry = parse_registry_directory(registry_dir)
