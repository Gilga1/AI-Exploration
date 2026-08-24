"""Application settings loaded from environment variables."""

from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the FastAPI service."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="APP_",
        extra="ignore",
    )

    app_name: str = "Agentic RAG Evaluation Harness"
    environment: str = "development"
    cors_allow_origins: list[str] = ["http://localhost:5173"]
    otel_service_name: str = "agentic-rag-eval-backend"
    otel_exporter_otlp_endpoint: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "OTEL_EXPORTER_OTLP_ENDPOINT",
            "APP_OTEL_EXPORTER_OTLP_ENDPOINT",
        ),
    )
    rag_embedding_model: str | None = None
    rag_embedding_dimension: int = 256
    rag_retrieval_k: int = 3
    llm_model: str = "gpt-4o-mini"
    openai_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("OPENAI_API_KEY", "APP_OPENAI_API_KEY"),
    )

    @property
    def has_llm_judge_credentials(self) -> bool:
        """Whether an LLM-backed generation or DeepEval judge can be used."""

        return bool(self.openai_api_key)


@lru_cache
def get_settings() -> Settings:
    """Return one cached settings instance per process."""

    return Settings()
