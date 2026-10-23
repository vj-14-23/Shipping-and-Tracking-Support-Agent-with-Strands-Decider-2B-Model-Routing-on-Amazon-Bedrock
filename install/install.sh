#!/bin/sh
# AWS User Group Madurai: Strands Decider hackathon kit installer (macOS, Linux, WSL).
#
# In Kiro: open an EMPTY folder, open the terminal (Ctrl+`), then run:
#   curl -fsSL __BASE__/install.sh | sh
# From GitHub (until the kit is hosted):
#   curl -fsSL https://raw.githubusercontent.com/Vivek0712/decider-hackathon-kit/main/install/install.sh | sh
# (private repo: add a token: GITHUB_TOKEN=$(gh auth token), see docs/GETTING-STARTED.md)
#
# It asks before installing anything. Everything goes into your home folder (no admin rights):
# uv and Python 3.12, the kit, its Python packages, then git, the GitHub CLI and Node if missing.
# Unattended: KIT_YES=1 (say yes to everything). Another host: KIT_BASE_URL=...
set -e
# Where the kit comes from: a hosted release (./kit release fills this in), else GitHub's archive
KIT_TARBALL_DEFAULT="https://codeload.github.com/Vivek0712/decider-hackathon-kit/tar.gz/refs/heads/main"
TARBALL="${KIT_TARBALL:-${KIT_BASE_URL:+$KIT_BASE_URL/decider-hackathon-kit.tar.gz}}"
TARBALL="${TARBALL:-$KIT_TARBALL_DEFAULT}"
AUTH=""; [ -n "$GITHUB_TOKEN" ] && AUTH="Authorization: Bearer $GITHUB_TOKEN"
say() { printf '%s\n' "$*"; }
ask() {
  [ -n "$KIT_YES" ] && return 0
  printf '%s [Y/n] ' "$1"
  read -r a </dev/tty || a=""
  case "$a" in ""|y|Y|yes|Yes) return 0 ;; *) return 1 ;; esac
}

say ""
say "Strands Decider hackathon kit  (AWS User Group Madurai)"
say "Installing into: $(pwd)"
say ""

# 1. An empty folder (Kiro must open the kit's own folder to find its /hackathon skill)
if [ -f scripts/kit.py ]; then
  say "The kit is already here: updating its Python environment."
elif [ -n "$(ls -A 2>/dev/null | grep -v '^\.')" ]; then
  say "This folder is not empty. In Kiro: File > Open Folder, make a new empty folder, open it, and run this again."
  exit 1
fi

# 2. uv: installs Python and the kit's packages, in your home folder
UV="$(command -v uv 2>/dev/null || true)"
[ -z "$UV" ] && [ -x "$HOME/.local/bin/uv" ] && UV="$HOME/.local/bin/uv"
if [ -z "$UV" ]; then
  say "Needed: uv (installs Python 3.12 and the kit's packages; about 30 MB, into ~/.local/bin, no admin)."
  ask "Install uv now?" || { say "Stopped. Nothing was installed."; exit 1; }
  command -v curl >/dev/null || { say "curl is needed (sudo apt install curl), then run this again."; exit 1; }
  curl -LsSf https://astral.sh/uv/install.sh | env UV_NO_MODIFY_PATH=1 sh >/dev/null
  UV="$HOME/.local/bin/uv"
fi
say "OK  uv $("$UV" --version | cut -d' ' -f2)"

# 3. The kit
if [ ! -f scripts/kit.py ]; then
  say "Downloading the kit ..."
  if [ -n "$AUTH" ]; then curl -fsSL -H "$AUTH" "$TARBALL"; else curl -fsSL "$TARBALL"; fi | tar -xz --strip-components=1 \
    || { say "Could not download the kit from $TARBALL"; exit 1; }
  say "OK  kit $(cat VERSION 2>/dev/null || echo '')"
fi

# 4. Python 3.12 and the kit's packages (about 2 min)
"$UV" python install 3.12 >/dev/null 2>&1 || true
[ -x .venv/bin/python ] || "$UV" venv -q --python 3.12 .venv
PATH="$HOME/.local/bin:$PATH" ./kit venv

# 5. Tools for publishing and deploying: git, GitHub CLI, Node (asks first)
./kit tools install base || true

say ""
say "Done. Now, in the Kiro chat, type:   /hackathon"
say "Kiro will ask which path you want (AWS, fully local, or the user group cloud), set it up, and build your agent with you."
