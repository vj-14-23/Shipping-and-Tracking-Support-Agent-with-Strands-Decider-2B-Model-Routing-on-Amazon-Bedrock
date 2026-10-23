"""REUSABLE DECISION PATTERN: shipping action guardrail  (#model-routing)

What it does
    Before the shipping agent calls an irreversible tool (carrier investigation, replacement,
    refund, or address change), Strands Decider 2B checks the call against the conversation:
    - are the arguments grounded in what the customer said (no invented tracking numbers)?
    - does the customer clearly ask for this action, rather than asking about it?
    - is it premature (should the agent confirm details first)?
    Grounded and explicitly-requested calls that are ready to proceed run; otherwise the agent
    is guided back to ask, or a human confirms when the decider is unsure.
    On input, injection attempts are denied and out-of-scope requests are redirected.

Typed questions and options
    args_grounded (noul), explicit_request (noul), premature (noul); see QUESTIONS below.
    Input questions: injection (noul), in_scope (noul).

Wiring
    `ShippingActionGuard` is a Strands `InterventionHandler`; agent/agent.py passes it:
        Agent(..., interventions=[ShippingActionGuard(decider)])
    It only inspects tools in GUARDED_TOOLS; read-only tools run untouched.
    Retried calls that were already guided are denied (Strands requires guide handlers to converge).

How to reuse it
    Copy this file, change GUARDED_TOOLS to your irreversible tools, and reword the questions
    for your domain. Thresholds (yes, unsure_band) are tunable in the constructor.
"""

from __future__ import annotations

import json
import time
from typing import Any

from strands.interventions import Confirm, Deny, Guide, InterventionHandler, Proceed

from decider_kit import Decider
from decider_kit.patterns.guardrails import input_questions, render_messages

PATTERN_TAG = "#model-routing"

GUARDED_TOOLS = {
    "initiate_carrier_investigation",
    "request_replacement",
    "initiate_refund",
    "request_address_change",
}

QUESTIONS = {
    "args_grounded": Decider.noul(
        "Are the tracking number, order ID, and any amounts in the proposed action stated by the customer or returned by an earlier tool lookup?",
        {
            "true": "every argument comes from the customer's words or a prior tool result",
            "false": "an argument was guessed or invented — not stated by the customer",
        },
    ),
    "explicit_request": Decider.noul(
        "Is the customer's latest message an explicit instruction to perform this action now, rather than a question about it?",
        {
            "true": "an explicit instruction such as 'start the investigation', 'refund it', 'change my address to ...'",
            "false": "a question ('can I...?', 'what happens if...?'), a complaint, or a status check",
        },
    ),
    "premature": Decider.noul(
        "Should the assistant confirm details with the customer before taking this action?",
        {
            "true": "something is ambiguous, unconfirmed, or the customer hasn't seen a summary of what will happen",
            "false": "the customer has seen the action summary and confirmed they want to proceed",
        },
    ),
}

_SCOPE = "shipping and order-tracking support"


class ShippingActionGuard(InterventionHandler):
    """Guards irreversible shipping actions with Decider-based checks.

    Checks three questions before any irreversible tool call:
      1. Are the arguments grounded in what the customer said?
      2. Did the customer explicitly request this action (not just ask about it)?
      3. Is it premature — should the agent confirm first?

    Also checks every incoming message for prompt injection and scope.
    """

    name = "shipping-action-guard"

    def __init__(
        self,
        decider: Decider,
        yes: float = 0.5,
        unsure_band: tuple[float, float] = (0.4, 0.6),
    ):
        self.decider = decider
        self.yes = yes
        self.unsure_band = unsure_band
        self.log: list[dict[str, Any]] = []
        self._guided: set[str] = set()

    def before_invocation(self, event, **kwargs):
        """Check for injection and scope on every new customer message."""
        self._guided.clear()  # new turn: previously guided calls may now be valid
        if not event.messages:
            return Proceed()

        t0 = time.perf_counter()
        text = render_messages(event.messages, last=1)
        state = f"User message to an assistant for: {_SCOPE}\n\n{text}"
        try:
            a = self.decider.ask(state, input_questions(_SCOPE))
        except Exception as exc:  # Decider unavailable — allow through, log the miss
            self.log.append({"pattern": PATTERN_TAG, "stage": "input", "verdict": "proceed",
                             "decider_error": str(exc), "decider_ms": 0})
            return Proceed()

        ms = round((time.perf_counter() - t0) * 1000)
        rec = {
            "pattern": PATTERN_TAG, "stage": "input",
            "injection": round(a["injection"].p_yes or 0, 3),
            "in_scope": round(a["in_scope"].p_yes or 0, 3),
            "decider_ms": ms,
        }

        if (a["injection"].p_yes or 0) >= self.yes:
            rec["verdict"] = "deny"
            self.log.append(rec)
            return Deny(reason="This request was blocked by the guardrail.")

        if (a["in_scope"].p_yes or 0) < (1 - self.yes):
            rec["verdict"] = "guide"
            self.log.append(rec)
            return Guide(
                feedback=f"This request is outside what I can help with ({_SCOPE}). "
                "I can help with tracking packages, delivery exceptions, and address changes."
            )

        rec["verdict"] = "proceed"
        self.log.append(rec)
        return Proceed()

    def before_tool_call(self, event, **kwargs):
        """Guard irreversible tools with the three-question Decider check."""
        name = event.tool_use["name"]
        if name not in GUARDED_TOOLS:
            return Proceed()

        args = event.tool_use.get("input") or {}
        sig = f"{name}:{json.dumps(args, sort_keys=True)}"

        # If this exact call was already guided, deny the retry (Strands convergence rule)
        if sig in self._guided:
            rec = {"pattern": PATTERN_TAG, "stage": "tool", "tool": name, "args": args,
                   "verdict": "deny", "reason": "retried a guided call unchanged"}
            self.log.append(rec)
            return Deny(reason="This action was already reviewed and requires more information from the customer.")

        state = (
            "A customer-support conversation about shipping, then an action the assistant wants to take.\n\n"
            f"--- CONVERSATION ---\n{render_messages(event.agent.messages)}\n\n"
            f"--- PROPOSED ACTION ---\ntool: {name}\narguments: {json.dumps(args)}"
        )

        t0 = time.perf_counter()
        try:
            a = self.decider.ask(state, QUESTIONS)
        except Exception as exc:
            # Decider unavailable: fall back to Confirm (Req 2.5 — safety preserved)
            ms = round((time.perf_counter() - t0) * 1000)
            rec = {"pattern": PATTERN_TAG, "stage": "tool", "tool": name, "args": args,
                   "verdict": "confirm", "reason": "decider_unavailable", "decider_error": str(exc),
                   "args_grounded": None, "explicit_request": None, "premature": None, "decider_ms": ms}
            self.log.append(rec)
            return Confirm(prompt=f"Approve {name}?", response="yes")

        ms = round((time.perf_counter() - t0) * 1000)
        g = a["args_grounded"].p_yes or 0.0
        e = a["explicit_request"].p_yes or 0.0
        p = a["premature"].p_yes or 0.0

        rec = {
            "pattern": PATTERN_TAG, "stage": "tool", "tool": name, "args": args,
            "args_grounded": round(g, 3), "explicit_request": round(e, 3),
            "premature": round(p, 3), "decider_ms": ms,
        }

        lo, hi = self.unsure_band

        if g < self.yes:
            rec["verdict"] = "guide"
            self._guided.add(sig)
            self.log.append(rec)
            return Guide(
                feedback="Do not guess tracking numbers or order IDs. "
                "Look up the shipment first or ask the customer to confirm the details."
            )

        if e < self.yes:
            rec["verdict"] = "guide"
            self._guided.add(sig)
            self.log.append(rec)
            return Guide(
                feedback="The customer has not explicitly asked for this action yet. "
                "Answer their question and offer this option before proceeding."
            )

        if lo <= p <= hi:
            rec["verdict"] = "confirm"
            self.log.append(rec)
            return Confirm(prompt=f"Approve {name} with {json.dumps(args)}?", response="yes")

        if p > hi:
            rec["verdict"] = "guide"
            self._guided.add(sig)
            self.log.append(rec)
            return Guide(
                feedback="Please confirm the details with the customer before taking this action."
            )

        rec["verdict"] = "proceed"
        self.log.append(rec)
        return Proceed()
