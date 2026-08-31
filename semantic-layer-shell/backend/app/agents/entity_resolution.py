from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.sql_gen.lookup_assembler import build_entity_lookup_sql, lookup_sql_hash
from app.warehouse.snowflake_client import SnowflakeClient


@dataclass
class EntityResolutionResult:
    resolutions: list[dict[str, Any]] = field(default_factory=list)
    filters: list[dict[str, Any]] = field(default_factory=list)
    resolution_sql: list[str] = field(default_factory=list)
    resolution_sql_hashes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "resolutions": self.resolutions,
            "filters": self.filters,
            "resolution_sql": self.resolution_sql,
            "resolution_sql_hashes": self.resolution_sql_hashes,
        }


class EntityResolver:
    def __init__(self, warehouse: SnowflakeClient | None = None) -> None:
        self.warehouse = warehouse or SnowflakeClient()

    def resolve(
        self,
        mentions: list[dict[str, Any]],
        entity_catalog: list[dict[str, Any]],
        data_sources: list[dict[str, Any]],
        joins: list[dict[str, Any]] | None = None,
        disambiguation: dict[str, Any] | None = None,
    ) -> EntityResolutionResult:
        result = EntityResolutionResult()
        ds_index = {ds["id"]: ds for ds in data_sources}
        entity_index = {e["id"]: e for e in entity_catalog}
        correlation: dict[str, Any] = {}

        if disambiguation:
            entity_type = disambiguation.get("entity_type")
            selected_key = disambiguation.get("selected_key")
            entity = entity_index.get(entity_type or "")
            if entity and entity.get("resolves_via") and selected_key is not None:
                resolves = entity["resolves_via"]
                filter_entry = _build_filter_entry(entity, resolves, selected_key, selected_key)
                result.filters.append(filter_entry)
                correlation[entity_type] = selected_key
                result.resolutions.append(
                    {
                        "mention_text": disambiguation.get("selected_label") or str(selected_key),
                        "entity_type": entity_type,
                        "status": "resolved",
                        "key_column": resolves["key_column"],
                        "key_value": selected_key,
                        "label_value": disambiguation.get("selected_label") or str(selected_key),
                        "resolution_method": "disambiguation",
                    }
                )

        for mention in mentions:
            entity_type = mention.get("entity_type")
            if not entity_type or entity_type == "time":
                continue
            if disambiguation and entity_type == disambiguation.get("entity_type"):
                continue
            entity = entity_index.get(entity_type)
            if not entity or not entity.get("resolves_via"):
                continue

            resolves = entity["resolves_via"]
            ds = ds_index.get(resolves["data_source"])
            if not ds:
                result.resolutions.append(
                    {
                        "mention_text": mention.get("text"),
                        "entity_type": entity_type,
                        "status": "error",
                        "message": f"data source {resolves['data_source']!r} not found",
                    }
                )
                continue

            subtype = mention.get("subtype")
            text = mention.get("text", "")

            if subtype and self._is_direct_subtype(entity, subtype):
                filter_entry = _build_filter_entry(entity, resolves, subtype, subtype)
                result.filters.append(filter_entry)
                correlation[entity_type] = subtype
                result.resolutions.append(
                    {
                        "mention_text": text,
                        "entity_type": entity_type,
                        "status": "resolved",
                        "key_column": resolves["key_column"],
                        "key_value": subtype,
                        "label_value": subtype,
                        "resolution_method": "subtype",
                    }
                )
                continue

            lookup_sql = build_entity_lookup_sql(
                entity,
                ds,
                text,
                subtype=subtype,
                correlation_filters=correlation,
                joins=joins,
            )
            result.resolution_sql.append(lookup_sql)
            result.resolution_sql_hashes.append(lookup_sql_hash(lookup_sql))

            rows, _ = self._execute_lookup(lookup_sql)
            if len(rows) == 0:
                result.resolutions.append(
                    {
                        "mention_text": text,
                        "entity_type": entity_type,
                        "status": "not_found",
                        "lookup_sql_hash": lookup_sql_hash(lookup_sql),
                    }
                )
                continue
            if len(rows) > 1:
                result.resolutions.append(
                    {
                        "mention_text": text,
                        "entity_type": entity_type,
                        "status": "ambiguous",
                        "candidates": rows,
                        "lookup_sql_hash": lookup_sql_hash(lookup_sql),
                    }
                )
                continue

            row = rows[0]
            key_value = row.get("RESOLVED_KEY") or row.get("resolved_key")
            label_value = row.get("RESOLVED_LABEL") or row.get("resolved_label")
            filter_entry = _build_filter_entry(entity, resolves, key_value, label_value)
            result.filters.append(filter_entry)
            correlation[entity_type] = key_value
            result.resolutions.append(
                {
                    "mention_text": text,
                    "entity_type": entity_type,
                    "status": "resolved",
                    "key_column": resolves["key_column"],
                    "key_value": key_value,
                    "label_value": label_value,
                    "lookup_sql_hash": lookup_sql_hash(lookup_sql),
                }
            )

        return result

    def _execute_lookup(self, sql: str) -> tuple[list[dict[str, Any]], list[str]]:
        if not self.warehouse.is_configured:
            return [], []
        try:
            return self.warehouse.execute(sql)
        except RuntimeError:
            return [], []

    @staticmethod
    def _is_direct_subtype(entity: dict[str, Any], subtype: str) -> bool:
        for attr in entity.get("attributes") or []:
            values = attr.get("values") or []
            if subtype in values:
                return True
        return False


def _build_filter_entry(
    entity: dict[str, Any],
    resolves: dict[str, Any],
    key_value: Any,
    label_value: Any,
) -> dict[str, Any]:
    targets = {
        ft["data_source"]: ft["column"]
        for ft in (entity.get("filter_targets") or [])
        if ft.get("data_source") and ft.get("column")
    }
    return {
        "column": resolves["key_column"],
        "operator": "=",
        "value": key_value,
        "source_entity": entity.get("id"),
        "resolved_label": label_value,
        "targets": targets,
    }


def build_mentions_from_intent(
    intent: dict[str, Any],
    selection: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    mentions = intent.get("mentions") or []
    bindings = (selection or {}).get("mention_bindings") or []
    if bindings and mentions:
        bound: list[dict[str, Any]] = []
        for binding in bindings:
            if binding.get("apply_as", "filter") != "filter":
                continue
            idx = binding.get("mention_index", 0)
            if idx >= len(mentions):
                continue
            mention = dict(mentions[idx])
            mention["entity_type"] = binding.get("entity_type") or mention.get("entity_type")
            if mention.get("entity_type") == "time":
                continue
            bound.append(mention)
        if bound:
            return bound

    if mentions:
        return [m for m in mentions if m.get("entity_type") != "time"]

    legacy_entities = intent.get("entities") or []
    return [{"text": text, "entity_type": None, "role": "filter"} for text in legacy_entities]
