from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from statistics import mean, pstdev
from typing import Any


def parse_date(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%m/%d/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(text[:19], fmt)
        except ValueError:
            continue
    return None


def flatten_collection(
    document: dict[str, Any],
    collection: str,
    *,
    date_field: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    filters: dict[str, Any] | None = None,
    parent_fields: list[str] | None = None,
) -> list[dict[str, Any]]:
    items = document.get(collection) or []
    if not isinstance(items, list):
        return []

    start = parse_date(date_from) if date_from else None
    end = parse_date(date_to) if date_to else None
    active_filters = filters or {}
    parent_fields = parent_fields or []

    rows: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        if date_field:
            item_date = parse_date(item.get(date_field))
            if start and item_date and item_date < start:
                continue
            if end and item_date and item_date > end:
                continue
        if any(str(item.get(k, "")).lower() != str(v).lower() for k, v in active_filters.items()):
            continue
        row = {field: document.get(field) for field in parent_fields}
        row.update(item)
        rows.append(row)
    return rows


def aggregate_records(
    records: list[dict[str, Any]],
    *,
    group_by: list[str],
    measures: dict[str, str],
    sort_by: str | None = None,
    sort_desc: bool = True,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    buckets: dict[tuple, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        key = tuple(record.get(field, "") for field in group_by)
        buckets[key].append(record)

    aggregated: list[dict[str, Any]] = []
    for key, bucket in buckets.items():
        row = {group_by[i]: key[i] for i in range(len(group_by))}
        for field, agg in measures.items():
            values = [_to_float(item.get(field)) for item in bucket if item.get(field) is not None]
            row[field] = _apply_agg(values, agg)
            row[f"{field}__{agg}"] = row[field]
        row["__count"] = len(bucket)
        aggregated.append(row)

    if sort_by:
        aggregated.sort(key=lambda r: _to_float(r.get(sort_by, 0)), reverse=sort_desc)
    if limit is not None:
        aggregated = aggregated[:limit]
    return aggregated


def compute_metrics(
    records: list[dict[str, Any]],
    metrics: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for metric in metrics:
        metric_type = metric.get("type", "ratio")
        name = metric.get("name", "metric")
        if metric_type == "ratio":
            numerator_field = metric["numerator_field"]
            denominator_field = metric["denominator_field"]
            numerator = sum(_to_float(r.get(numerator_field)) for r in records)
            denominator = sum(_to_float(r.get(denominator_field)) for r in records)
            value = numerator / denominator if denominator else 0.0
            results.append(
                {
                    "name": name,
                    "value": value,
                    "numerator": numerator,
                    "denominator": denominator,
                    "formula": metric.get("formula", f"{numerator_field}/{denominator_field}"),
                }
            )
        elif metric_type == "share_of_total":
            field = metric["field"]
            total = sum(_to_float(r.get(field)) for r in records)
            group_by = metric.get("group_by")
            if group_by:
                groups: dict[str, float] = defaultdict(float)
                for record in records:
                    groups[str(record.get(group_by, ""))] += _to_float(record.get(field))
                for group, amount in groups.items():
                    results.append(
                        {
                            "name": name,
                            "group": group,
                            "value": amount / total if total else 0.0,
                            "amount": amount,
                            "total": total,
                        }
                    )
            else:
                results.append({"name": name, "value": 1.0 if total else 0.0, "total": total})
    return results


def cohort_analysis(
    records: list[dict[str, Any]],
    *,
    cohort_field: str,
    measure_field: str,
    agg: str = "sum",
) -> list[dict[str, Any]]:
    return aggregate_records(
        records,
        group_by=[cohort_field],
        measures={measure_field: agg},
        sort_by=measure_field,
        sort_desc=True,
    )


def detect_anomalies(
    records: list[dict[str, Any]],
    *,
    value_field: str,
    z_threshold: float = 2.0,
) -> list[dict[str, Any]]:
    values = [_to_float(r.get(value_field)) for r in records]
    if len(values) < 3:
        return []
    avg = mean(values)
    std = pstdev(values) or 1.0
    anomalies: list[dict[str, Any]] = []
    for record, value in zip(records, values):
        z_score = (value - avg) / std
        if abs(z_score) >= z_threshold:
            anomalies.append({**record, "z_score": z_score, "value": value})
    return anomalies


def trend_forecast(
    records: list[dict[str, Any]],
    *,
    date_field: str,
    value_field: str,
    periods_ahead: int = 3,
) -> dict[str, Any]:
    points: list[tuple[float, float]] = []
    for index, record in enumerate(sorted(records, key=lambda r: str(r.get(date_field, "")))):
        points.append((float(index), _to_float(record.get(value_field))))
    if len(points) < 2:
        return {"history": records, "forecast": [], "slope": 0.0}

    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    x_mean = mean(xs)
    y_mean = mean(ys)
    numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys))
    denominator = sum((x - x_mean) ** 2 for x in xs) or 1.0
    slope = numerator / denominator
    intercept = y_mean - slope * x_mean

    forecast = []
    last_x = xs[-1]
    for step in range(1, periods_ahead + 1):
        x = last_x + step
        forecast.append({"period": step, "projected_value": intercept + slope * x})
    return {"history": records, "forecast": forecast, "slope": slope}


def _apply_agg(values: list[float], agg: str) -> float:
    if not values:
        return 0.0
    if agg == "sum":
        return sum(values)
    if agg == "avg":
        return mean(values)
    if agg == "count":
        return float(len(values))
    if agg == "min":
        return min(values)
    if agg == "max":
        return max(values)
    raise ValueError(f"Unsupported aggregation: {agg}")


def _to_float(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).replace(",", "").replace("$", "").strip()
    try:
        return float(text)
    except ValueError:
        return 0.0
