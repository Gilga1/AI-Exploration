from __future__ import annotations

from typing import Any

from app.sql_gen.filter_assembler import global_filters_for_data_source


def table_ref_for_data_source(data_source: dict[str, Any], strategy: str) -> str:
    ds_id = data_source["id"]
    if strategy == "latest_snapshot":
        return f"{ds_id}_latest"
    return data_source.get("location", ds_id)


def build_latest_snapshot_cte(
    target_id: str,
    location: str,
    grain_keys: list[str],
    effective_to_column: str = "effective_to",
    global_filter_sql: list[str] | None = None,
) -> str:
    """Wrap a dimension table to keep only the latest snapshot row per grain key."""
    partition = ", ".join(grain_keys) or "1"
    order_col = effective_to_column
    where_clause = ""
    if global_filter_sql:
        where_clause = "WHERE " + "\n    AND ".join(global_filter_sql)
    return f"""{target_id}_latest AS (
  SELECT *
  FROM {location}
  {where_clause}
  QUALIFY ROW_NUMBER() OVER (PARTITION BY {partition} ORDER BY {order_col} DESC NULLS LAST) = 1
)"""


def join_sql_for_strategy(
    join: dict[str, Any],
    source_alias: str,
    target_location: str,
    target_id: str,
    grain_keys: list[str] | None = None,
) -> str:
    strategy = join.get("strategy") or join.get("props", {}).get("strategy", "full_history")
    join_type = join.get("type") or join.get("props", {}).get("type", "left")
    on_clause = join.get("on") or join.get("props", {}).get("on", "1=1")

    if strategy == "latest_snapshot":
        cte_name = f"{target_id}_latest"
        return (
            f"{join_type.upper()} JOIN {cte_name} {target_id} ON {on_clause.replace(target_id + '.', target_id + '.')}"
        )

    return f"{join_type.upper()} JOIN {target_location} {target_id} ON {on_clause}"


def prepend_snapshot_ctes(joins: list[dict[str, Any]], data_sources: list[dict[str, Any]]) -> list[str]:
    """Build leading CTEs for latest_snapshot dimension joins referenced in subgraph."""
    ds_index = {ds["id"]: ds for ds in data_sources}
    ctes: list[str] = []
    seen: set[str] = set()

    for join in joins:
        target = join.get("target") or join.get("target_id")
        if not target or target in seen:
            continue
        strategy = join.get("strategy") or (join.get("props") or {}).get("strategy")
        if strategy != "latest_snapshot":
            continue
        ds = ds_index.get(target)
        if not ds:
            continue
        seen.add(target)
        strategy = join.get("strategy") or (join.get("props") or {}).get("strategy")
        filter_sql = global_filters_for_data_source(ds)
        ctes.append(
            build_latest_snapshot_cte(
                target,
                ds.get("location", target),
                ds.get("grain_keys", []),
                global_filter_sql=filter_sql or None,
            )
        )
    return ctes
