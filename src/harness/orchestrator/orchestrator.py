from __future__ import annotations

import re
import uuid
from typing import Any, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from harness.core.context import RunContext
from harness.core.request import IncomingRequest, OrchestratorResult
from harness.memory.artifacts import ArtifactStore
from harness.memory.manager import MemoryManager
from harness.registry.registry import ToolRegistry
from harness.routing.router import RoutingDecision, TieredRouter
from harness.settings import HarnessSettings
from harness.telemetry.bus import TelemetryBus


class OrchestratorState(TypedDict, total=False):
    request: IncomingRequest
    trace_id: str
    thread_id: str
    routing: RoutingDecision
    skill_output: dict[str, Any]
    artifacts: list[dict[str, Any]]
    message: str
    status: str
    error: str


class Orchestrator:
    def __init__(
        self,
        registry: ToolRegistry,
        router: TieredRouter,
        memory: MemoryManager,
        telemetry: TelemetryBus,
        settings: HarnessSettings,
    ) -> None:
        self.registry = registry
        self.router = router
        self.memory = memory
        self.telemetry = telemetry
        self.settings = settings
        self.graph = self._compile_graph()

    def _compile_graph(self):
        graph: StateGraph = StateGraph(OrchestratorState)
        graph.add_node("route", self._route_node)
        graph.add_node("dispatch_skill", self._dispatch_skill_node)
        graph.add_node("respond_directly", self._respond_directly_node)
        graph.add_node("synthesize", self._synthesize_node)

        graph.add_edge(START, "route")
        graph.add_conditional_edges(
            "route",
            self._route_branch,
            {
                "skill": "dispatch_skill",
                "agent": "respond_directly",
                "direct": "respond_directly",
            },
        )
        graph.add_edge("dispatch_skill", "synthesize")
        graph.add_edge("respond_directly", "synthesize")
        graph.add_edge("synthesize", END)
        return graph.compile(checkpointer=self.memory.working)

    async def handle(self, request: IncomingRequest) -> OrchestratorResult:
        trace_id = uuid.uuid4().hex
        thread_id = request.thread_id or trace_id
        config = {"configurable": {"thread_id": thread_id}}
        initial: OrchestratorState = {
            "request": request,
            "trace_id": trace_id,
            "thread_id": thread_id,
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
            output=final_state.get("skill_output"),
            artifacts=final_state.get("artifacts", []),
            events=self.telemetry.list_events(),
        )

    async def _route_node(self, state: OrchestratorState) -> OrchestratorState:
        request = state["request"]
        routing = self.router.route(request.message, trace_id=state["trace_id"])
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
        )
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

    async def _respond_directly_node(self, state: OrchestratorState) -> OrchestratorState:
        routing = state["routing"]
        if routing.kind == "agent":
            return {
                "status": "needs_agent_spawn",
                "message": (
                    f"Request routed to agent {routing.selected!r}, but agent spawning "
                    "is not implemented until Phase 7."
                ),
            }
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
