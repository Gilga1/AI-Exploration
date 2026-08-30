from __future__ import annotations

import json
from typing import Any

from app.graph.resolver import GraphResolver
from app.registry.parser import parse_registry_directory
from pathlib import Path


def _registry_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "registry"


def get_metric_dimensions(metric_id: str, resolver: GraphResolver | None = None) -> list[str]:
    if resolver is not None:
        subgraph = resolver.resolve_metric(metric_id)
        if subgraph:
            metric = subgraph.metric
            spec = metric.get("spec", metric)
            dims = spec.get("dimensions", metric.get("dimensions", []))
            return list(dims)

    registry_dir = _registry_dir()
    if registry_dir.exists():
        staged = parse_registry_directory(registry_dir)
        for doc in staged.documents:
            if doc.kind == "metric" and doc.metadata.id == metric_id:
                return list(doc.spec.dimensions)  # type: ignore[union-attr]
    return []


def validate_and_filter_dimensions(
    selection: dict[str, Any],
    metric_id: str,
    resolver: GraphResolver | None = None,
) -> dict[str, Any]:
    allowed = set(get_metric_dimensions(metric_id, resolver))
    requested = selection.get("dimensions") or []
    if not allowed:
        selection["dimensions"] = []
        return selection

    valid = [dim for dim in requested if dim in allowed]
    invalid = sorted(set(requested) - allowed)
    if invalid:
        selection["dimension_warnings"] = [
            f"dropped dimensions not on metric allow-list: {invalid}; allowed: {sorted(allowed)}"
        ]
    selection["dimensions"] = valid
    return selection


def enrich_candidates_with_metric_fields(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    registry_dir = _registry_dir()
    metric_dims: dict[str, list[str]] = {}
    if registry_dir.exists():
        staged = parse_registry_directory(registry_dir)
        for doc in staged.documents:
            if doc.kind == "metric":
                metric_dims[doc.metadata.id] = list(doc.spec.dimensions)  # type: ignore[union-attr]

    enriched: list[dict[str, Any]] = []
    for candidate in candidates:
        item = dict(candidate)
        if candidate.get("kind") == "metric":
            dims = candidate.get("dimensions")
            if isinstance(dims, str):
                try:
                    dims = json.loads(dims)
                except json.JSONDecodeError:
                    dims = []
            if not dims:
                dims = metric_dims.get(candidate.get("id", ""), [])
            item["dimensions"] = dims
        enriched.append(item)
    return enriched
