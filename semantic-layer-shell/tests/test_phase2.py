import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.agents.analysis import analyze_rows
from app.cache.query_cache import QueryResultCache
from app.sql_gen.assembler import SQLAssembler
from app.sql_gen.join_strategy import build_latest_snapshot_cte, prepend_snapshot_ctes
from app.graph.resolver import GraphResolver
from app.graph.neo4j_client import Neo4jClient
from app.registry.parser import parse_registry_directory

REGISTRY_DIR = Path(__file__).resolve().parents[1] / "registry"


def test_analyze_rows_numeric():
    rows = [{"fund_id": "A", "value": 10}, {"fund_id": "B", "value": 20}]
    stats = analyze_rows(rows, ["fund_id", "value"])
    assert stats["row_count"] == 2
    assert stats["columns"]["value"]["mean"] == 15


def test_query_cache_roundtrip():
    cache = QueryResultCache(db_path="/tmp/test-semantic-cache.db")
    key = QueryResultCache.make_key(
        graph_version_id="v1",
        node_ids=["m1", "m2"],
        edge_ids=["e1"],
        parameters={"basis": "net"},
        dimensions=["fund_id"],
        sql_hash="abc",
    )
    rows = [{"x": 1}]
    cache.set(key, rows, ["x"])
    hit = cache.get(key)
    assert hit is not None
    assert hit[0] == rows


def test_latest_snapshot_cte():
    cte = build_latest_snapshot_cte("dim_fund", "analytics.marts.dim_fund", ["fund_id"])
    assert "dim_fund_latest" in cte
    assert "QUALIFY ROW_NUMBER" in cte


def test_assembler_includes_snapshot_cte_for_latest_join():
    client = Neo4jClient("bolt://localhost:7687", "neo4j", "password")
    resolver = GraphResolver(client)
    subgraph = resolver.resolve_metric("net_flow_ratio")
    assert subgraph is not None
    assembler = SQLAssembler()
    sql = assembler.assemble(subgraph).sql
    assert "dim_fund_latest" in sql or "WITH" in sql
