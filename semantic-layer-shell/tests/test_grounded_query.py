import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.agents.entity_resolution import build_mentions_from_intent
from app.agents.time_resolution import resolve_time_range, time_predicate_for_measure
from app.graph.entity_catalog import format_catalog_for_prompt, load_entity_catalog
from app.graph.neo4j_client import Neo4jClient
from app.graph.resolver import GraphResolver
from app.registry.parser import parse_registry_directory
from app.registry.validator import validate_staged_registry
from app.sql_gen.assembler import SQLAssembler
from app.sql_gen.filter_assembler import global_filters_for_data_source, inject_where_predicates
from app.sql_gen.lookup_assembler import build_entity_lookup_sql

REGISTRY_DIR = Path(__file__).resolve().parents[1] / "registry"


@pytest.fixture
def staged_registry():
    return parse_registry_directory(REGISTRY_DIR)


def test_registry_includes_grounded_query_assets(staged_registry):
    ids = {d.metadata.id for d in staged_registry.documents}
    assert "product" in ids
    assert "share_class" in ids
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
    assembled = assembler.assemble(subgraph, parameters={"basis": "net"})
    assert "is_test_account" in assembled.sql
    assert "is_test_account = false" in assembled.sql.lower()
    assert assembled.provenance.get("global_filters_applied")


def test_entity_lookup_sql_includes_global_filters(staged_registry):
    entity = next(d for d in staged_registry.documents if d.metadata.id == "fund")
    ds = next(d for d in staged_registry.documents if d.metadata.id == "dim_fund")
    sql = build_entity_lookup_sql(
        {
            "id": entity.metadata.id,
            "resolves_via": entity.spec.resolves_via.model_dump(),
        },
        {
            "id": ds.metadata.id,
            "location": ds.spec.location,
            "grain_keys": ds.spec.grain_keys,
            "global_filters": [gf.model_dump(exclude_none=True) for gf in ds.spec.global_filters],
        },
        "Franklin Income",
    )
    assert "FROM analytics.marts.dim_fund dim_fund" in sql
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


def test_build_mentions_from_intent():
    intent = {
        "mentions": [
            {"text": "Franklin Income Fund", "entity_type": "product", "role": "filter"},
            {"text": "last 2 weeks", "entity_type": "time", "role": "filter"},
        ]
    }
    mentions = build_mentions_from_intent(intent)
    assert len(mentions) == 2
    assert mentions[0]["entity_type"] == "product"


def test_format_catalog_for_prompt():
    catalog = load_entity_catalog(Neo4jClient("bolt://localhost:7687", "neo4j", "password"))
    text = format_catalog_for_prompt(catalog)
    assert "id=fund" in text or "id=product" in text


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
