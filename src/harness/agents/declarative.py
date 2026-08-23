from __future__ import annotations

import re
import time
from typing import Any

from deepagents import create_deep_agent
from langchain.agents.middleware.human_in_the_loop import InterruptOnConfig
from langchain_core.tools import StructuredTool
from langgraph.types import Command

from harness.config.models import ConfigPlane, ModelEndpointConfig
from harness.core.context import RunContext
from harness.core.models import AgentManifest, AgentResult, ExecutionBudget, HandoffPacket
from harness.core.protocols import BaseAgent
from harness.hitl.store import ApprovalStore
from harness.llm.factory import build_chat_model
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
        approval_store: ApprovalStore | None = None,
        force_stub_models: bool = False,
        checkpointer: object | None = None,
    ) -> None:
        self.manifest = manifest
        self._config = config
        self._registry = registry
        self._telemetry = telemetry
        self._approval_store = approval_store
        self._force_stub_models = force_stub_models
        self._checkpointer = checkpointer
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
        model = build_chat_model(model_cfg)
        checkpointer = self._checkpointer or (memory if hasattr(memory, "get") else None)
        interrupt_on = self._build_interrupt_on(tool_registry)

        self._compiled = create_deep_agent(
            model=model,
            tools=lc_tools,
            system_prompt=system_prompt,
            name=self.manifest.name,
            checkpointer=checkpointer,
            interrupt_on=interrupt_on or None,
        )
        return self._compiled

    async def run(
        self,
        packet: HandoffPacket,
        *,
        resume_decisions: list[dict[str, Any]] | None = None,
    ) -> AgentResult:
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
                result = await self._run_deep_agent(packet, resume_decisions=resume_decisions)
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
            thread_id=packet.task_id,
            tools={
                name: self._registry.tools[name]
                for name in self.manifest.allowed_tools
                if name in self._registry.tools
            },
            metadata={
                "telemetry": self._telemetry,
                "parent_span_id": self._telemetry.new_span_id() if self._telemetry else None,
            },
        )

        search_output: dict[str, Any] = {}
        if "web_search" in context.tools:
            steps += 1
            if steps > budget.max_steps:
                return AgentResult(
                    task_id=packet.task_id,
                    status="budget_exceeded",
                    trace_summary="Step budget exceeded",
                )
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

    async def _run_deep_agent(
        self,
        packet: HandoffPacket,
        *,
        resume_decisions: list[dict[str, Any]] | None = None,
    ) -> AgentResult:
        graph = self.compile(tool_registry=self._registry, memory=self._checkpointer)
        if graph is None:
            return AgentResult(
                task_id=packet.task_id,
                status="failure",
                trace_summary="Failed to compile agent graph",
            )

        config = {"configurable": {"thread_id": packet.task_id}}

        if resume_decisions is not None:
            input_value: Any = Command(resume={"decisions": resume_decisions})
        else:
            input_value = {"messages": [{"role": "user", "content": packet.objective}]}

        result = await graph.ainvoke(input_value, config=config)

        interrupts = result.get("__interrupt__") if isinstance(result, dict) else None
        if interrupts:
            payload = _serialize_interrupts(interrupts)
            if self._approval_store:
                from harness.hitl.store import PendingApproval

                self._approval_store.save(
                    PendingApproval(
                        thread_id=packet.task_id,
                        task_id=packet.task_id,
                        agent_name=self.manifest.name,
                        trace_id=packet.parent_trace_id,
                        interrupt_payload=payload,
                    )
                )
            return AgentResult(
                task_id=packet.task_id,
                status="awaiting_approval",
                output={"interrupts": payload},
                trace_summary=f"Agent {self.manifest.name} paused for human approval",
            )

        messages = result.get("messages", []) if isinstance(result, dict) else []
        last_content = ""
        if messages:
            last = messages[-1]
            last_content = getattr(last, "content", str(last))

        return AgentResult(
            task_id=packet.task_id,
            status="success",
            output={"response": last_content},
            trace_summary=f"Agent {self.manifest.name} completed",
        )

    def _resolve_model_config(self) -> ModelEndpointConfig:
        if self._force_stub_models:
            return ModelEndpointConfig(name="test_stub", provider="stub", model="fake")
        for model in self._config.models.models:
            if model.name == self.manifest.model_config_ref:
                return model
        return ModelEndpointConfig(name="fallback_stub", provider="stub", model="fake")

    def _build_system_prompt(self) -> str:
        parts = [self.manifest.system_prompt]
        for pack_name in self.manifest.context_packs:
            for pack in self._config.context_packs:
                if pack.name == pack_name:
                    for entry in pack.entries:
                        parts.append(f"- {entry.get('term', '')}: {entry.get('definition', '')}")
                    for rule in pack.rules:
                        parts.append(f"Rule: {rule}")
        return "\n".join(parts)

    def _build_interrupt_on(self, tool_registry: ToolRegistry) -> dict[str, InterruptOnConfig]:
        interrupt_tools = set(self.manifest.interrupt_tools)
        for tool_name in self.manifest.allowed_tools:
            tool = tool_registry.tools.get(tool_name)
            if tool and tool.spec.requires_approval:
                interrupt_tools.add(tool_name)

        return {
            name: InterruptOnConfig(
                allowed_decisions=["approve", "edit", "reject"],
                description=f"Approve tool call: {name}",
            )
            for name in interrupt_tools
        }

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


def _serialize_interrupts(interrupts: Any) -> list[dict[str, Any]]:
    serialized: list[dict[str, Any]] = []
    for item in interrupts:
        if hasattr(item, "value"):
            value = item.value
            serialized.append(value if isinstance(value, dict) else {"value": str(value)})
        elif isinstance(item, dict):
            serialized.append(item)
        else:
            serialized.append({"value": str(item)})
    return serialized


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
