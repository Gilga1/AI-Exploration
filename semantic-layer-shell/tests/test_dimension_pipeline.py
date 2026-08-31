import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.agents.dimension_selection import validate_and_filter_dimensions
from app.graph.neo4j_client import Neo4jClient
from app.graph.resolver import GraphResolver
from app.llm.client import LLMClient
from app.registry.parser import parse_registry_directory
from app.registry.validator import validate_staged_registry
from app.sql_gen.assembler import SQLAssembler
from app.sql_gen.dimension_resolver import inject_dimensions_into_fragment, resolve_measure_dimensions

REGISTRY_DIR = Path(__file__).resolve().parents[1] / "registry"


@pytest.fixture
def subgraph():
    client = Neo4jClient("bolt://localhost:7687", "neo4j", "password")
    resolver = GraphResolver(client)
    sg = resolver.resolve_metric("net_flow_ratio")
    assert sg is not None
    return sg


def test_registry_still_validates_with_dimension_rules():
    staged = parse_registry_directory(REGISTRY_DIR)
    result = validate_staged_registry(staged)
    assert result.passed, result.errors


def test_dimension_allow_list_filters_invalid_selection():
    selection = {
        "metric_id": "net_flow_ratio",
        "dimensions": ["fund_id", "not_a_real_dimension"],
    }
    filtered = validate_and_filter_dimensions(selection, "net_flow_ratio")
    assert filtered["dimensions"] == ["fund_id"]
    assert filtered["dimension_warnings"]


def test_assembler_injects_fund_id_when_requested(subgraph):
    assembler = SQLAssembler()
    without = assembler.assemble(subgraph, parameters={"basis": "net"}, dimensions=[])
    with_fund = assembler.assemble(subgraph, parameters={"basis": "net"}, dimensions=["fund_id"])

    assert "fund_id" not in without.sql or "t.fund_id" not in without.sql
    assert "t.fund_id" in with_fund.sql
    assert with_fund.sql != without.sql


def test_assembler_injects_share_class_on_fact_column(subgraph):
    assembler = SQLAssembler()
    assembled = assembler.assemble(subgraph, parameters={"basis": "net"}, dimensions=["share_class"])
    assert "t.share_class" in assembled.sql


def test_assembler_rejects_disallowed_dimension(subgraph):
    assembler = SQLAssembler()
    with pytest.raises(ValueError, match="not allowed"):
        assembler.assemble(subgraph, dimensions=["transaction_id"])


def test_measure_without_dimension_context_skips_injection(subgraph):
    measure = dict(subgraph.measures[0])
    measure["dimension_context"] = {}
    dims = resolve_measure_dimensions(measure, ["fund_id"], subgraph.data_sources, subgraph.joins)
    assert dims == []


def test_inject_dimensions_into_fragment_before_group_by():
    fragment = """SELECT
      transaction_date,
      SUM(amount) AS total_amount
    FROM analytics.marts.fct_fund_transactions t
    GROUP BY ALL"""
    from app.sql_gen.dimension_resolver import ResolvedDimension

    updated = inject_dimensions_into_fragment(
        fragment,
        [
            ResolvedDimension(
                name="share_class",
                sql_expr="dim_fund.share_class",
                joins=["LEFT JOIN dim_fund_latest dim_fund ON t.fund_id = dim_fund.fund_id"],
            )
        ],
    )
    assert "dim_fund.share_class" in updated
    assert "LEFT JOIN dim_fund_latest dim_fund" in updated


def test_reason_heuristic_infers_fund_dimension_from_question():
    client = Neo4jClient("bolt://localhost:7687", "neo4j", "password")
    llm = LLMClient(GraphResolver(client))
    selection = llm.reason(
        "What is net flow ratio by fund?",
        [{"id": "net_flow_ratio", "kind": "metric", "name": "Net Flow Ratio", "score": 0.9}],
    )
    assert selection["metric_id"] == "net_flow_ratio"
    assert "fund_id" in selection["dimensions"]


def test_low_confidence_heuristic_sets_needs_confirmation_flag():
    client = Neo4jClient("bolt://localhost:7687", "neo4j", "password")
    llm = LLMClient(GraphResolver(client))
    selection = llm.reason(
        "ambiguous question",
        [
            {"id": "net_flow_ratio", "kind": "metric", "name": "A", "score": 0.51},
            {"id": "other_metric", "kind": "metric", "name": "B", "score": 0.5},
        ],
    )
    assert selection["confidence"] < 0.7
