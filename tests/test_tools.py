"""The tool installer picks the right download for each OS and chip (offline: downloads are faked)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import tools  # noqa: E402

SUMS = "\n".join(f"abc  node-v22.9.9-{p}" for p in (
    "darwin-arm64.tar.gz", "darwin-x64.tar.gz", "linux-arm64.tar.xz", "linux-x64.tar.xz", "win-x64.zip", "win-arm64.zip"))
GH = {"assets": [{"name": f"gh_2.1.0_{p}", "browser_download_url": f"https://x/{p}"} for p in (
    "macOS_arm64.zip", "macOS_amd64.zip", "linux_arm64.tar.gz", "linux_amd64.tar.gz", "windows_amd64.zip", "windows_arm64.zip")]}


@pytest.mark.parametrize("win,mac,x64,node,gh", [
    (False, True, False, "node-v22.9.9-darwin-arm64.tar.gz", "macOS_arm64.zip"),
    (False, False, True, "node-v22.9.9-linux-x64.tar.xz", "linux_amd64.tar.gz"),
    (False, False, False, "node-v22.9.9-linux-arm64.tar.xz", "linux_arm64.tar.gz"),
    (True, False, True, "node-v22.9.9-win-x64.zip", "windows_amd64.zip"),
])
def test_downloads_match_the_platform(monkeypatch, tmp_path, win, mac, x64, node, gh):
    got = []
    monkeypatch.setattr(tools, "WIN", win)
    monkeypatch.setattr(tools, "MAC", mac)
    monkeypatch.setattr(tools, "X64", x64)
    monkeypatch.setattr(tools, "TOOLS", tmp_path)
    monkeypatch.setattr(tools, "_get", lambda url: got.append(url) or (SUMS.encode() if url.endswith("SHASUMS256.txt")
                                                                     else json.dumps(GH).encode() if "api.github" in url else b""))
    monkeypatch.setattr(tools, "_extract", lambda data, dest, strip_top=True: None)
    tools.install_node()
    tools.install_gh()
    assert got[1].endswith(node) and got[-1].endswith(gh)


def test_ask_honours_kit_yes(monkeypatch):
    monkeypatch.setenv("KIT_YES", "1")
    assert tools.ask("install?", False)


def test_unknown_tool_is_refused(capsys):
    assert tools.main(["install", "photoshop"]) == 2
