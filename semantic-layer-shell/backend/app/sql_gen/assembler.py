from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from app.graph.resolver import ResolvedSubgraph
from app.sql_gen.dimension_resolver import inject_dimensions_into_fragment, resolve_measure_dimensions
from app.sql_gen.join_strategy import prepend_snapshot_ctes

PARAM_PATTERN = re.compile(r"\{\{(\w+)\.(\w+)\}\}")


@dataclass
class AssembledSQL:
    sql: str
    sql_hash: str
    metric_id: str
    graph_version_id: str | None
    node_ids: list[str]
    edge_ids: list[str]
    provenance: dict


class SQLAssembler:
    """Pure Python SQL assembly — no LLM involvement."""

    def assemble(
        self,
        subgraph: ResolvedSubgraph,
        parameters: dict[str, str] | None = None,
        dimensions: list[str] | None = None,
    ) -> AssembledSQL:
        parameters = parameters or {}
        dimensions = dimensions or []
        metric = subgraph.metric
        metric_spec = metric.get("spec", metric)
        allowed_dimensions = metric_spec.get("dimensions", metric.get("dimensions", []))
        self._validate_dimensions(dimensions, allowed_dimensions, subgraph.metric_id)

        if subgraph.measures:
            sql = self._assemble_from_measures(subgraph, parameters, dimensions)
        else:
            sql = self._assemble_metric_formula(subgraph, parameters, dimensions)

        sql_hash = hashlib.sha256(sql.encode("utf-8")).hexdigest()
        return AssembledSQL(
            sql=sql,
            sql_hash=sql_hash,
            metric_id=subgraph.metric_id,
            graph_version_id=subgraph.graph_version_id,
            node_ids=subgraph.node_ids,
            edge_ids=subgraph.edge_ids,
            provenance={
                "metric_id": subgraph.metric_id,
                "parameters": parameters,
                "dimensions": dimensions,
            },
        )

    def _validate_dimensions(
        self, requested: list[str], allowed: list[str], metric_id: str
    ) -> None:
        if not requested:
            return
        invalid = sorted(set(requested) - set(allowed))
        if invalid:
            raise ValueError(
                f"dimensions {invalid} are not allowed for metric {metric_id!r}; "
                f"allowed: {sorted(allowed)}"
            )

    def _assemble_from_measures(
        self,
        subgraph: ResolvedSubgraph,
        parameters: dict[str, str],
        dimensions: list[str],
    ) -> str:
        snapshot_ctes = prepend_snapshot_ctes(subgraph.joins, subgraph.data_sources)
        ctes: list[str] = list(snapshot_ctes)
        for measure in subgraph.measures:
            role = measure.get("role", measure.get("id"))
            fragment = measure.get("sql_fragment", "")
            spec_params = measure.get("spec_parameters", {})
            component_params = measure.get("parameters", {})
            merged = {
                **{k: v.get("default") for k, v in spec_params.items() if isinstance(v, dict)},
                **component_params,
                **parameters,
            }
            resolved_fragment = self._substitute_parameters(fragment, spec_params, merged)
            if dimensions and measure.get("dimension_context"):
                resolved_dims = resolve_measure_dimensions(
                    measure, dimensions, subgraph.data_sources, subgraph.joins
                )
                resolved_fragment = inject_dimensions_into_fragment(resolved_fragment, resolved_dims)
            cte_name = f"{role}_measure"
            ctes.append(f"{cte_name} AS (\n{resolved_fragment.strip()}\n)")

        metric_spec = subgraph.metric.get("spec", subgraph.metric)
        formula = metric_spec.get("formula", "")
        time_key = metric_spec.get("time_key", subgraph.metric.get("time_key", ""))
        if formula and ctes:
            if dimensions:
                return self._build_dimensional_outer(ctes, subgraph.measures, formula, dimensions, time_key)
            select_expr = formula
            for measure in subgraph.measures:
                role = measure.get("role")
                if role:
                    select_expr = select_expr.replace(f"{role}.", f"{role}_measure.")
            return f"WITH {', '.join(ctes)}\nSELECT {select_expr} AS metric_value"

        if ctes:
            return f"WITH {', '.join(ctes)}\nSELECT * FROM {ctes[-1].split(' AS ')[0]}"

        return "-- unable to assemble SQL: no measures resolved"

    def _build_dimensional_outer(
        self,
        ctes: list[str],
        measures: list[dict],
        formula: str,
        dimensions: list[str],
        time_key: str,
    ) -> str:
        cte_names = [f"{m.get('role')}_measure" for m in measures if m.get("role")]
        if len(cte_names) < 1:
            return f"WITH {', '.join(ctes)}\nSELECT 1"

        aliases = ["n", "d", "c", "e"][: len(cte_names)]
        if len(cte_names) > len(aliases):
            aliases = [f"t{i}" for i in range(len(cte_names))]

        primary_alias = aliases[0]
        select_parts = [f"{primary_alias}.{dim}" for dim in dimensions]
        join_conditions: list[str] = []
        for dim in dimensions:
            for alias in aliases[1:]:
                join_conditions.append(f"{primary_alias}.{dim} = {alias}.{dim}")
        if time_key:
            select_parts.append(f"{primary_alias}.{time_key}")
            for alias in aliases[1:]:
                join_conditions.append(f"{primary_alias}.{time_key} = {alias}.{time_key}")

        select_expr = formula
        for measure, alias in zip(measures, aliases, strict=False):
            role = measure.get("role")
            if role:
                select_expr = select_expr.replace(f"{role}.", f"{alias}.")

        metric_select = f"{select_expr} AS metric_value"
        select_clause = ", ".join([*select_parts, metric_select])

        from_clause = f"FROM {cte_names[0]} {aliases[0]}"
        for cte_name, alias in zip(cte_names[1:], aliases[1:], strict=False):
            from_clause += f"\nJOIN {cte_name} {alias} ON {' AND '.join(join_conditions)}"

        return f"WITH {', '.join(ctes)}\nSELECT {select_clause}\n{from_clause}"

    def _assemble_metric_formula(
        self, subgraph: ResolvedSubgraph, parameters: dict[str, str], dimensions: list[str]
    ) -> str:
        del parameters, dimensions
        return f"-- metric {subgraph.metric_id}: resolve measures before assembly"

    def _substitute_parameters(
        self, fragment: str, spec_params: dict, selected: dict[str, str]
    ) -> str:
        def replacer(match: re.Match[str]) -> str:
            param_name, field_name = match.group(1), match.group(2)
            if field_name != "column":
                return match.group(0)
            option_key = selected.get(param_name)
            if not option_key:
                param_def = spec_params.get(param_name, {})
                option_key = param_def.get("default")
            options = spec_params.get(param_name, {}).get("options", {})
            option = options.get(option_key, {})
            column = option.get("column", option_key)
            return str(column)

        return PARAM_PATTERN.sub(replacer, fragment)

    def filter_exposed_columns(self, subgraph: ResolvedSubgraph) -> list[str]:
        exposed: list[str] = []
        for ds in subgraph.data_sources:
            for field in ds.get("schema_fields", []):
                if field.get("exposed", True) and not field.get("pii", False):
                    exposed.append(field["name"])
        return exposed
