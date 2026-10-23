---
inclusion: always
---

# How this kit is laid out

Everything except the participant's own agent is already built and tested. Change `agent/`.
Change the rest only to fix a bug.

```
agent/                 THE PARTICIPANT'S AGENT (starts as the kit example; /new-agent replaces it)
  AGENT.md             the use case in plain words: drives the code, benchmark, article and video
  decision.py          the labelled REUSABLE DECISION PATTERN (PATTERN_TAG, QUESTIONS, the wiring class)
  tools.py             the agent's tools (Strands @tool functions); mock data is fine
  agent.py             HackathonAgent: Bedrock model + tools + the decision wired in
  eval_cases.jsonl     labelled cases for the benchmark: {"state", "expected": {question: answer}, "split"?}
  demo_script.yaml     the turns the video plays, with neutral narration lines
  features.yaml        Amazon Bedrock AgentCore features to deploy with it: Memory, Gateway (+ targets)
decider_kit/           reusable library (do not rename): Decider client, 5 patterns, LLM helpers (Strands),
                       AgentCore Memory/Gateway glue (agentcore.py), bench
examples/              memory_agent.py (AgentCore Memory, #context-memory), gateway_agent.py (AgentCore
                       Gateway, #tool-selection), vision_check.py (images, #policy)
demo/                  web UI: chat + live decision panel (./kit demo, recorded by ./kit video)
deploy/                AgentCore project used by ./kit deploy
scripts/               setup, status, video, article, readme, deploy, check, publish
submission/            generated outputs: bench/, video/, article/, SUBMISSION.md
.kiro/                 steering (this), skills (/hackathon, /new-agent, ...), hooks, specs
```

## Contracts other parts depend on (keep them)

- **`agent/agent.py`**
  - defines `NAME` and `class HackathonAgent` with `chat(message, session_id="default") -> dict`;
  - the dict holds `reply`, `decisions` (list of dicts: one per decider call, with probabilities
    in 0..1, a `verdict`, and `decider_ms`), `model_id` and `latency_ms`;
  - the constructor accepts `eager: bool | None` (demos only);
  - for agents that take photos: `chat(message, session_id, images=None)`, where `images` is a
    list of base64 strings or paths. The demo UI's paperclip sends them, the deployed runtime
    accepts `"images"` in its payload, and a `demo_script.yaml` turn can carry `image: <path>`.
    Tools get the photos through Strands' invocation state: `@tool(context=True)` and
    `decider_kit.llm.attached_images(tool_context)`.
- **`agent/decision.py`**
  - defines `PATTERN_TAG` (exactly one of the five tags: one decision pattern per agent) and
    `QUESTIONS` (the typed questions used by the benchmark);
  - starts with a docstring headed `REUSABLE DECISION PATTERN:` covering what it does, the
    typed questions and options, the wiring, and how to reuse it;
  - has no `IS_KIT_EXAMPLE` once it is the participant's.
- **`agent/eval_cases.jsonl`**: each case's `state` uses the same text layout the wiring sends
  to the decider at run time.

## Commands

Every command is `./kit <command>` on macOS and Linux, and `.\kit.cmd <command>` on Windows
(PowerShell or cmd). Use the form for the participant's OS (`./kit` below). `make <command>` also
works on macOS and Linux. `./kit help` lists them all.

| Command | What it does |
|---|---|
| `./kit tools` / `./kit tools install base\|deploy\|local` | check / install git, GitHub CLI, Node, AgentCore CLI, Ollama (asks first, user folder, no admin) |
| `./kit setup --yes --llm ... --mode ...` | where the LLM and the decider run; proves both with a real call |
| `./kit check-machine` | machine and AWS report; changes nothing |
| `./kit aws-login` | the participant types AWS keys **in the terminal** (never in chat); saved as profile `hackathon` |
| `./kit gh-login` | GitHub login in the browser (for publishing) |
| `./kit test`, `./kit run` | unit tests; one scripted conversation |
| `./kit demo-bg` / `./kit demo-stop` | the web UI at http://localhost:8501 in the background |
| `./kit data <name> --describe "..." --fields "a:str"` / `./kit data images <name> --query "..."` | synthetic rows / openly licensed photos |
| `./kit bench --split tune\|test` | decider vs the LLM on `agent/eval_cases.jsonl` → `submission/bench/` |
| `./kit deploy`, `./kit invoke "msg"`, `./kit destroy` | Amazon Bedrock AgentCore Runtime |
| `./kit article [--draft]`, `./kit video --target agentcore` | Builder Center bundle; `submission/video/demo.mp4` |
| `./kit readme`, `./kit check`, `./kit publish <repo>`, `./kit status` | README, requirements check, public GitHub repo, progress |

For anything else in Python use the venv's interpreter: `.venv/bin/python` (macOS, Linux) or
`.venv\Scripts\python.exe` (Windows). Settings live in `.env`, written by `./kit setup`: `DECIDER_MODE`
(local | ugmdu | custom), `DECIDER_URL`, `DECIDER_API_KEY`, `AWS_REGION`, `AWS_PROFILE`, and
the Amazon Bedrock model ids. Every model id is an environment variable, Amazon Nova by
default; never hardcode one:

| Variable | Used for | Default |
|---|---|---|
| `BEDROCK_MODEL_ID` | the agent | `us.amazon.nova-pro-v1:0` |
| `BEDROCK_SMALL_MODEL_ID` / `_MEDIUM_` / `_LARGE_` | model routing tiers | Nova Micro / Nova Lite / `BEDROCK_MODEL_ID` |
| `BENCH_LLM_MODEL_ID` | the LLM baseline in `./kit bench` | `BEDROCK_MODEL_ID` |
| `BEDROCK_PRICE_IN` / `_OUT` | cost numbers for a model the kit has no price for | none |

The agent's LLM runs where `LLM_PROVIDER` says: `bedrock` (default), `local` (Ollama,
`LLM_MODEL_ID` such as `qwen3.5:4b`), `ugmdu` (the user group's cloud: `qwen3.5-4b`,
`gpt-oss-20b`).

**Every LLM call goes through the Strands Agents SDK.** Build models with
`decider_kit.llm.agent_model(model_id=None)` and call them through a Strands `Agent`; for a
one-off call (no tools) use `decider_kit.llm.ask(prompt, output_model=...)`. Never call the
Bedrock runtime API (boto3 `converse`, `invoke_model`) or a provider SDK directly; a test fails
if you do. The deployed agent always uses Amazon Bedrock.

Images: `Decider.ask(state, questions, images=[...])` with a vision decider (`DECIDER_VISION=1`
locally, or the hosted API); Strands agents take images as content blocks
(`decider_kit.llm.image_blocks`).
