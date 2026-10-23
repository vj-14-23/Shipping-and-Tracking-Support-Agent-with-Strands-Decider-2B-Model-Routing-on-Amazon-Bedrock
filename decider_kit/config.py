"""Settings from `.env` (written by `scripts/setup.py`) and the environment. The environment wins."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# The AWS User Group Madurai hosted Strands Decider API. Keys are issued through the user
# group's platform; see README "Use the AWS User Group Madurai hosted API".
UGMDU_DECIDER_URL = "https://da25tnxy06gjk.cloudfront.net"
LOCAL_DECIDER_URL = "http://127.0.0.1:8099"
DEFAULT_DECIDER_MODEL = "StrandsAgents/strands-decider-2B-qwen3.5-v1-2610"
# Every Amazon Bedrock model id is an environment variable (set in .env); the defaults are Amazon Nova.
DEFAULT_BEDROCK_MODEL = "us.amazon.nova-pro-v1:0"
DEFAULT_SMALL_MODEL = "us.amazon.nova-micro-v1:0"
DEFAULT_MEDIUM_MODEL = "us.amazon.nova-lite-v1:0"


def load_dotenv(path: Path | None = None) -> None:
    """Minimal .env reader (KEY=VALUE lines); never overrides variables already set."""
    p = path or ROOT / ".env"
    if not p.exists():
        return
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


@dataclass(frozen=True)
class Settings:
    decider_mode: str  # local | ugmdu | custom
    decider_url: str
    decider_api_key: str
    decider_model: str
    bedrock_model: str      # BEDROCK_MODEL_ID: the agent's model
    small_model: str        # BEDROCK_SMALL_MODEL_ID: cheap tier (model routing)
    medium_model: str       # BEDROCK_MEDIUM_MODEL_ID
    large_model: str        # BEDROCK_LARGE_MODEL_ID: strong tier (defaults to BEDROCK_MODEL_ID)
    bench_model: str        # BENCH_LLM_MODEL_ID: the LLM baseline in ./kit bench (defaults to BEDROCK_MODEL_ID)
    aws_region: str


def settings() -> Settings:
    load_dotenv()
    mode = os.environ.get("DECIDER_MODE", "local")
    default_url = {"local": LOCAL_DECIDER_URL, "ugmdu": UGMDU_DECIDER_URL}.get(mode, LOCAL_DECIDER_URL)
    return Settings(
        decider_mode=mode,
        decider_url=os.environ.get("DECIDER_URL", default_url).rstrip("/"),
        decider_api_key=os.environ.get("DECIDER_API_KEY", ""),
        decider_model=os.environ.get("DECIDER_MODEL", DEFAULT_DECIDER_MODEL),
        bedrock_model=(main := os.environ.get("BEDROCK_MODEL_ID", DEFAULT_BEDROCK_MODEL)),
        small_model=os.environ.get("BEDROCK_SMALL_MODEL_ID", DEFAULT_SMALL_MODEL),
        medium_model=os.environ.get("BEDROCK_MEDIUM_MODEL_ID", DEFAULT_MEDIUM_MODEL),
        large_model=os.environ.get("BEDROCK_LARGE_MODEL_ID", main),
        bench_model=os.environ.get("BENCH_LLM_MODEL_ID", main),
        aws_region=os.environ.get("AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", "us-east-1")),
    )
