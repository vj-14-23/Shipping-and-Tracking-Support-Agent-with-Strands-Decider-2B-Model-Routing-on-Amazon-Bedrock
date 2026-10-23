"""REUSABLE DECISION PATTERN: policy classification  (#policy)

What it does
    Classifies a request (or a draft reply, or a document) against your own written policy and
    returns allow / review / block, before anything irreversible happens: before the agent acts,
    before a reply is sent, before content is published.

Typed questions and options
    `category` (choice): your policy categories, each with a one-line definition.
    `violates` (noul): does the content break the policy?
    `severity` (score): how serious is it? ["none", "minor", "serious", "critical"]

Wiring (where it sits in the agent's path)
    Either before the agent runs:

        verdict = PolicyCheck(Decider(), POLICY, CATEGORIES).check(user_message)
        if verdict.action == "block": return verdict.message
        if verdict.action == "review": queue_for_human(...)

    or after the agent drafts a reply, on the draft (the same call), before it is sent.

How to use it in your agent
    Write POLICY as the rules a human reviewer would apply, and CATEGORIES as your own
    taxonomy. The thresholds that turn probabilities into actions live in `decide()`: change them
    there, in code you own.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..client import Decider, Decision

SEVERITY = ["none", "minor", "serious", "critical"]


def questions(policy: str, categories: dict[str, str]) -> dict[str, dict[str, Any]]:
    return {
        "category": Decider.choice("Which policy category does this content fall under?", categories),
        "violates": Decider.noul(f"Does this content violate the policy? Policy: {policy}",
                                 {"true": "it breaks at least one rule of the policy", "false": "it complies with the policy"}),
        "severity": Decider.score("How serious would acting on this content be under the policy?", SEVERITY),
    }


@dataclass
class Verdict:
    action: str  # allow | review | block
    category: str
    p_violation: float
    severity: str
    confident: bool
    answers: dict[str, Decision] = field(repr=False, default_factory=dict)

    @property
    def message(self) -> str:
        return {"allow": "Allowed.", "review": "Held for human review under policy.",
                "block": f"Blocked: this falls under '{self.category}' and breaks the policy."}[self.action]


class PolicyCheck:
    def __init__(self, decider: Decider, policy: str, categories: dict[str, str], block_at: float = 0.7, review_at: float = 0.4):
        self.decider, self.policy, self.categories = decider, policy, categories
        self.block_at, self.review_at = block_at, review_at
        self.log: list[dict[str, Any]] = []

    def check(self, content: str, context: str = "", images: Any = None) -> Verdict:
        """`images` (optional): photos or screenshots checked with the text (a vision decider)."""
        state = (f"Context: {context}\n\n" if context else "") + f"Content to check:\n{content}"
        a = self.decider.ask(state, questions(self.policy, self.categories), images=images)
        v = self.decide(a)
        self.log.append({"stage": "policy", "action": v.action, "category": v.category, "p_violation": round(v.p_violation, 3),
                         "severity": v.severity, "decider_ms": self.decider.last_latency_ms})
        return v

    def decide(self, a: dict[str, Decision]) -> Verdict:
        p = a["violates"].p_yes or 0.0
        sev = a["severity"].label or "none"
        serious = sev in ("serious", "critical")
        if p >= self.block_at or (p >= self.review_at and sev == "critical"):
            action = "block"
        elif p >= self.review_at or (serious and a["severity"].confidence >= 0.5):
            action = "review"
        else:
            action = "allow"
        return Verdict(action, a["category"].label or "?", p, sev, confident=a["violates"].confidence >= 0.7, answers=a)
