# Design: kit example

- **Seam:** `InterventionHandler.before_tool_call` (`agent/decision.py: OrderActionGuard`), only
  for `GUARDED_TOOLS`.
- **State:** the conversation followed by the proposed action:
  `--- CONVERSATION --- ... --- PROPOSED ACTION --- tool / arguments`.
- **Questions:** `args_grounded`, `explicit_request`, `premature` (all noul with described
  options).
- **Policy:**
  - grounded < 0.5: Guide (ask);
  - explicit < 0.5: Guide (answer instead);
  - premature in [0.4, 0.6]: Confirm;
  - premature > 0.6: Guide;
  - otherwise: Proceed;
  - a retried guided call: Deny.
- **Eval:** `agent/eval_cases.jsonl`, 12 cases with tune/test splits.
