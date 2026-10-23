"""REUSABLE DECISION PATTERN: tool selection  (#tool-selection)

What it does
    Picks which tool (or specialist sub-agent) should handle a request before the LLM sees it,
    and hands the agent only that tool. Fewer tools in context means fewer wrong calls, fewer
    tokens and a faster, cheaper LLM turn. When the decider is unsure, the agent keeps every
    tool and the LLM chooses, so nothing is lost.

Typed questions and options
    `tool` (choice): one option per tool, described by the tool's own docstring, plus `none`
    ("no tool is needed, answer directly"). Options are read per request, so adding a tool
    needs no retraining.

Wiring (where it sits in the agent's path)
    Between the user message and the agent:

        from decider_kit.patterns.tool_selection import ToolSelector
        selector = ToolSelector(Decider(), tools=[get_weather, search_orders, create_ticket])
        agent = selector.agent_for(user_message, model=agent_model(), system_prompt=...)
        agent(user_message)

How to use it in your agent
    Give every tool a clear one-line docstring: that line becomes the option description.
    `threshold` (default 0.6) is the confidence below which all tools are kept.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from ..client import Decider, Decision


def _describe(tool: Any) -> tuple[str, str]:
    spec = getattr(tool, "tool_spec", None)
    if spec:
        return spec["name"], (spec.get("description") or spec["name"]).strip().split("\n")[0][:200]
    name = getattr(tool, "__name__", str(tool))
    return name, ((tool.__doc__ or name).strip().split("\n")[0])[:200]


def questions_for(tools: list[Any], context: str = "") -> dict[str, dict[str, Any]]:
    opts = dict(_describe(t) for t in tools)
    opts["none"] = "no tool is needed; the assistant can answer directly"
    return {"tool": Decider.choice(f"Which tool should handle this request?{(' ' + context) if context else ''}", opts)}


@dataclass
class Selection:
    tool: str
    confidence: float
    decision: Decision
    narrowed: bool


class ToolSelector:
    def __init__(self, decider: Decider, tools: list[Any], threshold: float = 0.6, context: str = ""):
        self.decider, self.tools, self.threshold, self.context = decider, tools, threshold, context
        self.by_name = {_describe(t)[0]: t for t in tools}
        self.log: list[dict[str, Any]] = []

    def select(self, request: str, history: str = "") -> Selection:
        state = (f"Conversation so far:\n{history}\n\n" if history else "") + f"User request: {request}"
        d = self.decider.ask(state, questions_for(self.tools, self.context))["tool"]
        sel = Selection(d.label or "none", d.confidence, d, narrowed=d.confidence >= self.threshold)
        self.log.append({"stage": "tool_selection", "tool": sel.tool, "confidence": round(sel.confidence, 3),
                         "narrowed": sel.narrowed, "probabilities": {k: round(v, 3) for k, v in d.probabilities.items()},
                         "decider_ms": self.decider.last_latency_ms})
        return sel

    def tools_for(self, request: str, history: str = "") -> list[Any]:
        sel = self.select(request, history)
        if not sel.narrowed:
            return list(self.tools)
        return [] if sel.tool == "none" else [self.by_name[sel.tool]]

    def agent_for(self, request: str, *, model: Any, system_prompt: str = "", agent_factory: Callable[..., Any] | None = None,
                  **agent_kwargs: Any) -> Any:
        from strands import Agent

        factory = agent_factory or Agent
        return factory(model=model, system_prompt=system_prompt, tools=self.tools_for(request), **agent_kwargs)
