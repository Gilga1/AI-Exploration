from __future__ import annotations

from harness.config.connectors import YamlBackedConnector
from harness.config.models import ConnectorConfig
from harness.connectors.azure_ai_search import AzureAISearchConnector
from harness.connectors.postgres import PostgresConnector
from harness.connectors.redis_connector import RedisConnector
from harness.connectors.snowflake import SnowflakeConnector


def build_connector(config: ConnectorConfig):
    provider = config.extra.get("provider", config.kind)

    if config.kind == "postgres" or provider == "azure_postgres":
        return PostgresConnector(config)
    if config.kind == "snowflake":
        return SnowflakeConnector(config)
    if config.kind == "redis":
        return RedisConnector(config)
    if config.kind in ("vector_index", "azure_ai_search") or provider == "azure_ai_search":
        return AzureAISearchConnector(config)

    return YamlBackedConnector(config)
