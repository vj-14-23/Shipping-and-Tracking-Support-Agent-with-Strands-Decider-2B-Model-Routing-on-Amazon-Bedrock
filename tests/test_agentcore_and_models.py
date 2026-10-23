"""One pattern per agent, env-driven model ids, and the AgentCore Memory/Gateway glue (offline)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from decider_kit.patterns import model_routing

ROOT = Path(__file__).resolve().parent.parent


def test_one_pattern_per_agent():
    import ast

    for f in ("agent/decision.py", "examples/memory_agent.py", "examples/gateway_agent.py"):
        tree = ast.parse((ROOT / f).read_text())
        tags = [n for n in tree.body if isinstance(n, ast.Assign) and any(getattr(t, "id", "") == "PATTERN_TAG" for t in n.targets)]
        assert len(tags) == 1, f
        assert "PATTERN_TAGS" not in (ROOT / f).read_text()


def test_model_ids_come_from_env(monkeypatch):
    from decider_kit.config import settings

    monkeypatch.setenv("BEDROCK_MODEL_ID", "us.anthropic.claude-haiku-4-5-20251001-v1:0")
    monkeypatch.setenv("BEDROCK_SMALL_MODEL_ID", "us.amazon.nova-micro-v1:0")
    monkeypatch.delenv("BEDROCK_LARGE_MODEL_ID", raising=False)
    monkeypatch.delenv("BENCH_LLM_MODEL_ID", raising=False)
    s = settings()
    assert s.large_model == s.bench_model == "us.anthropic.claude-haiku-4-5-20251001-v1:0"
    assert model_routing.default_tiers()["large"]["model_id"] == s.large_model


def test_memory_store_falls_back_to_process(monkeypatch):
    from decider_kit import agentcore

    monkeypatch.setattr(agentcore, "_deployed", lambda: {})
    for k in [k for k in __import__("os").environ if k.startswith("MEMORY_")]:
        monkeypatch.delenv(k)
    st = agentcore.AgentCoreMemoryStore()
    assert not st.enabled
    st.save("I am vegetarian")
    assert st.candidates("dinner") == ["I am vegetarian"]


def test_ids_from_env_and_deployment(monkeypatch):
    from decider_kit import agentcore

    monkeypatch.setenv("MEMORY_AGENT_MEMORY_ID", "mem-123")
    assert agentcore.memory_id("agent-memory") == "mem-123"
    monkeypatch.setattr(agentcore, "_deployed", lambda: {"gateways": {"tools": {"url": "https://gw/mcp", "auth_type": "AWS_IAM"}}})
    for k in [k for k in __import__("os").environ if k.startswith("AGENTCORE_GATEWAY_")]:
        monkeypatch.delenv(k)
    assert agentcore.gateway_url("tools") == ("https://gw/mcp", "AWS_IAM")


def test_deploy_adds_enabled_features(monkeypatch, tmp_path):
    sys.path.insert(0, str(ROOT / "scripts"))
    import deploy

    spec = tmp_path / "agentcore.json"
    spec.write_text(json.dumps({"runtimes": [{}], "memories": [], "agentCoreGateways": []}))
    feats = tmp_path / "features.yaml"
    feats.write_text("memory: {enabled: true, name: m1, strategies: [SEMANTIC], expiry_days: 7}\n"
                     "gateway: {enabled: true, name: gw, authorizer: AWS_IAM, targets: [{name: web, type: connector, connector: web-search}]}\n")
    calls = []
    monkeypatch.setattr(deploy, "SPEC", spec)
    monkeypatch.setattr(deploy, "FEATURES", feats)
    monkeypatch.setattr(deploy, "_run", lambda ac, args: calls.append(args))
    on = deploy.sync_features("agentcore")
    assert on == ["Memory 'm1'", "Gateway 'gw'"]
    assert calls[0][:3] == ["add", "memory", "--name"] and "SEMANTIC" in calls[0]
    assert calls[1][:2] == ["add", "gateway"] and "AWS_IAM" in calls[1]
    assert calls[2] == ["add", "gateway-target", "--gateway", "gw", "--name", "web", "--type", "connector", "--connector", "web-search"]


def test_kit_features_file_parses():
    import yaml

    f = yaml.safe_load((ROOT / "agent" / "features.yaml").read_text())
    assert set(f) == {"memory", "gateway"}


def test_data_load_json_and_csv(tmp_path, monkeypatch):
    import decider_kit.data as d

    monkeypatch.setattr(d, "DATA", tmp_path)
    (tmp_path / "orders.json").write_text('[{"id": "A1", "amount": 9.5}]')
    (tmp_path / "cities.csv").write_text("name,state\nMadurai,TN\n")
    assert d.load("orders") == [{"id": "A1", "amount": 9.5}]
    assert d.load("cities") == [{"name": "Madurai", "state": "TN"}]
