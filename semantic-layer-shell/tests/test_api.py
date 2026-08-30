import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.main import app

@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_health(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_sql_preview_net_flow_ratio(client):
    res = client.post(
        "/api/v1/sql/preview",
        json={"metric_id": "net_flow_ratio", "parameters": {}, "dimensions": []},
        headers={"X-User-Role": "developer"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["metric_id"] == "net_flow_ratio"
    assert "WITH" in body["sql"]
    assert body["sql_hash"]


def test_graph_dag_composition(client):
    res = client.get("/api/v1/graph/dag?subgraph=composition", headers={"X-User-Role": "viewer"})
    assert res.status_code == 200
    body = res.json()
    assert body["subgraph"] == "composition"
    assert len(body["nodes"]) >= 1


def test_registry_validate_bundled(client):
    res = client.post("/api/v1/registry/validate", headers={"X-User-Role": "developer"})
    assert res.status_code == 200
    assert res.json()["passed"] is True
