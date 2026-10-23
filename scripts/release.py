"""Package the kit for hosting (S3 or any web host): what participants download.

    ./kit release                                   # dist/, for the default base URL
    KIT_BASE_URL=https://example.com/kit ./kit release

Writes to dist/:
    decider-hackathon-kit.tar.gz   (macOS, Linux)   decider-hackathon-kit.zip (Windows)
    install.sh, install.ps1        (with the base URL filled in)
    VERSION, SHA256SUMS
Upload the whole folder to the base URL (for example s3://<bucket>/kit/ behind CloudFront).
Only files tracked by git go in, so .env, keys and local outputs never ship.
"""

from __future__ import annotations

import hashlib
import io
import os
import subprocess
import tarfile
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
DEFAULT_BASE = "https://REPLACE-WITH-THE-KIT-URL"  # set to the S3/CloudFront URL when it exists
TOP = "decider-hackathon-kit"
SKIP = ("dist/", "install/")  # the installers are published next to the archives, not inside them


def files() -> list[str]:
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.split("\n")
    return [f for f in out if f and not f.startswith(SKIP) and (ROOT / f).is_file()]


def main() -> None:
    base = os.environ.get("KIT_BASE_URL", DEFAULT_BASE).rstrip("/")
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    version = f"{time.strftime('%Y.%m.%d')}-{rev}"
    DIST.mkdir(exist_ok=True)
    names = files()
    ver = version.encode() + b"\n"
    with tarfile.open(DIST / f"{TOP}.tar.gz", "w:gz") as t:
        for f in names:
            t.add(ROOT / f, arcname=f"{TOP}/{f}")
        info = tarfile.TarInfo(f"{TOP}/VERSION")
        info.size, info.mtime = len(ver), int(time.time())
        t.addfile(info, io.BytesIO(ver))
    with zipfile.ZipFile(DIST / f"{TOP}.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for f in names:
            z.write(ROOT / f, f"{TOP}/{f}")
        z.writestr(f"{TOP}/VERSION", ver)
    for name in ("install.sh", "install.ps1"):
        text = (ROOT / "install" / name).read_text().replace("__BASE__", base)
        # a hosted release downloads from the host by default, not from GitHub
        text = text.replace("https://codeload.github.com/Vivek0712/decider-hackathon-kit/tar.gz/refs/heads/main",
                            f"{base}/{TOP}.tar.gz")
        text = text.replace("https://codeload.github.com/Vivek0712/decider-hackathon-kit/zip/refs/heads/main",
                            f"{base}/{TOP}.zip")
        (DIST / name).write_text(text)
    (DIST / "install.sh").chmod(0o755)
    (DIST / "VERSION").write_bytes(ver)
    sums = [f"{hashlib.sha256((DIST / n).read_bytes()).hexdigest()}  {n}"
            for n in (f"{TOP}.tar.gz", f"{TOP}.zip", "install.sh", "install.ps1")]
    (DIST / "SHA256SUMS").write_text("\n".join(sums) + "\n")
    print(f"[release] {version}: {len(names)} files -> dist/ for {base}")
    print(f"[release] participants run:  curl -fsSL {base}/install.sh | sh      (Windows: irm {base}/install.ps1 | iex)")


if __name__ == "__main__":
    main()
