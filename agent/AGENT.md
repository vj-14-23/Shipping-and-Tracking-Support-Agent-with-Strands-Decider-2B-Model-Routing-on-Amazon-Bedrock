# Use case

KIT EXAMPLE. Describe your own project here (/new-agent in Kiro interviews you and fills it in).
These answers drive the code, benchmark, README, article and video, and the project leads all three.

- **Pitch:** a store support agent that can refund and cancel orders, and cannot do it to the wrong order.
- **Who it is for:** customers of an online store, and the store that wants them served without a human queue.
- **Features:**
  - order lookup, refunds and cancellations through chat;
  - every irreversible action is checked before it runs, and unsure cases go to a human;
  - a live decision panel in the demo UI that shows why each action was allowed;
  - deployed on Amazon Bedrock AgentCore Runtime.
- **The decision handed to Strands Decider 2B:** before an irreversible order action, is it
  grounded and explicitly requested? (`#guardrails`)
- **Why a decision model:** the check runs on every action, so it must be fast, cheap and private,
  and it must return a number the code can branch on.
- **Amazon Bedrock:** the conversation and tool use (Amazon Nova Pro by default).
