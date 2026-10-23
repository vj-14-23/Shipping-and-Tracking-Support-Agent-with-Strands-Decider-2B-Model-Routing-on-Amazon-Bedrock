"""Check the submission against the hackathon rules. PASS / WARN / FAIL per requirement.

    ./kit check                                   # everything
    python scripts/check_submission.py --only pattern
"""

from __future__ import annotations

import ast
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
TAGS = {"#tool-selection", "#guardrails", "#policy", "#model-routing", "#context-memory"}
CREDIT = "AWS User Group Madurai"
OSI = ("Apache License", "MIT License", "BSD", "Mozilla Public License", "GNU GENERAL PUBLIC LICENSE")
results: list[tuple[str, str, str]] = []


def res(level: str, name: str, detail: str = "") -> None:
    results.append((level, name, detail))


def check_pattern() -> None:
    p = ROOT / "agent" / "decision.py"
    if not p.exists():
        res("FAIL", "decision pattern file", "agent/decision.py is missing")
        return
    src = p.read_text()
    tree = ast.parse(src)
    doc = ast.get_docstring(tree) or ""
    (res("PASS", "pattern labelled") if doc.startswith("REUSABLE DECISION PATTERN:") else
     res("FAIL", "pattern labelled", "the docstring must start with 'REUSABLE DECISION PATTERN:'"))
    for sec in ("What it does", "Typed questions", "Wiring", "reuse"):
        if sec.lower() not in doc.lower():
            res("FAIL", f"pattern note: '{sec}' section", "the rules ask for the questions, the wiring and a usage note")
    from decider_kit.inspect_agent import assignments, constant

    tag = constant(src, "PATTERN_TAG")
    if tag not in TAGS:
        res("FAIL", "PATTERN_TAG", f"must be one of {sorted(TAGS)}")
    else:
        res("PASS", "PATTERN_TAG", tag)
    if assignments(src, "PATTERN_TAGS") or len(assignments(src, "PATTERN_TAG")) > 1:
        res("FAIL", "one decision pattern", "the rules ask for exactly one pattern: keep a single PATTERN_TAG")
    (res("PASS", "QUESTIONS defined") if assignments(src, "QUESTIONS") else res("FAIL", "QUESTIONS defined", "the typed questions must be in QUESTIONS"))
    if "IS_KIT_EXAMPLE" in src:
        res("FAIL", "your own agent", "agent/ is still the kit example: run /new-agent (an original agent is required)")
    else:
        res("PASS", "your own agent", "kit example removed")


def check_agent() -> None:
    a = (ROOT / "agent" / "agent.py").read_text() if (ROOT / "agent" / "agent.py").exists() else ""
    (res("PASS", "LLM through Strands Agents") if any(x in a for x in ("agent_model", "bedrock_model", "BedrockModel")) else
     res("FAIL", "LLM through Strands Agents", "agent.py must build its Agent with decider_kit.llm.agent_model()"))
    from decider_kit.llm import provider

    if provider() != "bedrock":
        res("WARN", "Amazon Bedrock", f"LLM_PROVIDER={provider()} is fine for building, but the submission needs Amazon "
            "Bedrock for the generative part: ./kit deploy uses Bedrock; record the video with TARGET=agentcore")
    else:
        res("PASS", "Amazon Bedrock", "LLM_PROVIDER=bedrock")
    run = ROOT / "submission" / "video" / "run.json"
    if run.exists():
        mids = {t.get("out", {}).get("model_id", "") for t in json.loads(run.read_text())}
        other = sorted(m for m in mids if m and not re.match(r"^((us|eu|apac|global)\.)?(amazon|anthropic|meta|mistral|cohere|ai21|deepseek|openai|qwen|writer|google|nvidia|minimax|moonshot)\.", m))
        if other:  # e.g. qwen3.5:4b (Ollama) or gpt-oss-20b (hosted)
            res("WARN", "video on Amazon Bedrock", f"the video used {other}; re-record with ./kit video --target agentcore")
    (res("PASS", "Strands Decider in the agent's path") if "Decider" in a and "decision" in a else
     res("FAIL", "Strands Decider in the agent's path", "agent.py must wire agent/decision.py in"))
    cases = ROOT / "agent" / "eval_cases.jsonl"
    rows = [json.loads(x) for x in cases.read_text().splitlines() if x.strip()] if cases.exists() else []
    n, nt = len(rows), sum(1 for r in rows if r.get("split", "test") == "test")
    (res("PASS", "labelled eval cases", f"{n} ({nt} held out)") if n >= 24 and nt >= 12 else
     res("WARN", "labelled eval cases", f"{n} ({nt} held out); 24+ with 12+ in the test split makes the numbers credible"))


def check_measured() -> None:
    p = ROOT / "submission" / "bench" / "results.json"
    if not p.exists():
        res("WARN", "measured comparison", "./kit bench (latency/cost vs an LLM is a judging bonus)")
        return
    r = json.loads(p.read_text())
    if p.stat().st_mtime < (ROOT / "agent" / "decision.py").stat().st_mtime:
        res("WARN", "measured comparison", "decision.py changed after the last bench: run ./kit bench again")
    elif "llm" in r["summary"]:
        res("PASS", "measured comparison", f"decider {r['summary']['decider']['accuracy']:.0%} vs LLM {r['summary']['llm']['accuracy']:.0%}, split {r.get('split', 'all')}")
    else:
        res("WARN", "measured comparison", "no LLM baseline in the last bench")


def check_aws() -> None:
    p = ROOT / "submission" / "deployment.json"
    (res("PASS", "agent on AWS", json.loads(p.read_text()).get("runtime_arn", "")) if p.exists() else
     res("FAIL", "agent on AWS", "./kit deploy (the rules require a working agent on AWS)"))


def check_video() -> None:
    v = ROOT / "submission" / "video" / "demo.mp4"
    if not v.exists():
        res("FAIL", "demo video", "./kit video")
        return
    sys.path.insert(0, str(ROOT / "scripts"))
    from make_video import duration

    d = duration(v)
    (res("PASS", "demo video under 3 minutes", f"{d:.0f} s") if d < 180 else res("FAIL", "demo video under 3 minutes", f"{d:.0f} s"))
    sub = (ROOT / "submission" / "SUBMISSION.md").read_text() if (ROOT / "submission" / "SUBMISSION.md").exists() else ""
    (res("PASS", "public video link") if re.search(r"(youtube\.com|youtu\.be|vimeo\.com|facebook\.com|youku\.com)", sub) else
     res("WARN", "public video link", "upload demo.mp4 to YouTube or Vimeo (public) and paste the link in submission/SUBMISSION.md"))


def check_article() -> None:
    body = ROOT / "submission" / "article" / "body.md"
    fields = ROOT / "submission" / "article" / "fields.md"
    if not body.exists():
        res("FAIL", "Builder Center article", "/write-article, then ./kit article")
        return
    text = body.read_text()
    if "TODO" in text:
        res("FAIL", "article written", "body.md still has TODO sections")
    if CREDIT not in text:
        res("WARN", "kit credit in the article", f"keep '{CREDIT}' in the footer")
    f = fields.read_text() if fields.exists() else ""
    (res("PASS", "tags") if "strands-decider-2b" in f and any(t[1:] in f for t in TAGS) else
     res("FAIL", "tags", "strands-decider-2b and one pattern tag"))


def check_repo() -> None:
    lic = (ROOT / "LICENSE").read_text()[:400] if (ROOT / "LICENSE").exists() else ""
    (res("PASS", "OSI licence", lic.splitlines()[0].strip()) if any(o in lic for o in OSI) else res("FAIL", "OSI licence", "add an OSI-approved LICENSE"))
    readme = (ROOT / "README.md").read_text() if (ROOT / "README.md").exists() else ""
    (res("PASS", "kit credit in README") if CREDIT in readme else res("WARN", "kit credit in README", "./kit readme"))
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "secret_scan.py")], capture_output=True, text=True)
    (res("PASS", "no secrets in the repo") if r.returncode == 0 else res("FAIL", "no secrets in the repo", r.stdout.strip()))
    remote = subprocess.run(["git", "remote", "get-url", "origin"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    (res("PASS", "repository pushed", remote) if "github.com" in remote else res("WARN", "repository pushed", "./kit publish <repo>"))


CHECKS = {"pattern": check_pattern, "agent": check_agent, "measured": check_measured, "aws": check_aws,
          "video": check_video, "article": check_article, "repo": check_repo}


def main() -> None:
    only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None
    for name, fn in CHECKS.items():
        if only and name != only:
            continue
        try:
            fn()
        except Exception as e:  # noqa: BLE001
            res("FAIL", name, f"check crashed: {e}")
    color = {"PASS": "\033[32m", "WARN": "\033[33m", "FAIL": "\033[31m"}
    for level, name, detail in results:
        print(f"  {color[level]}{level}\033[0m {name}" + (f"  ({detail})" if detail else ""))
    fails = sum(1 for r in results if r[0] == "FAIL")
    print(f"\n{fails} FAIL, {sum(1 for r in results if r[0] == 'WARN')} WARN" + ("" if fails else ". Ready to submit once the WARN items are handled."))
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
