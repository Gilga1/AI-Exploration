from __future__ import annotations

from dataclasses import dataclass

from harness.config.models import ConfigPlane
from harness.hitl.store import ApprovalStore
from harness.memory.manager import MemoryManager
from harness.orchestrator.orchestrator import Orchestrator
from harness.orchestrator.plan_store import PlanStore
from harness.agents.profile_loader import AgentProfileRegistry
from harness.orchestrator.workflow_registry import WorkflowRegistry
from harness.registry.data_sources import DataSourceRegistry
from harness.registry.registry import ToolRegistry
from harness.routing.capability_index import CapabilityIndex
from harness.routing.router import TieredRouter
from harness.settings import HarnessSettings
from harness.telemetry.bus import TelemetryBus


@dataclass
class BootstrapState:
    settings: HarnessSettings
    config: ConfigPlane
    tool_registry: ToolRegistry
    connector_registry: DataSourceRegistry
    capability_index: CapabilityIndex
    memory: MemoryManager
    telemetry: TelemetryBus
    router: TieredRouter
    orchestrator: Orchestrator
    approval_store: ApprovalStore
    plan_store: PlanStore
    workflow_registry: WorkflowRegistry
    profile_registry: AgentProfileRegistry
    imported_modules: list[str]
