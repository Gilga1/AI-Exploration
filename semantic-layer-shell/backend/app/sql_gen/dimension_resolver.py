from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ResolvedDimension:
    name: str
    sql_expr: str
    joins: list[str] = field(default_factory=list)


def _ds_index(data_sources: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {ds["id"]: ds for ds in data_sources}


def _column_on_source(data_source: dict[str, Any], dimension: str) -> bool:
    for col in data_source.get("schema_fields", []):
        if col.get("name") == dimension:
            return True
    return False


def _find_join(source_id: str, target_id: str, joins: list[dict[str, Any]]) -> dict[str, Any] | None:
    for join in joins:
        src = join.get("source") or join.get("source_id")
        tgt = join.get("target") or join.get("target_id")
        if src == source_id and tgt == target_id:
            return join
    return None


def _qualify_join_on(on: str, source_alias: str, target_alias: str) -> str:
    clauses: list[str] = []
    for part in on.split(","):
        if "=" not in part:
            continue
        left, right = part.split("=", 1)
        left_key = left.strip().split(".")[-1]
        right_key = right.strip().split(".")[-1]
        clauses.append(f"{source_alias}.{left_key} = {target_alias}.{right_key}")
    return " AND ".join(clauses) if clauses else "1=1"


def _table_ref(data_source: dict[str, Any], strategy: str) -> str:
    ds_id = data_source["id"]
    if strategy == "latest_snapshot":
        return f"{ds_id}_latest"
    return data_source.get("location", ds_id)


def _find_dimension_source(
    primary_id: str,
    dimension: str,
    data_sources: list[dict[str, Any]],
    joins: list[dict[str, Any]],
) -> tuple[str, dict[str, Any] | None]:
    """Return (source_id, join_edge) where join_edge is None if dimension is on primary."""
    ds_by_id = _ds_index(data_sources)
    primary = ds_by_id.get(primary_id)
    if primary and _column_on_source(primary, dimension):
        return primary_id, None

    visited = {primary_id}
    queue = [primary_id]
    while queue:
        current = queue.pop(0)
        for join in joins:
            src = join.get("source") or join.get("source_id")
            tgt = join.get("target") or join.get("target_id")
            if src != current:
                continue
            if tgt in visited:
                continue
            target_ds = ds_by_id.get(tgt)
            if target_ds and _column_on_source(target_ds, dimension):
                return tgt, join
            visited.add(tgt)
            queue.append(tgt)
    raise ValueError(
        f"dimension {dimension!r} is not reachable from data source {primary_id!r} via declared joins"
    )


def resolve_measure_dimensions(
    measure: dict[str, Any],
    dimensions: list[str],
    data_sources: list[dict[str, Any]],
    joins: list[dict[str, Any]],
) -> list[ResolvedDimension]:
    """Resolve dimension names to SQL expressions and join clauses for one measure fragment."""
    dimension_context = measure.get("dimension_context") or {}
    if isinstance(dimension_context, str):
        import json

        try:
            dimension_context = json.loads(dimension_context)
        except json.JSONDecodeError:
            dimension_context = {}

    if not dimension_context or not dimensions:
        return []

    alias = dimension_context.get("alias")
    if not alias:
        raise ValueError(f"measure {measure.get('id')!r} is missing dimension_context.alias")

    depends_on = measure.get("depends_on_refs") or []
    if not depends_on:
        for dep in measure.get("depends_on", []):
            if isinstance(dep, dict):
                depends_on.append(dep.get("ref", ""))
    primary_id = depends_on[0] if depends_on else None
    if not primary_id:
        raise ValueError(f"measure {measure.get('id')!r} has no depends_on data source")

    ds_by_id = _ds_index(data_sources)
    resolved: list[ResolvedDimension] = []
    seen_joins: set[str] = set()

    for dimension in dimensions:
        source_id, join_edge = _find_dimension_source(primary_id, dimension, data_sources, joins)
        if source_id == primary_id:
            resolved.append(ResolvedDimension(name=dimension, sql_expr=f"{alias}.{dimension}"))
            continue

        target_ds = ds_by_id.get(source_id)
        if not target_ds:
            raise ValueError(f"data source {source_id!r} not found for dimension {dimension!r}")

        join_props = join_edge or {}
        strategy = join_props.get("strategy") or (join_props.get("props") or {}).get("strategy", "full_history")
        join_type = join_props.get("type") or (join_props.get("props") or {}).get("type", "left")
        on_clause = join_props.get("on") or (join_props.get("props") or {}).get("on", "1=1")
        target_alias = source_id
        table_ref = _table_ref(target_ds, strategy)
        qualified_on = _qualify_join_on(on_clause, alias, target_alias)
        join_sql = f"{join_type.upper()} JOIN {table_ref} {target_alias} ON {qualified_on}"
        if join_sql not in seen_joins:
            seen_joins.add(join_sql)
            resolved.append(
                ResolvedDimension(name=dimension, sql_expr=f"{target_alias}.{dimension}", joins=[join_sql])
            )
        else:
            resolved.append(ResolvedDimension(name=dimension, sql_expr=f"{target_alias}.{dimension}"))

    return resolved


def inject_dimensions_into_fragment(fragment: str, resolved: list[ResolvedDimension]) -> str:
    if not resolved:
        return fragment

    select_exprs = [dim.sql_expr for dim in resolved]
    join_clauses: list[str] = []
    seen: set[str] = set()
    for dim in resolved:
        for join in dim.joins:
            if join not in seen:
                seen.add(join)
                join_clauses.append(join)

    updated = fragment
    if select_exprs:
        cols = ",\n      ".join(select_exprs)
        import re

        updated = re.sub(
            r"(SELECT\s+)",
            rf"\1{cols},\n      ",
            updated,
            count=1,
            flags=re.IGNORECASE,
        )

    if join_clauses:
        import re

        join_block = "\n    ".join(join_clauses)
        with_where = re.sub(
            r"\n(\s*)(WHERE|GROUP BY)",
            rf"\n    {join_block}\n\1\2",
            updated,
            count=1,
            flags=re.IGNORECASE,
        )
        if with_where != updated:
            updated = with_where
        else:
            updated = re.sub(
                r"(\n\s*GROUP BY)",
                rf"\n    {join_block}\1",
                updated,
                count=1,
                flags=re.IGNORECASE,
            )

    return updated
