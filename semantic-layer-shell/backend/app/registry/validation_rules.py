from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any, Callable


RuleResult = dict[str, Any]
RuleEvaluator = Callable[[dict[str, Any], dict[str, Any]], RuleResult]


def evaluate_rule(rule: dict[str, Any], context: dict[str, Any]) -> RuleResult:
    rule_type = rule.get("type", "")
    evaluator = _EVALUATORS.get(rule_type)
    if not evaluator:
        return _result(rule, passed=True, message=f"unsupported rule type {rule_type!r} (skipped)")

    try:
        return evaluator(rule, context)
    except Exception as exc:
        return _result(rule, passed=False, message=f"rule evaluation error: {exc}")


def _result(rule: dict[str, Any], *, passed: bool, message: str) -> RuleResult:
    return {
        "rule_id": rule.get("id", ""),
        "type": rule.get("type", ""),
        "passed": passed,
        "severity": rule.get("severity", "medium"),
        "message": message or rule.get("message", ""),
        "on_fail": rule.get("on_fail"),
    }


def _eval_entity_resolution(rule: dict[str, Any], context: dict[str, Any]) -> RuleResult:
    expect = rule.get("expect", "exactly_one")
    resolutions = context.get("entity_resolutions", [])
    if expect == "optional":
        return _result(rule, passed=True, message="entity resolution optional")

    resolved = [r for r in resolutions if r.get("status") == "resolved"]
    failed = [r for r in resolutions if r.get("status") in {"not_found", "ambiguous", "error"}]

    if failed:
        return _result(
            rule,
            passed=False,
            message=rule.get("message") or f"{len(failed)} entity mention(s) not resolved",
        )
    if expect == "at_least_one" and not resolved:
        return _result(rule, passed=False, message=rule.get("message") or "no entities resolved")
    if expect == "exactly_one" and len(resolved) != 1 and resolutions:
        # Multiple distinct resolved entities is OK; rule applies per mention batch
        if not resolved:
            return _result(rule, passed=False, message=rule.get("message") or "no entities resolved")
    return _result(rule, passed=True, message="entity resolution passed")


def _eval_row_count(rule: dict[str, Any], context: dict[str, Any]) -> RuleResult:
    count = int(context.get("row_count", len(context.get("rows", []))))
    min_count = rule.get("min")
    max_count = rule.get("max")
    if min_count is not None and count < int(min_count):
        return _result(rule, passed=False, message=rule.get("message") or f"row_count {count} < {min_count}")
    if max_count is not None and count > int(max_count):
        return _result(rule, passed=False, message=rule.get("message") or f"row_count {count} > {max_count}")
    return _result(rule, passed=True, message=f"row_count {count} within bounds")


def _eval_column_range(rule: dict[str, Any], context: dict[str, Any]) -> RuleResult:
    column = rule.get("column") or (rule.get("params") or {}).get("column")
    params = rule.get("params") or {}
    min_val = rule.get("min", params.get("min"))
    max_val = rule.get("max", params.get("max"))
    rows = context.get("rows", [])
    if not column:
        return _result(rule, passed=True, message="no column specified")

    values = [_coerce_number(row.get(column)) for row in rows if row.get(column) is not None]
    if not values:
        return _result(rule, passed=True, message=f"no values for column {column!r}")

    for value in values:
        if min_val is not None and value < float(min_val):
            return _result(
                rule,
                passed=False,
                message=rule.get("message") or f"{column}={value} below min {min_val}",
            )
        if max_val is not None and value > float(max_val):
            return _result(
                rule,
                passed=False,
                message=rule.get("message") or f"{column}={value} above max {max_val}",
            )
    return _result(rule, passed=True, message=f"{column} within range")


def _eval_ratio_bounds(rule: dict[str, Any], context: dict[str, Any]) -> RuleResult:
    merged = {**rule, "type": "column_range", "column": (rule.get("params") or {}).get("column")}
    params = rule.get("params") or {}
    merged["min"] = params.get("min")
    merged["max"] = params.get("max")
    return _eval_column_range(merged, context)


def _eval_column_not_null(rule: dict[str, Any], context: dict[str, Any]) -> RuleResult:
    column = rule.get("column") or (rule.get("params") or {}).get("column")
    rows = context.get("rows", [])
    if not column:
        return _result(rule, passed=True, message="no column specified")
    nulls = sum(1 for row in rows if row.get(column) is None)
    if nulls:
        return _result(
            rule,
            passed=False,
            message=rule.get("message") or f"{nulls} null values in {column}",
        )
    return _result(rule, passed=True, message=f"{column} has no nulls")


def _eval_grain_check(rule: dict[str, Any], context: dict[str, Any]) -> RuleResult:
    required = (rule.get("params") or {}).get("required_dimensions") or []
    dimensions = context.get("dimensions") or []
    missing = sorted(set(required) - set(dimensions))
    if missing:
        return _result(
            rule,
            passed=False,
            message=rule.get("message") or f"missing dimensions: {missing}",
        )
    return _result(rule, passed=True, message="grain dimensions satisfied")


def _eval_denominator_nonzero(rule: dict[str, Any], context: dict[str, Any]) -> RuleResult:
    column = (rule.get("params") or {}).get("column") or rule.get("column")
    rows = context.get("rows", [])
    if not column:
        return _result(rule, passed=True, message="no denominator column specified")
    values = [_coerce_number(row.get(column)) for row in rows if row.get(column) is not None]
    if not values:
        return _result(rule, passed=False, message=rule.get("message") or f"no values for {column}")
    if all(v == 0 for v in values):
        return _result(rule, passed=False, message=rule.get("message") or f"denominator {column} is zero")
    return _result(rule, passed=True, message=f"denominator {column} non-zero")


def _eval_time_coverage(rule: dict[str, Any], context: dict[str, Any]) -> RuleResult:
    min_days = int(rule.get("min_days", (rule.get("params") or {}).get("min_days", 1)))
    time_key = rule.get("time_key") or (rule.get("params") or {}).get("time_key")
    resolved_time = context.get("resolved_time") or {}
    rows = context.get("rows", [])

    if not resolved_time.get("start") or not resolved_time.get("end"):
        return _result(rule, passed=True, message="no time filter to validate")

    if not rows:
        return _result(rule, passed=False, message=rule.get("message") or "no rows for time coverage")

    col = time_key
    if not col:
        for candidate in context.get("columns", []):
            if "date" in str(candidate).lower():
                col = candidate
                break
    if not col:
        return _result(rule, passed=True, message="no time column found")

    dates = [_parse_date(row.get(col)) for row in rows if row.get(col) is not None]
    dates = [d for d in dates if d]
    if not dates:
        return _result(rule, passed=False, message=rule.get("message") or "no parseable dates")

    coverage_days = (max(dates) - min(dates)).days + 1
    if coverage_days < min_days:
        return _result(
            rule,
            passed=False,
            message=rule.get("message") or f"time coverage {coverage_days}d < {min_days}d",
        )
    return _result(rule, passed=True, message=f"time coverage {coverage_days}d")


def _eval_expression(rule: dict[str, Any], context: dict[str, Any]) -> RuleResult:
    expression = rule.get("expression") or (rule.get("params") or {}).get("expression")
    if not expression:
        return _result(rule, passed=True, message="no expression")

    rows = context.get("rows", [])
    if not rows:
        context_values = {
            "row_count": context.get("row_count", 0),
            "filter_count": len(context.get("entity_filters", [])),
            "entity_resolution_status": _entity_resolution_status(context),
        }
        passed = _evaluate_expression(expression, context_values)
        return _result(rule, passed=passed, message=expression)

    for row in rows:
        values = {**row, "row_count": len(rows)}
        if not _evaluate_expression(expression, values):
            return _result(rule, passed=False, message=rule.get("message") or f"expression failed: {expression}")
    return _result(rule, passed=True, message="expression passed")


def _eval_llm_check(rule: dict[str, Any], context: dict[str, Any]) -> RuleResult:
    if rule.get("enabled") is False:
        return _result(rule, passed=True, message="llm_check disabled")
    return _result(rule, passed=True, message="llm_check not executed in v1")


_EVALUATORS: dict[str, RuleEvaluator] = {
    "entity_resolution": _eval_entity_resolution,
    "row_count": _eval_row_count,
    "column_range": _eval_column_range,
    "ratio_bounds": _eval_ratio_bounds,
    "column_not_null": _eval_column_not_null,
    "grain_check": _eval_grain_check,
    "denominator_nonzero": _eval_denominator_nonzero,
    "time_coverage": _eval_time_coverage,
    "expression": _eval_expression,
    "llm_check": _eval_llm_check,
}


def _coerce_number(value: Any) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    return float(str(value).replace(",", ""))


def _parse_date(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if not value:
        return None
    text = str(value)[:10]
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _entity_resolution_status(context: dict[str, Any]) -> str:
    resolutions = context.get("entity_resolutions", [])
    if any(r.get("status") in {"ambiguous", "not_found", "error"} for r in resolutions):
        return "failed"
    if resolutions:
        return "resolved"
    return "none"


def _evaluate_expression(expression: str, values: dict[str, Any]) -> bool:
    """Evaluate a small safe expression DSL over row/context values."""
    expr = expression.strip()
    for key, value in values.items():
        if isinstance(value, str):
            replacement = repr(value)
        elif value is None:
            replacement = "None"
        else:
            replacement = str(value)
        expr = re.sub(rf"\b{re.escape(key)}\b", replacement, expr)

    expr = expr.replace(" IS NULL", " is None").replace(" IS NOT NULL", " is not None")
    expr = expr.replace(" AND ", " and ").replace(" OR ", " or ").replace(" NOT ", " not ")
    allowed = set("0123456789.+-*/<>!=() abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_'\"")
    if any(ch not in allowed for ch in expr):
        return True
    try:
        return bool(eval(expr, {"__builtins__": {}}, {}))  # noqa: S307
    except Exception:
        return True
