# Shadow critique

`ShadowAgent` has no broker, money or execution dependency. It critiques deterministic candidate eligibility, fresh source mode, regime, entry/stop/target ordering, reward versus planned risk, analysis direction and overconfidence. Unknown live event coverage is an explicit objection; the final event-risk rule controls whether missing coverage itself blocks. Liquidity/filter rejections and normalized contracts accompany optional AI critique.

Output: `approve_for_risk_review`, objections, severity, confidence, missing information and `PROCEED|REDUCE_SIZE|WAIT|NO_TRADE`. Deterministic rejection always wins. AI may add a veto, not erase deterministic objections. AI `REDUCE_SIZE` conservatively becomes WAIT; Phase 3 does not parse a new quantity from model prose. BUY/CALL/PUT must match the deterministic instrument direction.

The orchestrator persists the review and emits `shadow_review_completed`. Only a permitted review may reach the existing RiskEngine, which independently checks portfolio, paper mode, market hours, data, full option premium and event proximity. Shadow approval is not a fill or profitability prediction. Closed linked trades support outcome counts; vetoed trades have no invented counterfactual return.
