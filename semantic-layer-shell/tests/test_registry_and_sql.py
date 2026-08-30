import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.registry.parser import parse_registry_directory
from app.registry.validator import validate_staged_registry
from app.graph.resolver import GraphResolver
from app.graph.neo4j_client import Neo4jClient
from app.sql_gen.assembler import SQLAssembler


REGISTRY_DIR = Path(__file__).resolve().parents[1] / "registry"


def test_parse_example_registry():
    staged = parse_registry_directory(REGISTRY_DIR)
    assert len(staged.documents) >= 6
    ids = {d.metadata.id for d in staged.documents}
    assert "net_flow_ratio" in ids
    assert "fct_fund_transactions" in ids


def test_validate_example_registry_passes():
    staged = parse_registry_directory(REGISTRY_DIR)
    result = validate_staged_registry(staged)
    assert result.passed, result.errors


def test_resolve_net_flow_ratio_from_registry():
    client = Neo4jClient("bolt://localhost:7687", "neo4j", "password")
    resolver = GraphResolver(client)
    subgraph = resolver.resolve_metric("net_flow_ratio")
    assert subgraph is not None
    assert subgraph.metric_id == "net_flow_ratio"
    assert len(subgraph.measures) == 2


def test_sql_assembler_produces_deterministic_sql():
    client = Neo4jClient("bolt://localhost:7687", "neo4j", "password")
    resolver = GraphResolver(client)
    subgraph = resolver.resolve_metric("net_flow_ratio")
    assert subgraph is not None

    assembler = SQLAssembler()
    assembled1 = assembler.assemble(subgraph, parameters={"basis": "net"})
    assembled2 = assembler.assemble(subgraph, parameters={"basis": "net"})

    assert assembled1.sql == assembled2.sql
    assert assembled1.sql_hash == assembled2.sql_hash
    assert "net_transaction_amount" in assembled1.sql
    assert "WITH" in assembled1.sql
