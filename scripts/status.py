"""Where the participant is in the hackathon flow. Run by the SessionStart and Stop hooks.

    python scripts/status.py          # full checklist
    python scripts/status.py --next   # only the next step
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def steps() -> list[tuple[str, bool, str]]:
    env = (ROOT / ".env").read_text() if (ROOT / ".env").exists() else ""
    decision = (ROOT / "agent" / "decision.py").read_text() if (ROOT / "agent" / "decision.py").exists() else ""
    own = "IS_KIT_EXAMPLE" not in decision
    bench = ROOT / "submission" / "bench" / "results.json"
    bench_own = bench.exists() and own and bench.stat().st_mtime > (ROOT / "agent" / "decision.py").stat().st_mtime
    dep = ROOT / "submission" / "deployment.json"
    video = ROOT / "submission" / "video" / "demo.mp4"
    article = ROOT / "submission" / "article" / "body.md"
    art_done = article.exists() and "TODO" not in article.read_text()
    sub = (ROOT / "submission" / "SUBMISSION.md").read_text() if (ROOT / "submission" / "SUBMISSION.md").exists() else ""
    published = "github.com" in sub
    return [
        ("Setup (./kit setup)", "DECIDER_MODE=" in env, "./kit setup  (or /setup in Kiro)"),
        ("Your own agent replaces the kit example (/new-agent)", own, "In Kiro: /new-agent and describe your idea"),
        ("Benchmark of your decision (./kit bench)", bench_own, "./kit bench"),
        ("Deployed to AWS (./kit deploy)", dep.exists() and own, "./kit deploy"),
        ("Builder Center article (/write-article)", art_done and own, "In Kiro: /write-article"),
        ("Demo video (./kit video)", video.exists() and own, "./kit video --target agentcore"),
        ("Public repo (./kit publish)", published, "./kit check, then ./kit publish <repo>"),
    ]


def main() -> None:
    s = steps()
    nxt = next((x for x in s if not x[1]), None)
    if "--next" in sys.argv:
        print(f"Next hackathon step: {nxt[2]}" if nxt else "All steps done. Submit your three links on the hackathon page.")
        return
    print("Strands Decider hackathon progress (AWS User Group Madurai kit)")
    for name, done, _ in s:
        print(f"  [{'x' if done else ' '}] {name}")
    if nxt:
        print(f"Next: {nxt[2]}")
    dep = ROOT / "submission" / "deployment.json"
    if dep.exists():
        print("Deployed: " + json.loads(dep.read_text()).get("runtime_arn", "?"))


if __name__ == "__main__":
    main()
