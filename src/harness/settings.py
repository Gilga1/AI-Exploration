from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class HarnessSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="HARNESS_",
        env_nested_delimiter="__",
        extra="ignore",
    )

    app_name: str = "AI Agent Harness"
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
    host: str = "0.0.0.0"
    port: int = 8000

    @classmethod
    def from_yaml(cls, path: str | Path) -> HarnessSettings:
        import yaml

        data = yaml.safe_load(Path(path).read_text()) or {}
        return cls(**data)
