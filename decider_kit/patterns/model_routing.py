"""REUSABLE DECISION PATTERN: model routing  (#model-routing)

What it does
    Sends each request to the cheapest Amazon Bedrock model that can handle it: easy requests to
    a small, fast model; requests that need multi-step reasoning to a stronger one. The decider
    judges difficulty in one forward pass, without spending an LLM call to decide which LLM to
    call. When it is unsure, the request goes to the strong model (quality first).

Typed questions and options
    `hard` (noul): does answering need careful multi-step reasoning?
    `tier` (choice): small / medium / large, each described by what it is good for.

Wiring (where it sits in the agent's path)
    Before the agent is built for a request:

        router = ModelRouter(Decider())
        route = router.route(user_message)            # route.model_id, route.tier, route.confidence
        agent = Agent(model=agent_model(route.model_id), ...)   # decider_kit.llm

How to use it in your agent
    Set the models in .env (BEDROCK_SMALL_MODEL_ID / _MEDIUM_ / _LARGE_; Amazon Nova by default), or
    pass your own `tiers`. `unsure_to` picks the tier used
    when confidence is below `threshold`. Measured on a 216-request benchmark: the decider was the
    most accurate difficulty judge (ROC AUC 1.00) but on a 2 vCPU CPU it took about 11 s; on a GPU
    or a c7i instance (about 0.7 s) routing pays off. Measure it on your own hardware with
    `./kit bench`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..client import Decider

def tier_models() -> tuple[str, str, str]:
    """(small, medium, large) model ids for LLM_PROVIDER, from .env.

    bedrock: BEDROCK_SMALL/MEDIUM/LARGE_MODEL_ID (Amazon Nova Micro, Lite, Pro by default).
    local, ugmdu: LLM_SMALL/MEDIUM/LARGE_MODEL_ID (local: qwen3.5 0.8b, 2b, 4b;
    ugmdu: qwen3.5-4b, qwen3.5-4b, gpt-oss-20b).
    """
    import os

    from ..config import settings
    from ..llm import default_model_id, provider

    p = provider()
    if p == "bedrock":
        s = settings()
        return s.small_model, s.medium_model, s.large_model
    d = {"local": ("qwen3.5:0.8b", "qwen3.5:2b-q4_K_M", default_model_id(p)),
         "ugmdu": ("qwen3.5-4b", "qwen3.5-4b", "gpt-oss-20b")}[p]
    return tuple(os.environ.get(f"LLM_{k}_MODEL_ID", v) for k, v in zip(("SMALL", "MEDIUM", "LARGE"), d))  # type: ignore[return-value]


def default_tiers() -> dict[str, dict[str, str]]:
    """Tiers for LLM_PROVIDER from .env (see tier_models); Amazon Nova on Bedrock by default."""
    small, medium, large = tier_models()
    return {
        "small": {"model_id": small,
                  "for": "lookups, yes/no checks, rewording or extracting facts already given in the request"},
        "medium": {"model_id": medium, "for": "short explanations, summaries and simple single-step tasks"},
        "large": {"model_id": large,
                  "for": "multi-step reasoning, calculations, planning, code that must work, or long careful answers"},
    }


TIERS = default_tiers()

QUESTIONS = {
    "hard": Decider.noul("Does answering this request correctly need careful multi-step reasoning?",
                         {"true": "a logic puzzle, a calculation with several steps, a plan, or code that must pass tests",
                          "false": "looking something up in the given text, a yes/no judgement, or reformatting given facts"}),
    "tier": Decider.choice("Which model size is enough to answer this request well?",
                           {k: v["for"] for k, v in TIERS.items()}),
}


@dataclass
class Route:
    tier: str
    model_id: str
    p_hard: float
    confidence: float
    reason: str


class ModelRouter:
    def __init__(self, decider: Decider, tiers: dict[str, dict[str, str]] | None = None, threshold: float = 0.65,
                 unsure_to: str = "large"):
        self.decider, self.tiers, self.threshold, self.unsure_to = decider, tiers or default_tiers(), threshold, unsure_to
        self.log: list[dict[str, Any]] = []

    def route(self, request: str) -> Route:
        qs = dict(QUESTIONS)
        qs["tier"] = Decider.choice("Which model size is enough to answer this request well?",
                                    {k: v["for"] for k, v in self.tiers.items()})
        a = self.decider.ask(f"User request: {request}", qs)
        p_hard = a["hard"].p_yes or 0.0
        tier, conf = a["tier"].label or self.unsure_to, a["tier"].confidence
        if p_hard >= 0.5 and tier != "large" and "large" in self.tiers:
            tier, reason = "large", "needs multi-step reasoning"
        elif conf < self.threshold:
            tier, reason = self.unsure_to, f"unsure ({conf:.2f}); quality first"
        else:
            reason = f"{tier} is enough ({conf:.2f})"
        r = Route(tier, self.tiers[tier]["model_id"], p_hard, conf, reason)
        self.log.append({"stage": "model_routing", "tier": r.tier, "model_id": r.model_id, "p_hard": round(p_hard, 3),
                         "confidence": round(conf, 3), "reason": reason, "decider_ms": self.decider.last_latency_ms})
        return r
