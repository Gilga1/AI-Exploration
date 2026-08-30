from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve .env from semantic-layer-shell/ root (parent of backend/)
_ENV_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Semantic Layer Shell"
    debug: bool = False

    # Neo4j
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "password"

    # Snowflake — set via environment
    snowflake_account: str = ""
    snowflake_user: str = ""
    snowflake_password: str = ""
    snowflake_warehouse: str = ""
    snowflake_database: str = ""
    snowflake_schema: str = ""
    snowflake_role: str = ""

    # LLM (OpenAI-compatible)
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_embedding_model: str = "text-embedding-3-small"
    openai_base_url: str = ""  # optional: Azure, local proxy, etc.

    # Embeddings
    embedding_dimensions: int = 1536

    # Auth
    default_user_role: str = "developer"

    # Registry
    registry_staging_dir: str = "/tmp/semantic-layer-staging"
    auto_publish_registry: bool = True
    audit_db_path: str = "/tmp/semantic-layer-audit/queries.db"


@lru_cache
def get_settings() -> Settings:
    return Settings()
