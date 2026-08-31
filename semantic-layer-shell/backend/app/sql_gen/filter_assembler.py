from __future__ import annotations

import re
from typing import Any


def format_sql_literal(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    escaped = str(value).replace("'", "''")
    return f"'{escaped}'"


def predicate_to_sql(predicate: dict[str, Any], alias: str | None = None) -> str:
    if predicate.get("sql"):
        return str(predicate["sql"])

    column = predicate["column"]
    qualified = f"{alias}.{column}" if alias else column
    operator = predicate.get("operator", "=")

    if operator == "is_null":
        return f"{qualified} IS NULL"
    if operator == "is_not_null":
        return f"{qualified} IS NOT NULL"
    if operator == "in":
        values = predicate.get("values") or []
        literals = ", ".join(format_sql_literal(v) for v in values)
        return f"{qualified} IN ({literals})"
    if operator == "not_in":
        values = predicate.get("values") or []
        literals = ", ".join(format_sql_literal(v) for v in values)
        return f"{qualified} NOT IN ({literals})"

    value = predicate.get("value")
    if operator == "ilike":
        pattern = format_sql_literal(f"%{value}%")
        return f"{qualified} ILIKE {pattern}"
    if operator == "prefix":
        pattern = format_sql_literal(f"{value}%")
        return f"{qualified} ILIKE {pattern}"

    return f"{qualified} {operator} {format_sql_literal(value)}"


def global_filters_for_data_source(data_source: dict[str, Any], alias: str | None = None) -> list[str]:
    predicates: list[str] = []
    for raw in data_source.get("global_filters") or []:
        if isinstance(raw, str):
            import json

            try:
                raw = json.loads(raw)
            except json.JSONDecodeError:
                continue
        predicates.append(predicate_to_sql(raw, alias=alias))
    return predicates


def entity_filter_to_sql(
    column: str, operator: str, value: Any, alias: str | None = None
) -> str:
    return predicate_to_sql(
        {"column": column, "operator": operator, "value": value},
        alias=alias,
    )


def inject_where_predicates(fragment: str, predicates: list[str]) -> str:
    if not predicates:
        return fragment

    clause = "\n  AND ".join(predicates)
    if re.search(r"\bWHERE\b", fragment, flags=re.IGNORECASE):
        return re.sub(
            r"(\bWHERE\b.*?)(\n\s*(?:GROUP BY|ORDER BY|LIMIT)\b)",
            rf"\1\n  AND {clause}\2",
            fragment,
            count=1,
            flags=re.IGNORECASE | re.DOTALL,
        )

    return re.sub(
        r"\n(\s*)(GROUP BY|ORDER BY|LIMIT)\b",
        rf"\nWHERE {clause}\n\1\2",
        fragment,
        count=1,
        flags=re.IGNORECASE,
    )
