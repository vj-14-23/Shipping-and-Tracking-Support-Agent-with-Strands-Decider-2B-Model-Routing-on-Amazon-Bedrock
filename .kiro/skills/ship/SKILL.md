---
name: ship
description: Deploy the agent to AWS (Amazon Bedrock AgentCore Runtime), draft the article, make the demo video, regenerate the README, run every submission check and publish the public GitHub repo. Use when the participant says /ship, "deploy", "make the video", "publish", "push to GitHub", or "am I ready to submit".
license: Apache-2.0
metadata:
  author: AWS User Group Madurai
  version: "1.0"
---

# /ship: deploy, article, video, README, check, publish

Do the steps in order. Each step is a single command; explain what it did in one line.

1. **Deploy** (`.kiro/steering/video-and-deploy.md`)
   1. Run `./kit deploy`.
      - On failure, read the output. The usual causes: the AgentCore CLI is missing
        (`./kit agentcore-cli`); the decider is not reachable from AWS (set
        `DEPLOY_DECIDER_URL` / `DEPLOY_DECIDER_API_KEY`); Bedrock model access is not enabled.
   2. Run `./kit invoke "..."` and show the reply plus its decision records.
2. **Article:** run the /write-article skill; the participant edits it into their own words.
3. **Video**
   1. Run `./kit video --target agentcore` (or `./kit video` if not deployed).
   2. Read `submission/video/narration.md`, and confirm with the participant it matches what
      they saw.
   3. If not, adjust `agent/demo_script.yaml` and re-run.
4. **README:** run `./kit readme`. It is generated from AGENT.md, decision.py, the benchmark and
   the deployment, and keeps the kit credit.
5. **Check:** run `./kit check` and fix every FAIL. WARN items are judgement calls; tell the
   participant.
6. **Publish:** public and outward-facing, so ask before running it.
   1. Ask for the repository name.
   2. Run `./kit publish <name>`. It needs `gh auth login`; it creates a **public** repo
      under their account, pushes, and checks LICENSE and README.
   3. Give the participant `submission/SUBMISSION.md`: three links to fill and the remaining
      manual steps (upload the video, publish the article, submit before 23 October 2026,
      11:59 p.m. PT).
