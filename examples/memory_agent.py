"""One decision pattern, #context-memory, on Amazon Bedrock AgentCore Memory.

Each turn, AgentCore Memory returns candidate records about the user; Strands Decider 2B decides
which are relevant enough to go in the prompt, and whether the new message is worth storing at
all (small talk never reaches Memory). Turn Memory on in agent/features.yaml and run
`./kit deploy`; without it the notes stay in this process. Same `chat()` interface as agent/agent.py:

    python -m examples.memory_agent "I'm vegetarian and I live in Madurai." "Suggest a dinner for tonight."
"""

from __future__ import annotations

import time
from typing import Any

from strands import Agent

from decider_kit import Decider
from decider_kit.agentcore import AgentCoreMemoryStore
from decider_kit.llm import agent_model, default_model_id, strip_thinking
from decider_kit.patterns.context_memory import DeciderMemory

NAME = "Example: assistant that remembers you (AgentCore Memory)"
PATTERN_TAG = "#context-memory"
SYSTEM_PROMPT = "You are a helpful assistant. Use the notes about the user when they help. Be brief."


class MemoryAgent:
    def __init__(self, decider: Decider | None = None, actor_id: str = "user"):
        self.memory = DeciderMemory(decider or Decider())
        self.actor_id = actor_id
        self.stores: dict[str, AgentCoreMemoryStore] = {}
        self.model_id = default_model_id()

    def chat(self, message: str, session_id: str = "default") -> dict[str, Any]:
        store = self.stores.setdefault(session_id, AgentCoreMemoryStore(actor_id=self.actor_id, session_id=session_id))
        mark = len(self.memory.log)
        t0 = time.perf_counter()
        notes = self.memory.recall(message, store.candidates(message))
        context = ("Notes about the user:\n- " + "\n- ".join(notes) + "\n\n") if notes else ""
        agent = Agent(model=agent_model(self.model_id), system_prompt=SYSTEM_PROMPT, callback_handler=None)
        reply = strip_thinking(str(agent(context + message)))
        if self.memory.maybe_store(message, []):
            store.save(message)
        return {"reply": reply, "decisions": self.memory.log[mark:], "model_id": self.model_id,
                "latency_ms": round((time.perf_counter() - t0) * 1000), "agent": NAME, "eager": False,
                "memory": "AgentCore Memory" if store.enabled else "in-process"}


if __name__ == "__main__":
    import json
    import sys

    a = MemoryAgent()
    for msg in sys.argv[1:] or ["I'm vegetarian and I live in Madurai.", "Suggest a dinner for tonight."]:
        print(json.dumps(a.chat(msg), indent=1, default=str))
