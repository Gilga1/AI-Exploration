from __future__ import annotations

import hashlib
from typing import Any

from app.sql_gen.filter_assembler import global_filters_for_data_source, predicate_to_sql
from app.sql_gen.join_strategy import build_latest_snapshot_cte, table_ref_for_data_source


def build_entity_lookup_sql(
    entity: dict[str, Any],
    data_source: dict[str, Any],
    mention_text: str,
    *,
    subtype: str | None = None,
    correlation_filters: dict[str, Any] | None = None,
    joins: list[dict[str, Any]] | None = None,
) -> str:
    resolves = entity.get("resolves_via") or {}
    label_column = resolves["label_column"]
    key_column = resolves["key_column"]
    match = resolves.get("match", "ilike")
    limit = int(resolves.get("limit", 10))
    ds_id = data_source["id"]
    alias = ds_id

    strategy = resolves.get("strategy") or _join_strategy_for_target(ds_id, joins or [])
    if strategy == "full_history" and data_source.get("type") == "dimension":
        strategy = "latest_snapshot"

    leading_ctes: list[str] = []
    if strategy == "latest_snapshot":
        filter_sql = global_filters_for_data_source(data_source, alias=None)
        leading_ctes.append(
            build_latest_snapshot_cte(
                ds_id,
                data_source.get("location", ds_id),
                data_source.get("grain_keys", []),
                global_filter_sql=filter_sql or None,
            )
        )
        table_ref = table_ref_for_data_source(data_source, strategy)
        filter_predicates = []
    else:
        table_ref = table_ref_for_data_source(data_source, strategy)
        filter_predicates = global_filters_for_data_source(data_source, alias=alias)

    predicates = list(filter_predicates)

    if subtype and label_column == key_column:
        predicates.append(
            predicate_to_sql(
                {"column": label_column, "operator": "exact", "value": subtype},
                alias=alias,
            )
        )
    else:
        predicates.append(
            _label_predicate(label_column, mention_text, match, alias=alias)
        )

    if correlation_filters:
        correlate_with = entity.get("correlate_with") or {}
        for entity_id, column in correlate_with.items():
            if entity_id in correlation_filters:
                predicates.append(
                    predicate_to_sql(
                        {
                            "column": column,
                            "operator": "=",
                            "value": correlation_filters[entity_id],
                        },
                        alias=alias,
                    )
                )

    where_clause = "\n  AND ".join(predicates)
    body = f"""SELECT DISTINCT
  {alias}.{key_column} AS resolved_key,
  {alias}.{label_column} AS resolved_label
FROM {table_ref} {alias}
WHERE {where_clause}
LIMIT {limit}"""

    if leading_ctes:
        return f"WITH {leading_ctes[0]}\n{body}"
    return body


def _join_strategy_for_target(target_id: str, joins: list[dict[str, Any]]) -> str:
    for join in joins:
        target = join.get("target") or join.get("target_id")
        if target == target_id:
            return join.get("strategy") or (join.get("props") or {}).get("strategy", "full_history")
    return "full_history"


def _label_predicate(
    label_column: str, mention_text: str, match: str, alias: str | None = None
) -> str:
    if match == "exact":
        return predicate_to_sql(
            {"column": label_column, "operator": "=", "value": mention_text},
            alias=alias,
        )
    if match == "prefix":
        return predicate_to_sql(
            {"column": label_column, "operator": "prefix", "value": mention_text},
            alias=alias,
        )
    return predicate_to_sql(
        {"column": label_column, "operator": "ilike", "value": mention_text},
        alias=alias,
    )


def lookup_sql_hash(sql: str) -> str:
    return hashlib.sha256(sql.encode("utf-8")).hexdigest()
