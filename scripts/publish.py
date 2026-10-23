"""Create the participant's public GitHub repository and push (needs `gh auth login`).

    ./kit publish my-decider-agent

Refuses to publish while agent/ is still the kit example, while a secret is found, or without a
LICENSE. Writes submission/SUBMISSION.md with the links to submit and the manual steps left.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def run(cmd: list[str], check: bool = True) -> str:
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    if check and r.returncode != 0:
        sys.exit(f"{' '.join(cmd)} failed:\n{r.stdout}{r.stderr}")
    return r.stdout.strip()


def submission_md(repo_url: str | None = None) -> None:
    """Write submission/SUBMISSION.md, keeping links already filled in (./kit video creates it first)."""
    p = ROOT / "submission" / "SUBMISSION.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    existing = p.read_text() if p.exists() else ""
    repo_url = repo_url or next((ln.split(":", 1)[1].strip() for ln in existing.splitlines() if ln.startswith("- Repository:")),
                                "<./kit publish ... fills this in>")
    video = next((ln.split(":", 1)[1].strip() for ln in existing.splitlines() if ln.startswith("- Video:")), "")
    article = next((ln.split(":", 1)[1].strip() for ln in existing.splitlines() if ln.startswith("- Article:")), "")
    dep = ROOT / "submission" / "deployment.json"
    arn = json.loads(dep.read_text())["runtime_arn"] if dep.exists() else "(not deployed)"
    sys.path.insert(0, str(ROOT))
    from decider_kit.inspect_agent import constant

    tag = constant((ROOT / "agent" / "decision.py").read_text(), "PATTERN_TAG") or "#<pattern tag>"
    p.write_text(f"""# Submission: Agent Experience Hackathon (Strands Decider)

Submit before 23 October 2026, 11:59 p.m. PT on the hackathon page.

- Repository: {repo_url}
- Video: {video or "<paste the public YouTube/Vimeo link after uploading submission/video/demo.mp4>"}
- Article: {article or "<paste the AWS Builder Center link after publishing submission/article/>"}
- Tags: #strands-decider-2b {tag}
- Agent on AWS: {arn}

Left to do by hand:
1. Upload submission/video/demo.mp4 to YouTube or Vimeo as Public, and paste the link above.
2. Publish the article on AWS Builder Center (submission/article/fields.md + body.md + cover.png + img/), with the two tags.
3. Submit the three links on the hackathon page.
""")


def main() -> None:
    args = dict(a.split("=", 1) for a in sys.argv[1:] if "=" in a)
    name = args.get("NAME") or (sys.argv[1] if len(sys.argv) > 1 and "=" not in sys.argv[1] else "")
    if "IS_KIT_EXAMPLE" in (ROOT / "agent" / "decision.py").read_text():
        sys.exit("agent/ is still the kit example. Build your own agent first (/new-agent): the rules require an original agent.")
    if subprocess.run([sys.executable, "scripts/secret_scan.py"], cwd=ROOT).returncode != 0:
        sys.exit("remove the secrets above first")
    if not (ROOT / "LICENSE").exists():
        sys.exit("a LICENSE (OSI-approved) is required")
    sys.path.insert(0, str(ROOT / "scripts"))
    import tools

    os.environ["PATH"] = tools.with_path()["PATH"]  # kit-installed git and gh
    if not tools.which("gh") or not tools.which("git"):
        sys.exit("git and the GitHub CLI are needed: ./kit tools install base")
    if subprocess.run(["gh", "auth", "status"], capture_output=True).returncode != 0:
        sys.exit("log in to GitHub first: ./kit gh-login")
    if not (ROOT / ".git").exists():  # the kit came as a download: start the participant's own repository
        run(["git", "init", "-q", "-b", "main"])
        if not run(["git", "config", "user.email"], check=False):
            login = run(["gh", "api", "user", "-q", ".login"], check=False) or "participant"
            run(["git", "config", "user.name", login])
            run(["git", "config", "user.email", f"{login}@users.noreply.github.com"])
    remote = run(["git", "remote", "get-url", "origin"], check=False)
    if "github.com" not in remote or "decider-hackathon-kit" in remote:
        if not name:
            sys.exit("give the repository a name: ./kit publish my-decider-agent")
        if remote:
            run(["git", "remote", "rename", "origin", "kit"], check=False)
        run(["git", "add", "-A"])
        run(["git", "commit", "-q", "-m", "My Strands Decider hackathon agent"], check=False)
        run(["gh", "repo", "create", name, "--public", "--source", ".", "--push",
             "--description", "Agent on AWS with a Strands Decider 2B decision and Amazon Bedrock (Agent Experience Hackathon)"])
    else:
        run(["git", "add", "-A"])
        run(["git", "commit", "-q", "-m", "Update hackathon submission"], check=False)
        run(["git", "push", "-q"])
    url = run(["gh", "repo", "view", "--json", "url", "-q", ".url"])
    submission_md(url)
    run(["git", "add", "submission/SUBMISSION.md"], check=False)
    run(["git", "commit", "-q", "-m", "Submission links"], check=False)
    run(["git", "push", "-q"], check=False)
    print(f"[publish] {url}\n[publish] next: submission/SUBMISSION.md")


if __name__ == "__main__":
    main()
