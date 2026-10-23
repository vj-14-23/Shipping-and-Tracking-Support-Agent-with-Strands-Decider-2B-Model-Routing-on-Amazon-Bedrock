"""REUSABLE DECISION PATTERN: context and memory selection  (#context-memory)

What it does
    Decides what goes into the LLM's context and what is worth remembering:
    - Recall: for each stored memory or document snippet, is it relevant to the current request?
      Only the relevant ones are put in the prompt (smaller prompts, fewer distractions).
    - Store: is the new user message worth saving as a long-term memory (a stable fact or
      preference), or is it small talk?

Typed questions and options
    `relevant` (noul), asked once per candidate with the request and that note as the state
    (RECALL_QUESTIONS). Candidates are checked concurrently (`parallel`, default 4). Putting the
    note in the state, not in the question, scored 7/8 against 4/8 on a hand-labelled check
    with the hosted decider (October 2026); measure your own with `./kit bench`.
    `remember` (noul) and `kind` (choice: preference, fact, task, none) for storing.

Wiring (where it sits in the agent's path)
    Around each agent turn:

        mem = DeciderMemory(Decider())
        context = mem.recall(user_message, memories)          # list of relevant memories
        reply = agent(f"Relevant context:\\n{context}\\n\\nUser: {user_message}")
        mem.maybe_store(user_message, memories)              # appends if worth keeping

How to use it in your agent
    `memories` is any list of strings (a file, DynamoDB, a vector store's top hits, or AgentCore
    Memory via `decider_kit.agentcore.AgentCoreMemoryStore.candidates`). `threshold` (default
    0.5) sets how relevant a memory must be. Up to `max_candidates` are checked per turn.
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from ..client import Decider

RECALL_QUESTIONS = {
    "relevant": Decider.noul("Would a good assistant use the stored note when answering this request?",
                             {"true": "the note changes or personalises the answer (where they are, what they like, what they need)",
                              "false": "the note has nothing to do with this request"}),
}


def recall_state(request: str, note: str) -> str:
    """The state layout for RECALL_QUESTIONS (use the same layout in eval_cases.jsonl)."""
    return f"User request: {request}\n\nStored note about the user: {note[:600]}"

STORE_QUESTIONS = {
    "remember": Decider.noul("Does this message contain a stable fact or preference about the user worth remembering for future conversations?",
                             {"true": "a lasting fact, preference or commitment", "false": "small talk, a one-off question or something temporary"}),
    "kind": Decider.choice("What kind of memory would this be?",
                           {"preference": "something the user likes, dislikes or wants", "fact": "a fact about the user or their situation",
                            "task": "something the user wants done later", "none": "nothing worth remembering"}),
}


class DeciderMemory:
    def __init__(self, decider: Decider, threshold: float = 0.5, max_candidates: int = 8, parallel: int = 4):
        self.decider, self.threshold, self.max_candidates, self.parallel = decider, threshold, max_candidates, parallel
        self.log: list[dict[str, Any]] = []

    def recall(self, request: str, memories: list[str]) -> list[str]:
        cands = memories[: self.max_candidates]
        if not cands:
            return []
        t0 = time.perf_counter()
        with ThreadPoolExecutor(max(1, min(self.parallel, len(cands)))) as ex:
            ps = list(ex.map(lambda m: self.decider.ask(recall_state(request, m), RECALL_QUESTIONS)["relevant"].p_yes or 0.0, cands))
        keep = list(zip(cands, ps))
        chosen = [m for m, p in sorted(keep, key=lambda x: -x[1]) if p >= self.threshold]
        self.log.append({"stage": "recall", "candidates": len(cands), "kept": len(chosen),
                         "scores": [round(p, 3) for _, p in keep], "decider_ms": round((time.perf_counter() - t0) * 1000)})
        return chosen

    def maybe_store(self, message: str, memories: list[str]) -> str | None:
        a = self.decider.ask(f"User message: {message}", STORE_QUESTIONS)
        store = a["remember"].yes and a["kind"].label != "none"
        self.log.append({"stage": "store", "remember": round(a["remember"].p_yes or 0, 3), "kind": a["kind"].label,
                         "stored": store, "decider_ms": self.decider.last_latency_ms})
        if store:
            memories.append(message)
            return a["kind"].label
        return None
