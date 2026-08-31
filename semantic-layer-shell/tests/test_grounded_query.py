import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.agents.entity_resolution import EntityResolver, build_mentions_from_intent
from app.agents.insights import generate_structured_insights, build_result_package
from app.agents.time_resolution import resolve_time_range, time_predicate_for_measure
from app.agents.visualization import build_visualization_package
from app.cache.query_cache import QueryResultCache
from app.graph.entity_catalog import format_catalog_for_prompt, load_entity_catalog
from app.graph.neo4j_client import Neo4jClient
from app.graph.resolver import GraphResolver
from app.llm.client import LLMClient
from app.registry.parser import parse_registry_directory
from app.registry.validator import validate_staged_registry
from app.sql_gen.assembler import SQLAssembler
from app.sql_gen.filter_assembler import global_filters_for_data_source, inject_where_predicates
from app.sql_gen.lookup_assembler import build_entity_lookup_sql
from app.sql_gen.result_limit import append_result_limit

REGISTRY_DIR = Path(__file__).resolve().parents[1] / "registry"


@pytest.fixture
def staged_registry():
    return parse_registry_directory(REGISTRY_DIR)


def test_registry_includes_full_entity_catalog(staged_registry):
    ids = {d.metadata.id for d in staged_registry.documents}
    for entity_id in (
        "firm",
        "buying_unit",
        "vehicle",
        "asset_class",
        "product",
        "share_class",
        "morningstar_category",
    ):
        assert entity_id in ids
    assert "net_flow_ratio_validation" in ids


def test_validate_registry_with_entities_and_global_filters(staged_registry):
    result = validate_staged_registry(staged_registry)
    assert result.passed, [e.message for e in result.errors]


def test_global_filter_injected_into_measure_sql():
    client = Neo4jClient("bolt://localhost:7687", "neo4j", "password")
    resolver = GraphResolver(client)
    subgraph = resolver.resolve_metric("net_flow_ratio")
    assert subgraph is not None

    assembler = SQLAssembler()
    assembled = assembler.assemble(
        subgraph,
        parameters={"basis": "net"},
        entity_filters=[
            {
                "column": "fund_id",
                "operator": "=",
                "value": "FUND-1",
                "targets": {"fct_fund_transactions": "fund_id"},
            },
            {
                "column": "share_class",
                "operator": "=",
                "value": "A",
                "targets": {"fct_fund_transactions": "share_class"},
            },
        ],
        resolved_time={"start": "2026-08-17", "end": "2026-08-31"},
    )
    assert "is_test_account" in assembled.sql
    assert "fund_id" in assembled.sql
    assert "share_class" in assembled.sql
    assert "transaction_date BETWEEN" in assembled.sql


def test_entity_lookup_sql_uses_latest_snapshot(staged_registry):
    entity = next(d for d in staged_registry.documents if d.metadata.id == "product")
    ds = next(d for d in staged_registry.documents if d.metadata.id == "dim_fund")
    sql = build_entity_lookup_sql(
        {
            "id": entity.metadata.id,
            "resolves_via": entity.spec.resolves_via.model_dump(),
        },
        {
            "id": ds.metadata.id,
            "location": ds.spec.location,
            "type": ds.spec.type,
            "grain_keys": ds.spec.grain_keys,
            "global_filters": [gf.model_dump(exclude_none=True) for gf in ds.spec.global_filters],
        },
        "Franklin Income",
    )
    assert "WITH dim_fund_latest AS" in sql
    assert "fund_name" in sql
    assert "ILIKE" in sql


def test_time_resolution_last_two_weeks():
    resolved = resolve_time_range(
        {"text": "last 2 weeks", "type": "relative"},
        reference_date=__import__("datetime").date(2026, 8, 31),
    )
    assert resolved is not None
    assert resolved["start"] == "2026-08-17"
    assert resolved["end"] == "2026-08-31"


def test_time_predicate_for_measure():
    measure = {
        "time_filter": {"column": "transaction_date", "alias": "t"},
    }
    resolved = {
        "start": "2026-08-17",
        "end": "2026-08-31",
    }
    pred = time_predicate_for_measure(resolved, measure)
    assert pred == "t.transaction_date BETWEEN '2026-08-17' AND '2026-08-31'"


def test_build_mentions_from_bindings():
    intent = {
        "mentions": [
            {"text": "Franklin Income Fund", "entity_type": "product", "role": "filter"},
            {"text": "Class A", "entity_type": "share_class", "role": "filter"},
        ]
    }
    selection = {
        "mention_bindings": [
            {"mention_index": 0, "entity_type": "product", "apply_as": "filter"},
            {"mention_index": 1, "entity_type": "share_class", "apply_as": "filter"},
        ]
    }
    mentions = build_mentions_from_intent(intent, selection)
    assert len(mentions) == 2
    assert mentions[1]["entity_type"] == "share_class"


def test_disambiguation_resolution_short_circuit():
    resolver = EntityResolver()
    catalog = [
        {
            "id": "product",
            "resolves_via": {
                "data_source": "dim_fund",
                "label_column": "fund_name",
                "key_column": "fund_id",
                "match": "ilike",
                "limit": 10,
            },
            "filter_targets": [{"data_source": "fct_fund_transactions", "column": "fund_id"}],
        }
    ]
    sources = [
        {
            "id": "dim_fund",
            "location": "analytics.marts.dim_fund",
            "type": "dimension",
            "grain_keys": ["fund_id"],
            "schema_fields": [],
            "global_filters": [],
        }
    ]
    result = resolver.resolve(
        [{"text": "Franklin", "entity_type": "product"}],
        catalog,
        sources,
        disambiguation={
            "entity_type": "product",
            "selected_key": "FUND-123",
            "selected_label": "Franklin Income Fund",
        },
    )
    assert result.filters[0]["value"] == "FUND-123"
    assert result.resolutions[0]["resolution_method"] == "disambiguation"


def test_cache_key_includes_entity_filters_and_time():
    key_a = QueryResultCache.make_key(
        graph_version_id="v1",
        node_ids=["m1"],
        edge_ids=[],
        parameters={},
        dimensions=[],
        sql_hash="abc",
    )
    key_b = QueryResultCache.make_key(
        graph_version_id="v1",
        node_ids=["m1"],
        edge_ids=[],
        parameters={},
        dimensions=[],
        sql_hash="abc",
        entity_filters=[{"column": "fund_id", "value": "FUND-1"}],
        resolved_time={"start": "2026-08-17", "end": "2026-08-31"},
    )
    assert key_a != key_b


def test_append_result_limit():
    sql = "SELECT 1"
    limited = append_result_limit(sql, limit=1000)
    assert limited.endswith("LIMIT 1000")


def test_structured_insights_heuristic():
    package = build_result_package(
        question="sales?",
        metric_id="net_flow_ratio",
        rows=[{"metric_value": 10}],
        columns=["metric_value"],
        analysis={
            "row_count": 1,
            "columns": {"metric_value": {"type": "numeric", "sum": 10, "min": 10, "max": 10}},
        },
    )
    llm = LLMClient(resolver=None)
    payload = generate_structured_insights(llm, package)
    assert payload["headline"]
    assert payload["insights"]


def test_visualization_template_selection():
    package = {
        "rows": [
            {"transaction_date": "2026-08-17", "metric_value": 1},
            {"transaction_date": "2026-08-18", "metric_value": 2},
        ],
        "columns": ["transaction_date", "metric_value"],
    }
    viz = build_visualization_package(package, "net_flow_ratio")
    assert viz is not None
    assert viz["charts"][0]["template_id"] == "line_temporal"


def test_format_catalog_for_prompt():
    catalog = load_entity_catalog(Neo4jClient("bolt://localhost:7687", "neo4j", "password"))
    text = format_catalog_for_prompt(catalog)
    assert "id=firm" in text or "id=product" in text


def test_inject_where_predicates_appends_to_existing_where():
    fragment = "SELECT 1\nFROM t\nWHERE x = 1\nGROUP BY 1"
    result = inject_where_predicates(fragment, ["t.y = 2"])
    assert "AND t.y = 2" in result


def test_global_filters_for_data_source():
    ds = {
        "global_filters": [{"column": "is_test_account", "operator": "=", "value": False}],
    }
    preds = global_filters_for_data_source(ds, alias="t")
    assert preds == ["t.is_test_account = false"]
