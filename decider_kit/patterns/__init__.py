"""Reusable Strands Decider 2B decision patterns, one per hackathon decision-pattern tag.

| Module            | Tag              | Seam in the agent                         |
|-------------------|------------------|-------------------------------------------|
| tool_selection    | #tool-selection  | before the agent: narrow its tools        |
| guardrails        | #guardrails      | InterventionHandler: inputs and tool calls |
| policy            | #policy          | before acting or before sending a reply   |
| model_routing     | #model-routing   | before the agent: pick the Bedrock model  |
| context_memory    | #context-memory  | around each turn: recall and store        |

One pattern per agent
    The hackathon asks for exactly one decision pattern: pick the decision that matters most
    and hand that one to Strands Decider 2B, at one clear seam.
"""


PATTERNS = {
    "tool_selection": "#tool-selection",
    "guardrails": "#guardrails",
    "policy": "#policy",
    "model_routing": "#model-routing",
    "context_memory": "#context-memory",
}
TAGS = set(PATTERNS.values())

