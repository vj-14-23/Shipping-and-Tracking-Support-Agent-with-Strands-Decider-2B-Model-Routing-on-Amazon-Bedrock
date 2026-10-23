---
name: decision-pattern
description: Design, label, measure and tune the reusable Strands Decider 2B decision pattern (typed questions, option descriptions, thresholds, low-confidence handling). Use when accuracy is weak, when choosing questions, or when the participant asks how the decision works or how others reuse it.
license: Apache-2.0
metadata:
  author: AWS User Group Madurai
  version: "1.0"
---

# /decision-pattern: make the decision good, and reusable

## What judges look for

30% of the score is effective Strands Decider 2B use, including the quality of the reusable
pattern. A good pattern:
- asks narrow questions with well-described options;
- keeps thresholds in code;
- handles low confidence explicitly;
- is wired at a clear seam;
- is labelled so another builder can copy `agent/decision.py` into their own agent.

## Pick a decision worth a model

The decider earns its place on judgements over language (intent, grounding, relevance, a rule
written in prose, choosing among tools by their descriptions). Thresholds, dates, counts and
lookups belong in code: an `if` is exact, free and instant, and judges will ask why a model
was used. Put the facts code already knows into the state; ask the decider what code cannot
answer. Never let the decision rest on values the LLM passed as tool arguments: read them from
your data.

## Tuning loop (once or twice, never on the test split)

1. Run `./kit bench --split tune` and look at the misses in `submission/bench/results.json`
   (`rows[*]` where the decider label differs from `expected`).
2. Diagnose each miss:
   - a question *about* an action read as a request? Sharpen the option descriptions with
     concrete examples on both sides;
   - missing facts? Put them into the state;
   - two judgements in one question? Split it.
3. Re-run on `tune`. When it stops improving, run `./kit bench --split test` and report **those**
   numbers.
4. Choose thresholds from `bench-confidence.png`: the confidence above which the decider acts
   alone, and what happens below it (ask the user, `Confirm` for a human, or fall back to the
   Bedrock LLM). Write that rule in `decision.py`'s docstring.

## Labelling checklist for agent/decision.py

- The first docstring line is `REUSABLE DECISION PATTERN: <name>  (<tag>)`.
- It has the sections What it does / Typed questions and options / Wiring / How to reuse it.
- `PATTERN_TAG` is one of `#tool-selection`, `#guardrails`, `#policy`, `#model-routing` or
  `#context-memory`.
- `QUESTIONS` holds the exact typed questions used at run time.
- Exactly one pattern: one `PATTERN_TAG`, one decision, one seam.
- `./kit check` passes its pattern checks.
