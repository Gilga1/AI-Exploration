from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ContextPackConfig(BaseModel):
    name: str
    description: str = ""
    scope: dict[str, list[str]] = Field(default_factory=dict)
    always_inject: bool = False
    entries: list[dict[str, str]] = Field(default_factory=list)
    rules: list[str] = Field(default_factory=list)


class ConnectorConfig(BaseModel):
    name: str
    kind: Literal["postgres", "snowflake", "redis", "vector_index"]
    host: str | None = None
    database: str | None = None
    user: str | None = None
    password: str | None = None
    pool_size: int = 5
    health_check_query: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class ModelEndpointConfig(BaseModel):
    name: str
    provider: str
    model: str
    max_tokens: int = 4096
    api_key: str | None = None
    endpoint: str | None = None


class ModelsConfig(BaseModel):
    models: list[ModelEndpointConfig] = Field(default_factory=list)


class MCPServerConfig(BaseModel):
    name: str
    transport: Literal["stdio", "http", "sse"] = "stdio"
    command: str | None = None
    args: list[str] = Field(default_factory=list)
    url: str | None = None
    headers: dict[str, str] = Field(default_factory=dict)
    enabled: bool = True


class MCPServersConfig(BaseModel):
    servers: list[MCPServerConfig] = Field(default_factory=list)


class ConfigPlane(BaseModel):
    context_packs: list[ContextPackConfig] = Field(default_factory=list)
    connectors: list[ConnectorConfig] = Field(default_factory=list)
    models: ModelsConfig = Field(default_factory=ModelsConfig)
    mcp: MCPServersConfig = Field(default_factory=MCPServersConfig)
