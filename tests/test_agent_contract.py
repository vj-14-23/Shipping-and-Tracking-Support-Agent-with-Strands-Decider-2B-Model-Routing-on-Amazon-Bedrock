"""The contract every agent/ must keep (the demo, bench, video and deployment depend on it)."""

import ast
import json
from pathlib import Path
from types import SimpleNamespace

from fakes import FakeDecider

ROOT = Path(__file__).resolve().parent.parent
TAGS = {"#tool-selection", "#guardrails", "#policy", "#model-routing", "#context-memory"}


def test_decision_file_is_labelled():
    src = (ROOT / "agent" / "decision.py").read_text()
    doc = ast.get_docstring(ast.parse(src))
    assert doc and doc.startswith("REUSABLE DECISION PATTERN:")
    from decider_kit.inspect_agent import constant

    assert constant(src, "PATTERN_TAG") in TAGS
    from agent.decision import QUESTIONS

    assert QUESTIONS and all(q["type"] in ("noul", "choice", "score") for q in QUESTIONS.values())


def test_eval_cases_match_questions():
    from agent.decision import QUESTIONS

    for line in (ROOT / "agent" / "eval_cases.jsonl").read_text().splitlines():
        if line.strip():
            c = json.loads(line)
            assert set(c["expected"]) <= set(QUESTIONS), c["expected"]
            assert isinstance(c["state"], str) and c["state"]


def test_agent_interface():
    from agent import agent as mod

    assert hasattr(mod, "NAME") and hasattr(mod, "HackathonAgent")
    a = mod.HackathonAgent(decider=FakeDecider(), model_id="us.amazon.nova-lite-v1:0")
    assert callable(a.chat)


def test_example_guard_converges():
    """A guided call retried unchanged is denied (Strands requires Guide to converge)."""
    from strands.interventions import Deny, Guide

    import agent.decision as dmod

    if not hasattr(dmod, "OrderActionGuard"):
        return  # the participant's own decision: covered by their own test
    g = dmod.OrderActionGuard(FakeDecider(lambda s, n, q: 0.1 if n == "args_grounded" else 0.9))
    ev = SimpleNamespace(tool_use={"name": "refund_order", "input": {"order_id": "X", "amount": 1}},
                         agent=SimpleNamespace(messages=[{"role": "user", "content": [{"text": "refund"}]}]))
    assert isinstance(g.before_tool_call(ev), Guide)
    assert isinstance(g.before_tool_call(ev), Deny)


def test_inspect_handles_annotated_questions():
    from decider_kit.inspect_agent import assignments, constant, source_of

    src = 'PATTERN_TAG: str = "#policy"\nQUESTIONS: dict[str, dict] = {\n    "a": {"type": "noul"},\n}\n'
    assert constant(src, "PATTERN_TAG") == "#policy"
    assert source_of(src, "QUESTIONS").startswith("QUESTIONS: dict[str, dict] = {") and len(assignments(src, "QUESTIONS")) == 1
