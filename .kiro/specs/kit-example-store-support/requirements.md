# Requirements: kit example (store support agent)

KIT EXAMPLE: it shows the spec format /new-agent writes. It is not a submission.

## User stories

1. As a customer, I want to get a refund or a cancellation by chatting, so I do not wait for a
   human.
2. As the store, I want no refund or cancellation that the customer did not clearly ask for, or
   whose order id or amount was guessed.

## Acceptance criteria (EARS)

- WHEN the agent proposes `refund_order` or `cancel_order`, THE agent SHALL ask Strands Decider
  2B whether the arguments are grounded, whether the customer explicitly asked, and whether it
  is premature, BEFORE the tool runs.
- IF the arguments are not grounded (P < 0.5), THEN the agent SHALL be guided to ask the
  customer instead of acting.
- IF the agent retries the same guided call unchanged, THEN the call SHALL be denied.
- WHILE the decider is unsure about prematurity (0.4 <= P <= 0.6), THE agent SHALL request
  confirmation.
- THE agent SHALL use Amazon Bedrock (Amazon Nova Pro) for the conversation.
