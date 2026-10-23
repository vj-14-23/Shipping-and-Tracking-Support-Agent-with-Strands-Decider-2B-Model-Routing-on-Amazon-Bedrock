---
inclusion: auto
name: builder-center-article
description: How to write the hackathon article for AWS Builder Center (title, description, tags, cover, figures, structure and style). Use when writing, editing or reviewing the article, or running /write-article or ./kit article.
---

# The AWS Builder Center article

## Form fields (Builder Center's editor)

| Field | Rule |
|---|---|
| Title | at most 255 characters; specific; name the agent and the decision |
| Description | at most 512 characters; what the agent does, the decision, and one measured result |
| Tags | `strands-decider-2b`, the one pattern tag (`guardrails`, `tool-selection`, `policy`, `model-routing` or `context-memory`), and up to 3 more such as `amazon-bedrock`, `strands-agents`, `agentcore` |
| Cover | 1200 x 675 PNG or JPG, at most 2 MB, **no text on it**. `./kit article` generates one. |

Figures are uploaded into the editor. In `submission/article/body.md` each figure is a marker,
`< FIGURE n of N: upload <path> here >`, followed by an `Alt text:` line.

## Structure (use these sections, in this order)

Showcase the whole project first, with Strands Decider 2B as its key ingredient. Judges score
creativity (30%) and communication (25%) as well as the decider's use (30%), so roughly half
the article is about the project and half about the decision.

1. **Hook.** The problem, the project in one sentence, why it is cool, and the headline result.
2. **The project.** Who it is for, what it does, and its features (a short list). Include a real
   conversation or screenshot from the demo, and anything that makes it stand out: the domain,
   the data, the UI, the integrations.
3. **How I built it.** Architecture figure: Strands Agents, the tools, Amazon Bedrock for the
   generative part, AgentCore Runtime (plus Memory or Gateway if used: `agentcore_features` in
   facts.json), and where Strands Decider 2B sits. Mention Kiro and the spec-driven build
   briefly.
4. **The decision handed to Strands Decider 2B.** Why this decision needs a fast, calibrated
   decision model rather than another LLM call. Show the typed questions and options as code, and
   what the agent does with each answer, including when the decider is unsure.
5. **Measured.** The table from `submission/bench/results.md`:
   - accuracy, latency and cost against the Bedrock LLM asked the same questions;
   - what happens on low confidence.

   Say where the decider ran. Report weak numbers honestly.
6. **The reusable decision pattern.** Where it lives in the repo and how another builder drops it
   into their agent.
7. **What I learned / what's next** for the project.
8. **Footer.** Links to the repo, the video, Strands Decider and the tags, plus "Built with the
   AWS User Group Madurai Strands Decider hackathon kit".

## Style

- First person ("I built"), plain ASCII punctuation (no em dashes, no curly quotes, no unicode
  arrows), and one paragraph per line in Markdown.
- Concrete over abstract: real numbers from the run files.
- No marketing fluff, no rhetorical questions, no stakes inflation.
- Avoid these words: tapestry, landscape, paradigm, synergy, ecosystem, game-changer.
- Do not use the kit's example agent as the subject.
- 900 to 1,600 words is the right length.
