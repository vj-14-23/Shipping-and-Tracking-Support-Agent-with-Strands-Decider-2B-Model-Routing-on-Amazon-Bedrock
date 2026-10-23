"""One decision pattern, #tool-selection, over Amazon Bedrock AgentCore Gateway tools.

The gateway can put many tools behind one MCP endpoint (web search, a knowledge base, Lambda
functions, REST APIs, MCP servers). Before each turn Strands Decider 2B picks the one tool the
request needs, and the agent only sees that tool: fewer wrong calls and a smaller prompt. Turn the
gateway on in agent/features.yaml and run `./kit deploy`. Same `chat()` interface as agent/agent.py:

    python -m examples.gateway_agent "Find a well-known vegetarian restaurant in Madurai."
"""

from __future__ import annotations

import time
from typing import Any

from strands import Agent, tool

from decider_kit import Decider
from decider_kit.agentcore import gateway_client, gateway_tools
from decider_kit.llm import agent_model, default_model_id, strip_thinking
from decider_kit.patterns.tool_selection import ToolSelector

NAME = "Example: assistant with gateway tools (AgentCore Gateway)"
PATTERN_TAG = "#tool-selection"
SYSTEM_PROMPT = "You are a helpful assistant. Use your tool when it helps. Be brief."


@tool
def get_time(city: str) -> str:
    """Current local time in a city."""
    return f"It is 19:30 in {city}."


class GatewayAgent:
    def __init__(self, decider: Decider | None = None, local_tools: list[Any] | None = None):
        self.gateway = gateway_client()  # None without an AgentCore Gateway: local tools only
        tools = list(local_tools or [get_time]) + (gateway_tools(self.gateway) if self.gateway else [])
        self.selector = ToolSelector(decider or Decider(), tools)
        self.model_id = default_model_id()

    def chat(self, message: str, session_id: str = "default") -> dict[str, Any]:
        mark = len(self.selector.log)
        t0 = time.perf_counter()
        tools = self.selector.tools_for(message)
        agent = Agent(model=agent_model(self.model_id), system_prompt=SYSTEM_PROMPT, tools=tools, callback_handler=None)
        reply = strip_thinking(str(agent(message)))
        return {"reply": reply, "decisions": self.selector.log[mark:], "model_id": self.model_id,
                "latency_ms": round((time.perf_counter() - t0) * 1000), "agent": NAME, "eager": False,
                "tools": [getattr(t, "tool_name", str(t)) for t in tools]}


if __name__ == "__main__":
    import json
    import sys

    a = GatewayAgent()
    for msg in sys.argv[1:] or ["Find a well-known vegetarian restaurant in Madurai.", "What time is it in Madurai?"]:
        print(json.dumps(a.chat(msg), indent=1, default=str))
