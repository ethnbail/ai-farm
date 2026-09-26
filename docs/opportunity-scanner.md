# Research and opportunity queue

Each agent has a configured universe merged with persistent watchlists, deduplicated and capped at 30 symbols. Defaults: A SPY/QQQ/NVDA, B SPY/FARM (FARM is synthetic). A strategy/feature scan produces candidates even for rejected symbols, so failure and NO_TRADE are inspectable. Only eligible top-K rows enter deeper analysis; others are dismissed audit records.

Scoring v1 weights trend 35, momentum 15, volume 15 (5 when below average), liquidity 15 and known-regime fit 10. RSI, ATR, breakout and volatility remain explanatory features, not secretly AI-computed scores. Ties use symbol order. A minimum score and expiry are configurable. A new scan expires or supersedes earlier nonterminal rows; terminal trade/risk history remains. This bounds active queue size, not audit history. Repeated scheduled scans may analyze a still-valid setup again, subject to persisted scan/day/budget limits; there is no cross-scan semantic AI cache.

Agent B first derives direction from the underlying, then filters normalized contracts for matching call/put, quote age, DTE, spread, volume/OI, IV, delta, gamma/theta and full-premium affordability. Live Greeks must have verified recent timestamps. Weighted delta fit (20), DTE fit (15), spread quality (25), liquidity (20), affordability (20) rank eligible contracts first, then score/symbol. Every rejected contract retains reason codes. AI never selects by doing arithmetic.

Queue records include rank, expiry, AI/Shadow/risk statuses and order/trade linkage. Status transitions distinguish SHORTLISTED, AI_ANALYZED, SHADOW_REVIEWED, DISMISSED, EXPIRED, RISK_REJECTED and EXECUTED. Broker approval/fill is atomic; there is no misleading separately committed RISK_APPROVED state before a fill. Time is checked again after AI and before broker execution; live broker quotes are aged at execution. Same-symbol duplicate positions remain blocked by final risk even across scans.

Research detail and agent intelligence expose normalized data, proposals, option metrics/reasons, analysis, objections and final outcome. API pagination is bounded; audit retention remains future operational work.
