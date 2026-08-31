import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.agents.dimension_selection import infer_dimensions_from_intent
from app.config.settings import Settings
from app.graph.resolver import GraphResolver
from app.graph.neo4j_client import Neo4jClient
from app.llm.client import LLMClient
from tests.fixtures import PILOT_METRIC_ID


def test_registry_fallback_disabled_by_default():
    settings = Settings(allow_registry_fallback=False, debug=False)
    assert settings.allow_registry_fallback is False
    assert not (settings.allow_registry_fallback or settings.debug)


def test_reason_heuristic_raises_without_candidates():
    llm = LLMClient(resolver=None)
    with pytest.raises(ValueError, match="No metric candidates"):
        llm._reason_heuristic("sales?", [], {})


def test_infer_dimensions_from_intent_uses_allow_list_only():
    intent = {
        "raw_question": "net flow ratio by fund and share class",
        "search_terms": ["flow", "ratio"],
        "mentions": [],
    }
    dims = infer_dimensions_from_intent(intent, ["fund_id", "share_class", "transaction_date"])
    assert "fund_id" in dims
    assert "share_class" in dims
    assert "transaction_date" not in dims


def test_resolver_uses_registry_when_fallback_enabled():
    client = Neo4jClient("bolt://localhost:7687", "neo4j", "password")
    resolver = GraphResolver(client)
    subgraph = resolver.resolve_metric(PILOT_METRIC_ID)
    assert subgraph is not None
    assert subgraph.metric_id == PILOT_METRIC_ID
