from __future__ import annotations

from typing import Any

from app.graph.fallback import registry_fallback_allowed
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

    if registry_fallback_allowed():
        registry_dir = _registry_dir()
        if registry_dir.exists():
            staged = parse_registry_directory(registry_dir)
            for doc in staged.documents:
                if doc.kind == "metric" and doc.metadata.id == metric_id:
                    return list(doc.spec.dimensions)  # type: ignore[union-attr]
    return []


def infer_dimensions_from_intent(intent: dict[str, Any], allowed: list[str]) -> list[str]:
    """Infer breakdown dimensions from question text using the metric allow-list only."""
    if not allowed:
        return []

    haystack = " ".join(
        [
            str(intent.get("raw_question", "")),
            * [str(term) for term in intent.get("search_terms", [])],
            *[str(m.get("text", "")) for m in intent.get("mentions", [])],
        ]
    ).lower()

    inferred: list[str] = []
    for dim in allowed:
        variants = {dim.lower(), dim.replace("_", " ").lower()}
        if dim.endswith("_id"):
            variants.add(dim[:-3].lower())
        if any(variant and variant in haystack for variant in variants):
            inferred.append(dim)
    return inferred


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


def enrich_candidates_with_metric_fields(
    candidates: list[dict[str, Any]],
    resolver: GraphResolver | None = None,
) -> list[dict[str, Any]]:
    metric_dims: dict[str, list[str]] = {}
    metric_policies: dict[str, str | None] = {}

    if resolver is not None:
        for candidate in candidates:
            if candidate.get("kind") != "metric":
                continue
            metric_id = candidate.get("id", "")
            if metric_id:
                metric_dims[metric_id] = get_metric_dimensions(metric_id, resolver)

    if registry_fallback_allowed():
        registry_dir = _registry_dir()
        if registry_dir.exists():
            staged = parse_registry_directory(registry_dir)
            for doc in staged.documents:
                if doc.kind == "metric":
                    metric_dims.setdefault(doc.metadata.id, list(doc.spec.dimensions))  # type: ignore[union-attr]
                    metric_policies[doc.metadata.id] = doc.spec.validation_policy  # type: ignore[union-attr]

    enriched: list[dict[str, Any]] = []
    for candidate in candidates:
        item = dict(candidate)
        if candidate.get("kind") == "metric":
            dims = candidate.get("dimensions")
            if isinstance(dims, str):
                import json

                try:
                    dims = json.loads(dims)
                except json.JSONDecodeError:
                    dims = []
            if not dims:
                dims = metric_dims.get(candidate.get("id", ""), [])
            item["dimensions"] = dims
            policy = candidate.get("validation_policy")
            if not policy:
                item["validation_policy"] = metric_policies.get(candidate.get("id", ""))
        enriched.append(item)
    return enriched
