"""Amazon Bedrock models for Strands agents. Kept for existing imports: use `decider_kit.llm`.

`bedrock_model()` is `agent_model(p="bedrock")`: a Strands BedrockModel for BEDROCK_MODEL_ID.
Every LLM call in the kit goes through a Strands Agent (see decider_kit/llm.py); none calls the
Bedrock runtime API directly.
"""

from __future__ import annotations

from typing import Any

from .llm import BEDROCK_PRICES as PRICES  # noqa: F401  (old name)
from .llm import agent_model, llm_answer, options_of, price  # noqa: F401


def bedrock_model(model_id: str | None = None, **kw: Any) -> Any:
    """A Strands BedrockModel (defaults to BEDROCK_MODEL_ID from .env)."""
    return agent_model(model_id, "bedrock", **kw)
