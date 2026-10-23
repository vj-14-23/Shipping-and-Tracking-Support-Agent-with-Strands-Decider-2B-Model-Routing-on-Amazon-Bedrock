---
inclusion: always
---

# Strands Decider 2B: how to hand it a decision

Strands Decider 2B is an open 2-billion-parameter **decision** model. It does not generate text.
It reads a **state** (any text) and **typed questions**, and returns calibrated probabilities in
one forward pass:
- **noul:** yes or no, giving P(yes).
- **choice:** one of N named options, each with a probability.
- **score:** a level on an ordered rubric, giving the expected level and a probability per level.

Default model: `StrandsAgents/strands-decider-2B-qwen3.5-v1-2610`, Apache-2.0. The older
`StrandsAgents/strands-decider-2B-hobson-v19` also works.

## The client (decider_kit)

```python
from decider_kit import Decider
d = Decider()   # reads .env: local server, the AWS User Group Madurai hosted API, or a custom URL
a = d.ask(state_text, {
    "refund": Decider.noul("Is the customer asking for a refund?", {"true": "...", "false": "..."}),
    "team":   Decider.choice("Which team should handle it?", {"billing": "money", "shipping": "deliveries"}),
    "urgency": Decider.score("How urgent is it?", ["low", "medium", "high"]),
})
a["refund"].p_yes, a["refund"].yes, a["team"].label, a["team"].confidence, a["urgency"].label
d.last_latency_ms
```

## Writing questions that work

- **One judgement per question.** Narrow yes/no questions beat broad ones.
- **Always describe the options.** Give noul `{"true": ..., "false": ...}` and choice
  `{option: meaning}`. The descriptions carry most of the signal.
- **Put all the facts in the state:** conversation, proposed tool call, document. The decider
  sees nothing else.
- **Ask everything about one state in one call.** The state is encoded once and shared, so eight
  questions cost far less than eight calls.
- **The model classifies; your code decides.** Thresholds and actions are ordinary `if`
  statements in code you own.
- **Handle low confidence explicitly.** Below about 0.6 to 0.7 confidence: ask the user, send to
  a human (`Confirm`), or fall back to the LLM. Report how often that happens.
- **Measure, then reword.** Run `./kit bench`.
  - Watch for the classic confusion: a question *about* an action read as a request *for* it.
  - Fix it with sharper option descriptions ("an instruction such as ..." against "a question
    such as ...").
  - Keep a held-out split for the numbers you report.

## Wiring into a Strands agent (strands-agents >= 1.60)

- **Before a tool runs:** a Strands `InterventionHandler.before_tool_call`. It returns:
  - `Proceed`;
  - `Guide(feedback=...)`: send the model back with advice;
  - `Deny(reason=...)`;
  - `Confirm(prompt=...)`: ask a human.
- **Before the agent starts:** `before_invocation`, for input checks.
- **Make `Guide` converge.** If the agent retries the same guided call unchanged, return `Deny`.
  See `agent/decision.py`.
- **Outside the agent:** routing (model or tool) and memory recall happen before you build or
  call the Agent. See `decider_kit/patterns/`.

| Pattern (`decider_kit/patterns/`) | Tag | Seam |
|---|---|---|
| `tool_selection.ToolSelector` | #tool-selection | narrow the agent's tools per request |
| `guardrails.DeciderGuardrail` | #guardrails | InterventionHandler on inputs and tool calls |
| `policy.PolicyCheck` | #policy | allow / review / block before acting or sending |
| `model_routing.ModelRouter` | #model-routing | pick the Bedrock model per request |
| `context_memory.DeciderMemory` | #context-memory | recall relevant memories, decide what to store |

## Speed expectations (be honest in the article)

| Where the decider runs | Time per decision |
|---|---|
| GPU or Apple silicon (MLX) | about 0.1 to 0.3 s |
| c7i CPU instance | about 0.7 s |
| The hosted API, plus your network | about 1 to 2 s |
| A 2 vCPU microVM | about 10 s |

A Bedrock LLM call is about 1 to 2 s. The decider wins on cost, privacy and calibrated
confidence everywhere, and on speed when it runs on a GPU, on MLX or close to the agent.
