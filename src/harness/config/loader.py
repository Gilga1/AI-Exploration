from __future__ import annotations

from pathlib import Path

import yaml

from harness.config.models import (
    ConfigPlane,
    ConnectorConfig,
    ContextPackConfig,
    MCPServerConfig,
    MCPServersConfig,
    ModelEndpointConfig,
    ModelsConfig,
)
from harness.config.secrets import resolve_tree


def load_config_plane(root: str | Path = "harness") -> ConfigPlane:
    root_path = Path(root)
    context_packs = _load_context_packs(root_path / "context")
    connectors = _load_connectors(root_path / "connectors")
    models = _load_models(root_path / "models" / "models.yaml")
    mcp = _load_mcp(root_path / "mcp" / "servers.yaml")
    return ConfigPlane(
        context_packs=context_packs,
        connectors=connectors,
        models=models,
        mcp=mcp,
    )


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text()) or {}
    return resolve_tree(data)


def _load_context_packs(context_dir: Path) -> list[ContextPackConfig]:
    packs: list[ContextPackConfig] = []
    if not context_dir.is_dir():
        return packs
    for yaml_file in sorted(context_dir.glob("*.yaml")):
        data = _load_yaml(yaml_file)
        if data:
            packs.append(ContextPackConfig(**data))
    return packs


def _load_connectors(connectors_dir: Path) -> list[ConnectorConfig]:
    configs: list[ConnectorConfig] = []
    if not connectors_dir.is_dir():
        return configs
    for connector_dir in sorted(connectors_dir.iterdir()):
        if not connector_dir.is_dir():
            continue
        connector_yaml = connector_dir / "connector.yaml"
        if not connector_yaml.exists():
            continue
        data = _load_yaml(connector_yaml)
        known = {field for field in ConnectorConfig.model_fields}
        extra = {k: v for k, v in data.items() if k not in known}
        schema_yaml = connector_dir / "schema.yaml"
        if schema_yaml.exists():
            extra["schema"] = _load_yaml(schema_yaml)
        payload = {k: v for k, v in data.items() if k in known}
        payload["extra"] = extra
        configs.append(ConnectorConfig(**payload))
    return configs


def _load_models(path: Path) -> ModelsConfig:
    data = _load_yaml(path)
    if not data:
        return ModelsConfig()
    models = [ModelEndpointConfig(**item) for item in data.get("models", [])]
    return ModelsConfig(models=models)


def _load_mcp(path: Path) -> MCPServersConfig:
    data = _load_yaml(path)
    if not data:
        return MCPServersConfig()
    servers = [MCPServerConfig(name=name, **cfg) for name, cfg in data.get("servers", {}).items()]
    return MCPServersConfig(servers=servers)
