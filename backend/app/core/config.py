"""Application settings loaded from environment variables."""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Annotated

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


def _parse_csv_origins(value: str) -> list[str]:
    return [origin.strip() for origin in value.split(",") if origin.strip()]


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
    cors_allow_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:5173"],
        validation_alias=AliasChoices("CORS_ALLOW_ORIGINS", "APP_CORS_ALLOW_ORIGINS"),
    )
    otel_service_name: str = "agentic-rag-eval-backend"
    otel_exporter_otlp_endpoint: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "OTEL_EXPORTER_OTLP_ENDPOINT",
            "APP_OTEL_EXPORTER_OTLP_ENDPOINT",
        ),
    )
    otel_console_exporter: bool = False
    database_url: str = Field(
        ...,
        validation_alias=AliasChoices("DATABASE_URL", "APP_DATABASE_URL"),
    )
    rag_embedding_model: str | None = None
    rag_embedding_dimension: int = 256
    rag_retrieval_k: int = 3
    eval_sampling_rate: float = Field(default=1.0, ge=0.0, le=1.0)
    metrics_score_backstop: bool = Field(
        default=False,
        validation_alias=AliasChoices("METRICS_SCORE_BACKSTOP", "APP_METRICS_SCORE_BACKSTOP"),
    )
    metrics_per_trace_limit: int = Field(default=500, ge=1, le=5000)
    alert_webhook_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("ALERT_WEBHOOK_URL", "APP_ALERT_WEBHOOK_URL"),
    )
    alert_thresholds_json: str | None = Field(
        default=None,
        validation_alias=AliasChoices("ALERT_THRESHOLDS", "APP_ALERT_THRESHOLDS"),
    )
    alert_window_hours: int = Field(default=24, ge=1, le=168)
    alert_cooldown_minutes: int = Field(default=30, ge=1, le=1440)
    api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("API_KEY", "APP_API_KEY"),
    )
    auth_disabled: bool = Field(
        default=False,
        validation_alias=AliasChoices("AUTH_DISABLED", "APP_AUTH_DISABLED"),
    )
    llm_provider: str = "openrouter"
    llm_model: str = Field(
        ...,
        validation_alias=AliasChoices("LLM_MODEL", "APP_LLM_MODEL"),
    )
    llm_api_key: str = Field(
        ...,
        validation_alias=AliasChoices(
            "OPENROUTER_API_KEY",
            "LLM_API_KEY",
            "OPENAI_API_KEY",
            "APP_LLM_API_KEY",
            "APP_OPENAI_API_KEY",
        ),
    )
    llm_base_url: str = Field(
        ...,
        validation_alias=AliasChoices("LLM_BASE_URL", "APP_LLM_BASE_URL", "OPENAI_BASE_URL"),
    )
    agent_question_max_length: int = Field(default=4096, ge=1, le=32_768)
    agent_min_iterations: int = Field(default=2, ge=1, le=10)
    docs_enabled: bool = Field(default=True)
    open_api_url: str | None = Field(default="/openapi.json")

    @field_validator("cors_allow_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: object) -> list[str]:
        if value is None:
            return ["http://localhost:5173"]
        if isinstance(value, str):
            return _parse_csv_origins(value)
        if isinstance(value, (list, tuple)):
            return [str(item).strip() for item in value if str(item).strip()]
        raise ValueError("cors_allow_origins must be a comma-separated string or list")

    @property
    def has_llm_judge_credentials(self) -> bool:
        """Whether an LLM-backed generation or DeepEval judge can be used."""

        return bool(self.llm_api_key)

    @property
    def auth_required(self) -> bool:
        """Whether protected routes must receive a valid API key."""

        if self.auth_disabled:
            return False
        if self.api_key:
            return True
        return self.environment not in ("development", "dev", "local", "test")

    @property
    def expose_openapi(self) -> bool:
        return self.docs_enabled and self.environment in ("development", "dev", "local", "test")


@lru_cache
def get_settings() -> Settings:
    """Return one cached settings instance per process."""

    return Settings()


def validate_startup_settings(settings: Settings | None = None) -> None:
    """Fail fast when production-critical configuration is missing."""

    resolved = settings or get_settings()
    if not resolved.database_url:
        raise RuntimeError("DATABASE_URL (APP_DATABASE_URL) must be configured.")
    if resolved.auth_required and not resolved.api_key:
        raise RuntimeError(
            "APP_API_KEY must be set when auth is required "
            f"(environment={resolved.environment!r}). "
            "Set APP_AUTH_DISABLED=true only for explicit local/dev use."
        )
    if resolved.alert_webhook_url:
        from app.evaluation.alerting import validate_webhook_url

        validate_webhook_url(resolved.alert_webhook_url)
