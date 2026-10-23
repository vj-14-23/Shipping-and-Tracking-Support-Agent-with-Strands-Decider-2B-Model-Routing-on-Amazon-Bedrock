"""Set up the kit: check this machine, choose where Strands Decider 2B runs, test everything.

    ./kit setup                    # interactive
    python scripts/setup.py --yes --mode ugmdu --key dcd_live_...      # non-interactive

Steps
  1. Machine check: OS, chip, RAM, free disk, GPU (Apple silicon / NVIDIA / CPU), Python, git,
     GitHub CLI, Node + AgentCore CLI (for deploying to AWS), Kiro.
  2. Where should the agent's LLM run? (always called through a Strands Agent)
       bedrock - Amazon Bedrock (default; the submission needs it): checks your AWS credentials
       local   - a model on this machine through Ollama: no cloud, no cost. Choose its size.
       ugmdu   - Qwen3.5 or gpt-oss on the AWS User Group Madurai cloud (same key as the decider)
     Then one real tool call through a Strands Agent proves the model can drive an agent.
  3. Where should Strands Decider 2B run? The script recommends one from step 1:
       local  - download the 2B model from Hugging Face (about 5 GB) and serve it on this machine
                (Apple silicon: MLX; NVIDIA: CUDA; other CPUs work but are slow)
       ugmdu  - use the AWS User Group Madurai hosted API (nothing to download; needs a key)
       custom - any compatible endpoint (your own deployment)
     A local decider can also read images (--vision: v19 or the v1 Qwen3.5 release; +0.7 GB).
  4. Writes .env, starts the local server if chosen, and asks one real question to prove it works.

Completely local (no cloud, no cost): python scripts/setup.py --llm local --mode local
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from decider_kit.config import DEFAULT_BEDROCK_MODEL, DEFAULT_DECIDER_MODEL, DEFAULT_MEDIUM_MODEL, DEFAULT_SMALL_MODEL, LOCAL_DECIDER_URL, UGMDU_DECIDER_URL  # noqa: E402

MODEL_CHOICES = ["us.amazon.nova-pro-v1:0", "us.amazon.nova-lite-v1:0", "us.amazon.nova-micro-v1:0",
                 "us.amazon.nova-premier-v1:0", "us.anthropic.claude-haiku-4-5-20251001-v1:0", "us.anthropic.claude-sonnet-4-6"]
V19 = "StrandsAgents/strands-decider-2B-hobson-v19"
DECIDER_REF = "b9fc836"  # strands-decider commit the kit was tested with (needs the qwen3.5 v1 loader)
GREEN, YELLOW, RED, DIM, END = "\033[32m", "\033[33m", "\033[31m", "\033[2m", "\033[0m"


def ok(msg: str) -> None:
    print(f"  {GREEN}OK{END}   {msg}")


def warn(msg: str) -> None:
    print(f"  {YELLOW}WARN{END} {msg}")


def bad(msg: str) -> None:
    print(f"  {RED}FAIL{END} {msg}")


def sh(cmd: list[str], timeout: int = 20) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout).stdout.strip()
    except Exception:  # noqa: BLE001
        return ""


# ---- 1. machine -----------------------------------------------------------------------------------


def ram_gb() -> float:
    if sys.platform == "darwin":
        return int(sh(["sysctl", "-n", "hw.memsize"]) or 0) / 2**30
    if sys.platform == "win32":
        import ctypes

        class Mem(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong), ("ullTotalPhys", ctypes.c_ulonglong),
                        ("ullAvailPhys", ctypes.c_ulonglong), ("ullTotalPageFile", ctypes.c_ulonglong),
                        ("ullAvailPageFile", ctypes.c_ulonglong), ("ullTotalVirtual", ctypes.c_ulonglong),
                        ("ullAvailVirtual", ctypes.c_ulonglong), ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]

        m = Mem()
        m.dwLength = ctypes.sizeof(Mem)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))  # type: ignore[attr-defined]
        return m.ullTotalPhys / 2**30
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemTotal"):
                return int(line.split()[1]) / 2**20
    except OSError:
        pass
    return 0.0


def machine() -> dict:
    print("\n1. This machine")
    info = {"os": platform.system(), "arch": platform.machine(), "python": platform.python_version(), "ram_gb": round(ram_gb(), 1),
            "free_disk_gb": round(shutil.disk_usage(ROOT).free / 2**30, 1), "cpus": os.cpu_count()}
    info["apple_silicon"] = info["os"] == "Darwin" and info["arch"] == "arm64"
    gpu = sh(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"])
    info["nvidia"] = gpu.splitlines()[0] if gpu else ""
    chip = sh(["sysctl", "-n", "machdep.cpu.brand_string"]) if info["os"] == "Darwin" else platform.processor()
    ok(f"{info['os']} {info['arch']} ({chip or 'unknown CPU'}), {info['cpus']} CPUs, {info['ram_gb']} GB RAM, {info['free_disk_gb']} GB free")
    (ok if sys.version_info[:2] in ((3, 10), (3, 11), (3, 12), (3, 13)) else warn)(f"Python {info['python']}")
    if info["apple_silicon"]:
        ok("Apple silicon: the decider can run on the GPU through MLX")
    elif info["nvidia"]:
        ok(f"NVIDIA GPU: {info['nvidia']}")
    else:
        warn("no GPU found: a local decider runs on the CPU (slow: seconds per decision); the hosted API is faster")
    for tool, why in (("git", "version control"), ("gh", "publishing your repo (./kit publish)"), ("node", "the AgentCore CLI (./kit deploy)")):
        (ok if shutil.which(tool) else warn)(f"{tool}: {'found' if shutil.which(tool) else 'missing'} ({why})")
    import tools

    ac = tools.which("agentcore")
    acv = tools.version("agentcore") or "" if ac else ""
    if ac and acv[:1].isdigit():
        ok(f"AgentCore CLI {acv}")
    else:
        warn("AgentCore CLI not found: ./kit agentcore-cli  (needed for ./kit deploy; no sudo)")
    if shutil.which("kiro") or Path("/Applications/Kiro.app").exists():
        ok("Kiro found")
    else:
        warn("Kiro not found: https://kiro.dev  (the guided /hackathon flow runs in Kiro)")
    info["local_ok"] = info["ram_gb"] >= 8 and info["free_disk_gb"] >= 12
    info["local_good"] = info["local_ok"] and (info["apple_silicon"] or bool(info["nvidia"]))
    return info


# ---- 2. AWS ---------------------------------------------------------------------------------------


def aws(model_id: str, region: str) -> bool:
    print("\n2. AWS and Amazon Bedrock")
    try:
        import boto3

        ident = boto3.client("sts", region_name=region).get_caller_identity()
        acct = ident["Account"]
        ok(f"credentials work (account ...{acct[-4:]}, region {region})")
    except Exception as e:  # noqa: BLE001
        bad(f"no working AWS credentials ({type(e).__name__}). Run `aws configure` or `aws sso login`, then ./kit setup again.")
        return False
    os.environ.update({"LLM_PROVIDER": "bedrock", "BEDROCK_MODEL_ID": model_id, "AWS_REGION": region})
    if not llm_check():
        print(f"       {DIM}Enable model access in the Bedrock console (Model access), or pick another model with BEDROCK_MODEL_ID.{END}")
        return False
    return True


# ---- 2. the agent's LLM -----------------------------------------------------------------------------


def llm_check() -> bool:
    """One real tool call through a Strands Agent on LLM_PROVIDER: proves the model can drive an agent."""
    from strands import Agent, tool

    from decider_kit.llm import agent_model, describe

    calls: list[str] = []

    @tool
    def order_status(order_id: str) -> str:
        """Look up the delivery status of an order by its id."""
        calls.append(order_id)
        return f"Order {order_id} was delivered yesterday."

    where = describe()
    try:
        t0 = time.time()
        agent = Agent(model=agent_model(), tools=[order_status], callback_handler=None,
                      system_prompt="You are a support agent. Use your tools. Be brief.")
        reply = str(agent("Where is my order B2001?")).strip()
        s = time.time() - t0
    except Exception as e:  # noqa: BLE001
        bad(f"{where} failed: {type(e).__name__}: {str(e)[:300]}")
        return False
    if calls:
        ok(f"{where}: a Strands Agent called a tool ({calls[0]}) and replied in {s:.1f} s")
    else:
        warn(f"{where} replied in {s:.1f} s but did not call the tool; a larger model is more reliable for agents")
    print(f"       {DIM}{reply[:160]}{END}")
    return True


def ollama_up(url: str) -> dict | None:
    import urllib.request

    try:
        with urllib.request.urlopen(url.rstrip("/") + "/api/version", timeout=3) as r:
            return json.loads(r.read())
    except Exception:  # noqa: BLE001
        return None


def install_help() -> None:
    print("   Install Ollama (free, runs models on your machine), any one of:")
    if sys.platform == "darwin":
        print("     brew install ollama            (Homebrew), or the app from https://ollama.com/download")
    elif sys.platform.startswith("linux"):
        print("     curl -fsSL https://ollama.com/install.sh | sh")
    else:
        print("     the Windows installer from https://ollama.com/download")
    print("     docker run -d -p 11434:11434 -v ollama:/root/.ollama --name ollama ollama/ollama")


def setup_ollama(info: dict, model: str | None, assume_yes: bool) -> dict[str, str] | None:
    """Ollama running, the chosen model pulled. Returns the .env values, or None."""
    import urllib.request

    from decider_kit.llm import DEFAULT_LOCAL_MODEL, LOCAL_MODELS

    url = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
    if not ollama_up(url):
        import tools

        if not tools.which("ollama"):
            print("   Ollama is not installed.")
            if not tools.install(["ollama"], assume_yes=assume_yes) or not tools.which("ollama"):
                install_help()
                return None
        print("   starting ollama serve ...")
        subprocess.Popen([tools.which("ollama"), "serve"], stdout=open(ROOT / ".ollama.log", "w"), stderr=subprocess.STDOUT,
                         env=tools.with_path(), **({"start_new_session": True} if sys.platform != "win32" else {}))
        for _ in range(30):
            if ollama_up(url):
                break
            time.sleep(1)
        if not ollama_up(url):
            bad(f"Ollama is not running at {url}")
            install_help()
            return None
    ok(f"Ollama {ollama_up(url).get('version')} at {url}")
    ram = info["ram_gb"]
    fits = [m for m in LOCAL_MODELS if m["ram_gb"] <= max(ram - 6, 4)]  # leave room for the decider and the OS
    rec = DEFAULT_LOCAL_MODEL if any(m["id"] == DEFAULT_LOCAL_MODEL for m in fits) else (fits[-1]["id"] if fits else LOCAL_MODELS[0]["id"])
    if not model:
        print("   Local model for the agent (download size; all call tools; bigger is better at it):")
        for k, m in enumerate(LOCAL_MODELS, 1):
            flag = "  [recommended]" if m["id"] == rec else ("" if m in fits else f"  {YELLOW}(needs {m['ram_gb']}+ GB free RAM){END}")
            print(f"     {k}. {m['id']:<20} {m['gb']:>4} GB  {m['note']}{flag}")
        pick = "" if assume_yes else input(f"   choose 1-{len(LOCAL_MODELS)} or any Ollama model name ({rec}): ").strip()
        model = LOCAL_MODELS[int(pick) - 1]["id"] if pick.isdigit() and 1 <= int(pick) <= len(LOCAL_MODELS) else (pick or rec)
    print(f"   pulling {model} (first time only) ...")
    req = urllib.request.Request(url.rstrip("/") + "/api/pull", data=json.dumps({"model": model, "stream": False}).encode(),
                                 headers={"content-type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=3600) as r:
            status = json.loads(r.read()).get("status")
    except urllib.error.HTTPError as e:
        msg = e.read().decode(errors="replace")[:300]
        bad(f"could not pull {model}: {e.code} {msg}")
        if e.code == 412 or "newer version" in msg:
            print("       Upgrade Ollama (brew upgrade ollama, or https://ollama.com/download), then ./kit setup again.")
        return None
    ok(f"{model}: {status}")
    return {"LLM_PROVIDER": "local", "LLM_MODEL_ID": model, "OLLAMA_URL": url}


def choose_llm(aws_creds: bool, provider: str | None, assume_yes: bool) -> str:
    print("\n2. Where should the agent's LLM run? (called through a Strands Agent in every case)")
    print("   bedrock : Amazon Bedrock, e.g. Amazon Nova (the hackathon submission needs it; a few cents)")
    print("   local   : a model on this machine through Ollama; no cloud, no cost (1.2 to 6.6 GB download)")
    print("   ugmdu   : Qwen3.5 or gpt-oss on the AWS User Group Madurai cloud (your decider key)")
    rec = "bedrock" if aws_creds else "local"
    if provider:
        return provider
    if assume_yes:
        return rec
    got = input(f"   choose [bedrock/local/ugmdu] ({rec}): ").strip().lower() or rec
    return got if got in ("bedrock", "local", "ugmdu") else rec


def aws_creds(region: str) -> bool:
    try:
        import boto3

        boto3.client("sts", region_name=region).get_caller_identity()
        return True
    except Exception:  # noqa: BLE001
        return False


# ---- 3. the decider -------------------------------------------------------------------------------


def choose(info: dict, mode: str | None, assume_yes: bool) -> str:
    print("\n3. Where should Strands Decider 2B run?")
    rec = "local" if info["local_good"] else "ugmdu"
    print(f"   local  : download the 2B model ({DEFAULT_DECIDER_MODEL}, about 5 GB) and serve it here"
          f"{'  [recommended: ' + ('MLX on Apple silicon' if info['apple_silicon'] else 'your NVIDIA GPU') + ']' if rec == 'local' else ''}")
    if not info["local_ok"]:
        print(f"            {YELLOW}not advised here: needs 8 GB RAM and 12 GB free disk{END}")
    print(f"   ugmdu  : the AWS User Group Madurai hosted API, nothing to download (needs a key){'  [recommended]' if rec == 'ugmdu' else ''}")
    print("   custom : your own compatible endpoint")
    if mode:
        return mode
    if assume_yes:
        return rec
    got = input(f"   choose [local/ugmdu/custom] ({rec}): ").strip().lower() or rec
    return got if got in ("local", "ugmdu", "custom") else rec


def setup_local(info: dict, model: str = DEFAULT_DECIDER_MODEL, vision: bool = False) -> dict[str, str]:
    print("\n   Installing strands-decider and downloading the model (first time: a few minutes)...")
    extras = (["mlx"] if info["apple_silicon"] and not vision else []) + (["vision"] if vision else [])
    extra = f"[{','.join(extras)}]" if extras else ""
    pkg = f"strands-decider{extra} @ git+https://github.com/strands-labs/strands-decider@{DECIDER_REF}"
    has_pip = subprocess.run([sys.executable, "-m", "pip", "--version"], capture_output=True).returncode == 0
    if has_pip:
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", pkg], check=True)
    else:  # a uv-created venv has no pip
        subprocess.run(["uv", "pip", "install", "-q", "-p", sys.executable, pkg], check=True)
    from huggingface_hub import snapshot_download

    path = snapshot_download(model)
    cfg_file = next(Path(path) / n for n in ("strands_decider_config.json", "hobson_config.json")  # v19 uses the older name
                    if (Path(path) / n).exists())
    cfg = json.loads(cfg_file.read_text())
    snapshot_download(cfg["base_model"], revision=cfg.get("base_model_revision"),
                      allow_patterns=["*.json", "*.safetensors", "*.txt", "*.jinja", "*.model"])
    ok(f"model ready: {model} (base {cfg['base_model']}){' with the vision tower' if vision else ''}")
    # MLX is fastest on Apple silicon, but the vision tower runs on torch: Metal (mps) there
    device = ("mps" if vision else "mlx") if info["apple_silicon"] else ("cuda" if info["nvidia"] else "cpu")
    return {"DECIDER_MODE": "local", "DECIDER_URL": LOCAL_DECIDER_URL, "DECIDER_DEVICE": device, "DECIDER_MODEL": model,
            "DECIDER_VISION": "1" if vision else "0", "DECIDER_API_KEY": ""}


def start_local(env: dict[str, str]) -> subprocess.Popen:
    log = open(ROOT / ".decider-server.log", "w")
    exe = str(Path(sys.executable).parent / "strands-decider")
    if not Path(exe).exists():
        exe = shutil.which("strands-decider") or exe
    proc = subprocess.Popen([exe, "serve", env["DECIDER_MODEL"], "--port", "8099", "--device", env["DECIDER_DEVICE"],
                             *(["--vision"] if env.get("DECIDER_VISION") == "1" else [])],
                            stdout=log, stderr=subprocess.STDOUT, cwd=ROOT)
    (ROOT / ".decider-server.pid").write_text(str(proc.pid))
    return proc


def write_env(values: dict[str, str]) -> None:
    p = ROOT / ".env"
    cur: dict[str, str] = {}
    if p.exists():
        for line in p.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                cur[k.strip()] = v.strip()
    cur.update({k: v for k, v in values.items() if v is not None})
    p.write_text("# written by scripts/setup.py; never commit this file\n" + "".join(f"{k}={v}\n" for k, v in cur.items()))
    p.chmod(0o600)
    ok(f"wrote {p.name} ({', '.join(k for k in values)})")


def smoke(vision: bool = False) -> bool:
    print("\n4. One real decision")
    for k in list(os.environ):
        if k.startswith("DECIDER_"):
            del os.environ[k]
    from decider_kit import Decider, DeciderError

    d = Decider()
    for attempt in range(60):
        try:
            a = d.ask("Ticket: I was charged twice for my order, please refund one of the charges.",
                      {"refund": Decider.noul("Is the customer asking for a refund?"),
                       "team": Decider.choice("Which team should handle it?", {"billing": "payments and refunds", "shipping": "deliveries"})})
            ok(f"refund? {a['refund'].p_yes:.2f}  team: {a['team'].label} ({a['team'].confidence:.2f})  in {d.last_latency_ms:.0f} ms")
            if vision:
                img = ROOT / "tests" / "data" / "red-square.png"
                v = d.ask("", {"red": Decider.noul("Is the main shape in the image red?")}, images=[img])
                ok(f"image: red square? {v['red'].p_yes:.2f} in {d.last_latency_ms:.0f} ms")
            return True
        except DeciderError as e:
            if attempt == 0:
                print(f"   {DIM}waiting for the decider to come up...{END}")
            if "no Strands Decider" not in str(e):
                bad(str(e))
                return False
            time.sleep(5)
    bad("the decider did not answer; see .decider-server.log")
    return False


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--llm", choices=["bedrock", "local", "ugmdu"], help="where the agent's LLM runs")
    ap.add_argument("--llm-model", help="model id for --llm local/ugmdu (e.g. qwen3.5:4b, gpt-oss-20b)")
    ap.add_argument("--mode", choices=["local", "ugmdu", "custom"], help="where the decider runs")
    ap.add_argument("--vision", action="store_true", help="local decider reads images too (+0.7 GB)")
    ap.add_argument("--decider-model", help=f"local decider checkpoint (default {DEFAULT_DECIDER_MODEL}; or {V19})")
    ap.add_argument("--key", help="API key for the AWS User Group Madurai hosted API (decider and LLM)")
    ap.add_argument("--url", help="decider URL for --mode custom")
    ap.add_argument("--bedrock-model", default=os.environ.get("BEDROCK_MODEL_ID", DEFAULT_BEDROCK_MODEL))
    ap.add_argument("--region", default=os.environ.get("AWS_REGION", "us-east-1"))
    ap.add_argument("--yes", action="store_true", help="accept the recommendations")
    ap.add_argument("--skip-aws", action="store_true")
    ap.add_argument("--check-only", action="store_true", help="report the checks and the recommendation; change nothing")
    a = ap.parse_args()
    print("Strands Decider hackathon kit setup  (AWS User Group Madurai)")
    info = machine()
    creds = False if a.skip_aws else aws_creds(a.region)
    if a.check_only:
        aws_ok = aws(a.bedrock_model, a.region) if creds else False
        choose_llm(creds, "bedrock" if creds else "local", True)
        choose(info, "local" if info["local_good"] else "ugmdu", True)
        print(f"\n   Recommended: LLM {'bedrock' if creds else 'local'}, decider {'local' if info['local_good'] else 'ugmdu'}. Nothing was changed.")
        sys.exit(0 if aws_ok else 1)

    values: dict[str, str] = {"AWS_REGION": a.region}
    if os.environ.get("AWS_PROFILE"):
        values["AWS_PROFILE"] = os.environ["AWS_PROFILE"]
    llm = choose_llm(creds, a.llm, a.yes)
    key = a.key or os.environ.get("DECIDER_API_KEY") or ""
    if llm == "bedrock":
        if not a.yes and "BEDROCK_MODEL_ID" not in os.environ:
            print("\n   Amazon Bedrock model for your agent (any model you have access to; change it later in .env):")
            for k, m in enumerate(MODEL_CHOICES, 1):
                print(f"     {k}. {m}")
            pick = input(f"   choose 1-{len(MODEL_CHOICES)} or paste a model id ({a.bedrock_model}): ").strip()
            if pick.isdigit() and 1 <= int(pick) <= len(MODEL_CHOICES):
                a.bedrock_model = MODEL_CHOICES[int(pick) - 1]
            elif pick:
                a.bedrock_model = pick
        llm_ok = aws(a.bedrock_model, a.region)
        values.update({"LLM_PROVIDER": "bedrock"})
    else:
        if llm == "local":
            got = setup_ollama(info, a.llm_model, a.yes)
            if not got:
                sys.exit(1)
            values.update(got)
        elif llm == "ugmdu":
            from decider_kit.llm import DEFAULT_UGMDU_MODEL, UGMDU_MODELS

            key = key or ("" if a.yes else input("   AWS User Group Madurai API key (dcd_live_...): ").strip())
            model = a.llm_model or ("" if a.yes else input(f"   model {UGMDU_MODELS} ({DEFAULT_UGMDU_MODEL}): ").strip()) or DEFAULT_UGMDU_MODEL
            values.update({"LLM_PROVIDER": "ugmdu", "LLM_MODEL_ID": model, "DECIDER_API_KEY": key})
        os.environ.update({k: v for k, v in values.items() if v})
        llm_ok = llm_check()
        if creds:
            aws(a.bedrock_model, a.region)  # for ./kit deploy later; not needed to build
        else:
            warn("no AWS credentials: fine for building locally; the submission needs AWS and Amazon Bedrock (./kit deploy)")
    values.update({"BEDROCK_MODEL_ID": a.bedrock_model,
                   # model routing tiers on Bedrock: Amazon Nova by default; change them in .env
                   "BEDROCK_SMALL_MODEL_ID": os.environ.get("BEDROCK_SMALL_MODEL_ID", DEFAULT_SMALL_MODEL),
                   "BEDROCK_MEDIUM_MODEL_ID": os.environ.get("BEDROCK_MEDIUM_MODEL_ID", DEFAULT_MEDIUM_MODEL),
                   "BEDROCK_LARGE_MODEL_ID": os.environ.get("BEDROCK_LARGE_MODEL_ID", a.bedrock_model)})

    mode = choose(info, a.mode, a.yes)
    if mode == "local":
        vision = a.vision or (not a.yes and input("   Should the decider read images too (vision tower, +0.7 GB)? [y/N] ").strip().lower() == "y")
        dmodel = a.decider_model
        if not dmodel and not a.yes:
            print(f"   Decider checkpoint:  1. {DEFAULT_DECIDER_MODEL} (latest release)   2. {V19} (what the hosted API serves)")
            dmodel = V19 if input("   choose 1-2 (1): ").strip() == "2" else DEFAULT_DECIDER_MODEL
        values.update(setup_local(info, dmodel or DEFAULT_DECIDER_MODEL, vision))
        write_env(values)
        start_local(values)
    elif mode == "ugmdu":
        key = key or ("" if a.yes else input("   AWS User Group Madurai API key (dcd_live_...): ").strip())
        if not key:
            bad("no key. Request one from the AWS User Group Madurai platform (see README), then run ./kit setup again.")
            sys.exit(1)
        values.update({"DECIDER_MODE": "ugmdu", "DECIDER_URL": UGMDU_DECIDER_URL, "DECIDER_API_KEY": key})
        write_env(values)
    else:
        url = a.url or input("   decider URL: ").strip()
        key = a.key or ("" if a.yes else input("   API key (blank if none): ").strip())
        values.update({"DECIDER_MODE": "custom", "DECIDER_URL": url, "DECIDER_API_KEY": key})
        write_env(values)
    good = smoke(vision=values.get("DECIDER_VISION") == "1")
    done = good and llm_ok
    print("\nNext:" if done else "\nFix the FAIL lines above, then run ./kit setup again.")
    if done:
        if values.get("LLM_PROVIDER") != "bedrock":
            print(f"   {DIM}Building with a {values['LLM_PROVIDER']} LLM. For the submission, ./kit deploy uses Amazon Bedrock.{END}")
        print("   In Kiro: type /hackathon and describe your agent.   Without Kiro: see docs/BUILD.md")
    sys.exit(0 if done else 1)


if __name__ == "__main__":
    main()
