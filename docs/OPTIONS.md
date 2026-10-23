# Your options: what to install, how long it takes, what it costs

Kiro shows you this before building (`/hackathon`, step 1). Every number below was measured with
this kit in October 2026 (Apple silicon laptop with 24 GB of RAM, and the AWS User Group Madurai
cloud on CPU instances). Your machine and network will differ; `./kit setup` measures yours.

You choose two things, then whether to add AgentCore features. You can change any of them later
in `.env` and run `./kit setup` again.

## 1. Where the agent's LLM runs (the conversation)

Always called through the Strands Agents SDK.

| | Amazon Bedrock (default) | Local (Ollama) | AWS User Group Madurai cloud |
|---|---|---|---|
| Install | nothing; an AWS account with Bedrock model access (console, about 2 min) | Ollama (about 2 min) plus one model, 1.2 to 6.6 GB | nothing; a key from the user group's platform |
| Models | Amazon Nova (default Nova Pro), any Bedrock model | `qwen3.5:0.8b` 1.2 GB, `granite4:3b-h` 1.9 GB, `qwen3.5:2b-q4_K_M` 1.9 GB, `qwen3.5:4b` 4.0 GB (recommended), `qwen3.5:9b` 6.6 GB | `qwen3.5-4b`, `gpt-oss-20b` |
| One agent turn with a tool call | about 3 to 5 s (estimated: 2 to 3 model calls; one Nova Pro call measured about 1.3 s) | 1.4 to 4.6 s median, model size dependent; slower without Apple silicon or a GPU | about 10 to 12 s (CPU for now) |
| Cost | pay per token: about 0.2 to 0.5 US cents a turn on Nova Pro; the whole hackathon is usually under 1 USD | free | free during the hackathon |
| Usage limits | your account's Bedrock quotas | your RAM: 4 GB (0.8b) to 16 GB (9b) | free tier: 300,000 tokens a month, 1,024 output tokens a request, 10 requests a minute |
| Counts for the submission | yes (required) | build only | build only |

## 2. Where Strands Decider 2B runs (the decision)

| | Local | AWS User Group Madurai hosted API |
|---|---|---|
| Install | about 5 GB from Hugging Face; 5 to 10 min the first time; needs 8 GB RAM and 12 GB free disk | nothing; the same key |
| Model | `strands-decider-2B-qwen3.5-v1-2610` or `hobson-v19` | `hobson-v19` |
| Latency per call | 0.2 to 0.3 s (MLX on Apple silicon, text); with images 0.3 to 1.7 s (Metal) | about 1.2 s text, 2.2 to 2.8 s with an image (CPU) |
| Images | yes, with `--vision` (+0.7 GB) | yes |
| Cost | free | free tier: 2,000 decisions a month, 10 requests a minute, 4 questions and 1 image per request |
| Reachable by the deployed agent on AWS | no (use the hosted API for the deployed agent) | yes |

## 3. Deployment to AWS (required for the submission)

| | |
|---|---|
| What | Amazon Bedrock AgentCore Runtime, with Amazon Bedrock for the LLM and the hosted decider |
| Install | Node 20+ and the AgentCore CLI (`./kit agentcore-cli`, about 1 min); AWS credentials |
| Time | first deploy 2 to 5 min (measured 84 to 289 s); updates about 2 min |
| Cost | pay per use: Runtime bills only while a request runs, plus Bedrock tokens; a hackathon's demo traffic costs cents. `./kit destroy` removes everything |
| Optional: AgentCore Memory | long-term memory across sessions (pairs with `#context-memory`); a recalled fact was available in a new session about a minute after it was stored; pay per use |
| Optional: AgentCore Gateway | many tools behind one MCP endpoint: web search, a knowledge base, Lambda functions, REST APIs, MCP servers (pairs with `#tool-selection`); pay per use |

## Recommended combinations

| You want | LLM | Decider | Setup command |
|---|---|---|---|
| The fastest path (has AWS) | Bedrock | hosted | `python scripts/setup.py --llm bedrock --mode ugmdu --key ...` |
| No cloud cost while building | local `qwen3.5:4b` | local | `python scripts/setup.py --llm local --mode local` |
| A small laptop, no AWS yet | user group cloud | hosted | `python scripts/setup.py --llm ugmdu --mode ugmdu --key ...` |

Whatever you build with, `./kit deploy` runs the submitted agent on Amazon Bedrock.

## How long the whole thing takes

| Step | Time |
|---|---|
| Setup (with downloads) | 5 to 15 min |
| Interview and data | 5 min |
| Build, test, benchmark | 10 min |
| Deploy | 5 min |
| Article and video | 7 min |
| Publish | 2 min |
