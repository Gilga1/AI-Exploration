from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import Field
from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict


class HarnessSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="HARNESS_",
        env_nested_delimiter="__",
        extra="ignore",
    )

    app_name: str = "AI Agent Harness"
    config_root: str = "harness"
    settings_file: str = "harness.settings.yaml"
    scan_paths: list[str] = Field(
        default_factory=lambda: [
            "harness/tools",
            "harness/skills",
            "harness/agents",
            "harness/connectors",
        ]
    )
    strict_sandbox_validation: bool = True
    connector_health_check: bool = False
    connector_fail_fast: bool = False
    routing_top_k: int = 5
    routing_clear_margin: float = 0.15
    routing_min_score: float = 0.2
    routing_use_llm: bool = False
    telemetry_content_sample_rate: float = 0.0
    telemetry_enable_otel: bool = True
    telemetry_enable_ledger: bool = True
    telemetry_ledger_db_path: str = "data/harness_events.db"
    episodic_db_path: str = "data/harness_episodic.db"
    approvals_db_path: str = "data/harness_approvals.db"
    force_stub_models: bool = False
    langfuse_enabled: bool = True
    mcp_enabled: bool = True
    host: str = "0.0.0.0"
    port: int = 8000
    orchestration_mode: Literal["auto", "single", "multi"] = "auto"
    orchestration_require_plan_approval: bool = True
    orchestration_max_tasks: int = 5
    orchestration_synthesizer_agent: str = "synthesizer"
    orchestration_continue_on_failure: bool = True
    orchestration_fast_path_single_task: bool = True

    @classmethod
    def load(cls, path: str | Path | None = None) -> HarnessSettings:
        settings_path = Path(path or "harness.settings.yaml")
        if settings_path.exists():
            data = yaml.safe_load(settings_path.read_text()) or {}
            return cls(**data)
        return cls()

    @classmethod
    def from_yaml(cls, path: str | Path) -> HarnessSettings:
        return cls.load(path)
