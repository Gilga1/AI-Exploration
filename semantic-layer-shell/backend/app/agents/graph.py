"""LangGraph pipeline entry point — Phase 1 uses QueryPipeline directly.

This module is reserved for LangGraph state-machine wiring as the agent
orchestration matures beyond the heuristic Phase 1 implementation.
"""

from app.agents.nodes import QueryPipeline

__all__ = ["QueryPipeline"]
