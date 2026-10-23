---
inclusion: auto
name: video-and-deploy
description: How the demo video is made (./kit video) and how the agent is deployed to AWS (./kit deploy, Amazon Bedrock AgentCore Runtime). Use when making or fixing the video, the demo script, or deploying the agent.
---

# Demo video (`./kit video`)

- **What it does:**
  1. Records the demo UI (`demo/`) while it plays the turns in `agent/demo_script.yaml` against
     the real agent.
  2. Writes narration from each turn's neutral `narrate` line, plus what the decider actually
     decided, taken from the run.
  3. Speaks the narration with Amazon Polly (macOS `say` as fallback).
  4. Adds title, benchmark and end-card slides.
  5. Writes `submission/video/demo.mp4`, under 2:55.
- **Showcase the project:** `pitch` and `features` in `demo_script.yaml` become a project slide
  right after the title. Choose turns that show what the project does for its users, not only
  the decision.
- **Writing `demo_script.yaml`:**
  - Use 3 or 4 turns.
  - At least one turn should make the decision change the outcome (a blocked guess, a narrowed
    tool, a cheaper model), and one should show the normal path.
  - `narrate` describes the situation only, never the result.
  - `intro`, `outro` and `pitch` contain no numbers (no speeds, counts or percentages): the video
    adds the measured figures itself, and `./kit video` stops if a figure is written by hand.
  - `eager: true` makes the agent act without asking, for demos where the decision has to catch
    something. The intro must say the agent was made eager for the demo.
- **Recording the deployed agent:** `./kit video --target agentcore`. This records the agent
  running on AWS, the strongest proof of "an agent on AWS".
- **The participant uploads it** to YouTube or Vimeo as public, and pastes the link into
  `submission/SUBMISSION.md`. There's no music; nothing to license.

# Deploying to AWS (`./kit deploy`)

- **What it does:**
  1. Packages `agent/` and `decider_kit/` into `deploy/app/agent/`.
  2. Sets the runtime's environment from `.env`, temporarily: `DECIDER_URL`, `DECIDER_API_KEY`,
     and the Bedrock model ids (`BEDROCK_MODEL_ID`, `BEDROCK_SMALL/MEDIUM/LARGE_MODEL_ID`).
  3. Adds the AgentCore features enabled in `agent/features.yaml` to the project, once:
     `agentcore add memory`, `agentcore add gateway`, `agentcore add gateway-target` per target.
     The CDK constructs give the runtime `MEMORY_<NAME>_ID` and `AGENTCORE_GATEWAY_<NAME>_URL`
     plus the IAM permissions to use them.
  4. Runs `agentcore deploy -y` (AgentCore CLI, `./kit agentcore-cli`, Node 20+).
  5. Writes the runtime ARN, memory ids and gateway URLs to `submission/deployment.json`; local
     runs (`./kit demo`, `./kit run`) read them from there.
- **Turning a feature off:** set `enabled: false`, then remove it from the project with
  `cd deploy && agentcore remove memory --name <name>` (or `remove gateway`) and `./kit deploy`.
- **The decider must be reachable from AWS.** Use the AWS User Group Madurai hosted API or your
  own deployed decider. A decider on your laptop (`DECIDER_MODE=local`) is not reachable, and
  the script stops with that message.
- **Invoking it:**
  - `./kit invoke "..."`;
  - `./kit demo --target agentcore`, which sets `AGENTCORE_ARN` from `submission/deployment.json`.
- **Removing it:** `./kit destroy`.
