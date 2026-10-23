"""AWS User Group Madurai: Strands Decider hackathon kit. Its commands, the same on macOS, Linux and Windows.

    ./kit <command>        macOS and Linux        (make <command> also works there)
    .\\kit.cmd <command>    Windows (PowerShell or cmd)

Getting ready
    tools [check|install base|deploy|local|<name>]   check and install git, gh, node, agentcore, ollama
    venv                     create .venv and install the Python packages
    setup [setup.py flags]   choose where the LLM and the decider run, and test both
    check-machine            report this machine and AWS; change nothing
    aws-login                save AWS access keys for this kit (asked in the terminal, never in chat)
    gh-login                 log in to GitHub (for publishing)
Building
    test | run | demo | demo-bg | demo-stop | serve | stop | status
    data NAME --describe "..." --fields "a:str,b:float" [--n 20]
    bench [--split tune|test]
Shipping
    agentcore-cli | deploy | invoke "message" | destroy
    article [--draft] | video [--target agentcore] | readme | check | publish NAME
Releasing the kit (maintainers)
    release                  dist/ zip + tar.gz + install scripts for hosting (S3)
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WIN = sys.platform == "win32"
VENV_PY = ROOT / ".venv" / ("Scripts/python.exe" if WIN else "bin/python")
sys.path.insert(0, str(ROOT / "scripts"))
import tools  # noqa: E402

ENV = tools.with_path()  # kit-installed tools (node, gh, agentcore, ollama) come first on PATH


def py() -> str:
    return str(VENV_PY) if VENV_PY.exists() else sys.executable


def run(*args: str, check: bool = True) -> int:
    r = subprocess.run([*args], cwd=ROOT, env=ENV)
    if check and r.returncode != 0:
        sys.exit(r.returncode)
    return r.returncode


def pyrun(*args: str, check: bool = True) -> int:
    return run(py(), *args, check=check)


def deployed_arn() -> str:
    return json.loads((ROOT / "submission" / "deployment.json").read_text())["runtime_arn"]


# ---- background processes (demo, local decider) -----------------------------------------------------


def spawn(pidfile: str, logfile: str, *args: str, extra_env: dict[str, str] | None = None) -> int:
    log = open(ROOT / logfile, "w")
    kw: dict = {"cwd": ROOT, "stdout": log, "stderr": subprocess.STDOUT, "env": {**ENV, **(extra_env or {})}}
    if WIN:
        kw["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS  # type: ignore[attr-defined]
    else:
        kw["start_new_session"] = True
    p = subprocess.Popen([*args], **kw)
    (ROOT / pidfile).write_text(str(p.pid))
    return p.pid


def kill(pidfile: str) -> bool:
    f = ROOT / pidfile
    if not f.exists():
        return False
    pid = int(f.read_text().strip() or 0)
    f.unlink()
    try:
        if WIN:
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
        else:
            os.killpg(pid, signal.SIGTERM)
        return True
    except (ProcessLookupError, PermissionError, OSError):
        return False


def up(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=2):
            return True
    except Exception:  # noqa: BLE001
        return False


# ---- commands --------------------------------------------------------------------------------------


def cmd_venv(_: list[str]) -> None:
    if not VENV_PY.exists():
        if sys.version_info[:2] < (3, 10) or sys.version_info[:2] > (3, 13):
            sys.exit(f"Python 3.10 to 3.13 is needed (this is {sys.version.split()[0]}). The install script sets it up: "
                     "see docs/GETTING-STARTED.md")
        print(f"creating .venv with Python {sys.version.split()[0]} ...")
        uv = tools.which("uv")
        run(*([uv, "venv", "-q", "--python", sys.executable, ".venv"] if uv else [sys.executable, "-m", "venv", ".venv"]))
    uv = tools.which("uv")
    print("installing Python packages (1 to 2 min the first time) ...")
    if uv:
        run(uv, "pip", "install", "-q", "--python", str(VENV_PY), "-r", "requirements.txt")
    else:
        run(str(VENV_PY), "-m", "pip", "install", "-q", "--upgrade", "pip")
        run(str(VENV_PY), "-m", "pip", "install", "-q", "-r", "requirements.txt")
    print("installing the browser used for the video and the article images ...")
    run(str(VENV_PY), "-m", "playwright", "install", "chromium")
    if sys.platform.startswith("linux"):  # the browser needs system libraries on Linux (WSL included)
        probe = "from playwright.sync_api import sync_playwright as s\nwith s() as p: p.chromium.launch().close()"
        if subprocess.run([str(VENV_PY), "-c", probe], capture_output=True).returncode != 0:
            print("the browser needs a few system libraries (one sudo command, for the video and article images)")
            if tools.ask("  Install them now with sudo? [Y/n]", False):
                run(*([] if os.geteuid() == 0 else ["sudo"]), str(VENV_PY), "-m", "playwright", "install-deps", "chromium", check=False)
            else:
                print(f"  later: sudo {VENV_PY} -m playwright install-deps chromium")
    print("venv ready")


def cmd_demo(args: list[str], background: bool = False) -> None:
    target = args[args.index("--target") + 1] if "--target" in args else os.environ.get("TARGET", "local")
    extra = {"DEMO_TARGET": "agentcore", "AGENTCORE_ARN": deployed_arn()} if target == "agentcore" else {}
    cmd = [py(), "-m", "uvicorn", "demo.server:app", "--port", "8501"]
    if not background:
        os.environ.update(extra)
        sys.exit(subprocess.run(cmd, cwd=ROOT, env={**ENV, **extra}).returncode)
    if up("http://127.0.0.1:8501/api/info"):
        sys.exit("port 8501 is already in use (another demo?): run kit demo-stop there, or close that program")
    spawn(".demo.pid", ".demo.log", *cmd, extra_env=extra)
    for _ in range(40):
        if up("http://127.0.0.1:8501/api/info"):
            print("demo running: http://localhost:8501  (log: .demo.log; stop with kit demo-stop)")
            return
        time.sleep(1)
    print((ROOT / ".demo.log").read_text()[-2000:])
    sys.exit("demo did not start; see .demo.log")


def cmd_serve(_: list[str]) -> None:
    sys.path.insert(0, str(ROOT))
    from decider_kit.config import DEFAULT_DECIDER_MODEL, load_dotenv

    load_dotenv()
    exe = ROOT / ".venv" / ("Scripts/strands-decider.exe" if WIN else "bin/strands-decider")
    args = [str(exe), "serve", os.environ.get("DECIDER_MODEL", DEFAULT_DECIDER_MODEL), "--port", "8099",
            "--device", os.environ.get("DECIDER_DEVICE", "cpu")]
    if os.environ.get("DECIDER_VISION") == "1":
        args.append("--vision")
    spawn(".decider-server.pid", ".decider-server.log", *args)
    print("decider starting on :8099 (log: .decider-server.log; stop with kit stop)")


def cmd_aws_login(_: list[str]) -> None:
    """Save AWS access keys into ~/.aws (profile 'hackathon') and point .env at it. Typed here, not in chat."""
    import configparser
    import getpass

    print("AWS access keys for the hackathon (IAM user or temporary keys). They go to ~/.aws/credentials,")
    print("profile 'hackathon', and never into this repo or the Kiro chat. SSO users: run `aws sso login` instead.\n")
    key_id = input("  AWS Access Key ID: ").strip()
    secret = getpass.getpass("  AWS Secret Access Key (hidden): ").strip()
    token = getpass.getpass("  Session token (Enter if none, hidden): ").strip()
    region = input("  Region [us-east-1]: ").strip() or "us-east-1"
    if not key_id or not secret:
        sys.exit("nothing saved")
    aws = Path.home() / ".aws"
    aws.mkdir(exist_ok=True)
    for name, values in (("credentials", {"aws_access_key_id": key_id, "aws_secret_access_key": secret,
                                          **({"aws_session_token": token} if token else {})}),
                         ("config", {"region": region})):
        cp = configparser.ConfigParser()
        f = aws / name
        cp.read(f)
        section = "hackathon" if name == "credentials" else "profile hackathon"
        cp[section] = values
        with open(f, "w") as fh:
            cp.write(fh)
        if not WIN:
            f.chmod(0o600)
    sys.path.insert(0, str(ROOT / "scripts"))
    from setup import write_env

    write_env({"AWS_PROFILE": "hackathon", "AWS_REGION": region})
    os.environ.update({"AWS_PROFILE": "hackathon", "AWS_REGION": region})
    import boto3

    try:
        acct = boto3.client("sts", region_name=region).get_caller_identity()["Account"]
        print(f"\nOK  AWS works (account ...{acct[-4:]}, {region}); saved as profile 'hackathon'")
    except Exception as e:  # noqa: BLE001
        sys.exit(f"\nthose keys did not work: {type(e).__name__}: {e}")


def cmd_gh_login(_: list[str]) -> None:
    gh = tools.which("gh")
    if not gh:
        tools.install(["gh"])
        gh = tools.which("gh")
    if not gh:
        sys.exit("the GitHub CLI is not installed: kit tools install gh")
    run(gh, "auth", "login", "--web", "--git-protocol", "https")


def cmd_video(args: list[str]) -> None:
    if opt(args, "--target") == "agentcore":
        ENV["AGENTCORE_ARN"] = deployed_arn()
    pyrun("scripts/make_video.py", *args)


def cmd_release(_: list[str]) -> None:
    pyrun("scripts/release.py")


def opt(args: list[str], name: str, default: str | None = None) -> str | None:
    return args[args.index(name) + 1] if name in args and args.index(name) + 1 < len(args) else default


COMMANDS = {
    "venv": cmd_venv,
    "tools": lambda a: sys.exit(tools.main(a)),
    "setup": lambda a: pyrun("scripts/setup.py", *a),
    "check-machine": lambda a: pyrun("scripts/setup.py", "--check-only", *a),
    "aws-login": cmd_aws_login,
    "gh-login": cmd_gh_login,
    "test": lambda a: pyrun("-m", "pytest", "-q", "tests", *a),
    "run": lambda a: pyrun("-m", "agent.agent", *a),
    "demo": lambda a: cmd_demo(a),
    "demo-bg": lambda a: cmd_demo(a, background=True),
    "demo-stop": lambda a: print("demo stopped" if kill(".demo.pid") else "no demo running"),
    "serve": cmd_serve,
    "stop": lambda a: print("decider stopped" if kill(".decider-server.pid") else "no local decider running"),
    "status": lambda a: pyrun("scripts/status.py", *a),
    "secret-scan": lambda a: pyrun("scripts/secret_scan.py", *a),
    "data": lambda a: pyrun("-m", "decider_kit.data", *a),
    "bench": lambda a: pyrun("-m", "decider_kit.bench", "--cases", "agent/eval_cases.jsonl", "--questions", "agent.decision:QUESTIONS",
                             "--out", "submission/bench", *a),
    "agentcore-cli": lambda a: sys.exit(tools.main(["install", "agentcore", *a])),
    "deploy": lambda a: pyrun("scripts/deploy.py", "deploy", *a),
    "invoke": lambda a: pyrun("scripts/deploy.py", "invoke", " ".join(a) or "Hello, what can you do?"),
    "destroy": lambda a: pyrun("scripts/deploy.py", "destroy", *a),
    "article": lambda a: pyrun("scripts/article.py", *a),
    "video": lambda a: cmd_video(a),
    "readme": lambda a: pyrun("scripts/readme.py", *a),
    "check": lambda a: pyrun("scripts/check_submission.py", *a),
    "publish": lambda a: pyrun("scripts/publish.py", *(f"NAME={x}" if "=" not in x else x for x in a)),
    "release": cmd_release,
}


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] in ("help", "-h", "--help"):
        print(__doc__)
        return
    name, args = sys.argv[1], sys.argv[2:]
    if name not in COMMANDS:
        sys.exit(f"unknown command {name!r}. Run: kit help")
    COMMANDS[name](args)


if __name__ == "__main__":
    main()
