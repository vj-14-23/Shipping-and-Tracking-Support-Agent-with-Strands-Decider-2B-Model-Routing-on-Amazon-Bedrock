"""A fake Decider for offline tests: answers from a rule you give it, records every call."""

from __future__ import annotations

from typing import Any, Callable

from decider_kit.client import Decision


class FakeDecider:
    def __init__(self, rule: Callable[[str, str, dict[str, Any]], Any] | None = None):
        """rule(state, name, question) -> P(yes) for noul, an option name for choice/score."""
        self.rule = rule or (lambda s, n, q: 0.9 if q["type"] == "noul" else next(iter(q["criteria"])))
        self.calls: list[tuple[str, dict]] = []
        self.last_latency_ms = 12.0
        self.last_server_ms = 10.0
        self.url = "fake://decider"

    def ask(self, state: Any, questions: dict[str, dict[str, Any]], images: Any = None) -> dict[str, Decision]:
        self.calls.append((state, questions))
        out = {}
        for name, q in questions.items():
            v = self.rule(state, name, q)
            if q["type"] == "noul":
                out[name] = Decision.parse({"type": "noul", "noul": float(v)})
            elif q["type"] == "choice":
                opts = list(q["criteria"])
                probs = {o: (0.85 if o == v else 0.15 / max(1, len(opts) - 1)) for o in opts}
                out[name] = Decision.parse({"type": "choice", "choice": v, "probabilities": probs, "confidence": 0.85})
            else:
                levels = q["criteria"]
                i = levels.index(v)
                probs = {str(k): (0.8 if k == i else 0.2 / max(1, len(levels) - 1)) for k in range(len(levels))}
                out[name] = Decision.parse({"type": "score", "score": float(i), "probabilities": probs,
                                            "legend": {str(k): l for k, l in enumerate(levels)}})
        return out

    def health(self) -> dict[str, Any]:
        return {"checkpoint": "fake"}
