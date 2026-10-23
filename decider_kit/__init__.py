"""decider_kit: the reusable pieces of the AWS User Group Madurai Strands Decider hackathon kit.

- `Decider`: one client for a local Strands Decider server, the AWS User Group Madurai hosted
  API, or any compatible endpoint.
- `decider_kit.patterns`: five labelled, reusable decision patterns (tool selection, guardrails,
  policy, model routing, context and memory), each with its typed questions, its option set and
  the wiring that puts it in a Strands agent's path.
- `decider_kit.bedrock`: Amazon Bedrock models for the generative part, and an LLM baseline
  for benchmarks.
- `decider_kit.bench`: Strands Decider compared with a Bedrock LLM on the same decisions
  (accuracy, latency, cost, low-confidence handling).
"""

from .client import Decider, DeciderError, Decision

__all__ = ["Decider", "DeciderError", "Decision"]
__version__ = "0.1.0"
