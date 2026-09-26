# Model routing

Tier 0 does all arithmetic, indicators, filters, ranking, contract choice and risk. Only top-K eligible candidates reach analysis. AI disabled returns deterministic analysis without a ledger reservation or HTTP call. Its neutral 0.5 placeholder is explicitly uncalibrated and is **not** saved as an AI confidence forecast.

`AI_CHEAP_MODEL`, `AI_REASONING_MODEL` and `AI_SHADOW_MODEL` are backend configuration slots, not hardcoded model IDs. Rank-one candidates scoring at least 90 may use the reasoning slot; other analysis uses cheap. Shadow uses its own slot. Denied preferred-model reservations fall back to cheap, then deterministic. Models and verified price ceilings are intentionally unconfigured by default: no assumptions about account access or changing provider prices.

Context is bounded structured JSON: normalized snapshot/features/contracts, regime, score, account equity/cash/exposure, event coverage and deterministic proposal. Descriptions are untrusted data. No tools, executable instructions, raw account secrets or order capability are given to a model. UTF-8 context size and output tokens are capped.

The OpenAI adapter uses fixed-host `POST /v1/responses`, `store:false` and `text.format` with a strict JSON Schema from Pydantic. `TradeAnalysis` and `ShadowReviewOutput` forbid extra fields. Incomplete/refused, malformed, oversized and unverified-usage responses degrade safely; no automatic network retry may duplicate a paid request. Valid AI cannot change a price, size or stop. A contradictory recommendation can only veto.

Implementation follows the official [Structured Outputs guide](https://developers.openai.com/api/docs/guides/structured-outputs). Real API compatibility/model availability remains unverified without credentials. Tests inject HTTP transports and test-only model names; **no paid calls were made**. Configure model IDs supported by the Responses structured-output contract, then verify current price ceilings before enabling. See [budget accounting](ai-budget.md).
