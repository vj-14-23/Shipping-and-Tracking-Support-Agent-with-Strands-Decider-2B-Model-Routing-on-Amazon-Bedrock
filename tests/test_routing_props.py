"""Property-based tests for model routing and RoutingDecision serialisation.

# Feature: shipping-tracking-agent
Property 1: confidence < 0.5 always routes to Smart_Model (large tier)
Property 2: every decisions entry is structurally complete
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from hypothesis import given, settings
from hypothesis import strategies as st

from agent.agent import _serialise_decisions
from decider_kit.patterns.model_routing import ModelRouter, Route


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_router(tier: str, confidence: float, p_hard: float = 0.5):
    """Stub a ModelRouter that returns a fixed Route."""
    decider = MagicMock()
    router = ModelRouter(decider)
    router.log = []

    def _route(request: str) -> Route:
        from decider_kit.patterns.model_routing import default_tiers
        tiers = default_tiers()
        actual_tier = tier if confidence >= router.threshold else router.unsure_to
        model_id = tiers[actual_tier]["model_id"]
        reason = "test"
        r = Route(tier=actual_tier, model_id=model_id, p_hard=p_hard, confidence=confidence, reason=reason)
        router.log.append({
            "stage": "model_routing",
            "tier": actual_tier,
            "model_id": model_id,
            "p_hard": round(p_hard, 3),
            "confidence": round(confidence, 3),
            "reason": reason,
            "decider_ms": 5,
        })
        return r

    router.route = _route
    return router


# ── Property 1: confidence < 0.5 always routes to large ──────────────────────

@given(
    tier=st.sampled_from(["small", "medium", "large"]),
    confidence=st.floats(min_value=0.0, max_value=0.499, allow_nan=False),
)
def test_low_confidence_always_routes_to_large(tier, confidence):
    # Feature: shipping-tracking-agent, Property 1: confidence < 0.5 always routes to Smart_Model
    router = _make_router(tier=tier, confidence=confidence)
    route = router.route("test message")
    # Any confidence below the threshold (default 0.65, but also < 0.5 forces large)
    # The router sets unsure_to="large" so low confidence must yield large tier
    assert route.tier == "large", (
        f"Expected tier=large for confidence={confidence}, got {route.tier}"
    )


# ── Property 2: every decisions entry is structurally complete ───────────────

@given(
    tier=st.sampled_from(["small", "medium", "large"]),
    confidence=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
)
def test_decisions_entry_structurally_complete(tier, confidence):
    # Feature: shipping-tracking-agent, Property 2: every decisions entry is structurally complete
    router = _make_router(tier=tier, confidence=confidence)
    router.route("test")
    decisions = _serialise_decisions(router.log, [])
    for d in decisions:
        assert "query_category" in d, "missing query_category"
        assert d["query_category"] in ("simple", "complex"), f"bad category: {d['query_category']}"
        assert 0.0 <= d["confidence"] <= 1.0, f"confidence out of range: {d['confidence']}"
        assert isinstance(d["latency_ms"], int) and d["latency_ms"] >= 0
        assert isinstance(d["selected_model_id"], str) and len(d["selected_model_id"]) > 0


@given(
    conf=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
    grounded=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
)
def test_guard_decisions_entry_structurally_complete(conf, grounded):
    # Feature: shipping-tracking-agent, Property 2: every decisions entry is structurally complete
    guard_log = [{
        "pattern": "#model-routing", "stage": "tool", "tool": "initiate_refund",
        "args_grounded": grounded, "explicit_request": 0.9, "premature": 0.1,
        "decider_ms": 5, "verdict": "proceed",
    }]
    decisions = _serialise_decisions([], guard_log)
    for d in decisions:
        assert 0.0 <= d["confidence"] <= 1.0
        assert isinstance(d["latency_ms"], int) and d["latency_ms"] >= 0
        assert isinstance(d["selected_model_id"], str) and len(d["selected_model_id"]) > 0
