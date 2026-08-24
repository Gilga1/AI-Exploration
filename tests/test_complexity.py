from __future__ import annotations

from harness.core.request import IncomingRequest
from harness.orchestrator.complexity import should_use_multi_agent
from harness.routing.capability_index import RetrievalCandidate
from harness.settings import HarnessSettings


def _settings(**kwargs) -> HarnessSettings:
    return HarnessSettings(**kwargs)


def test_single_mode_never_uses_multi_agent():
    candidates = [
        RetrievalCandidate(name="agent_a", kind="agent", score=0.9, description="A"),
        RetrievalCandidate(name="agent_b", kind="agent", score=0.85, description="B"),
    ]
    assert not should_use_multi_agent(
        "any message",
        _settings(orchestration_mode="single"),
        candidates=candidates,
    )


def test_multi_mode_always_uses_multi_agent():
    assert should_use_multi_agent(
        "any message",
        _settings(orchestration_mode="multi"),
        candidates=[],
    )


def test_auto_mode_uses_multi_agent_when_routing_is_ambiguous():
    candidates = [
        RetrievalCandidate(name="agent_a", kind="agent", score=0.42, description="A"),
        RetrievalCandidate(name="agent_b", kind="agent", score=0.40, description="B"),
    ]
    assert should_use_multi_agent(
        "do two different things",
        _settings(
            orchestration_mode="auto",
            routing_min_score=0.2,
            routing_clear_margin=0.15,
        ),
        candidates=candidates,
    )


def test_auto_mode_single_agent_when_top_match_is_clear():
    candidates = [
        RetrievalCandidate(name="agent_a", kind="agent", score=0.9, description="A"),
        RetrievalCandidate(name="agent_b", kind="agent", score=0.2, description="B"),
    ]
    assert not should_use_multi_agent(
        "focused request",
        _settings(
            orchestration_mode="auto",
            routing_min_score=0.2,
            routing_clear_margin=0.15,
        ),
        candidates=candidates,
    )


def test_request_override_forces_multi_mode():
    assert should_use_multi_agent(
        "message",
        _settings(orchestration_mode="auto"),
        request=IncomingRequest(message="message", orchestration={"mode": "multi"}),
        candidates=[],
    )


def test_synthesizer_excluded_from_ambiguity_check():
    candidates = [
        RetrievalCandidate(name="agent_a", kind="agent", score=0.42, description="A"),
        RetrievalCandidate(name="synthesizer", kind="agent", score=0.41, description="Synth"),
    ]
    assert not should_use_multi_agent(
        "message",
        _settings(
            orchestration_mode="auto",
            orchestration_synthesizer_agent="synthesizer",
            routing_min_score=0.2,
            routing_clear_margin=0.15,
        ),
        candidates=candidates,
    )
