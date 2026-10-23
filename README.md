# Strands Decider Hackathon Kit

**From an idea to a complete Agent Experience Hackathon submission in about 30 minutes.**

**New here? Follow [the step-by-step guide](docs/GETTING-STARTED.md).**

You describe your agent. Kiro builds it on top of this kit, then:
- benchmarks its decision against an Amazon Bedrock LLM;
- deploys it to AWS;
- records the demo video;
- drafts the AWS Builder Center article;
- writes the README;
- publishes the public repo.

You review, upload the video, publish the article and submit.

Made by **AWS User Group Madurai** for the
[Agent Experience Hackathon: Strands Decider](https://builder.aws.com/build/hackathons/4f50957c-1d08-37ab-b11c-97516b9adeb4/agent-experience-hackathon-strands-decider)
(16 to 23 October 2026). If you use it, keep the line *"Built with the AWS User Group Madurai
Strands Decider hackathon kit"* in your README, article and video. It is already there.

```
 describe your idea ──> /hackathon in Kiro ──> your agent + decision pattern
                                         ├─> ./kit bench    accuracy, latency, cost vs a Bedrock LLM
                                         ├─> ./kit deploy   Amazon Bedrock AgentCore Runtime
                                         ├─> ./kit video    a real recorded run, narrated, under 3 minutes
                                         ├─> ./kit article  Builder Center bundle: fields, cover, figures, body
                                         ├─> ./kit readme   README with your real numbers
                                         └─> ./kit publish  public GitHub repo, Apache-2.0
```

## What the hackathon asks for, and where the kit covers it

| Requirement (official rules) | How the kit does it |
|---|---|
| An agent on AWS using Strands Decider 2B for a meaningful decision, paired with Amazon Bedrock | `agent/` (Strands Agents + Amazon Bedrock), deployed to AgentCore Runtime by `./kit deploy` |
| A public repo with the agent and at least one labelled **reusable decision pattern** | `agent/decision.py` (labelled `REUSABLE DECISION PATTERN`), plus five ready patterns in `decider_kit/patterns/`; Apache-2.0; `./kit publish` |
| An article on AWS Builder Center | `/write-article` + `./kit article` (fields, a text-free cover, figures, body with figure markers, validated) |
| A video under 3 minutes | `./kit video`: records your real agent, narrates with Amazon Polly, no music, checks it is under 2:55 |
| Tags: `#strands-decider-2b` plus one pattern tag | set from `PATTERN_TAG` in the article fields, video and README |
| Original agent | the interview builds *your* idea; `./kit check` fails while the kit example is still in `agent/` |
| Bonus: measured latency or cost vs an LLM | `./kit bench`: the same questions answered by the decider and a Bedrock LLM, with accuracy, p50/p95, cost per 1,000 and low-confidence handling |

## 30 minutes, step by step

Works on macOS, Windows and Linux. Full guide: [docs/GETTING-STARTED.md](docs/GETTING-STARTED.md).

1. **Install Kiro** from https://kiro.dev. That is the only thing you install yourself.
2. **In Kiro, open a new empty folder**, open the terminal, and run the install line:
   `curl -fsSL https://raw.githubusercontent.com/Vivek0712/decider-hackathon-kit/main/install/install.sh | sh` (macOS, Linux) or `irm https://raw.githubusercontent.com/Vivek0712/decider-hackathon-kit/main/install/install.ps1 | iex`
   (Windows). It asks first, then installs Python, the kit and the tools into your user folder.
3. **In the Kiro chat, type `/hackathon`.** Kiro shows the three paths (AWS, fully local, the user
   group cloud) with their time, cost and speed, sets up the one you pick, interviews you about
   your use case and data, builds and tests your agent, shows you the app and the benchmark,
   deploys it to AWS, drafts the article, records the video, and publishes your project to your
   GitHub after asking.
4. **Submit by hand:** upload the video (public), publish the article on Builder Center, and
   submit the three links before 23 October 2026, 11:59 p.m. PT.

Every step is also a command (`./kit help`; Windows `.\kit.cmd help`).

## Three places to run the LLM

The agent's generative part always goes through the **Strands Agents SDK** (`decider_kit/llm.py`
gives every option as a Strands model). Pick one with `LLM_PROVIDER` in `.env`; `./kit setup` asks.

| Option | What you need | Cost | Models |
|---|---|---|---|
| `bedrock` (default) | AWS account, Bedrock model access | a few cents | Amazon Nova (any Bedrock model via `BEDROCK_MODEL_ID`) |
| `local` | [Ollama](https://ollama.com/download) on your machine | none | see below |
| `ugmdu` | an AWS User Group Madurai key (the same one as the decider) | free during the hackathon | `qwen3.5-4b`, `gpt-oss-20b` (on CPU for now: about 10 to 12 s a tool-calling turn) |

**Completely local, no cloud cost:** `python scripts/setup.py --llm local --mode local` runs both
the agent's LLM (Ollama) and Strands Decider 2B on your machine. Install Ollama any one way:
`brew install ollama` (macOS), `curl -fsSL https://ollama.com/install.sh | sh` (Linux), the
installer from https://ollama.com/download (Windows), or
`docker run -d -p 11434:11434 -v ollama:/root/.ollama ollama/ollama`. Then choose a model by
size (`./kit setup` shows which fit your RAM):

| Model | Download | Notes |
|---|---|---|
| `qwen3.5:0.8b` | 1.2 GB | tiny; simple tool calls only |
| `granite4:3b-h` | 1.9 GB | IBM Granite 4 Micro; fast, built for tool calling |
| `qwen3.5:2b-q4_K_M` | 1.9 GB | small Qwen3.5; reads images |
| `qwen3.5:4b` | 4.0 GB | **recommended**: good tool use, reads images |
| `qwen3.5:9b` | 6.6 GB | best local quality; 16 GB+ RAM |

The four smaller ones each made the right tool call on all 5 prompts of a quick check through a
Strands Agent on an Apple silicon laptop (median 1.4 to 4.6 s a turn; `qwen3.5:9b` was not
measured). Five prompts is a smoke test, not a benchmark: bigger models handle harder agent
tasks better.
Qwen3.5's thinking is off by default for speed (`LLM_THINK=1` turns it on).

**The submission still needs AWS and Amazon Bedrock** (the rules ask for an agent on AWS with
Amazon Bedrock for the generative part). Build with any option; `./kit deploy` always runs the
deployed agent on Bedrock, and `./kit check` warns if your video was recorded with another LLM.

## What is prebuilt

| Piece | Where |
|---|---|
| One client for local / hosted / custom deciders (stdlib only, typed answers with confidence) | `decider_kit/client.py` |
| Five labelled reusable patterns: tool selection, guardrails, policy, model routing, context and memory | `decider_kit/patterns/` |
| Amazon Bedrock model factory and an LLM baseline for the same typed questions | `decider_kit/bedrock.py` |
| Amazon Bedrock AgentCore Memory and Gateway, created by `./kit deploy` from `agent/features.yaml` | `decider_kit/agentcore.py` |
| Benchmark: decider vs LLM (accuracy, latency, cost, low-confidence handling) with charts | `decider_kit/bench.py` |
| A working example agent (reference only; `/new-agent` replaces it) | `agent/` |
| Demo web UI: chat plus live decision panel | `demo/` |
| AgentCore Runtime project and a deploy / invoke / destroy script | `deploy/`, `scripts/deploy.py` |
| Video maker: Playwright recording + Polly narration + slides + ffmpeg | `scripts/make_video.py` |
| Builder Center article builder and validator | `scripts/article.py` |
| Machine and AWS checker, decider installer | `scripts/setup.py` |
| Submission checker, secret scanner, progress tracker, publisher | `scripts/` |
| Kiro steering, skills (`/hackathon`, `/new-agent`, `/decision-pattern`, `/write-article`, `/ship`, `/setup`), hooks, a spec template | `.kiro/` |

**Kiro hooks included:**
- **Session start:** shows your progress.
- **On save:** runs the tests, scans for secrets, and checks the decision pattern is still
  labelled.
- **After each turn:** prints the next step.

## Strands Decider 2B in one paragraph

An open 2-billion-parameter decision model from the Strands team. It does not write text. You
give it a state (any text) and typed questions (yes/no, choice, score), and it returns
calibrated probabilities in one forward pass. Your code turns those probabilities into actions.
- Model: `StrandsAgents/strands-decider-2B-qwen3.5-v1-2610` (Apache-2.0).
- Code: [strands-labs/strands-decider](https://github.com/strands-labs/strands-decider).
- Background: [Introducing Strands Decider](https://strandsagents.com/blog/introducing-strands-decider/).

## Honest by default

The kit writes numbers only from real runs:
- **Narration:** the video's narration states what the decider actually decided.
- **Benchmark:** reports where the decider ran and which model it was.
- **Tuning:** the article builder asks you to tune on one split and report on the other.

If your decider is slower than the LLM on your setup (a hosted or CPU decider can be), the kit
says so. Cost, privacy and calibrated confidence are still yours to show.

## FAQ

- **Can I submit the example agent?** No. The rules require an original agent; `./kit check` and
  `./kit publish` refuse while it is still there.
- **Do I need a GPU?** No. Use the hosted API, or a local model on Apple silicon.
- **Where do keys go?** In `.env`, which git ignores. A hook blocks keys in any other file.
- **How do I get an AWS User Group Madurai API key?** Through the user group's platform
  (https://www.awsugmdu.in). Keys have per-minute and monthly limits; ask there for more.
- **Can I build without any cloud cost?** Yes: `LLM_PROVIDER=local` and `DECIDER_MODE=local`
  (see [Three places to run the LLM](#three-places-to-run-the-llm)). Deploying and submitting
  need AWS.
- **Can the decider read images?** Yes: a local decider with `DECIDER_VISION=1`, or the hosted
  API (always on; no setting needed). Sample photos: your own, or openly licensed ones with
  `./kit data images <name> --query "..."` (Wikimedia Commons, credits recorded;
  check each one). Pass `images=[...]` (paths, bytes or base64) to `Decider.ask`, and add `"images"` to eval
  cases for `./kit bench`.
- **Can I change the Bedrock model?** Yes. Every model id is an environment variable in `.env`,
  Amazon Nova by default: `BEDROCK_MODEL_ID` (the agent), `BEDROCK_SMALL_MODEL_ID`,
  `BEDROCK_MEDIUM_MODEL_ID`, `BEDROCK_LARGE_MODEL_ID` (model routing tiers) and
  `BENCH_LLM_MODEL_ID` (the benchmark's LLM). `./kit setup` asks; `./kit deploy` passes them to
  the runtime.
- **Can my agent use more than one pattern?** No: the rules ask for exactly one decision pattern
  and one pattern tag. Pick the decision that matters most for your demo.
- **Can it use AgentCore Memory or Gateway?** Yes. `/new-agent` asks; turn them on in
  `agent/features.yaml` and `./kit deploy` creates them with the AgentCore CLI. With Memory the
  decider picks which memories go in the prompt and what is stored (`#context-memory`,
  `examples/memory_agent.py`); with Gateway it picks which tool handles a request
  (`#tool-selection`, `examples/gateway_agent.py`). See `decider_kit/agentcore.py`.

Licence: Apache-2.0. Credits: AWS User Group Madurai. It uses Strands Agents and Strands Decider
(Apache-2.0). It is not an official AWS project.
