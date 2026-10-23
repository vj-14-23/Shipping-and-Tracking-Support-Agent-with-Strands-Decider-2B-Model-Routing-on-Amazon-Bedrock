import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).parent))
sys.modules.setdefault("scripts_path", types.SimpleNamespace(load=None))

import pytest  # noqa: E402

_ENV_KEYS = ("LLM_PROVIDER", "LLM_MODEL_ID", "LLM_URL", "OLLAMA_URL", "UGMDU_LLM_URL", "LLM_API_KEY", "LLM_THINK", "LLM_SMALL_MODEL_ID",
             "LLM_MEDIUM_MODEL_ID", "LLM_LARGE_MODEL_ID", "BENCH_LLM_MODEL_ID", "BEDROCK_MODEL_ID",
             "BEDROCK_SMALL_MODEL_ID", "BEDROCK_MEDIUM_MODEL_ID", "BEDROCK_LARGE_MODEL_ID", "LLM_PRICE_IN", "LLM_PRICE_OUT")


@pytest.fixture(autouse=True)
def _hermetic_env(monkeypatch):
    """Tests never read the developer's .env: kit defaults (Amazon Bedrock, Amazon Nova) unless a test sets them."""
    import decider_kit.config as cfg

    monkeypatch.setattr(cfg, "load_dotenv", lambda path=None: None)
    for k in _ENV_KEYS:
        monkeypatch.delenv(k, raising=False)

# ---------------------------------------------------------------------------
# Hypothesis profiles
# ---------------------------------------------------------------------------
from hypothesis import settings as hs_settings, HealthCheck

hs_settings.register_profile("ci", max_examples=200, suppress_health_check=[HealthCheck.too_slow])
hs_settings.register_profile("dev", max_examples=50, suppress_health_check=[HealthCheck.too_slow])
hs_settings.load_profile("dev")  # default; override with --hypothesis-profile=ci in CI
