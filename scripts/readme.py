"""Write README.md for the participant's agent (the kit's own guide stays in docs/KIT.md).

    ./kit readme

Built from agent/AGENT.md, agent/decision.py, the benchmark, the deployment and the video link,
so every number in it comes from a real run. Keeps the kit credit.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from article import CREDIT, facts  # noqa: E402


def main() -> None:
    f = facts()
    dec_src = (ROOT / "agent" / "decision.py").read_text()
    doc = ast.get_docstring(ast.parse(dec_src)) or ""
    title = doc.splitlines()[0].replace("REUSABLE DECISION PATTERN:", "").strip() if doc else "decision pattern"
    bench = f.get("bench_table", "Run `./kit bench` to measure the decision against a Bedrock LLM.")
    dep = f.get("deployment")
    pitch = (re.search(r"\*\*Pitch:\*\*\s*(.+)", f["agent_md"]) or [None, ""])[1].strip()
    lines = [
        f"# {f['agent_name']}",
        "",
        f"**{pitch}**" if pitch else "",
        "",
        f"An agent on AWS that hands one decision to **Strands Decider 2B** and the conversation to **Amazon Bedrock**. "
        f"Decision pattern: `{f['pattern_tag']}`. Tags: `#strands-decider-2b` `{f['pattern_tag']}`.",
        "",
        f"- Video: {f['video_url'] or '(add the YouTube/Vimeo link)'}",
        "- Article: (add the AWS Builder Center link)",
        f"- Deployed: {'Amazon Bedrock AgentCore Runtime, ' + dep['region'] if dep else 'run `./kit deploy`'}",
        "",
        "## The project",
        "",
        re.sub(r"(?m)^(# .*|KIT EXAMPLE.*|These answers.*)\n", "", f["agent_md"]).strip(),
        "",
        "![Demo: the conversation and the live decision panel](submission/article/img/demo.png)" if (ROOT / "submission/article/img/demo.png").exists() else "",
        "",
        "## How it is built",
        "",
        "Strands Agents with Amazon Bedrock for the generative part, the tools in `agent/tools.py`, deployed to Amazon "
        "Bedrock AgentCore Runtime, and one decision handed to Strands Decider 2B at a clear seam in the agent's path.",
        "",
        *([f"Amazon Bedrock AgentCore features: {'; '.join(f['agentcore_features'])} (configured in `agent/features.yaml`, "
           "created by `./kit deploy`).", ""] if f["agentcore_features"] else []),
        "Every Amazon Bedrock model id is set in `.env` (`BEDROCK_MODEL_ID`, and `BEDROCK_SMALL/MEDIUM/LARGE_MODEL_ID` for "
        "routing), Amazon Nova by default.",
        "",
        "![Architecture](submission/article/img/architecture.png)" if (ROOT / "submission/article/img/architecture.png").exists() else "",
        "",
        f"## Reusable decision pattern: {title}",
        "",
        "The pattern lives in [`agent/decision.py`](agent/decision.py), labelled `REUSABLE DECISION PATTERN`. "
        "It contains the typed questions and their options, the wiring that puts the decision in the agent's path, "
        "and a note on how to reuse it:",
        "",
        "```text",
        doc.strip(),
        "```",
        "",
        "Typed questions:",
        "",
        "```python",
        f["questions_code"],
        "```",
        "",
        "## Measured",
        "",
        bench.strip(),
        "",
        "Reproduce with `./kit bench` (cases in `agent/eval_cases.jsonl`; charts in `submission/bench/`).",
        "",
        "## Run it",
        "",
        "```bash",
        "./kit setup        # checks your machine and AWS, sets up Strands Decider 2B (local model or hosted API)",
        "./kit demo         # web UI at http://localhost:8501",
        "./kit bench        # the decision vs an Amazon Bedrock LLM",
        "./kit deploy       # Amazon Bedrock AgentCore Runtime",
        "```",
        "",
        "Requirements: Python 3.10+, AWS credentials with Amazon Bedrock access, and for deploying, Node 20+ with "
        "the AgentCore CLI (`./kit agentcore-cli`).",
        "",
        "## Credits",
        "",
        f"{CREDIT} (https://github.com/awsugmdu). The kit's reusable library (`decider_kit/`, the demo UI, the "
        "video and article tooling, and the Kiro steering, skills and hooks) is the user group's; the agent in "
        "`agent/` is mine. Strands Decider: https://github.com/strands-labs/strands-decider (Apache-2.0).",
        "",
        "Licence: Apache-2.0 (see LICENSE).",
        "",
    ]
    (ROOT / "README.md").write_text("\n".join(lines))
    print("[readme] wrote README.md (the kit guide is docs/KIT.md)")


if __name__ == "__main__":
    main()
