"""Fail if a tracked or changed file contains a secret (API keys, AWS keys, private keys).

    python scripts/secret_scan.py            # every file git would commit
    python scripts/secret_scan.py --changed  # only files changed since the last commit (used by the hook)
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PATTERNS = {
    "decider API key": re.compile(r"dcd_(live|test)_[A-Za-z0-9]{40,}"),
    "AWS access key id": re.compile(r"\b(AKIA|ASIA)[A-Z0-9]{16}\b"),
    "AWS secret key": re.compile(r"(?i)aws_secret_access_key\s*[=:]\s*['\"]?[A-Za-z0-9/+=]{40}"),
    "private key": re.compile(r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "GitHub token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b"),
    "Hugging Face token": re.compile(r"\bhf_[A-Za-z0-9]{30,}\b"),
}
SKIP = {".env", ".env.bak", ".env.example"}


def files(changed: bool) -> list[Path]:
    cmd = ["git", "diff", "--name-only", "HEAD"] if changed else ["git", "ls-files", "-co", "--exclude-standard"]
    out = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True).stdout.split()
    if changed:
        out += subprocess.run(["git", "ls-files", "-o", "--exclude-standard"], cwd=ROOT, capture_output=True, text=True).stdout.split()
    return [ROOT / f for f in dict.fromkeys(out) if Path(f).name not in SKIP and (ROOT / f).is_file()]


def main() -> None:
    hits = []
    for f in files("--changed" in sys.argv):
        if f.suffix in (".png", ".jpg", ".mp4", ".webm", ".mp3", ".aiff", ".safetensors", ".bin"):
            continue
        try:
            text = f.read_text(errors="ignore")
        except OSError:
            continue
        for name, rx in PATTERNS.items():
            if rx.search(text):
                hits.append(f"{f.relative_to(ROOT)}: {name}")
    if hits:
        print("SECRET FOUND (remove it; keys belong in .env, which git ignores):\n  " + "\n  ".join(hits))
        sys.exit(1)
    print("secret scan: clean")


if __name__ == "__main__":
    main()
