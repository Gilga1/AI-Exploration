from __future__ import annotations

from pathlib import Path

import yaml

from harness.agents.declarative import DeclarativeAgent
from harness.config.models import ConfigPlane
from harness.config.secrets import resolve_tree
from harness.core.models import AgentManifest
from harness.registry.registry import ToolRegistry


def load_yaml_agents(
    config_root: str | Path,
    config: ConfigPlane,
    registry: ToolRegistry,
    telemetry: object | None = None,
    approval_store: object | None = None,
    force_stub_models: bool = False,
    checkpointer: object | None = None,
    connectors: dict[str, object] | None = None,
) -> list[str]:
    """Load declarative agents from harness/agents/*.yaml."""
    agents_dir = Path(config_root) / "agents"
    loaded: list[str] = []
    if not agents_dir.is_dir():
        return loaded

    for yaml_file in sorted(agents_dir.glob("*.yaml")):
        data = resolve_tree(yaml.safe_load(yaml_file.read_text()) or {})
        manifest = AgentManifest(**data)
        agent = DeclarativeAgent(
            manifest=manifest,
            config=config,
            registry=registry,
            telemetry=telemetry,
            approval_store=approval_store,
            force_stub_models=force_stub_models,
            checkpointer=checkpointer,
            connectors=connectors or {},
        )
        registry.register_agent(agent)
        loaded.append(str(yaml_file))
    return loaded
