from __future__ import annotations

import re
import time
import uuid
from typing import Any

from deepagents import create_deep_agent
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.tools import StructuredTool

from harness.config.models import ConfigPlane, ModelEndpointConfig
from harness.core.context import RunContext
from harness.core.models import AgentManifest, AgentResult, ArtifactRef, ExecutionBudget, HandoffPacket
from harness.core.protocols import BaseAgent
from harness.registry.registry import ToolRegistry
from harness.telemetry.bus import TelemetryBus
from harness.telemetry.events import AgentThoughtEvent, HandoffEvent, LLMCallEvent
from harness.telemetry.instrumentation import invoke_tool_with_telemetry


class DeclarativeAgent(BaseAgent):
    """YAML-driven agent compiled through deepagents."""

    def __init__(
        self,
        *,
        manifest: AgentManifest,
        config: ConfigPlane,
        registry: ToolRegistry,
        telemetry: TelemetryBus | None = None,
    ) -> None:
        self.manifest = manifest
        self._config = config
        self._registry = registry
        self._telemetry = telemetry
        self._compiled: object | None = None

    def compile(self, *, tool_registry: ToolRegistry, memory: object) -> object:
        if self._compiled is not None:
            return self._compiled

        model_cfg = self._resolve_model_config()
        if model_cfg.provider == "stub":
            self._compiled = None
            return self._compiled

        lc_tools = self._build_langchain_tools(tool_registry)
        system_prompt = self._build_system_prompt()
        model = self._build_chat_model(model_cfg)
        self._compiled = create_deep_agent(
            model=model,
            tools=lc_tools,
            system_prompt=system_prompt,
            name=self.manifest.name,
            checkpointer=memory if hasattr(memory, "get") else None,
        )
        return self._compiled

    async def run(self, packet: HandoffPacket) -> AgentResult:
        model_cfg = self._resolve_model_config()
        start = time.perf_counter()
        handoff_span = self._telemetry.new_span_id() if self._telemetry else None

        if self._telemetry:
            self._telemetry.emit(
                HandoffEvent(
                    trace_id=packet.parent_trace_id,
                    span_id=handoff_span or self._telemetry.new_span_id(),
                    child_task_id=packet.task_id,
                    agent_name=self.manifest.name,
                    budget=packet.budget,
                    status="started",
                )
            )

        try:
            if model_cfg.provider == "stub":
                result = await self._run_stub(packet)
            else:
                result = await self._run_deep_agent(packet, model_cfg)
        except Exception as exc:
            if self._telemetry and handoff_span:
                self._telemetry.emit(
                    HandoffEvent(
                        trace_id=packet.parent_trace_id,
                        span_id=handoff_span,
                        child_task_id=packet.task_id,
                        agent_name=self.manifest.name,
                        budget=packet.budget,
                        status="failure",
                        latency_ms=int((time.perf_counter() - start) * 1000),
                    )
                )
            return AgentResult(
                task_id=packet.task_id,
                status="failure",
                trace_summary=str(exc),
            )

        if self._telemetry and handoff_span:
            self._telemetry.emit(
                HandoffEvent(
                    trace_id=packet.parent_trace_id,
                    span_id=handoff_span,
                    child_task_id=packet.task_id,
                    agent_name=self.manifest.name,
                    budget=packet.budget,
                    status=result.status,
                    latency_ms=int((time.perf_counter() - start) * 1000),
                )
            )
        return result

    async def _run_stub(self, packet: HandoffPacket) -> AgentResult:
        """Deterministic agent path for tests and dry-run environments."""
        steps = 0
        budget = packet.budget

        if self._telemetry:
            self._telemetry.emit(
                AgentThoughtEvent(
                    trace_id=packet.parent_trace_id,
                    span_id=self._telemetry.new_span_id(),
                    agent_name=self.manifest.name,
                    thought=f"Starting research for: {packet.objective}",
                    capture_content=self._telemetry.should_capture_content(),
                )
            )

        competitor = _extract_competitor_name(packet.objective)
        context = RunContext(
            trace_id=packet.parent_trace_id,
            tools={name: self._registry.tools[name] for name in self.manifest.allowed_tools if name in self._registry.tools},
            metadata={
                "telemetry": self._telemetry,
                "parent_span_id": self._telemetry.new_span_id() if self._telemetry else None,
            },
        )

        search_output: dict[str, Any] = {}
        if "web_search" in context.tools:
            steps += 1
            if steps > budget.max_steps:
                return AgentResult(task_id=packet.task_id, status="budget_exceeded", trace_summary="Step budget exceeded")
            tool = context.tools["web_search"]
            args = tool.spec.input_schema(query=competitor)
            search_result = await invoke_tool_with_telemetry(
                "web_search", tool, args, context=context, rationale="Gather public competitor information"
            )
            search_output = search_result.model_dump() if hasattr(search_result, "model_dump") else {}

        if self._telemetry:
            self._telemetry.emit(
                LLMCallEvent(
                    trace_id=packet.parent_trace_id,
                    span_id=self._telemetry.new_span_id(),
                    model="stub",
                    input_tokens=len(packet.objective.split()),
                    output_tokens=50,
                    finish_reason="stop",
                    capture_content=False,
                )
            )

        brief = {
            "competitor": competitor,
            "positioning_summary": search_output.get("summary", f"Research brief for {competitor}"),
            "sources": search_output.get("sources", []),
        }
        return AgentResult(
            task_id=packet.task_id,
            status="success",
            output=brief,
            trace_summary=f"Completed competitor research for {competitor}",
        )

    async def _run_deep_agent(self, packet: HandoffPacket, model_cfg: ModelEndpointConfig) -> AgentResult:
        graph = self.compile(tool_registry=self._registry, memory=None)
        if graph is None:
            return AgentResult(
                task_id=packet.task_id,
                status="failure",
                trace_summary="Failed to compile agent graph",
            )

        config = {"configurable": {"thread_id": packet.task_id}}
        result = await graph.ainvoke(
            {"messages": [{"role": "user", "content": packet.objective}]},
            config=config,
        )
        messages = result.get("messages", [])
        last_content = messages[-1].content if messages else ""
        return AgentResult(
            task_id=packet.task_id,
            status="success",
            output={"response": last_content},
            trace_summary=f"Agent {self.manifest.name} completed",
        )

    def _resolve_model_config(self) -> ModelEndpointConfig:
        for model in self._config.models.models:
            if model.name == self.manifest.model_config_ref:
                return model
        return ModelEndpointConfig(
            name="fallback_stub",
            provider="stub",
            model="fake",
        )

    def _build_system_prompt(self) -> str:
        parts = [self.manifest.system_prompt]
        for pack_name in self.manifest.context_packs:
            for pack in self._config.context_packs:
                if pack.name == pack_name:
                    for entry in pack.entries:
                        parts.append(f"- {entry.get('term', '')}: {entry.get('definition', '')}")
        return "\n".join(parts)

    def _build_chat_model(self, model_cfg: ModelEndpointConfig):
        if model_cfg.provider == "stub":
            return FakeListChatModel(responses=["Research complete."])
        raise NotImplementedError(
            f"Provider {model_cfg.provider!r} requires API credentials; use provider=stub for tests"
        )

    def _build_langchain_tools(self, tool_registry: ToolRegistry) -> list[StructuredTool]:
        tools: list[StructuredTool] = []
        for tool_name in self.manifest.allowed_tools:
            harness_tool = tool_registry.tools.get(tool_name)
            if harness_tool is None:
                continue

            def _make_runner(name: str, ht: Any):
                async def _run(**kwargs: Any) -> dict[str, Any]:
                    ctx = RunContext(
                        trace_id="agent-internal",
                        tools=tool_registry.tools,
                        metadata={"telemetry": self._telemetry},
                    )
                    args = ht.spec.input_schema(**kwargs)
                    result = await invoke_tool_with_telemetry(name, ht, args, context=ctx)
                    return result.model_dump() if hasattr(result, "model_dump") else {"result": str(result)}

                return _run

            runner = _make_runner(tool_name, harness_tool)
            tools.append(
                StructuredTool.from_function(
                    coroutine=runner,
                    name=tool_name,
                    description=harness_tool.spec.description,
                )
            )
        return tools


def _extract_competitor_name(objective: str) -> str:
    patterns = [
        r"competitor[s]?\s+(?:named\s+)?['\"]?([A-Za-z0-9][A-Za-z0-9 ._-]*?)(?:\s+and\s+|\s+for\s+|[,.]|$)",
        r"research\s+(?:our\s+)?(?:top\s+)?competitor\s+['\"]?([A-Za-z0-9][A-Za-z0-9 ._-]*?)(?:\s+and\s+|[,.]|$)",
        r"research\s+['\"]?([A-Za-z0-9][A-Za-z0-9 ._-]*?)(?:\s+and\s+|\s+for\s+|[,.]|$)",
    ]
    for pattern in patterns:
        match = re.search(pattern, objective, re.I)
        if match:
            return match.group(1).strip().rstrip(".")
    return "Unknown Competitor"
