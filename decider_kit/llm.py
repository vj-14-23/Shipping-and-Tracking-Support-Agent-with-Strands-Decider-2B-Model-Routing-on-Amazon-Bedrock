"""The generative half of the agent, always through the Strands Agents SDK.

Pick where the LLM runs with LLM_PROVIDER in .env (`./kit setup` asks):

    bedrock  Amazon Bedrock (default; required for the hackathon submission). BEDROCK_MODEL_ID.
    local    a model on your machine, served by Ollama: no cloud, no cost. LLM_MODEL_ID
             (default qwen3.5:4b), OLLAMA_URL (default http://127.0.0.1:11434).
    ugmdu    the AWS User Group Madurai cloud: Qwen3.5 and gpt-oss, with the same key as the
             hosted decider. LLM_MODEL_ID (default qwen3.5-4b). The endpoint speaks the OpenAI chat
             format, so Strands talks to it with its OpenAIModel provider.

Everything that talks to an LLM (the agent, model routing, the benchmark's LLM baseline, the
article draft, the setup check) gets its model from `agent_model()` and calls it through a
Strands `Agent`.
"""

from __future__ import annotations

import os
import time
from typing import Any, Literal

from .config import UGMDU_DECIDER_URL, settings

PROVIDERS = ("bedrock", "local", "ugmdu")

# Local models offered by `./kit setup`, smallest first (Ollama download sizes, October 2026).
# All read tool calls; quality for agents grows with size. Apache-2.0 licences.
LOCAL_MODELS = [
    {"id": "qwen3.5:0.8b", "gb": 1.2, "ram_gb": 4, "note": "tiny; simple tool calls only, for very small machines"},
    {"id": "granite4:3b-h", "gb": 1.9, "ram_gb": 6, "note": "IBM Granite 4 Micro (hybrid); fast, built for tool calling"},
    {"id": "qwen3.5:2b-q4_K_M", "gb": 1.9, "ram_gb": 6, "note": "small Qwen3.5; reads images too"},
    {"id": "qwen3.5:4b", "gb": 4.0, "ram_gb": 8, "note": "recommended: good tool use, reads images"},
    {"id": "qwen3.5:9b", "gb": 6.6, "ram_gb": 16, "note": "best local quality; needs 16 GB+ RAM"},
]
DEFAULT_LOCAL_MODEL = "qwen3.5:4b"
# Served by the AWS User Group Madurai cloud (GET /v1/models lists what is live).
UGMDU_MODELS = ["qwen3.5-4b", "gpt-oss-20b"]
DEFAULT_UGMDU_MODEL = "qwen3.5-4b"

# USD per 1M tokens (input, output), Amazon Bedrock us-east-1 on-demand, October 2026.
BEDROCK_PRICES = {
    "amazon.nova-micro-v1:0": (0.035, 0.14),
    "amazon.nova-lite-v1:0": (0.06, 0.24),
    "amazon.nova-pro-v1:0": (0.80, 3.20),
    "anthropic.claude-haiku-4-5-20251001-v1:0": (1.00, 5.00),
    "anthropic.claude-sonnet-4-6": (3.00, 15.00),
}


def provider() -> str:
    from .config import load_dotenv

    load_dotenv()
    p = os.environ.get("LLM_PROVIDER", "bedrock").lower()
    if p not in PROVIDERS:
        raise ValueError(f"LLM_PROVIDER={p!r}: use one of {', '.join(PROVIDERS)}")
    return p


def default_model_id(p: str | None = None) -> str:
    p = p or provider()  # loads .env
    if p == "bedrock":
        return settings().bedrock_model
    if p == "local":
        return os.environ.get("LLM_MODEL_ID", DEFAULT_LOCAL_MODEL)
    return os.environ.get("LLM_MODEL_ID", DEFAULT_UGMDU_MODEL)


def agent_model(model_id: str | None = None, p: str | None = None, **kw: Any) -> Any:
    """A Strands model for an Agent, from LLM_PROVIDER (or `p`), with `model_id` or the default."""
    p = p or provider()
    mid = model_id or default_model_id(p)
    if p == "bedrock":
        from strands.models import BedrockModel

        return BedrockModel(model_id=mid, region_name=settings().aws_region, **kw)
    if p == "local":
        from strands.models.ollama import OllamaModel

        # Qwen3.5 thinks before answering by default; off unless LLM_THINK=1 (faster turns, fewer tokens)
        kw.setdefault("additional_args", {"think": os.environ.get("LLM_THINK", "0") == "1"})
        return OllamaModel(os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434"), model_id=mid, **kw)
    from strands.models.openai import OpenAIModel

    url = os.environ.get("UGMDU_LLM_URL", UGMDU_DECIDER_URL).rstrip("/") + "/v1"
    key = os.environ.get("LLM_API_KEY") or settings().decider_api_key
    return OpenAIModel(client_args={"base_url": url, "api_key": key or "none"}, model_id=mid, params=kw.pop("params", {}), **kw)


def describe(p: str | None = None, model_id: str | None = None) -> str:
    """'Amazon Bedrock (us.amazon.nova-pro-v1:0)', 'Ollama on this machine (qwen3.5:4b)', ..."""
    p = p or provider()
    where = {"bedrock": "Amazon Bedrock", "local": "Ollama on this machine",
             "ugmdu": "AWS User Group Madurai cloud"}[p]
    return f"{where} ({model_id or default_model_id(p)})"


def price(model_id: str, p: str | None = None) -> tuple[float, float]:
    """USD per 1M (input, output) tokens: LLM_PRICE_IN/OUT if set; Bedrock table; 0 for local."""
    if os.environ.get("LLM_PRICE_IN"):
        return float(os.environ["LLM_PRICE_IN"]), float(os.environ.get("LLM_PRICE_OUT", "0"))
    if (p or provider()) != "bedrock":
        return 0.0, 0.0  # local: your machine; ugmdu: free during the hackathon
    base = model_id.split(".", 1)[1] if model_id.split(".", 1)[0] in ("us", "eu", "apac", "global") else model_id
    if base in BEDROCK_PRICES:
        return BEDROCK_PRICES[base]
    print(f"[llm] no price for {model_id}: set LLM_PRICE_IN and LLM_PRICE_OUT (USD per 1M tokens) for cost numbers")
    return 0.0, 0.0


def ask(prompt: str, system: str = "", model_id: str | None = None, p: str | None = None,
        output_model: Any = None, max_tokens: int = 800, images: Any = None) -> tuple[Any, dict[str, Any]]:
    """One Strands Agent call with no tools. Returns (text, or the `output_model` instance; usage).

    `images` (paths, bytes or base64) go in as Strands image content blocks; the model must read
    images (Amazon Nova Lite/Pro, Qwen3.5, gpt-oss does not).
    """
    from strands import Agent

    p = p or provider()
    mid = model_id or default_model_id(p)
    kw: dict[str, Any] = ({"max_tokens": max_tokens, "temperature": 0} if p in ("bedrock", "local")
                          else {"params": {"max_tokens": max_tokens, "temperature": 0}})
    agent = Agent(model=agent_model(mid, p, **kw), system_prompt=system or None, callback_handler=None)
    content: Any = prompt
    if images:
        content = [*image_blocks(images), {"text": prompt}]
    t0 = time.perf_counter()
    result = agent(content, structured_output_model=output_model) if output_model else agent(content)
    ms = (time.perf_counter() - t0) * 1000
    u = result.metrics.accumulated_usage
    tin, tout = int(u.get("inputTokens", 0)), int(u.get("outputTokens", 0))
    pin, pout = price(mid, p)
    usage = {"input_tokens": tin, "output_tokens": tout, "latency_ms": ms, "cost_usd": tin / 1e6 * pin + tout / 1e6 * pout,
             "model_id": mid, "provider": p}
    if output_model:
        return result.structured_output, usage
    return strip_thinking(str(result)), usage


def image_blocks(images: Any) -> list[dict[str, Any]]:
    """Strands image content blocks from paths, bytes or base64 strings."""
    import base64

    from .client import encode_images

    blocks = []
    for b64 in encode_images(images):
        raw = base64.b64decode(b64.split(",", 1)[1] if b64.startswith("data:") else b64)
        fmt = "png" if raw[:4] == b"\x89PNG" else "gif" if raw[:3] == b"GIF" else "webp" if raw[8:12] == b"WEBP" else "jpeg"
        blocks.append({"image": {"format": fmt, "source": {"bytes": raw}}})
    return blocks


def attached_images(tool_context: Any) -> list[Any]:
    """The photos the user attached this turn, inside a Strands tool.

    `HackathonAgent.chat(message, images=[...])` calls the agent with
    `invocation_state={"images": images}`; a tool declared `@tool(context=True)` reads them:

        @tool(context=True)
        def submit_listing(description: str, tool_context: ToolContext) -> str:
            photos = attached_images(tool_context)
            answers = decider.ask(f"Listing: {description}", QUESTIONS, images=photos)
    """
    return list((getattr(tool_context, "invocation_state", None) or {}).get("images") or [])


def strip_thinking(text: str) -> str:
    """The reply to show the user: no <thinking>/<think> blocks (Nova, Qwen), and no "DENIED: "
    prefix (Strands adds it when a guardrail Denies the whole request; the reason is the reply)."""
    import re

    text = re.sub(r"<(thinking|think)>.*?</\1>", "", text, flags=re.S).strip()
    return re.sub(r"^DENIED:\s*", "", text)


def options_of(q: dict[str, Any]) -> list[str]:
    if q["type"] == "noul":
        return ["yes", "no"]
    return [str(o) for o in q["criteria"]]  # choice options, or score levels lowest first


def llm_answer(state: Any, questions: dict[str, dict[str, Any]], model_id: str | None = None,
               p: str | None = None, images: Any = None) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """The same typed questions, answered by an LLM through a Strands Agent with structured output.

    Returns ({name: {"label", "confidence"}}, usage). The baseline in `./kit bench`.
    """
    from pydantic import BaseModel, Field, create_model

    fields: dict[str, Any] = {}
    lines = []
    for name, q in questions.items():
        opts = options_of(q)
        answer_t = Literal[tuple(opts)]  # type: ignore[valid-type]
        sub = create_model(f"A_{name}", answer=(answer_t, ...), confidence=(float, Field(ge=0, le=1)), __base__=BaseModel)
        fields[name] = (sub, ...)
        meaning = q.get("criteria") if q["type"] == "choice" else (
            {"yes": q.get("criteria", {}).get("true", ""), "no": q.get("criteria", {}).get("false", "")} if q["type"] == "noul" else None)
        lines.append(f'- "{name}": {q["instructions"]} Options: {opts}' + (f" Meanings: {meaning}" if meaning else ""))
    Answers = create_model("Answers", **fields, __base__=BaseModel)
    prompt = (f"Read the state and answer each question with exactly one of its options, plus your confidence (0 to 1).\n\n"
              f"STATE:\n{state}\n\nQUESTIONS:\n" + "\n".join(lines))
    out, usage = ask(prompt, model_id=model_id, p=p, output_model=Answers, max_tokens=400 + 80 * len(questions), images=images)
    res = {}
    for name in questions:
        a = getattr(out, name, None)
        res[name] = {"label": getattr(a, "answer", None), "confidence": float(getattr(a, "confidence", 0.0) or 0.0)}
    return res, usage
