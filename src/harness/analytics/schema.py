from __future__ import annotations

from typing import Any

from harness.core.protocols import BaseDataConnector


def connector_schema(connector: BaseDataConnector) -> dict[str, Any]:
    extra = getattr(getattr(connector, "_config", None), "extra", None) or {}
    return extra.get("schema") or {}


def document_key_field(schema: dict[str, Any], override: str | None = None) -> str:
    return override or schema.get("document_key_field") or "id"


def lookup_profile(schema: dict[str, Any]) -> dict[str, Any]:
    return schema.get("lookup") or {}


def collection_schema(schema: dict[str, Any], collection: str) -> dict[str, Any]:
    collections = schema.get("collections") or {}
    return collections.get(collection) or {}
