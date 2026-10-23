---
name: write-article
description: Write the AWS Builder Center hackathon article from the participant's real agent, benchmark and video run, and build the paste-ready bundle (fields, cover, figures, body with figure markers). Use when the participant says /write-article, "write the blog", or asks for the Builder Center post.
license: Apache-2.0
metadata:
  author: AWS User Group Madurai
  version: "1.0"
---

# /write-article: the Builder Center article

Follow `.kiro/steering/builder-center-article.md` for structure and style.

## Inputs (read them all first; every number must come from these)

- `agent/AGENT.md`, `agent/decision.py` (questions, thresholds, docstring) and `agent/tools.py`.
- `submission/bench/results.json` and `results.md`: accuracy, latency, cost, confident share,
  decider model and mode.
- `submission/video/run.json`: the real demo turns and their decision records.
- `submission/deployment.json`: the AgentCore runtime ARN and region, if deployed.
- `README.md` and the repo URL (from `git remote -v`, if published).

## Steps

1. Run `./kit article`. It builds `submission/article/`:
   - `fields.md`: title and description placeholders, tags;
   - `cover.png`: no text;
   - `img/`: architecture, benchmark charts, a demo screenshot;
   - `facts.json`: every number you may use;
   - `body.md`: section headings with TODO markers and the figure markers already placed.
2. Write the article into `submission/article/body.md`, replacing every TODO and keeping the
   figure markers and alt text.
   - **Structure:** hook and headline result; what the agent does (a short real conversation from
     `run.json`); the decision (show `QUESTIONS` as code); wiring; measured (paste the table,
     state the decider mode, model and hardware, and be honest about weak spots); the reusable
     pattern and how to reuse it; what I learned; footer.
   - **Style:** first person, ASCII only, one paragraph per line, 900 to 1,600 words.
3. Fill the title (at most 255 characters) and description (at most 512) in `fields.md`.
   Name the agent, the decision and one measured number.
4. Run `./kit article` again. It validates lengths, tags, ASCII, the figure markers, that numbers
   appear in `facts.json`, and the credit line, and rebuilds the paste bundle.
5. Tell the participant how to publish:
   1. Open Builder Center and choose Create, then Article.
   2. Paste the title and description, and add the tags `strands-decider-2b` and the pattern tag.
   3. Upload `cover.png`.
   4. Paste `body.md` section by section.
   5. Replace each figure marker with an upload of that image, and put the Alt text line in the
      image's alt field.
