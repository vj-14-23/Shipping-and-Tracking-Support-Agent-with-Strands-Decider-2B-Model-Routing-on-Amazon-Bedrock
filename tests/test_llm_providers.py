"""The LLM provider switch: every option is a Strands model; images and baseline plumbing (offline)."""

from __future__ import annotations

import base64
from pathlib import Path

import pytest

DATA = Path(__file__).parent / "data"


@pytest.mark.parametrize("prov,cls", [("bedrock", "BedrockModel"), ("local", "OllamaModel"), ("ugmdu", "OpenAIModel")])
def test_agent_model_is_a_strands_model(monkeypatch, prov, cls):
    from decider_kit import llm

    monkeypatch.setenv("LLM_PROVIDER", prov)
    monkeypatch.setenv("LLM_URL", "http://127.0.0.1:9/v1")
    monkeypatch.setenv("LLM_API_KEY", "k")
    m = llm.agent_model()
    assert type(m).__name__ == cls
    if prov == "ugmdu":  # always the user group's endpoint
        assert str(m.client_args["base_url"]).startswith("https://da25tnxy06gjk.cloudfront.net/v1")
    assert m.get_config()["model_id"] == llm.default_model_id()


def test_defaults_per_provider(monkeypatch):
    from decider_kit import llm

    monkeypatch.delenv("LLM_MODEL_ID", raising=False)
    monkeypatch.setenv("LLM_PROVIDER", "local")
    assert llm.default_model_id() == "qwen3.5:4b" and llm.price("qwen3.5:4b") == (0.0, 0.0)
    assert llm.agent_model().get_config()["additional_args"] == {"think": False}
    monkeypatch.setenv("LLM_PROVIDER", "ugmdu")
    assert llm.default_model_id() == "qwen3.5-4b"
    monkeypatch.setenv("LLM_PROVIDER", "bedrock")
    assert llm.price("us.amazon.nova-pro-v1:0") == (0.80, 3.20)
    monkeypatch.setenv("LLM_PROVIDER", "openai")  # removed: Bedrock, local or the user group's cloud only
    with pytest.raises(ValueError):
        llm.provider()


def test_routing_tiers_follow_the_provider(monkeypatch):
    from decider_kit.patterns.model_routing import tier_models

    for k in ("LLM_SMALL_MODEL_ID", "LLM_MEDIUM_MODEL_ID", "LLM_LARGE_MODEL_ID", "LLM_MODEL_ID"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("LLM_PROVIDER", "ugmdu")
    assert tier_models() == ("qwen3.5-4b", "qwen3.5-4b", "gpt-oss-20b")
    monkeypatch.setenv("LLM_PROVIDER", "local")
    assert tier_models()[0] == "qwen3.5:0.8b"


def test_images_encode_for_decider_and_strands():
    from decider_kit.client import encode_images
    from decider_kit.llm import image_blocks

    raw = (DATA / "red-square.png").read_bytes()
    b64 = encode_images([DATA / "red-square.png", raw, base64.b64encode(raw).decode()])
    assert len(b64) == 3 and all(base64.b64decode(x) == raw for x in b64)
    blk = image_blocks([str(DATA / "red-square.png")])[0]["image"]
    assert blk["format"] == "png" and blk["source"]["bytes"] == raw
    with pytest.raises(Exception):
        encode_images([raw] * 5)


def test_baseline_goes_through_a_strands_agent(monkeypatch):
    """llm_answer builds a structured-output Agent call; the model is stubbed, no network."""
    from decider_kit import llm

    seen = {}

    def fake_ask(prompt, model_id=None, p=None, output_model=None, max_tokens=0, images=None, system=""):
        seen["model"] = output_model
        out = output_model.model_validate({"refund": {"answer": "yes", "confidence": 0.9},
                                           "team": {"answer": "billing", "confidence": 0.8}})
        return out, {"latency_ms": 5, "cost_usd": 0.0}

    monkeypatch.setattr(llm, "ask", fake_ask)
    from decider_kit import Decider

    qs = {"refund": Decider.noul("Refund?"), "team": Decider.choice("Team?", {"billing": "b", "shipping": "s"})}
    ans, usage = llm.llm_answer("I was charged twice", qs)
    assert ans == {"refund": {"label": "yes", "confidence": 0.9}, "team": {"label": "billing", "confidence": 0.8}}
    with pytest.raises(Exception):  # options are enforced by the schema
        seen["model"].model_validate({"refund": {"answer": "maybe", "confidence": 1}, "team": {"answer": "billing", "confidence": 1}})


def test_no_direct_bedrock_runtime_calls():
    """Every LLM call goes through the Strands Agents SDK: no boto3 converse/invoke_model anywhere."""
    root = Path(__file__).resolve().parent.parent
    hits = [str(p.relative_to(root)) for d in ("decider_kit", "scripts", "agent", "examples", "demo")
            for p in (root / d).rglob("*.py")
            if any(s in p.read_text() for s in ('"bedrock-runtime"', ".converse(", "invoke_model("))]
    assert hits == []


def test_attached_images_reaches_a_tool():
    from types import SimpleNamespace

    from decider_kit.llm import attached_images

    assert attached_images(SimpleNamespace(invocation_state={"images": ["AAAA"]})) == ["AAAA"]
    assert attached_images(SimpleNamespace(invocation_state={})) == []


def test_reply_cleanup():
    from decider_kit.llm import strip_thinking

    assert strip_thinking("<thinking>x</thinking> Hi") == "Hi"
    assert strip_thinking("DENIED: Please call 108 now.") == "Please call 108 now."
