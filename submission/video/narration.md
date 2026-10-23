0. This shipping support agent runs on Amazon Bedrock. Strands Decider decides which model tier handles each question and guards every irreversible action before it runs.

1. A shipping support agent that routes easy questions to a fast model and complex issues to a smarter one using Strands Decider. What it does: Track shipments by tracking number or order ID in natural language. Route simple lookups to a fast model and complex issues to a capable model. Guard every irreversible action (investigation, refund, replacement, address change) with Decider 2B. Handle delivery exceptions and lost package claims.

2. The agent you are about to see is running on Amazon Bedrock AgentCore Runtime.

3. A simple status lookup — the Decider should route this to the fast model. The decider scored confidence 0.66, so the verdict was small. The decider scored confidence 0.90, so the verdict was proceed.

4. A delivery exception — the Decider routes this to the capable model. The decider scored confidence 0.60, so the verdict was large. The decider scored confidence 0.83, so the verdict was proceed.

5. The customer asks about an investigation — Decider checks if the request is explicit enough before allowing the irreversible tool. The decider scored confidence 0.62, so the verdict was large. The decider scored confidence 0.84, so the verdict was proceed.

6. Explicit confirmation — Decider should now allow the tool call to proceed. The decider scored confidence 0.66, so the verdict was small. The decider scored confidence 0.62, so the verdict was proceed.

7. An address change request — routed to the capable model and guarded before submission. The decider scored confidence 0.57, so the verdict was large. The decider scored confidence 0.74, so the verdict was proceed.

8. On 12 labelled decisions, with the decider on the AWS User Group Madurai hosted API, Strands Decider was 100% accurate at a median of 2699 milliseconds, against 92% and 2270 milliseconds for the Bedrock LLM asked the same questions.

9. One Decider call per routing decision, another per irreversible action, and Amazon Bedrock for the conversation — cost-efficient and safe by design.