from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.graph.fallback import registry_fallback_allowed
from app.graph.neo4j_client import Neo4jClient
from app.registry.models import EntityDocument
from app.registry.parser import parse_registry_directory


def _entity_to_catalog_entry(doc: EntityDocument) -> dict[str, Any]:
    spec = doc.spec
    attributes = [
        {"id": attr.id, "description": attr.description, "values": attr.values}
        for attr in spec.attributes
    ]
    resolves_via = spec.resolves_via.model_dump() if spec.resolves_via else None
    return {
        "id": doc.metadata.id,
        "name": doc.metadata.name,
        "description": doc.metadata.description,
        "synonyms": doc.metadata.synonyms,
        "attributes": attributes,
        "resolves_via": resolves_via,
        "correlate_with": spec.correlate_with,
        "filter_targets": [ft.model_dump() for ft in spec.filter_targets],
    }


def load_entity_catalog(client: Neo4jClient | None = None) -> list[dict[str, Any]]:
    if client and client.is_connected:
        rows = client.run(
            """
            MATCH (e:Entity)
            RETURN e.id AS id, e.name AS name, e.description AS description,
                   e.synonyms AS synonyms, e.attributes AS attributes,
                   e.resolves_via AS resolves_via, e.correlate_with AS correlate_with,
                   e.filter_targets AS filter_targets
            ORDER BY e.id
            """
        )
        if rows:
            catalog: list[dict[str, Any]] = []
            for row in rows:
                entry = dict(row)
                for key in ("attributes", "resolves_via", "correlate_with", "filter_targets"):
                    val = entry.get(key)
                    if isinstance(val, str):
                        try:
                            entry[key] = json.loads(val)
                        except json.JSONDecodeError:
                            entry[key] = [] if key != "resolves_via" else None
                if entry.get("resolves_via") is None:
                    entry["resolves_via"] = None
                catalog.append(entry)
            return catalog

    if not registry_fallback_allowed():
        return []

    registry_dir = Path(__file__).resolve().parents[3] / "registry"
    if not registry_dir.exists():
        return []

    staged = parse_registry_directory(registry_dir)
    return [
        _entity_to_catalog_entry(doc)  # type: ignore[arg-type]
        for doc in staged.documents
        if doc.kind == "entity"
    ]


def load_data_sources_for_catalog(
    entity_catalog: list[dict[str, Any]], client: Neo4jClient | None = None
) -> list[dict[str, Any]]:
    needed: set[str] = set()
    for entity in entity_catalog:
        resolves = entity.get("resolves_via")
        if resolves and resolves.get("data_source"):
            needed.add(resolves["data_source"])

    if client and client.is_connected and needed:
        rows = client.run(
            """
            MATCH (d:DataSource)
            WHERE d.id IN $ids
            RETURN d
            """,
            {"ids": list(needed)},
        )
        if rows:
            sources: list[dict[str, Any]] = []
            for row in rows:
                ds = dict(row["d"])
                gf = ds.get("global_filters")
                if isinstance(gf, str):
                    try:
                        ds["global_filters"] = json.loads(gf)
                    except json.JSONDecodeError:
                        ds["global_filters"] = []
                sources.append(ds)
            return sources

    if not registry_fallback_allowed():
        return []

    registry_dir = Path(__file__).resolve().parents[3] / "registry"
    if not registry_dir.exists():
        return []

    from app.registry.models import DataSourceDocument
    from app.registry.parser import parse_registry_directory

    staged = parse_registry_directory(registry_dir)
    return [
        {
            "id": doc.metadata.id,
            "location": doc.spec.location,
            "type": doc.spec.type,
            "grain_keys": doc.spec.grain_keys,
            "schema_fields": [f.model_dump() for f in doc.spec.schema_fields],
            "global_filters": [gf.model_dump(exclude_none=True) for gf in doc.spec.global_filters],
        }
        for doc in staged.documents
        if isinstance(doc, DataSourceDocument) and doc.metadata.id in needed
    ]


def format_catalog_for_prompt(catalog: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for entity in catalog:
        attrs = entity.get("attributes") or []
        attr_text = ""
        if attrs:
            attr_bits = []
            for attr in attrs:
                values = attr.get("values") or []
                if values:
                    attr_bits.append(f"{attr['id']}: {values}")
            if attr_bits:
                attr_text = f" subtypes=[{'; '.join(attr_bits)}]"
        synonyms = entity.get("synonyms") or []
        syn_text = f" synonyms={synonyms}" if synonyms else ""
        lines.append(
            f"- id={entity['id']} name={entity.get('name')}{syn_text}{attr_text}"
        )
    return "\n".join(lines)
