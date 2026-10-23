"""Deploy the agent to Amazon Bedrock AgentCore Runtime, invoke it, or remove it.

    ./kit deploy                 # python scripts/deploy.py deploy
    ./kit invoke "..."       # python scripts/deploy.py invoke "..."
    ./kit destroy                # python scripts/deploy.py destroy

Deploy:
  1. Finds the AgentCore CLI (./kit agentcore-cli) and your AWS account and region.
  2. Copies agent/ and decider_kit/ into deploy/app/agent/ (the runtime's code).
  3. Sets the runtime's environment (decider URL and key, Bedrock model) in
     deploy/agentcore/agentcore.json for the deploy only, then restores the file, so keys are
     never committed.
  4. Adds the AgentCore features enabled in agent/features.yaml (Memory, Gateway and its targets)
     to the project with `agentcore add ...`, once.
  5. Runs `agentcore deploy -y` (CDK; about 5 minutes the first time) and records the runtime ARN,
     memory ids and gateway URLs in submission/deployment.json (so local runs use them too).

The deployed agent calls the decider over HTTPS, so the decider must be reachable from AWS:
the AWS User Group Madurai hosted API or your own deployed decider. A decider on your laptop is
not; set DEPLOY_DECIDER_URL and DEPLOY_DECIDER_API_KEY in .env in that case.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
DEPLOY = ROOT / "deploy"
APP = DEPLOY / "app" / "agent"
SPEC = DEPLOY / "agentcore" / "agentcore.json"
OUT = ROOT / "submission" / "deployment.json"
FEATURES = ROOT / "agent" / "features.yaml"
STATE = DEPLOY / "agentcore" / ".cli" / "deployed-state.json"


def cli() -> str:
    sys.path.insert(0, str(ROOT / "scripts"))
    import tools

    os.environ["PATH"] = tools.with_path()["PATH"]  # kit-installed node and AgentCore CLI
    bin_ = Path.home() / ".local/agentcore-cli/node_modules/.bin"
    for c in (tools.which("agentcore"), str(bin_ / ("agentcore.cmd" if sys.platform == "win32" else "agentcore")),
              str(Path.home() / ".npm-global/bin/agentcore")):
        if c and Path(c).exists():
            v = subprocess.run([c, "--version"], capture_output=True, text=True).stdout.strip()
            if v[:1].isdigit():  # the npm AgentCore CLI (not the older Python starter toolkit)
                return c
    sys.exit("AgentCore CLI not found. Install it with: ./kit agentcore-cli   (Node 20+; no sudo needed)")


def decider_env() -> dict[str, str]:
    from decider_kit.config import UGMDU_DECIDER_URL, load_dotenv, settings

    load_dotenv()
    s = settings()
    url = os.environ.get("DEPLOY_DECIDER_URL") or (s.decider_url if s.decider_mode != "local" else "")
    key = os.environ.get("DEPLOY_DECIDER_API_KEY") or (s.decider_api_key if s.decider_mode != "local" else "")
    if not url:
        sys.exit("Your decider runs on this laptop, which AWS cannot reach. For the deployed agent, set in .env:\n"
                 f"  DEPLOY_DECIDER_URL={UGMDU_DECIDER_URL}\n  DEPLOY_DECIDER_API_KEY=<your AWS User Group Madurai key>\n"
                 "(or your own deployed decider's URL), then run ./kit deploy again.")
    mode = "ugmdu" if url.rstrip("/") == UGMDU_DECIDER_URL else ("custom" if key else "local")
    # The deployed agent always uses Amazon Bedrock (the submission requires it), whatever LLM_PROVIDER
    # is set for local building.
    return {"DECIDER_MODE": mode, "DECIDER_URL": url, "DECIDER_API_KEY": key, "LLM_PROVIDER": "bedrock",
            "BEDROCK_MODEL_ID": s.bedrock_model,
            "BEDROCK_SMALL_MODEL_ID": s.small_model, "BEDROCK_MEDIUM_MODEL_ID": s.medium_model,
            "BEDROCK_LARGE_MODEL_ID": s.large_model, "DEMO_EAGER": os.environ.get("DEMO_EAGER", "0")}


def features() -> dict:
    import yaml

    return (yaml.safe_load(FEATURES.read_text()) or {}) if FEATURES.exists() else {}


def _run(ac: str, args: list[str]) -> None:
    print("[deploy] agentcore " + " ".join(args))
    r = subprocess.run([ac, *args, "--json"], cwd=DEPLOY, capture_output=True, text=True)
    out = (r.stdout or r.stderr).strip()
    if r.returncode != 0 or '"success":false' in out.replace(" ", ""):
        sys.exit(f"[deploy] failed: {out[-1500:]}")


def sync_features(ac: str) -> list[str]:
    """Add the Memory and Gateway enabled in agent/features.yaml to agentcore.json (idempotent)."""
    f, spec = features(), json.loads(SPEC.read_text())
    on: list[str] = []
    m = f.get("memory") or {}
    have = {x["name"] for x in spec.get("memories", [])}
    if m.get("enabled"):
        on.append(f"Memory '{m['name']}'")
        if m["name"] not in have:
            _run(ac, ["add", "memory", "--name", m["name"], "--strategies", ",".join(m.get("strategies") or ["SEMANTIC"]),
                      "--expiry", str(m.get("expiry_days", 30))])
    elif m.get("name") in have:
        print(f"[deploy] note: memory '{m['name']}' is disabled in features.yaml but still in the project; "
              f"remove it with: cd deploy && agentcore remove memory --name {m['name']}")
    g = f.get("gateway") or {}
    gws = {x["name"]: x for x in spec.get("agentCoreGateways", [])}
    if g.get("enabled"):
        on.append(f"Gateway '{g['name']}'")
        if g["name"] not in gws:
            _run(ac, ["add", "gateway", "--name", g["name"], "--protocol-type", "MCP",
                      "--authorizer-type", g.get("authorizer", "AWS_IAM")])
        have_t = {t["name"] for t in gws.get(g["name"], {}).get("targets", [])}
        for t in g.get("targets") or []:
            if t["name"] in have_t:
                continue
            args = ["add", "gateway-target", "--gateway", g["name"]]
            for k, v in t.items():
                v = ",".join(map(str, v)) if isinstance(v, list) else str(v)
                if k in ("schema", "tool-schema-file") and not v.startswith("s3://"):
                    v = str((ROOT / v).resolve())
                args += [f"--{k}", v]
            _run(ac, args)
    elif g.get("name") in gws:
        print(f"[deploy] note: gateway '{g['name']}' is disabled in features.yaml but still in the project; "
              f"remove it with: cd deploy && agentcore remove gateway --name {g['name']}")
    return on


def deployed_resources() -> dict:
    """Memory ids and gateway URLs from the AgentCore CLI's deployed state."""
    try:
        res = next(iter(json.loads(STATE.read_text())["targets"].values()))["resources"]
    except (OSError, KeyError, StopIteration, json.JSONDecodeError):
        return {}
    spec = json.loads(SPEC.read_text())
    auth = {x["name"]: x.get("authorizerType", "NONE") for x in spec.get("agentCoreGateways", [])}
    return {"memories": {k: v.get("memoryId") for k, v in (res.get("memories") or {}).items()},
            "gateways": {k: {"url": v.get("gatewayUrl"), "auth_type": auth.get(k, "NONE")}
                         for k, v in ((res.get("mcp") or {}).get("gateways") or {}).items() if v.get("gatewayUrl")}}


def account_region() -> tuple[str, str]:
    import boto3

    from decider_kit.config import settings

    region = settings().aws_region
    return boto3.client("sts", region_name=region).get_caller_identity()["Account"], region


def package() -> None:
    for name in ("agent", "decider_kit"):
        dst = APP / name
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(ROOT / name, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "eval_cases.jsonl", "demo_script.yaml"))


def deploy() -> None:
    ac = cli()
    env = decider_env()
    acct, region = account_region()
    (DEPLOY / "agentcore" / "aws-targets.json").write_text(json.dumps([{"name": "default", "account": acct, "region": region}], indent=2))
    package()
    cdk = DEPLOY / "agentcore" / "cdk"
    if not (cdk / "node_modules").exists():
        print("[deploy] installing the CDK app's dependencies (once)...")
        subprocess.run([shutil.which("npm") or "npm", "ci", "--silent"], cwd=cdk, check=True)
    on = sync_features(ac)
    if on:
        print("[deploy] AgentCore features: " + ", ".join(on))
    original = SPEC.read_text()
    spec = json.loads(original)
    spec["runtimes"][0]["envVars"] = [{"name": k, "value": v} for k, v in env.items() if v != ""]
    SPEC.write_text(json.dumps(spec, indent=2))
    print(f"[deploy] deploying to account ...{acct[-4:]} in {region} (about 5 minutes the first time)...")
    t0 = time.time()
    try:
        r = subprocess.run([ac, "deploy", "--json"], cwd=DEPLOY, capture_output=True, text=True,
                           env={**os.environ, "AWS_REGION": region})
    finally:
        SPEC.write_text(original)  # keys never stay in the committed config
    if r.returncode != 0:
        print(r.stdout[-3000:], r.stderr[-3000:])
        sys.exit("[deploy] failed (see above). Common fixes: Bedrock model access, AgentCore region support, CDK bootstrap (npx cdk bootstrap).")
    arn = runtime_arn(ac)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"runtime_arn": arn, "region": region, "deployed_at": time.time(),
                               "deploy_seconds": round(time.time() - t0), "decider_mode": env["DECIDER_MODE"],
                               "bedrock_model": env["BEDROCK_MODEL_ID"], "eager": env["DEMO_EAGER"] == "1",
                               **deployed_resources()}, indent=2))
    print(f"[deploy] done in {time.time() - t0:.0f} s: {arn}\n[deploy] try it: ./kit invoke \"hello\"")


def runtime_arn(ac: str) -> str:
    r = subprocess.run([ac, "status", "--json"], cwd=DEPLOY, capture_output=True, text=True)
    text = r.stdout
    try:
        data = json.loads(text)
        found = []

        def walk(x: object) -> None:
            if isinstance(x, dict):
                for v in x.values():
                    walk(v)
            elif isinstance(x, list):
                for v in x:
                    walk(v)
            elif isinstance(x, str) and ":runtime/" in x and x.startswith("arn:aws"):
                found.append(x)

        walk(data)
        if found:
            return found[0].split("/runtime-endpoint/")[0]
    except json.JSONDecodeError:
        pass
    import re

    m = re.search(r"arn:aws:bedrock-agentcore:[\w-]+:\d+:runtime/[\w-]+", text)
    if m:
        return m.group(0)
    sys.exit(f"[deploy] deployed, but could not read the runtime ARN from `agentcore status --json`:\n{text[:1500]}")


def invoke(msg: str, session: str | None = None) -> dict:
    import boto3

    d = json.loads(OUT.read_text())
    c = boto3.client("bedrock-agentcore", region_name=d["region"])
    sid = session or f"invoke-{uuid.uuid4().hex}"
    r = c.invoke_agent_runtime(agentRuntimeArn=d["runtime_arn"], runtimeSessionId=sid, payload=json.dumps({"prompt": msg}).encode())
    body = r["response"].read()
    return json.loads(body)


def destroy() -> None:
    ac = cli()
    acct, region = account_region()
    (DEPLOY / "agentcore" / "aws-targets.json").write_text(json.dumps([{"name": "default", "account": acct, "region": region}], indent=2))
    original = SPEC.read_text()
    try:
        subprocess.run([ac, "remove", "all", "-y"], cwd=DEPLOY)
        subprocess.run([ac, "deploy", "-y"], cwd=DEPLOY)
    finally:
        SPEC.write_text(original)  # keep the project (runtime, features) so ./kit deploy works again
    OUT.unlink(missing_ok=True)
    print("[deploy] removed")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "deploy"
    if cmd == "deploy":
        deploy()
    elif cmd == "invoke":
        print(json.dumps(invoke(" ".join(sys.argv[2:]) or "Hello, what can you do?"), indent=1))
    elif cmd == "destroy":
        destroy()
    else:
        sys.exit(__doc__)

