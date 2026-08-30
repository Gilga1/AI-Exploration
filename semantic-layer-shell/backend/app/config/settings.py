from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Semantic Layer Shell"
    debug: bool = False

    # Neo4j
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "password"

    # Snowflake
    snowflake_account: str = ""
    snowflake_user: str = ""
    snowflake_password: str = ""
    snowflake_warehouse: str = ""
    snowflake_database: str = ""
    snowflake_schema: str = ""

    # LLM (optional — pipeline degrades gracefully without)
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    # Embeddings
    embedding_dimensions: int = 1536

    # Auth
    default_user_role: str = "developer"

    # Registry staging
    registry_staging_dir: str = "/tmp/semantic-layer-staging"


@lru_cache
def get_settings() -> Settings:
    return Settings()
