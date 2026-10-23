---
name: new-agent
description: Turn the participant's use-case description into their own agent - interview, Kiro spec, then agent/ code (decision pattern, tools, Bedrock agent, labelled eval cases, demo script) that replaces the kit example. Use when the participant describes an agent idea, says /new-agent, or asks to build or change their agent.
license: Apache-2.0
metadata:
  author: AWS User Group Madurai
  version: "1.0"
---

# /new-agent: from a description to a working agent

## 1. Interview: several short rounds until the agent is clear

Start by asking the participant to **describe the use case in their own words**. Then keep asking,
two or three questions per message, until you could write the spec without guessing. Skip what
they already answered; offer concrete options (with a recommendation) whenever a choice helps them
decide faster. Typical rounds:

**Round 1: the job.**
- Who uses the agent, and what do they ask it? One real example request.
- What goes wrong today without the agent, or without a good decision?

**Round 2: the one decision.** The rules ask for exactly one decision pattern. Offer the five
shapes, each with an example from *their* domain, and recommend one:
- **tool selection:** which tool or specialist handles this request?
- **guardrails:** is this tool call or input safe and grounded?
- **policy:** does this content break our rules: allow, review or block?
- **model routing:** which model is enough for this request?
- **context and memory:** which notes are relevant, and what is worth remembering?

**Give the decider a judgement, not arithmetic.** If a few lines of code can decide it (a number
over a limit, a date window, a count, a lookup), do that in code, in the tool, and never ask the
decider. The decider is for what needs reading language: what the user actually asked for,
whether an action is grounded in the conversation, whether a message breaks a rule written in
prose, which tool fits, whether a note is relevant. A good test: "could an `if` statement do
this reliably?" If yes, it is not the decision. Facts the decision needs (records, fines,
history) come from your data or tools, never from arguments the LLM made up.

Then: what happens on each answer, and when the decider is unsure (ask the user, a human
confirms, or fall back to the LLM)? Should the decision look at images (photos, screenshots)?

**Round 3: tools and data.**
- What should the agent be able to do? 2 to 4 tools.
- **Where does the data come from?** Offer:
  1. **synthetic** (recommended without real data): generated now with
     `./kit data <name> --describe "..." --fields "a:str,b:float" --n 20`
     into `agent/data/`, deterministic for tests and the demo;
  2. **an API** (public, or theirs): a tool calls it, the key goes in `.env`, and a recorded
     sample in `agent/data/` keeps tests and the demo working offline;
  3. **a file or service they have:** CSV or JSON copied into `agent/data/`, or an AWS source
     (DynamoDB, S3, a Bedrock knowledge base through AgentCore Gateway);
  4. a mix.
- **If the decision looks at images**, ask where the photos come from:
  1. their own photos (best; phone pictures are fine);
  2. openly licensed photos from Wikimedia Commons:
     `./kit data images <name> --query "<what to find>" --n 6` (credits go to
     `agent/data/images/SOURCES.md`; keep it). Search results are noisy: **open every image,
     check it shows what you will label it as, and delete the wrong ones** before writing cases;
  3. an image model in their AWS account, if they have one enabled.
  Never draw the answer into an image (a "FRESH" or "ROTTEN" label, coloured blocks standing
  for produce): the decider would read the text, and the benchmark would measure nothing.
- Ask for the fields that matter, and a few tricky cases the decision must handle.

**Round 4: AgentCore features** (optional; say what each adds):
- **Memory:** remembers users across sessions; the natural fit for `#context-memory`
  (`examples/memory_agent.py`).
- **Gateway:** many tools behind one MCP endpoint (web search with no infrastructure, a
  knowledge base, a Lambda function, a REST API, an MCP server); the natural fit for
  `#tool-selection` (`examples/gateway_agent.py`).
- **Neither:** fine; Runtime alone already puts the agent on AWS.

**Round 5: the showcase.**
- What makes it memorable in a 3-minute demo: what does the decider catch or save?
- A short name, a one-line pitch, and 3 to 5 features beyond the decision (domain, data, UI,
  integrations). These lead the README, the article and the video.

**Confirm.** Restate the agent in one paragraph: users, the one decision and its pattern tag,
the tools, the data source, the AgentCore features. Get a "yes" before writing code. The idea
must be the participant's own: if it is the kit example (store refunds), ask for another angle.

## 2. Spec: `.kiro/specs/<agent-slug>/`

- **`requirements.md`:** user stories with EARS acceptance criteria. Include:
  - "WHEN <situation> THE agent SHALL ask Strands Decider 2B <question> BEFORE <action>";
  - low-confidence handling;
  - "paired with Amazon Bedrock".
- **`design.md`:**
  - the state text layout;
  - the typed questions with option descriptions;
  - the thresholds and actions;
  - the seam (InterventionHandler method or pre-agent step);
  - tools;
  - the eval-case plan: at least 24 cases covering every branch, including near-misses, tagged
    `"split": "tune"` or `"split": "test"` (about half each).
- **`tasks.md`:** checkbox tasks mapping to the files below. Tick them as you go.

## 3. Code: replace the kit example in `agent/`

Copy shapes, never use cases. Start from the closest pattern in `decider_kit/patterns/` and from
`agent/` (the example) for structure.

- **`agent/AGENT.md`:** the interview's answers, in the same layout as the example: the pitch, the features, who it is for, the decision and Amazon Bedrock.
- **`agent/decision.py`:**
  - **Header docstring:** must begin `REUSABLE DECISION PATTERN: <name>  (<tag>)`, with sections
    What it does / Typed questions and options / Wiring / How to reuse it.
  - **Constants:** `PATTERN_TAG` (exactly one) and `QUESTIONS`.
  - **The wiring class or function**, which appends one record per decider call to `.log`: the
    probabilities, a `verdict` and `decider_ms`.
  - **Remove `IS_KIT_EXAMPLE`.**
  - **For `Guide`, keep the convergence guard:** a retried guided call is denied.
- **`agent/features.yaml`:** set `enabled: true` for the AgentCore features chosen in question
  7, with the memory strategies and the gateway targets (each key is an
  `agentcore add gateway-target` flag; `./kit deploy` adds them). Wire them in with
  `decider_kit/agentcore.py`: `AgentCoreMemoryStore` (candidates for `DeciderMemory`, `save`)
  and `gateway_client()` + `gateway_tools()` (tools for `ToolSelector` or the Agent). Copy the
  shape of `examples/memory_agent.py` (Memory, `#context-memory`) or
  `examples/gateway_agent.py` (Gateway, `#tool-selection`).
- **`agent/data/`:** the data chosen in round 3 (generated, copied or a recorded API sample).
- **`agent/tools.py`:** `@tool` functions with one-line docstrings; read data with
  `decider_kit.data.load("<name>")`; API calls read their key from the environment and fall back
  to the recorded sample when it is missing.
- **`agent/agent.py`:**
  - keep `HackathonAgent.chat()` and its return keys;
  - build the Strands `Agent` with `decider_kit.llm.agent_model(self.model_id)`: it follows
    `LLM_PROVIDER` (Bedrock, local Ollama, the user group's cloud); never call boto3 or a model
    SDK directly;
  - for image decisions: add `images=None` to `chat()` and call the Strands Agent with
    `agent([*image_blocks(images), {"text": message}], invocation_state={"images": images})`
    (as `agent/agent.py` does); a tool that checks the photo is `@tool(context=True)` and reads
    them with `attached_images(tool_context)`, then `Decider.ask(..., images=photos)`; users attach photos with the
    paperclip in `./kit demo`, and video turns take `image: agent/data/images/<file>`
    (see `examples/vision_check.py`);
  - set `NAME` and `SYSTEM_PROMPT`;
  - add `EAGER_PROMPT` only if a demo needs the agent to make mistakes;
  - if the seam is outside the agent (routing, tool selection, memory), call it in `chat()`
    before building or calling the Agent, and add its log records to `decisions`.
- **`agent/eval_cases.jsonl`:** 24+ cases, one JSON object per line:
  `{"state": ..., "expected": {question: "yes"|"no"|option|level}, "split": "tune"|"test"}`.
  The state must use exactly the layout the wiring builds at run time. Label by the question's
  own definitions; when a case is ambiguous, rewrite it rather than guess.
- **`agent/demo_script.yaml`:** 3 or 4 turns, neutral `narrate` lines, and an honest `intro`
  (mention eager mode if used).
- **Tests:** `tests/test_agent_contract.py` already checks the contract. Add one test for your
  wiring with `tests/fakes.py:FakeDecider`.

## 4. Verify

1. Run `./kit test`, then `./kit run`. Fix until green. With AgentCore features on, run
   `./kit deploy` once so Memory and the Gateway exist; local runs then use them (their ids are
   read from `submission/deployment.json`).
2. Show the participant one real conversation with its decision records.
3. Update `tasks.md`.
