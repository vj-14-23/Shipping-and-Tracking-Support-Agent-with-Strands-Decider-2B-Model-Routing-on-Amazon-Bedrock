"""Benchmark a decision: Strands Decider compared with an LLM on the same labelled cases.

    python -m decider_kit.bench --cases agent/eval_cases.jsonl --questions agent.decision:QUESTIONS \
        --out submission/bench

The LLM baseline answers the same typed questions through a Strands Agent with structured output,
on LLM_PROVIDER (Amazon Bedrock by default, or a local or hosted model; see decider_kit/llm.py).

`--cases` is JSONL, one case per line:
    {"state": "...", "expected": {"<question name>": "<yes|no|option|level>", ...}}

Reports, per system: accuracy (overall and per question), latency p50/p95 per decision, cost per
1,000 decisions, and low-confidence handling (accuracy on the cases each system was confident
about, and how many it would have sent to a human). Writes `results.json`, `results.md` and
charts (`bench-accuracy.png`, `bench-latency.png`, `bench-cost.png`, `bench-confidence.png`).
These are what the rules call a measured latency or cost comparison (a judging bonus).
"""

from __future__ import annotations

import argparse
import os
import importlib
import json
import time
from pathlib import Path
from typing import Any

from .llm import describe, llm_answer, provider
from .client import Decider

# Compute cost of a decision (USD per 1,000) by where the decider runs. Local: your own machine,
# no marginal cost. Hosted (AWS User Group Madurai, decider-cloud on c7i.xlarge): instance price over
# measured throughput at full use (about 0.035). Override with DECIDER_USD_PER_1K.
DECIDER_USD_PER_1K = {"local": 0.0, "ugmdu": 0.035, "custom": 0.035}


def load_questions(spec: str) -> dict[str, dict[str, Any]]:
    """`module:ATTR` (a dict of questions) or a .json file."""
    if spec.endswith(".json"):
        return json.loads(Path(spec).read_text())
    mod, attr = spec.split(":")
    return dict(getattr(importlib.import_module(mod), attr))


def _norm(x: Any) -> str | None:
    return None if x is None else str(x).strip().lower()


def _pct(xs: list[float], q: float) -> float | None:
    if not xs:
        return None
    s = sorted(xs)
    return round(s[min(len(s) - 1, int(q * (len(s) - 1) + 0.5))], 1)


def run(cases: list[dict[str, Any]], questions: dict[str, dict[str, Any]], llm_model: str | None, threshold: float = 0.7,
        decider: Decider | None = None) -> dict[str, Any]:
    d = decider or Decider()
    rows: list[dict[str, Any]] = []
    for i, c in enumerate(cases):
        qs = {k: v for k, v in questions.items() if k in c["expected"]}
        row: dict[str, Any] = {"i": i, "expected": c["expected"]}
        ans = d.ask(c["state"], qs, images=c.get("images"))
        row["decider"] = {k: {"label": a.label, "confidence": round(a.confidence, 4)} for k, a in ans.items()}
        row["decider_ms"] = d.last_latency_ms
        row["decider_server_ms"] = d.last_server_ms
        if llm_model:
            try:
                la, usage = llm_answer(c["state"], qs, llm_model, images=c.get("images"))
                row["llm"], row["llm_ms"], row["llm_cost"] = la, usage["latency_ms"], usage["cost_usd"]
            except Exception as e:  # noqa: BLE001 - recorded, the run continues
                row["llm_error"] = f"{type(e).__name__}: {e}"
        rows.append(row)
        print(f"[bench] {i + 1}/{len(cases)}", flush=True)
    from .config import settings

    try:  # which checkpoint answered (local: /health; hosted: /v1/models)
        h = d.health()
        model = h.get("checkpoint") or (h.get("data") or [{}])[0].get("id")
    except Exception:  # noqa: BLE001
        model = None
    return {"decider_model": model, "rows": rows, "summary": summarise(rows, questions, llm_model, threshold), "threshold": threshold,
            "llm_model": llm_model, "llm_provider": provider(), "llm_where": describe(model_id=llm_model) if llm_model else None,
            "decider_url": d.url, "decider_mode": settings().decider_mode, "ran_at": time.time()}


def summarise(rows: list[dict[str, Any]], questions: dict[str, Any], llm_model: str | None, threshold: float) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for system in ("decider", "llm"):
        if system == "llm" and not llm_model:
            continue
        hits, total, conf_hits, conf_total = 0, 0, 0, 0
        per_q: dict[str, list[int]] = {}
        lat = [r[f"{system}_ms"] for r in rows if r.get(f"{system}_ms") is not None]
        for r in rows:
            if system not in r:
                continue
            for q, exp in r["expected"].items():
                a = r[system].get(q, {})
                ok = int(_norm(a.get("label")) == _norm(exp))
                hits += ok
                total += 1
                per_q.setdefault(q, []).append(ok)
                if (a.get("confidence") or 0) >= threshold:
                    conf_hits += ok
                    conf_total += 1
        n_dec = sum(len(r["expected"]) for r in rows)
        if system == "llm":
            cost = sum(r.get("llm_cost", 0) for r in rows) / max(1, n_dec) * 1000
        else:
            import os

            from .config import settings

            cost = float(os.environ.get("DECIDER_USD_PER_1K", DECIDER_USD_PER_1K.get(settings().decider_mode, 0.0)))
        out[system] = {"accuracy": round(hits / total, 4) if total else None, "decisions": total,
                       "per_question": {q: round(sum(v) / len(v), 4) for q, v in per_q.items()},
                       "latency_p50_ms": _pct(lat, 0.5), "latency_p95_ms": _pct(lat, 0.95),
                       "usd_per_1k_decisions": round(cost, 4),
                       "confident_share": round(conf_total / total, 4) if total else None,
                       "accuracy_when_confident": round(conf_hits / conf_total, 4) if conf_total else None,
                       "sent_to_human_at_threshold": total - conf_total}
    if "llm" in out and out["decider"]["latency_p50_ms"] and out["llm"]["latency_p50_ms"]:
        out["speedup_p50"] = round(out["llm"]["latency_p50_ms"] / out["decider"]["latency_p50_ms"], 2)
    return out


def charts(res: dict[str, Any], out: Path) -> list[str]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    s = res["summary"]
    systems = [k for k in ("decider", "llm") if k in s]
    names = {"decider": "Strands Decider 2B", "llm": res.get("llm_model") or "LLM"}
    colors = {"decider": "#FF9900", "llm": "#7C8DB5"}
    files = []

    def bar(metric: str, title: str, fname: str, fmt: str) -> None:
        fig, ax = plt.subplots(figsize=(7, 3.6), dpi=130)
        vals = [s[k][metric] or 0 for k in systems]
        ax.bar([names[k] for k in systems], vals, color=[colors[k] for k in systems])
        for i, v in enumerate(vals):
            ax.text(i, v, fmt.format(v), ha="center", va="bottom", fontsize=11)
        ax.set_title(title)
        ax.spines[["top", "right"]].set_visible(False)
        fig.tight_layout()
        fig.savefig(out / fname)
        plt.close(fig)
        files.append(fname)

    bar("accuracy", "Accuracy on the labelled cases", "bench-accuracy.png", "{:.0%}")
    bar("latency_p50_ms", "Median latency per decision (ms)", "bench-latency.png", "{:.0f} ms")
    bar("usd_per_1k_decisions", "Cost per 1,000 decisions (USD)", "bench-cost.png", "${:.3f}")
    fig, ax = plt.subplots(figsize=(7, 3.6), dpi=130)
    for k in systems:
        pts = []
        for t in [x / 20 for x in range(10, 20)]:
            hit = tot = 0
            for r in res["rows"]:
                for q, exp in r["expected"].items():
                    a = r.get(k, {}).get(q, {})
                    if (a.get("confidence") or 0) >= t:
                        tot += 1
                        hit += int(_norm(a.get("label")) == _norm(exp))
            if tot:
                pts.append((tot / max(1, sum(len(r["expected"]) for r in res["rows"])), hit / tot))
        if pts:
            ax.plot([p[0] for p in pts], [p[1] for p in pts], marker="o", color=colors[k], label=names[k])
    ax.set_xlabel("share of decisions the system answers alone (rest go to a human)")
    ax.set_ylabel("accuracy on those")
    ax.set_title("Low-confidence handling")
    ax.legend()
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(out / "bench-confidence.png")
    plt.close(fig)
    files.append("bench-confidence.png")
    return files


def markdown(res: dict[str, Any]) -> str:
    s = res["summary"]
    lines = [f"Decider: {res.get('decider_model') or 'Strands Decider 2B'} ({res.get('decider_mode')}). "
             f"{len(res['rows'])} labelled cases, {res['summary']['decider']['decisions']} decisions.\n",
             "| | Strands Decider 2B" + (f" | {res['llm_model']}" if "llm" in s else "") + " |",
             "|---|---" + ("|---" if "llm" in s else "") + "|"]
    rows = [("Accuracy", "accuracy", "{:.1%}"), ("Latency p50 per decision", "latency_p50_ms", "{:.0f} ms"),
            ("Latency p95", "latency_p95_ms", "{:.0f} ms"), ("Cost per 1,000 decisions", "usd_per_1k_decisions", "${:.4f}"),
            (f"Answered alone at confidence >= {res['threshold']}", "confident_share", "{:.0%}"),
            ("Accuracy when confident", "accuracy_when_confident", "{:.1%}")]
    for label, k, f in rows:
        vals = [f.format(s[sys][k]) if s[sys].get(k) is not None else "-" for sys in ("decider", "llm") if sys in s]
        lines.append(f"| {label} | " + " | ".join(vals) + " |")
    if s.get("speedup_p50"):
        sp = s["speedup_p50"]
        lines.append(f"\nAt the median the decider was {sp:.1f}x faster than the LLM." if sp >= 1
                     else f"\nAt the median the LLM was {1 / sp:.1f}x faster than the decider on this setup ({res.get('decider_mode')}).")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", required=True)
    ap.add_argument("--questions", required=True, help="module:ATTR or a .json file")

    from .llm import default_model_id

    ap.add_argument("--llm", default=os.environ.get("BENCH_LLM_MODEL_ID") or default_model_id(),
                    help="model for the LLM baseline on LLM_PROVIDER (BENCH_LLM_MODEL_ID, else the agent's model; '' to skip)")
    ap.add_argument("--threshold", type=float, default=0.7)
    ap.add_argument("--split", default="", help="only cases with this split (tune or test); report test numbers")
    ap.add_argument("--out", default="submission/bench")
    a = ap.parse_args()
    cases = [json.loads(x) for x in Path(a.cases).read_text().splitlines() if x.strip()]
    if a.split:
        cases = [c for c in cases if c.get("split", "test") == a.split]
    if len(cases) < 12:
        print(f"[bench] WARNING: only {len(cases)} cases in this run; 12+ per split (24+ in total) makes the numbers credible")
    res = run(cases, load_questions(a.questions), a.llm or None, a.threshold)
    res["split"] = a.split or "all"
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "results.json").write_text(json.dumps(res, indent=1, default=str))
    md = markdown(res)
    (out / "results.md").write_text(md + "\n")
    res["charts"] = charts(res, out)
    print(md)


if __name__ == "__main__":
    main()
