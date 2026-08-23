from __future__ import annotations

import re
import uuid
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from harness.core.context import RunContext
from harness.core.models import ExecutionBudget, HandoffPacket
from harness.core.request import IncomingRequest, OrchestratorResult, ResumeRequest
from harness.hitl.store import ApprovalStore
from harness.memory.artifacts import ArtifactStore
from harness.memory.manager import MemoryManager
from harness.registry.registry import ToolRegistry
from harness.routing.decision import RoutingDecision
from harness.routing.router import TieredRouter
from harness.settings import HarnessSettings
from harness.telemetry.bus import TelemetryBus
from harness.telemetry.instrumentation import invoke_tool_with_telemetry


class OrchestratorState(TypedDict, total=False):
    request: IncomingRequest
    trace_id: str
    thread_id: str
    root_span_id: str
    routing: RoutingDecision
    skill_output: dict[str, Any]
    agent_output: dict[str, Any]
    artifacts: list[dict[str, Any]]
    message: str
    status: str
    error: str
    task_id: str
    interrupts: list[dict[str, Any]]


class Orchestrator:
    def __init__(
        self,
        registry: ToolRegistry,
        router: TieredRouter,
        memory: MemoryManager,
        telemetry: TelemetryBus,
        settings: HarnessSettings,
        approval_store: ApprovalStore | None = None,
    ) -> None:
        self.registry = registry
        self.router = router
        self.memory = memory
        self.telemetry = telemetry
        self.settings = settings
        self.approval_store = approval_store
        self.graph = self._compile_graph()

    def _compile_graph(self):
        graph: StateGraph = StateGraph(OrchestratorState)
        graph.add_node("route", self._route_node)
        graph.add_node("dispatch_skill", self._dispatch_skill_node)
        graph.add_node("spawn_agent", self._spawn_agent_node)
        graph.add_node("respond_directly", self._respond_directly_node)
        graph.add_node("synthesize", self._synthesize_node)

        graph.add_edge(START, "route")
        graph.add_conditional_edges(
            "route",
            self._route_branch,
            {
                "skill": "dispatch_skill",
                "agent": "spawn_agent",
                "direct": "respond_directly",
            },
        )
        graph.add_edge("dispatch_skill", "synthesize")
        graph.add_edge("spawn_agent", "synthesize")
        graph.add_edge("respond_directly", "synthesize")
        graph.add_edge("synthesize", END)
        return graph.compile(checkpointer=self.memory.working)

    async def handle(self, request: IncomingRequest) -> OrchestratorResult:
        trace_id = uuid.uuid4().hex
        thread_id = request.thread_id or trace_id
        config = {"configurable": {"thread_id": thread_id}}
        root_span_id = self.telemetry.new_span_id()

        with self.telemetry.span(
            "invoke_agent",
            trace_id=trace_id,
            span_id=root_span_id,
            otel_attributes={
                "gen_ai.operation.name": "invoke_agent",
                "harness.request_id": trace_id,
            },
        ):
            initial: OrchestratorState = {
                "request": request,
                "trace_id": trace_id,
                "thread_id": thread_id,
                "root_span_id": root_span_id,
            }
            final_state = await self.graph.ainvoke(initial, config=config)

        return OrchestratorResult(
            trace_id=trace_id,
            thread_id=thread_id,
            status=final_state.get("status", "success"),
            message=final_state.get("message", ""),
            route={
                "selected": final_state["routing"].selected,
                "kind": final_state["routing"].kind,
                "confidence": final_state["routing"].confidence,
                "rationale": final_state["routing"].rationale,
            }
            if final_state.get("routing")
            else {},
            output=final_state.get("skill_output") or final_state.get("agent_output"),
            artifacts=final_state.get("artifacts", []),
            events=self.telemetry.list_events_for_trace(trace_id),
            task_id=final_state.get("task_id"),
            interrupts=final_state.get("interrupts", []),
        )

    async def resume(self, request: ResumeRequest) -> OrchestratorResult:
        approval = self.approval_store.get(request.task_id) if self.approval_store else None
        if approval is None:
            return OrchestratorResult(
                trace_id=request.task_id,
                thread_id=request.thread_id,
                status="failure",
                message=f"No pending approval for task {request.task_id!r}",
            )

        agent = self.registry.agents.get(approval.agent_name)
        if agent is None:
            return OrchestratorResult(
                trace_id=approval.trace_id,
                thread_id=request.thread_id,
                status="failure",
                message=f"Agent {approval.agent_name!r} not found",
            )

        from harness.core.models import ExecutionBudget, HandoffPacket

        packet = HandoffPacket(
            task_id=request.task_id,
            parent_trace_id=approval.trace_id,
            objective="",
            context_summary="",
            budget=ExecutionBudget(max_steps=25, max_tokens=60_000, timeout_s=120),
            memory_namespace=("agent", approval.agent_name, "default", "default"),
        )

        with self.telemetry.span(
            "resume_agent",
            trace_id=approval.trace_id,
            otel_attributes={"harness.operation": "hitl_resume"},
        ):
            agent_result = await agent.run(packet, resume_decisions=request.decisions)

        if self.approval_store:
            self.approval_store.resolve(request.task_id)

        status = agent_result.status
        message = agent_result.trace_summary or "Resumed agent execution"
        if status == "awaiting_approval":
            message = "Agent still awaiting additional approvals"
        elif status == "success":
            message = _format_agent_message(approval.agent_name, agent_result.output)

        return OrchestratorResult(
            trace_id=approval.trace_id,
            thread_id=request.thread_id,
            status=status,
            message=message,
            output=agent_result.output,
            artifacts=[
                {"url": ref.url, "kind": ref.kind, "metadata": ref.metadata}
                for ref in agent_result.artifacts
            ],
            events=self.telemetry.list_events_for_trace(approval.trace_id),
            task_id=request.task_id,
            interrupts=agent_result.output.get("interrupts", []) if agent_result.output else [],
        )

    async def _route_node(self, state: OrchestratorState) -> OrchestratorState:
        request = state["request"]
        with self.telemetry.span(
            "harness.routing",
            trace_id=state["trace_id"],
            otel_attributes={"harness.operation": "routing"},
        ):
            routing = self.router.route(
                request.message,
                trace_id=state["trace_id"],
                parent_span_id=state.get("root_span_id"),
            )
        return {"routing": routing}

    def _route_branch(self, state: OrchestratorState) -> str:
        routing = state["routing"]
        if routing.kind == "skill":
            return "skill"
        if routing.kind == "agent":
            return "agent"
        return "direct"

    async def _dispatch_skill_node(self, state: OrchestratorState) -> OrchestratorState:
        request = state["request"]
        routing = state["routing"]
        skill = self.registry.skills.get(routing.selected)
        if skill is None:
            return {
                "status": "failure",
                "error": f"Skill {routing.selected!r} not found",
                "message": f"Could not dispatch skill {routing.selected!r}.",
            }

        payload_data = request.skill_input or _infer_skill_input(routing.selected, request.message)
        payload = skill.validate_input(payload_data)
        artifacts = ArtifactStore()
        context = RunContext(
            trace_id=state["trace_id"],
            tools=self.registry.tools,
            artifacts=artifacts,
            thread_id=state["thread_id"],
            metadata={
                "telemetry": self.telemetry,
                "parent_span_id": state.get("root_span_id"),
            },
        )
        with self.telemetry.span(
            f"skill:{routing.selected}",
            trace_id=state["trace_id"],
            otel_attributes={"harness.skill.name": routing.selected},
        ):
            result = await skill.execute(payload, context=context)
        output = result.model_dump() if hasattr(result, "model_dump") else dict(result)
        stored_artifacts = [
            {"url": ref["url"], "kind": ref["kind"], "metadata": ref.get("metadata", {})}
            for ref in artifacts._artifacts.values()
        ]
        return {
            "skill_output": output,
            "artifacts": stored_artifacts,
            "status": "success",
        }

    async def _spawn_agent_node(self, state: OrchestratorState) -> OrchestratorState:
        routing = state["routing"]
        request = state["request"]
        agent = self.registry.agents.get(routing.selected)
        if agent is None:
            return {
                "status": "failure",
                "error": f"Agent {routing.selected!r} not found",
                "message": f"Could not spawn agent {routing.selected!r}.",
            }

        task_id = uuid.uuid4().hex
        packet = HandoffPacket(
            task_id=task_id,
            parent_trace_id=state["trace_id"],
            objective=request.message,
            context_summary=request.message[:500],
            budget=ExecutionBudget(
                max_steps=agent.manifest.max_steps,
                max_tokens=agent.manifest.max_tokens_budget,
                timeout_s=agent.manifest.timeout_s,
            ),
            memory_namespace=("agent", routing.selected, "default", "default"),
        )

        with self.telemetry.span(
            f"invoke_agent:{routing.selected}",
            trace_id=state["trace_id"],
            otel_attributes={
                "gen_ai.operation.name": "invoke_agent",
                "gen_ai.agent.name": routing.selected,
            },
        ):
            agent_result = await agent.run(packet)

        if agent_result.status == "awaiting_approval":
            interrupts = (agent_result.output or {}).get("interrupts", [])
            return {
                "status": "awaiting_approval",
                "task_id": task_id,
                "interrupts": interrupts,
                "message": (
                    f"Agent {routing.selected!r} paused — human approval required. "
                    f"Resume via POST /v1/resume with task_id={task_id!r}."
                ),
                "agent_output": agent_result.output,
            }
        if agent_result.status == "budget_exceeded":
            return {
                "status": "budget_exceeded",
                "message": f"Agent {routing.selected!r} exceeded its execution budget.",
                "agent_output": agent_result.output,
            }
        if agent_result.status == "failure":
            return {
                "status": "failure",
                "message": agent_result.trace_summary or f"Agent {routing.selected!r} failed.",
                "agent_output": agent_result.output,
            }

        artifacts = [
            {"url": ref.url, "kind": ref.kind, "metadata": ref.metadata}
            for ref in agent_result.artifacts
        ]
        return {
            "status": "success",
            "agent_output": agent_result.output,
            "artifacts": artifacts,
            "message": _format_agent_message(routing.selected, agent_result.output),
        }

    async def _respond_directly_node(self, state: OrchestratorState) -> OrchestratorState:
        return {
            "status": "success",
            "message": "No matching skill found. Please rephrase or provide structured skill_input.",
        }

    async def _synthesize_node(self, state: OrchestratorState) -> OrchestratorState:
        if state.get("message"):
            return {}
        routing = state["routing"]
        output = state.get("skill_output") or {}
        if routing.kind == "skill" and "artifact_url" in output:
            return {
                "message": (
                    f"Completed {routing.selected} — your document is ready: {output['artifact_url']}"
                ),
            }
        if routing.kind == "skill":
            return {"message": f"Completed {routing.selected}."}
        return {"message": state.get("message", "Done.")}


def _infer_skill_input(skill_name: str, message: str) -> dict[str, Any]:
    if skill_name == "markdown_to_pdf":
        title_match = re.search(r"title[:\s]+(.+)", message, flags=re.IGNORECASE)
        markdown = message
        if "into a pdf" in message.lower():
            markdown = re.sub(r"(?i).*?(notes|markdown)[:\s]*", "", message, count=1)
            markdown = re.sub(r"(?i)\s*into a pdf.*", "", markdown).strip()
        payload: dict[str, Any] = {"markdown": markdown or message}
        if title_match:
            payload["title"] = title_match.group(1).strip()
        return payload
    return {"message": message}


def _format_agent_message(agent_name: str, output: dict[str, Any] | None) -> str:
    if not output:
        return f"Agent {agent_name} completed."
    if "positioning_summary" in output:
        return (
            f"Completed {agent_name} for {output.get('competitor', 'competitor')}: "
            f"{output['positioning_summary']}"
        )
    if "response" in output:
        return str(output["response"])
    return f"Agent {agent_name} completed with results."
