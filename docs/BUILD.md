# Without Kiro: the same flow with make

1. `./kit setup`: checks the machine and AWS, and chooses where the decider runs.
2. Write your agent in `agent/`. Copy the example's shape (see `.kiro/steering/kit.md` for the
   contract), and start from the closest pattern in `decider_kit/patterns/`.
   - `agent/AGENT.md`: your use case.
   - `agent/decision.py`: the `REUSABLE DECISION PATTERN` header, `PATTERN_TAG`, `QUESTIONS`
     and the wiring. Delete `IS_KIT_EXAMPLE`.
   - `agent/tools.py`, `agent/agent.py` (keep `HackathonAgent.chat`), `agent/eval_cases.jsonl`
     (20+ labelled cases with a tune/test split) and `agent/demo_script.yaml`.
   - One decision pattern only (the rules ask for exactly one): one `PATTERN_TAG`.
   - AgentCore Memory or Gateway: set `enabled: true` in `agent/features.yaml` (targets for the
     gateway), and use `decider_kit/agentcore.py` from the agent. `./kit deploy` creates them.
   - Models: set `BEDROCK_MODEL_ID` (and the `BEDROCK_SMALL/MEDIUM/LARGE_MODEL_ID` routing tiers,
     `BENCH_LLM_MODEL_ID`) in `.env`; Amazon Nova by default.
3. `./kit test` and `./kit run`.
4. `./kit bench --split tune`. Improve the questions, then `./kit bench --split test` for the numbers
   you report.
5. `./kit deploy`, then `./kit invoke "..."`.
6. `./kit video --target agentcore`.
7. `./kit article --draft`: drafts the article with Amazon Bedrock from your real numbers. Edit
   it into your own words, fill `submission/article/fields.md`, and run `./kit article` until it
   says ready.
8. `./kit readme`, `./kit check`, then `./kit publish <repo>`.
9. Upload the video (public), publish the article, fill `submission/SUBMISSION.md`, and submit.
