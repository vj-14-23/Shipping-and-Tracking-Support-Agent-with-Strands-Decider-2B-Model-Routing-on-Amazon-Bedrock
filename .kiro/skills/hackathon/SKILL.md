---
name: hackathon
description: Run the whole Agent Experience Hackathon (Strands Decider) submission end to end - present the options (where the LLM and the decider run, deployment, cost, latency, time), set up, interview the participant about their use case and data until it is clear, build the agent, show the running app, docs and benchmarks, deploy to AWS, write the article, make the video, publish. Use when the participant says /hackathon, "do the hackathon", "build my submission" or "start".
license: Apache-2.0
metadata:
  author: AWS User Group Madurai
  version: "2.0"
---

# /hackathon: from an idea to a full submission

You are guiding a participant through the Agent Experience Hackathon: Strands Decider. The kit
has everything prebuilt (`.kiro/steering/kit.md`); the rules are in
`.kiro/steering/hackathon.md`. Turn **their idea** into **their agent**, then produce everything
the rules require.

Ground rules for the whole flow:
- **One step at a time.** End each step with one line on what is done and what is next
  (`./kit status`), and wait for the participant where a step says to.
- **Ask, then build.** Never guess what they want: when something is unclear, ask, and offer 2 to 4
  concrete options with a recommendation. Keep each message short.
- **Honest numbers only.** Every figure you show comes from a real run or from
  `docs/OPTIONS.md`, copied as written: never round, improve or invent a latency, cost or limit.
  The kit example is never the submission. Keys stay in `.env`.
- **Run, don't ask, what a command can tell you** (RAM, disk, chip, installed tools, AWS
  credentials, tools): `./kit check-machine` and `./kit tools` report all of it.
- **Commands:** `./kit <command>` on macOS and Linux, `.\kit.cmd <command>` on Windows. Install
  nothing without asking in chat first; once they say yes, pass `--yes`.
- **Secrets never go through chat.** AWS keys: the participant runs `./kit aws-login` in the Kiro
  terminal. GitHub: `./kit gh-login` in the terminal. Only the user group key may be pasted in chat
  (you store it in `.env` and never repeat it).
- **One decision pattern.** The rules ask for exactly one.

## 1. Welcome and options (2 min): check, present, then ask

Open with this welcome, word for word, before running anything:

> Welcome to the Agent Experience Hackathon: Strands Decider, with the **AWS User Group Madurai**
> hackathon kit. I'm here to take you from an idea to a complete submission. Let me first check
> your machine and installed tools so my recommendations fit your setup.

The participant installed the kit with one command (docs/GETTING-STARTED.md), so `./kit` and
`.venv` should exist; if `.venv` is missing, run `./kit venv`. Run `./kit check-machine` and
`./kit tools` so your recommendation fits *their* machine, AWS state and installed tools. Then show the participant,
from `docs/OPTIONS.md`, in a compact form:
1. **Where the agent's LLM runs:** Amazon Bedrock (default; required for the submission),
   local through Ollama (no cloud cost; pick a model by size, 1.2 to 6.6 GB), or the AWS User
   Group Madurai cloud (`qwen3.5-4b`, `gpt-oss-20b`; nothing to install). For each: what to
   install, time to set up, latency per agent turn, cost and usage limits.
2. **Where Strands Decider 2B runs:** local (about 5 GB, 0.2 to 0.3 s a decision on Apple
   silicon) or the hosted API (nothing to install, about 1.2 s). Both can read images.
3. **Deployment to AWS** (required to submit): Amazon Bedrock AgentCore Runtime, 2 to 5 min to
   deploy, pay per use (cents for a hackathon), plus optional AgentCore Memory and Gateway.
   Ask now whether they have AWS credentials and Bedrock access, so there is no surprise later;
   if not, they can build locally first and add AWS before step 6.
4. **Time:** about 30 minutes in total (the table at the end of `docs/OPTIONS.md`).

Recommend a combination from "Recommended combinations" based on what they told you (no AWS yet,
small laptop, wants zero cost), then **ask them to choose** the LLM option, the decider option and
whether they will deploy with Memory or Gateway (or decide later).

## 2. Setup (5 to 15 min, mostly downloads): run the /setup skill

1. **Keys and accounts for their path, before setup:**
   - hosted decider or user group cloud (paths A and C): ask for their AWS User Group Madurai key
     (from https://www.awsugmdu.in) unless `.env` already has one;
   - Amazon Bedrock (path A): if `check-machine` found no AWS credentials, ask them to run
     `./kit aws-login` in the terminal and wait until it prints OK; if Bedrock model access is
     missing, tell them to enable Amazon Nova Pro under Bedrock → Model access (us-east-1);
   - local (path B): tell them Ollama (if missing) and the model download sizes, and get a yes:
     setup installs Ollama into their user folder.
2. Run setup with their choices, non-interactively:
`./kit setup --yes --llm <bedrock|local|ugmdu> [--llm-model qwen3.5:4b]
--mode <local|ugmdu> [--key ...] [--vision]`. Never echo a key.
3. Report what it measured on their machine: the LLM's tool call and its time, the decider's answer
   and its time. If something failed, fix it with them (the table "If something goes wrong" in
   docs/GETTING-STARTED.md) and run setup again.

## 3. The use case (5 min, several rounds): run the /new-agent interview

1. Ask them to **describe the use case** in their own words: who uses it, and what they ask it.
2. Keep asking follow-up questions **until you could write the spec without guessing**, a few
   at a time, each with options where that helps:
   - the users and one real example request;
   - the **one decision** for Strands Decider 2B, with the five shapes as options (tool
     selection, guardrails, policy, model routing, context and memory) and your recommendation;
   - what happens on each answer, and when the decider is unsure;
   - the tools (2 to 4) and what makes the demo memorable;
   - whether the decision should look at images;
   - name, one-line pitch and 3 to 5 features.
3. **Ask where the data comes from**, with options:
   - **synthetic:** generated now by the LLM into `agent/data/` (`./kit data`),
     deterministic for tests and the demo; best when there is no real data yet;
   - **a public or their own API:** a tool calls it; the key goes in `.env`, and a recorded
     sample in `agent/data/` keeps tests and the demo working offline;
   - **a file or service they have:** CSV or JSON copied into `agent/data/`, or an AWS source
     (DynamoDB, S3, a Bedrock knowledge base through AgentCore Gateway);
   - mixed is fine (for example synthetic orders plus a real weather API).
4. Restate the agent in one paragraph: the users, the decision and its pattern tag, the tools,
   the data source, the AgentCore features. **Get a "yes"** before building.

## 4. Build (10 min): continue /new-agent

1. Write the spec in `.kiro/specs/<agent-slug>/` (requirements.md, design.md, tasks.md).
2. Prepare the data (generate, copy or record a sample).
3. Implement `agent/` (AGENT.md, decision.py, tools.py, agent.py, eval_cases.jsonl,
   demo_script.yaml, features.yaml). Write **at least 24 eval cases, at least 12 of them in the
   test split**, covering every branch and some near-misses; fewer makes the benchmark noise.
4. `./kit test`, then `./kit run`. Fix until both pass.
5. `./kit bench --split tune`, tune once with /decision-pattern if needed, then `./kit bench --split test`.

## 5. Show them what they built (3 min): wait for their reaction

1. **The app:** start it yourself with `./kit demo-bg` (runs in the background and prints the URL;
   `./kit demo-stop` stops it), then give them http://localhost:8501. Suggest 2 or 3 messages to
   try, including one where the decision changes the outcome (photos: the paperclip button).
   Ask what they think.
2. **The docs (do not skip):** run `./kit readme`, then show README.md section by section (pitch, features, the
   decision pattern, the measured table, how to run it) and point to the spec in `.kiro/specs/`.
3. **The benchmark:** show `submission/bench/results.md` and name the four charts in
   `submission/bench/` (accuracy, latency, cost, confidence) so they can open them. Explain
   what happens on low confidence, and say plainly where it is weak.
4. Ask whether to change anything. Loop back to step 4 for changes; move on when they are happy.

## 6. Deploy to AWS (5 min, mostly waiting)

1. Remind them of the cost (pay per use; `./kit destroy` removes it) and that the deployed agent
   uses Amazon Bedrock and the hosted decider.
2. Tools and AWS: run `./kit tools check deploy`; if anything is missing, ask, then
   `./kit tools install deploy --yes` (Node and the AgentCore CLI into the user folder; never `sudo`
   or a global npm install). No AWS credentials yet (paths B and C)? Ask them to run
   `./kit aws-login` in the terminal now, and to enable Amazon Nova Pro in Bedrock → Model access.
3. `./kit deploy` (adds Memory and Gateway from `agent/features.yaml`), then
   `./kit invoke "<a demo turn>"` to prove it answers from AWS.

## 7. Article (4 min): run the /write-article skill

Draft, then hand it over: the article must be in their own words before they publish it.

## 8. Video (3 min)

1. Refresh `agent/demo_script.yaml` (`.kiro/steering/video-and-deploy.md`).
2. `./kit video --target agentcore` (plain `./kit video` only if the deploy failed).
3. Show them `submission/video/demo.mp4` and `narration.md`; re-record if anything is off.

## 9. Finish (2 min)

1. `./kit readme`, `./kit check`, and fix every FAIL.
2. Ask for the repository name and confirm it will be **public** on their GitHub. If
   `./kit tools check base` shows git or gh missing, ask and install (`./kit tools install base --yes`).
   If they are not logged in to GitHub, ask them to run `./kit gh-login` in the terminal. Then
   `./kit publish <repo>` (it creates their repository; the kit itself came from the user group's
   download and is not a git clone).
3. Give them `submission/SUBMISSION.md`: what is done (repo, article bundle, video file) and what
   is left (upload the video as public, publish the article with the two tags, submit the three
   links before 23 October 2026, 11:59 p.m. PT), plus `./kit destroy` once judging is over.
4. Close with: "Built with the AWS User Group Madurai Strands Decider hackathon kit. Good luck!"
   and point them to https://www.awsugmdu.in for the user group's community and events.
