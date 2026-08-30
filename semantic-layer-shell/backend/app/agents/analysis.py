from __future__ import annotations

from typing import Any


def analyze_rows(rows: list[dict[str, Any]], columns: list[str]) -> dict[str, Any]:
    if not rows or not columns:
        return {"row_count": 0, "columns": {}, "summary": "No data to analyze."}

    stats: dict[str, Any] = {"row_count": len(rows), "columns": {}}
    for col in columns:
        values = [row.get(col) for row in rows if row.get(col) is not None]
        numeric = [v for v in values if isinstance(v, (int, float))]
        col_stats: dict[str, Any] = {"non_null": len(values), "null_count": len(rows) - len(values)}
        if numeric:
            col_stats.update(
                {
                    "type": "numeric",
                    "min": min(numeric),
                    "max": max(numeric),
                    "mean": sum(numeric) / len(numeric),
                    "sum": sum(numeric),
                }
            )
        elif values:
            unique = list({str(v) for v in values})
            col_stats.update({"type": "categorical", "unique_count": len(unique), "top_values": unique[:5]})
        else:
            col_stats["type"] = "empty"
        stats["columns"][col] = col_stats

    return stats
