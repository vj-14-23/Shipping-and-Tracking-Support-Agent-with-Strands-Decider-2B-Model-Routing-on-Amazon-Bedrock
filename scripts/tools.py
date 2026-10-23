"""Check and install the tools the kit needs, on macOS, Linux (and WSL) and Windows.

    kit tools                      # what is installed, what is missing, and why it is needed
    kit tools install base         # git, GitHub CLI and Node (publishing and deploying)
    kit tools install ollama       # a local LLM (the "fully local" path)
    kit tools install agentcore    # the AgentCore CLI (deploying to AWS)

Everything goes into the user's home folder (~/.decider-kit/tools) where possible, so no admin
rights are needed: Node, the GitHub CLI, the AgentCore CLI and (on macOS and Linux) Ollama.
Only git may need the system installer (Xcode tools on macOS, apt on Linux, winget on Windows).
Nothing is installed without asking, unless --yes is passed.
"""

from __future__ import annotations

import io
import json
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import urllib.request
import zipfile
from pathlib import Path

HOME = Path.home()
TOOLS = HOME / ".decider-kit" / "tools"
AGENTCORE = HOME / ".local" / "agentcore-cli"
WIN = sys.platform == "win32"
MAC = sys.platform == "darwin"
ARCH = platform.machine().lower()
X64 = ARCH in ("x86_64", "amd64")
UA = {"User-Agent": "decider-hackathon-kit"}

WHY = {
    "git": "saving your work and publishing your repo",
    "gh": "publishing your repo on GitHub",
    "node": "the AgentCore CLI (deploying to AWS)",
    "agentcore": "deploying your agent to Amazon Bedrock AgentCore Runtime",
    "ollama": "running an LLM on this machine (the fully local path)",
}
GROUPS = {"base": ["git", "gh", "node"], "deploy": ["node", "agentcore"], "local": ["ollama"],
          "all": ["git", "gh", "node", "agentcore", "ollama"]}


def path_dirs() -> list[Path]:
    """Folders with kit-installed tools, to put first on PATH (kit.py does this for every command)."""
    dirs = [TOOLS / "gh" / "bin", AGENTCORE / "node_modules" / ".bin", TOOLS / "ollama" / "bin", HOME / ".local" / "bin"]
    node = TOOLS / "node"
    dirs.append(node if WIN else node / "bin")
    if MAC:
        dirs.append(HOME / "Applications" / "Ollama.app" / "Contents" / "Resources")
    return [d for d in dirs if d.exists()]


def with_path() -> dict[str, str]:
    env = dict(os.environ)
    env["PATH"] = os.pathsep.join([str(d) for d in path_dirs()] + [env.get("PATH", "")])
    return env


def which(name: str) -> str | None:
    return shutil.which(name, path=with_path()["PATH"])


def version(name: str) -> str | None:
    exe = which({"agentcore": "agentcore"}.get(name, name))
    if not exe:
        return None
    args = {"node": ["--version"], "ollama": ["--version"], "agentcore": ["--version"]}.get(name, ["--version"])
    try:
        out = subprocess.run([exe, *args], capture_output=True, text=True, timeout=20, env=with_path())
        lines = [x.replace("Warning:", "").strip() for x in (out.stdout + "\n" + out.stderr).splitlines() if x.strip()]
        pick = [x for x in lines if any(c.isdigit() for c in x)]  # e.g. Ollama prints "Warning: client version is 0.40.3"
        return (next((x for x in pick if "version" in x.lower()), pick[0] if pick else (lines[0] if lines else "?")))[:60]
    except (OSError, subprocess.SubprocessError):
        return None


def ok_version(name: str) -> bool:
    v = version(name)
    if not v:
        return False
    if name == "node":
        try:
            return int(v.lstrip("v").split(".")[0]) >= 20
        except ValueError:
            return False
    if name == "agentcore":
        return v[:1].isdigit()  # the npm AgentCore CLI, not the older Python starter toolkit
    return True


# ---- installers ----------------------------------------------------------------------------------


def _get(url: str) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=600) as r:
        return r.read()


def _extract(data: bytes, dest: Path, strip_top: bool = True) -> None:
    """Unpack a .zip or .tar.* into dest, dropping the archive's single top-level folder."""
    if dest.exists():
        shutil.rmtree(dest)
    tmp = dest.with_name(dest.name + ".tmp")
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    if data[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            z.extractall(tmp)
            for info in z.infolist():  # keep the executable bit (zip stores it in external_attr)
                mode = (info.external_attr >> 16) & 0o777
                if mode:
                    os.chmod(tmp / info.filename, mode)
    else:
        with tarfile.open(fileobj=io.BytesIO(data)) as t:
            t.extractall(tmp)
    kids = list(tmp.iterdir())
    src = kids[0] if strip_top and len(kids) == 1 and kids[0].is_dir() else tmp
    shutil.move(str(src), str(dest))
    if tmp.exists():
        shutil.rmtree(tmp, ignore_errors=True)


def install_node() -> None:
    sums = _get("https://nodejs.org/dist/latest-v22.x/SHASUMS256.txt").decode()
    plat = "win" if WIN else ("darwin" if MAC else "linux")
    arch = "x64" if X64 else "arm64"
    ext = ".zip" if WIN else (".tar.gz" if MAC else ".tar.xz")
    name = next(line.split()[1] for line in sums.splitlines() if line.endswith(f"-{plat}-{arch}{ext}"))
    print(f"   downloading {name} ...")
    _extract(_get(f"https://nodejs.org/dist/latest-v22.x/{name}"), TOOLS / "node")


def install_gh() -> None:
    rel = json.loads(_get("https://api.github.com/repos/cli/cli/releases/latest"))
    plat = "windows" if WIN else ("macOS" if MAC else "linux")
    arch = "amd64" if X64 else "arm64"
    ext = ".zip" if (WIN or MAC) else ".tar.gz"
    asset = next(a for a in rel["assets"] if a["name"].endswith(f"_{plat}_{arch}{ext}"))
    print(f"   downloading {asset['name']} ...")
    _extract(_get(asset["browser_download_url"]), TOOLS / "gh")


def install_agentcore() -> None:
    if not ok_version("node"):
        install_node()
    npm = which("npm")
    if not npm:
        raise RuntimeError("npm not found after installing Node")
    AGENTCORE.mkdir(parents=True, exist_ok=True)
    print("   npm install @aws/agentcore (about 1 min) ...")
    subprocess.run([npm, "install", "--silent", "--prefix", str(AGENTCORE), "@aws/agentcore"], check=True, env=with_path())


def install_ollama() -> None:
    if WIN:
        winget = shutil.which("winget")
        if winget:
            subprocess.run([winget, "install", "-e", "--id", "Ollama.Ollama", "--accept-source-agreements",
                            "--accept-package-agreements"], check=True)
            return
        exe = TOOLS / "OllamaSetup.exe"
        exe.parent.mkdir(parents=True, exist_ok=True)
        exe.write_bytes(_get("https://ollama.com/download/OllamaSetup.exe"))
        subprocess.run([str(exe), "/SILENT"], check=True)
        return
    if MAC:  # the app, into ~/Applications (the CLI is inside it)
        print("   downloading Ollama for macOS ...")
        apps = HOME / "Applications"
        apps.mkdir(exist_ok=True)
        with zipfile.ZipFile(io.BytesIO(_get("https://ollama.com/download/Ollama-darwin.zip"))) as z:
            z.extractall(apps)
        subprocess.run(["chmod", "-R", "u+x", str(apps / "Ollama.app" / "Contents" / "MacOS"),
                        str(apps / "Ollama.app" / "Contents" / "Resources")], check=False)
        return
    arch = "amd64" if X64 else "arm64"
    print(f"   downloading Ollama for Linux ({arch}; about 1.5 GB with GPU libraries) ...")
    _extract(_get(f"https://ollama.com/download/ollama-linux-{arch}.tgz"), TOOLS / "ollama", strip_top=False)


def install_git() -> None:
    if MAC:
        subprocess.run(["xcode-select", "--install"], check=False)
        print("   a macOS window asks to install the command line developer tools: click Install, then run this again")
        return
    if WIN:
        subprocess.run(["winget", "install", "-e", "--id", "Git.Git", "--accept-source-agreements",
                        "--accept-package-agreements"], check=True)
        return
    sudo = [] if os.geteuid() == 0 else ["sudo"]
    for mgr, cmd in (("apt-get", [*sudo, "apt-get", "install", "-y", "git"]), ("dnf", [*sudo, "dnf", "install", "-y", "git"]),
                     ("yum", [*sudo, "yum", "install", "-y", "git"])):
        if shutil.which(mgr):
            print(f"   {' '.join(cmd)}  (asks for your password)")
            subprocess.run(cmd, check=True)
            return
    raise RuntimeError("install git with your system's package manager")


INSTALL = {"node": install_node, "gh": install_gh, "agentcore": install_agentcore, "ollama": install_ollama, "git": install_git}


# ---- commands --------------------------------------------------------------------------------------


def report(names: list[str]) -> list[str]:
    missing = []
    for n in names:
        good = ok_version(n)
        print(f"  {'OK  ' if good else 'MISS'}  {n:<10} {version(n) or 'not installed':<34} for {WHY[n]}")
        if not good:
            missing.append(n)
    return missing


def ask(question: str, assume_yes: bool) -> bool:
    """Yes/no on the terminal (works under `curl | sh`); KIT_YES=1 answers yes; no terminal answers no."""
    if assume_yes or os.environ.get("KIT_YES"):
        return True
    print(question, end=" ", flush=True)
    try:
        with open("CON" if WIN else "/dev/tty") as tty:
            return tty.readline().strip().lower() in ("", "y", "yes")
    except OSError:
        pass
    if sys.stdin and sys.stdin.isatty():
        return input().strip().lower() in ("", "y", "yes")
    print("(no terminal to ask: skipped; run this command yourself, or set KIT_YES=1)")
    return False


def install(names: list[str], assume_yes: bool = False) -> bool:
    missing = report(names)
    if not missing:
        print("  everything needed is installed")
        return True
    where = "your home folder (~/.decider-kit), no admin rights" if not set(missing) & {"git"} else "your home folder, plus the system installer for git"
    if not ask(f"\n  Install {', '.join(missing)} into {where}? [Y/n]", assume_yes):
        print("  skipped; install them later with: kit tools install " + " ".join(missing))
        return False
    good = True
    for n in missing:
        print(f"\n  installing {n} ...")
        try:
            INSTALL[n]()
            print(f"  OK  {n} {version(n) or ''}")
        except Exception as e:  # noqa: BLE001 - report and continue with the next tool
            good = False
            print(f"  could not install {n}: {e}")
    return good


def main(argv: list[str]) -> int:
    assume_yes = "--yes" in argv
    args = [a for a in argv if a != "--yes"]
    if not args or args[0] == "check":
        names = [n for a in (args[1:] or ["all"]) for n in GROUPS.get(a, [a])]
        missing = report(list(dict.fromkeys(names)))
        print(f"\n  missing: {', '.join(missing)}  (kit tools install ...)" if missing else "\n  all set")
        return 0
    if args[0] == "install":
        names = [n for a in (args[1:] or ["base"]) for n in GROUPS.get(a, [a])]
        unknown = [n for n in names if n not in WHY]
        if unknown:
            print(f"unknown tool(s): {unknown}; choose from {sorted(WHY)} or {sorted(GROUPS)}")
            return 2
        return 0 if install(list(dict.fromkeys(names)), assume_yes) else 1
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
