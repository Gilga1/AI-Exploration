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
    otel_service_name: str = "agentic-rag-eval-backend"
    otel_exporter_otlp_endpoint: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "OTEL_EXPORTER_OTLP_ENDPOINT",
            "APP_OTEL_EXPORTER_OTLP_ENDPOINT",
        ),
    )


@lru_cache
def get_settings() -> Settings:
    """Return one cached settings instance per process."""

    return Settings()
