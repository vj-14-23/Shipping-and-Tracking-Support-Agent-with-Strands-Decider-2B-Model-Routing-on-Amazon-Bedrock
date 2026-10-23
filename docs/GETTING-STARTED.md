# Getting started: your hackathon submission, step by step

AWS User Group Madurai kit for the **Agent Experience Hackathon: Strands Decider**
(submissions 16 to 23 October 2026, 11:59 p.m. PT). Works on **macOS, Windows and Linux**. You
install one app; everything else is installed for you, after asking.

---

## Step 1. Install Kiro (5 min)

Download and install Kiro from **https://kiro.dev** and sign in. That is the only thing you
install yourself.

---

## Step 2. Get the kit, in Kiro (3 to 5 min)

1. In Kiro: **File → Open Folder**, create a **new empty folder** (for example `my-agent`) and open it.
2. Open the terminal: **View → Terminal** (or <kbd>Ctrl</kbd>+<kbd>`</kbd>).
3. Paste the line for your computer and press Enter:

**macOS or Linux**
```bash
curl -fsSL https://raw.githubusercontent.com/Vivek0712/decider-hackathon-kit/main/install/install.sh | sh
```

**Windows** (PowerShell, the default Kiro terminal)
```powershell
irm https://raw.githubusercontent.com/Vivek0712/decider-hackathon-kit/main/install/install.ps1 | iex
```

It shows what it will install and asks first. Everything goes into your user folder, with no
admin rights: Python 3.12 (through uv), the kit, its packages, and git, the GitHub CLI and Node if
you do not have them. It ends with:

```
Done. Now, in the Kiro chat, type:   /hackathon
```

---

## Step 3. Type `/hackathon` in the Kiro chat (25 to 35 min)

Kiro does the rest with you, one step at a time:

| Kiro asks or does | What you do |
|---|---|
| Checks your computer, then shows three paths with their time, cost and speed, and recommends one | pick one (below) |
| Asks for what your path needs (a user group key, AWS keys, a model download) | answer; AWS keys are typed in the terminal, never in the chat |
| Sets your path up and proves it works with a real tool call and decision | wait; it tells you the measured speeds |
| "Describe your use case" | who uses it and what they ask, in plain words |
| Follow-up questions with options | answer; "go with your recommendation" is fine |
| The **one decision** for Strands Decider 2B | tool selection, guardrails, policy, model routing, or context and memory |
| Where the data comes from | synthetic (generated for you), an API, or your own file |
| A one-paragraph summary | say **yes** to start building |
| Builds, tests, benchmarks, then **shows you the app** at http://localhost:8501 | try it; ask for changes |
| Deploys to AWS | it installs what is missing and helps you log in to AWS |
| Drafts the article, then records the video | read both; make the article your own words |
| Publishes your project to **your GitHub** | log in to GitHub when asked; confirm the repo name |

**The three paths** (you choose in Kiro):

| Path | Good for | You need | Cost while building |
|---|---|---|---|
| **A. AWS** (fastest) | you have an AWS account | AWS account with Amazon Bedrock, a user group key | a few cents |
| **B. Fully local** | no cloud cost while building | 16 GB+ RAM (Apple silicon or NVIDIA is best), about 10 GB free disk | free |
| **C. User group cloud** | a small or older laptop, no AWS yet | a user group key | free |

Get a **user group key** on https://www.awsugmdu.in. The **submission needs AWS** (an agent on
AWS with Amazon Bedrock): paths B and C build first and add AWS before deploying, and Kiro walks
you through it.

---

## Step 4. Submit (10 min, by hand)

1. **Video:** upload `submission/video/demo.mp4` to YouTube or Vimeo as **Public**; paste the
   link into `submission/SUBMISSION.md`.
2. **Article:** on AWS Builder Center, create an article from `submission/article/`: `fields.md`
   (title, description, tags), `body.md` (upload each image at its `< FIGURE n >` marker),
   `cover.png`. Tags: `strands-decider-2b` and your pattern tag.
3. **Submit** the three links (your GitHub repo, the article, the video) on the hackathon page
   before **23 October 2026, 11:59 p.m. PT**.

---

## Step 5. Clean up (after judging)

In the Kiro terminal (Windows: `.\kit.cmd` instead of `./kit`):
```bash
./kit destroy      # removes your agent from AWS (stops charges)
./kit demo-stop    # stops the local web app
./kit stop         # stops a local decider
```

---

## Without Kiro

Every step is a `./kit` command (Windows: `.\kit.cmd`; `./kit help` lists them):

| Step | Command |
|---|---|
| Check and install tools | `./kit tools`, `./kit tools install base` |
| Set up a path | A: `./kit setup --yes --llm bedrock --mode ugmdu --key YOUR_KEY` · B: `./kit setup --yes --llm local --llm-model qwen3.5:4b --mode local` · C: `./kit setup --yes --llm ugmdu --mode ugmdu --key YOUR_KEY` |
| AWS and GitHub logins | `./kit aws-login`, `./kit gh-login` |
| Try the kit example | `./kit run`, then `./kit demo` |
| Your agent | edit `agent/` (see [BUILD.md](BUILD.md)) |
| Data | `./kit data orders --describe "..." --fields "id:str,amount:float"`, `./kit data images bananas --query "banana bunch"` |
| Test and benchmark | `./kit test`, `./kit bench --split test` |
| Deploy | `./kit tools install deploy`, `./kit deploy`, `./kit invoke "hello"` |
| Article and video | `./kit article --draft`, `./kit video --target agentcore` |
| Check and publish | `./kit readme`, `./kit check`, `./kit publish my-agent` |

---

## If something goes wrong

| You see | Do this |
|---|---|
| `This folder is not empty` | open a new empty folder in Kiro and run the install line again |
| `curl is needed` (Linux) | `sudo apt install curl`, then run the install line again |
| `the browser needs a few system libraries` (Linux) | answer **y** (one sudo command), or run the printed command later |
| `Ollama is not running` | start the Ollama app, or `ollama serve` |
| `requires a newer version of Ollama` | `./kit tools install ollama` again, or https://ollama.com/download |
| Bedrock `AccessDeniedException` | enable Amazon Nova Pro in Bedrock → Model access (us-east-1) |
| `decider returned 401` | check the key in `.env` (`DECIDER_API_KEY`) |
| `decider returned 429` | free-tier limit (10 requests a minute): wait a minute |
| `AgentCore CLI not found` | `./kit tools install deploy` |
| `Your decider runs on this laptop, which AWS cannot reach` | add `DEPLOY_DECIDER_URL=https://da25tnxy06gjk.cloudfront.net` and `DEPLOY_DECIDER_API_KEY=YOUR_KEY` to `.env` |
| `port 8501 is already in use` | `./kit demo-stop`, or close the other demo |
| `log in to GitHub first` | `./kit gh-login` |
| Kiro says it is throttled or out of usage | wait a few minutes; check your Kiro plan |

More: [OPTIONS.md](OPTIONS.md) (speeds, costs and limits of every option) · [KIT.md](KIT.md)
(what is in the kit) · [BUILD.md](BUILD.md) (building without Kiro).

---

Built by the AWS User Group Madurai. Strands Decider and Strands Agents are open source
(Apache-2.0). This kit is not an official AWS project.
