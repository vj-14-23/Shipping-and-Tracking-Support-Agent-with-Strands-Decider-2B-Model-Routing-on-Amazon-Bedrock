"""Shipping and tracking support agent for an online store.

Uses Strands Decider 2B with the #model-routing pattern: simple queries (status lookups,
ETAs) go to a fast, cheap model; complex or high-stakes interactions (exceptions, address
changes, damage claims) go to a more capable model. All irreversible tool calls are
checked by ShippingActionGuard before execution.

Contract (kit.md):
    from agent.agent import HackathonAgent
    out = HackathonAgent().chat("Where is my package TRK001?")
    out["reply"], out["decisions"], out["model_id"], out["latency_ms"]
"""
from __future__ import annotations

import re
import time
from typing import Any

from strands import Agent

from decider_kit import Decider
from decider_kit.llm import agent_model, default_model_id, image_blocks, strip_thinking
from decider_kit.patterns.model_routing import ModelRouter

from .carrier import CarrierConfigError, carrier_from_env
from .decision import ShippingActionGuard
from .session import SessionStore
from .tools import TOOLS, set_current_session

NAME = "Shipping & Tracking Support Agent"

SYSTEM_PROMPT = """You are a shipping and tracking support agent for an online store.
You help customers check shipment status, understand delivery exceptions, and resolve issues.

You can:
- Look up shipment status by tracking number or order ID
- Explain delivery exceptions and present resolution options
- Collect damage reports and initiate replacements or refunds
- Request address changes for in-transit shipments
- Open carrier investigations for lost packages

Guidelines:
- Always look up shipment data before discussing status or exceptions.
- For irreversible actions (investigations, replacements, refunds, address changes),
  present a clear summary and ask the customer to confirm before proceeding.
- Never guess tracking numbers or order IDs — always ask if you don't have them.
- If the carrier API is unavailable, tell the customer and suggest retrying in 15 minutes.
- Be brief, accurate, and empathetic. Never make promises you cannot keep.
- This agent uses stub carrier integrations; real carrier API keys are needed for live data.

Built with the AWS User Group Madurai Strands Decider hackathon kit."""


class ShippingTrackingAgent:
    """Shipping and tracking support agent.

    One Strands Agent per session. ModelRouter routes each message to the appropriate
    Bedrock model tier before the agent is invoked. ShippingActionGuard checks every
    irreversible tool call with Strands Decider 2B.
    """

    def __init__(
        self,
        decider: Decider | None = None,
        model_id: str | None = None,
        eager: bool | None = None,  # kept for kit contract compatibility; not used
    ):
        self.decider = decider or Decider()
        self.model_id = model_id or default_model_id()
        self.router = ModelRouter(self.decider)
        self._sessions: dict[str, tuple[Agent, ShippingActionGuard]] = {}
        self._carrier_error: str | None = None

        # Initialise carrier; catch config errors so chat() can respond gracefully
        try:
            self._carrier = carrier_from_env()
        except CarrierConfigError as exc:
            self._carrier = None
            self._carrier_error = str(exc)

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------

    def _evict_expired(self) -> None:
        """Remove sessions that have been idle for more than 30 minutes."""
        expired = [sid for sid, (_, _) in self._sessions.items()
                   if _get_store(self._sessions, sid).is_expired()]
        for sid in expired:
            store = _get_store(self._sessions, sid)
            store.clear()
            del self._sessions[sid]

    def _get_session(self, session_id: str) -> tuple[Agent, ShippingActionGuard]:
        if session_id not in self._sessions:
            guard = ShippingActionGuard(self.decider)
            store = SessionStore()
            # We embed the store on the guard so eviction can reach it
            guard._store = store  # type: ignore[attr-defined]
            agent = Agent(
                model=agent_model(self.model_id),
                system_prompt=SYSTEM_PROMPT,
                tools=TOOLS,
                interventions=[guard],
                callback_handler=None,
            )
            agent._store = store  # type: ignore[attr-defined]
            self._sessions[session_id] = (agent, guard)
        return self._sessions[session_id]

    # ------------------------------------------------------------------
    # chat()
    # ------------------------------------------------------------------

    def chat(
        self,
        message: str,
        session_id: str = "default",
        images: list[Any] | None = None,
    ) -> dict[str, Any]:
        """Process one customer message and return a structured response.

        Returns:
            dict with keys: reply, decisions, model_id, latency_ms, agent, tier
        """
        # Carrier not configured — fail gracefully
        if self._carrier is None:
            return {
                "reply": "I'm sorry, the shipping integration is not configured. "
                         "Please contact support.",
                "decisions": [],
                "model_id": self.model_id,
                "latency_ms": 0,
                "agent": NAME,
                "tier": "none",
                "error": "carrier_not_configured",
            }

        self._evict_expired()
        agent, guard = self._get_session(session_id)
        store: SessionStore = agent._store  # type: ignore[attr-defined]

        # Set session context so tools can access store + carrier
        set_current_session(store, self._carrier)

        # Route message to the right model tier
        before_route_log = len(self.router.log)
        try:
            route = self.router.route(message)
            routed_model_id = route.model_id
            tier = route.tier
        except Exception:
            routed_model_id = self.model_id
            tier = "large"
            route = None

        # Rebuild agent with routed model if tier changed
        if route is not None and routed_model_id != self.model_id:
            agent._model = agent_model(routed_model_id)

        before_guard_log = len(guard.log)
        t0 = time.perf_counter()

        result = agent(
            [*image_blocks(images), {"text": message}] if images else message,
            invocation_state={"images": list(images or [])},
        )

        latency_ms = round((time.perf_counter() - t0) * 1000)
        reply = strip_thinking(str(result))

        # Build decisions list: router entries + guard entries this turn
        router_entries = self.router.log[before_route_log:]
        guard_entries = guard.log[before_guard_log:]

        decisions = _serialise_decisions(router_entries, guard_entries)
        # Cap at 50 entries (Req 7.1)
        decisions = decisions[:50]

        store.touch()
        return {
            "reply": reply,
            "decisions": decisions,
            "model_id": routed_model_id,
            "latency_ms": latency_ms,
            "agent": NAME,
            "tier": tier,
        }


# ------------------------------------------------------------------
# Decision serialisation helpers (task 6.2)
# ------------------------------------------------------------------

def _serialise_decisions(
    router_entries: list[dict[str, Any]],
    guard_entries: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Convert raw log dicts from ModelRouter and ShippingActionGuard into the
    RoutingDecision shape expected by the demo UI and Req 7.2.

    Shape: {query_category, confidence, selected_model_id, latency_ms, ...extra}
    """
    out: list[dict[str, Any]] = []

    for entry in router_entries:
        tier = entry.get("tier", "large")
        conf = float(entry.get("confidence") or 0.0)
        # Map tier to simple/complex (Req 7.2)
        category = "simple" if tier in ("small", "medium") else "complex"
        out.append({
            "query_category": category,
            "confidence": round(max(0.0, min(1.0, conf)), 3),
            "selected_model_id": entry.get("model_id", ""),
            "latency_ms": int(entry.get("decider_ms") or 0),
            "stage": "model_routing",
            "tier": tier,
            "reason": entry.get("reason", ""),
        })

    for entry in guard_entries:
        # Guard entries may not have a model_id; use pattern tag as identifier
        conf_raw = entry.get("args_grounded") or entry.get("in_scope") or 0.0
        out.append({
            "query_category": "complex",  # guard only fires on complex / irreversible actions
            "confidence": round(max(0.0, min(1.0, float(conf_raw or 0.0))), 3),
            "selected_model_id": entry.get("pattern", "#model-routing"),
            "latency_ms": int(entry.get("decider_ms") or 0),
            "stage": entry.get("stage", "tool"),
            "verdict": entry.get("verdict", ""),
            "tool": entry.get("tool", ""),
        })

    return out


# ------------------------------------------------------------------
# Private helpers
# ------------------------------------------------------------------

def _get_store(sessions: dict, session_id: str) -> SessionStore:
    agent, _ = sessions[session_id]
    return agent._store  # type: ignore[attr-defined]


# ------------------------------------------------------------------
# HackathonAgent alias — keeps demo UI, benchmark and AgentCore working
# ------------------------------------------------------------------
HackathonAgent = ShippingTrackingAgent


# ------------------------------------------------------------------
# CLI smoke test
# ------------------------------------------------------------------
if __name__ == "__main__":
    import json, sys, os
    # Requires CARRIER_API_KEY to be set; prints graceful error otherwise
    a = ShippingTrackingAgent()
    msgs = sys.argv[1:] or ["Where is my package TRK001?", "Has it been delivered yet?"]
    for msg in msgs:
        print(json.dumps(a.chat(msg), indent=2, default=str))
