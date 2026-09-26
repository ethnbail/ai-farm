# Persisted AI budget enforcement

AI defaults off. Both dollar budgets, an API key, a model ID and verified positive input/output rates are required for a paid request. Blank/zero budgets permit no paid calls. `.env.example` suggests $1/day, $10/month, four calls per scan, 30/day and a 10% non-priority reserve; an existing blank monthly budget stays unconfigured. Limits apply across both agents and all model slots in this database. Separate databases/accounts outside this application are not covered.

Before HTTP, `AIBudgetManager` updates singleton `BudgetGuard` to acquire a transaction lock, reads persisted UTC day/month totals and scan/day call counts, checks the full conservative cost, inserts the usage reservation and commits. Concurrent workers cannot both spend the same remaining allowance. A denied attempt is persisted at zero charge with a reason and `ai_budget_warning` event. Both analysis and Shadow consume limits. Rank-one priority may use the protected reserve.

Estimated input allowance uses UTF-8 bytes of context, instructions and schema plus an envelope margin; output reserves the configured maximum. Cost is rounded up to eight decimals from configured USD-per-million ceilings. Actual reported input/output tokens are saved after a valid response, but the full reservation remains charged, including failures/timeouts/crashes. No refund can create a concurrency overspend. Consequently UI spend is a conservative ledger, **not a vendor invoice**. Provider billing outside supplied rates/token bounds cannot be guaranteed by an application; verify ceilings, use a dedicated provider project spending limit, and leave AI disabled until configuration is trusted. This implementation makes no tool calls with separate fees.

Example **shape**, not verified current pricing:

```dotenv
AI_ENABLED=false
AI_MONTHLY_BUDGET_USD=10
AI_DAILY_BUDGET_USD=1
AI_CHEAP_MODEL=your-supported-model-id
AI_MODEL_PRICES={"your-supported-model-id":{"input":"1","output":"2"}}
```

Do not enable with placeholder prices. Unknown/unpriced models are denied. More expensive preferred models downgrade to cheap when budget/call configuration permits; otherwise research stays deterministic. Failed reservations remain charged until normal UTC window rollover. Do not delete ledger rows or manually release uncertain reservations to gain more budget.

`GET /ai/usage` reports daily/monthly reserved spend, remaining caps, calls and denied attempts. `/ai/status` reports configured slots and mode without keys. Tests cover scan/day calls, daily/monthly ceilings separately, reserve access, malformed results and cheap fallback. Native PostgreSQL verification launches ten competing connections for one affordable call and asserts one approval/nine denials without HTTP.
