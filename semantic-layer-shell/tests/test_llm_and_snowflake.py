import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.llm.client import LLMClient


def test_llm_decompose_heuristic_without_api_key():
    with patch("app.llm.client.get_settings") as mock_settings:
        mock_settings.return_value = MagicMock(openai_api_key="", openai_model="gpt-4o-mini", openai_base_url="")
        client = LLMClient()
        result = client.decompose("What is the net flow ratio by fund?")
        assert result["intent"] == "metric_query"
        assert result["llm"] is False
        assert len(result["search_terms"]) > 0


def test_llm_reason_constrained_to_candidates():
    with patch("app.llm.client.get_settings") as mock_settings:
        mock_settings.return_value = MagicMock(openai_api_key="", openai_model="gpt-4o-mini", openai_base_url="")
        client = LLMClient()
        candidates = [
            {"id": "net_flow_ratio", "kind": "metric", "name": "Net Flow Ratio"},
            {"id": "other_metric", "kind": "metric", "name": "Other"},
        ]
        result = client.reason("net flow", candidates)
        assert result["metric_id"] in {"net_flow_ratio", "other_metric"}


def test_snowflake_reports_missing_config():
    from app.warehouse.snowflake_client import SnowflakeClient

    with patch("app.warehouse.snowflake_client.get_settings") as mock_settings:
        mock_settings.return_value = MagicMock(
            snowflake_account="",
            snowflake_user="",
            snowflake_password="",
            snowflake_warehouse="",
            snowflake_database="",
            snowflake_schema="",
            snowflake_role="",
        )
        sf = SnowflakeClient()
        assert sf.is_configured is False
        assert sf.connect() is False
        assert "SNOWFLAKE_ACCOUNT" in (sf.last_error or "")
