---
name: setup
description: Check this machine and AWS, present the options (where the agent's LLM runs - Amazon Bedrock, local Ollama or the AWS User Group Madurai cloud - and where Strands Decider 2B runs - local or hosted - with install, time, latency, cost and usage), then set up the chosen ones and prove them with a real tool call and a real decision. Use when the participant says /setup, first opens the repo, or anything about models, the decider not answering, Bedrock access, keys or requirements.
license: Apache-2.0
metadata:
  author: AWS User Group Madurai
  version: "1.0"
---

# /setup: options, then machine, LLM and decider

1. If `.venv` does not exist, run `./kit venv` (about 1 min).
2. Run `./kit check-machine`. It reports the machine (RAM, disk,
   GPU), AWS credentials and its recommendation, and changes nothing.
3. **Present the options** from `docs/OPTIONS.md` as two short tables (install, setup time,
   latency, cost, usage limits), with your recommendation for *this* machine:
   - **the agent's LLM:** Amazon Bedrock (default; the submission needs it), local Ollama
     (no cloud cost; model sizes 1.2 to 6.6 GB, filtered by their RAM), or the AWS User Group
     Madurai cloud (`qwen3.5-4b`, `gpt-oss-20b`; nothing to install, slower on CPU);
   - **Strands Decider 2B:** local (about 5 GB; fastest on Apple silicon or an NVIDIA GPU) or the
     hosted API (nothing to install). Ask whether it should read images (`--vision`).
   If they pick local Ollama and it is missing, give the install command for their OS
   (`brew install ollama`; `curl -fsSL https://ollama.com/install.sh | sh`; the Windows
   installer; or Docker) and wait until it is installed.
4. Run the real setup with their choices:
   `./kit setup --yes --llm <bedrock|local|ugmdu> [--llm-model <id>]
   --mode <local|ugmdu> [--key <key>] [--vision]`. Never echo the key back.
5. Report what it measured: the LLM's tool call and its time, the decider's answer and its time.
6. If the Bedrock check fails: they must enable model access for `BEDROCK_MODEL_ID` in the Amazon
   Bedrock console (Model access) in their region, or choose another model they have. They can
   still build with local or the user group's cloud, and fix Bedrock before deploying.
7. Finish with `./kit status`.
