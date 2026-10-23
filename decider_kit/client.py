"""One client for Strands Decider, wherever it runs.

    from decider_kit import Decider
    d = Decider()                       # reads .env: local server, the UG Madurai API, or a custom URL
    answers = d.ask("Ticket: refund please, charged twice.", {
        "refund": Decider.noul("Is the customer asking for a refund?"),
        "team": Decider.choice("Which team?", {"billing": "money", "support": "accounts"}),
        "urgency": Decider.score("How urgent?", ["low", "medium", "high"]),
    })
    answers["refund"].yes          # True / False
    answers["refund"].confidence   # 0..1
    answers["team"].label          # "billing"

Two wire formats are supported:
- a local `strands-decider serve` (POST /v1/systemone, no key);
- the AWS User Group Madurai hosted API, or any decider-cloud endpoint (POST /v1/decide,
  `Authorization: Bearer <key>`).

Ask every question about one state in one call: the state is encoded once and shared, so
eight questions cost far less than eight requests. Stdlib only (urllib), so it works inside
any agent runtime.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from .config import settings


class DeciderError(RuntimeError):
    """The decider could not answer (not running, bad key, limit reached, bad question)."""


@dataclass
class Decision:
    """One typed answer.

    - noul: `p_yes` is P(yes); `yes` is p_yes >= 0.5; `confidence` is max(p, 1 - p).
    - choice: `label` is the best option; `probabilities` maps each option to its probability.
    - score: `score` is the expected level (0..n-1); `label` is the most likely level's name.
    """

    kind: str
    raw: dict[str, Any] = field(repr=False)
    p_yes: float | None = None
    label: str | None = None
    score: float | None = None
    probabilities: dict[str, float] = field(default_factory=dict)
    confidence: float = 0.0

    @property
    def yes(self) -> bool:
        return bool(self.p_yes is not None and self.p_yes >= 0.5)

    def unsure(self, threshold: float = 0.7) -> bool:
        """True when the decider is not confident enough to act alone (send it to a human or an LLM)."""
        return self.confidence < threshold

    @classmethod
    def parse(cls, ans: dict[str, Any]) -> Decision:
        kind = ans.get("type", "")
        if kind == "noul":
            p = float(ans["noul"])
            return cls(kind, ans, p_yes=p, label="yes" if p >= 0.5 else "no", confidence=max(p, 1 - p),
                       probabilities={"yes": p, "no": 1 - p})
        if kind == "choice":
            probs = {k: float(v) for k, v in ans.get("probabilities", {}).items()}
            return cls(kind, ans, label=ans.get("choice"), probabilities=probs,
                       confidence=max(probs.values()) if probs else float(ans.get("confidence", 0)))
        if kind == "score":
            probs = {k: float(v) for k, v in ans.get("probabilities", {}).items()}
            legend = ans.get("legend", {})
            top = max(probs, key=probs.get) if probs else None  # type: ignore[arg-type]
            return cls(kind, ans, score=float(ans.get("score", 0)), label=legend.get(top, top) if top else None,
                       probabilities={legend.get(k, k): v for k, v in probs.items()},
                       confidence=max(probs.values()) if probs else 0.0)
        raise DeciderError(f"unknown answer type {kind!r}")


def encode_images(images: Any) -> list[str]:
    """Images for the decider: file paths, raw bytes, PIL images or base64 strings -> base64 strings.

    PNG, JPEG, WebP or GIF; at most 4 per request; the server scales each to 448 px on its longer
    side. Needs a vision decider (`./kit serve` with DECIDER_VISION=1, or the hosted API).
    """
    import base64
    import io
    from pathlib import Path

    out: list[str] = []
    for im in list(images or []):
        if isinstance(im, (bytes, bytearray)):
            out.append(base64.b64encode(bytes(im)).decode())
        elif isinstance(im, Path) or (isinstance(im, str) and not im.startswith("data:") and len(im) < 1024 and Path(im).exists()):
            out.append(base64.b64encode(Path(im).read_bytes()).decode())
        elif isinstance(im, str):
            out.append(im)  # already base64 (a data: URL prefix is accepted)
        elif hasattr(im, "save"):  # PIL
            buf = io.BytesIO()
            im.save(buf, format="PNG")
            out.append(base64.b64encode(buf.getvalue()).decode())
        else:
            raise DeciderError(f"cannot read image of type {type(im).__name__}")
    if len(out) > 4:
        raise DeciderError("at most 4 images per request")
    return out


class Decider:
    def __init__(self, url: str | None = None, api_key: str | None = None, timeout: float = 120.0):
        s = settings()
        self.url = (url or s.decider_url).rstrip("/")
        self.api_key = api_key if api_key is not None else s.decider_api_key
        # local strands-decider serve: POST /v1/systemone; hosted (UG Madurai / decider-cloud): POST /v1/decide.
        # A custom endpoint with a key is treated as hosted, without one as a plain strands-decider server.
        self.hosted = s.decider_mode == "ugmdu" or (s.decider_mode == "custom" and bool(self.api_key))
        if url and api_key is not None:  # explicit arguments decide
            self.hosted = bool(api_key)
        self.timeout = timeout
        self.calls = 0
        self.input_tokens = 0
        self.last_latency_ms: float | None = None   # wall time seen by this client
        self.last_server_ms: float | None = None    # time reported by the server

    # ---- question builders --------------------------------------------------------------------

    @staticmethod
    def noul(instructions: str, criteria: Mapping[str, str] | None = None) -> dict[str, Any]:
        """Yes/no. Describing what "true" and "false" mean sharpens the answer a lot."""
        q: dict[str, Any] = {"type": "noul", "instructions": instructions}
        if criteria:
            q["criteria"] = dict(criteria)
        return q

    @staticmethod
    def choice(instructions: str, criteria: Mapping[str, str]) -> dict[str, Any]:
        """Pick one of N; `criteria` maps option name -> what it means. Options can change per call."""
        return {"type": "choice", "instructions": instructions, "criteria": dict(criteria)}

    @staticmethod
    def score(instructions: str, levels: list[str]) -> dict[str, Any]:
        """Rate on an ordered rubric, lowest level first."""
        return {"type": "score", "instructions": instructions, "criteria": list(levels)}

    # ---- asking -------------------------------------------------------------------------------

    def ask(self, state: Any, questions: Mapping[str, dict[str, Any]], images: Any = None) -> dict[str, Decision]:
        """All questions about one state in one round trip; answers come back under the same names.

        `images` (optional): file paths, bytes, PIL images or base64 strings, read with the state
        by a vision decider (v19 or the v1 Qwen3.5 release with --vision).
        """
        if not questions:
            raise DeciderError("ask at least one question")
        body: dict[str, Any] = {"state": state, "questions": dict(questions)}
        if images:
            body["images"] = encode_images(images)
        path = "/v1/decide" if self.hosted else "/v1/systemone"
        headers = {"content-type": "application/json"}
        if self.api_key:
            headers["authorization"] = f"Bearer {self.api_key}"
        req = urllib.request.Request(self.url + path, data=json.dumps(body).encode(), headers=headers, method="POST")
        t0 = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                payload = json.loads(r.read())
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")[:300]
            hint = {401: "check DECIDER_API_KEY", 402: "monthly quota used up", 429: "rate limited; retry after a moment",
                    503: "server busy; retry"}.get(e.code, "")
            if e.code == 422 and "image" in detail.lower():
                hint = "this decider reads text only: run ./kit serve with DECIDER_VISION=1 (or use the hosted API)"
            raise DeciderError(f"decider returned {e.code} {hint}: {detail}") from e
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            start = "./kit serve   (or: python scripts/setup.py)"
            raise DeciderError(f"no Strands Decider at {self.url} ({e}). Start one with: {start}") from e
        self.last_latency_ms = (time.perf_counter() - t0) * 1000
        self.last_server_ms = payload.get("latency_ms")
        self.calls += 1
        self.input_tokens += int(payload.get("usage", {}).get("input_tokens", 0))
        return {name: Decision.parse(a) for name, a in payload["answers"].items()}

    def health(self) -> dict[str, Any]:
        path = "/v1/models" if self.hosted else "/health"
        req = urllib.request.Request(self.url + path, headers={"authorization": f"Bearer {self.api_key}"} if self.api_key else {})
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                return dict(json.loads(r.read()))
        except (urllib.error.URLError, TimeoutError) as e:
            raise DeciderError(f"no Strands Decider at {self.url}: {e}") from e
