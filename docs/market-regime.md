# Deterministic market regimes

`MarketRegimeService` requires fresh SPY and QQQ quotes and at least 20 completed historical bars. Feature calculations use Decimal, not AI: SMA5/20, RSI14, ATR14/price, realized return standard deviation, five-bar momentum, relative volume, breakout distance and observed drawdown.

Priority is explicit:

1. Both trends down and either drawdown at least 8%: RISK_OFF.
2. Either ATR/price at least 4%: HIGH_VOLATILITY.
3. Both SMA5 above SMA20: BULL_TREND.
4. Both below: BEAR_TREND.
5. Otherwise both ATR/price below 0.5%: LOW_VOLATILITY.
6. Otherwise RANGE_BOUND.
7. Missing, malformed or stale data: UNKNOWN.

Persisted snapshots include features, reason, source mode and oldest contributing quote timestamp. The API ages the observation to STALE without rewriting historical facts. UNKNOWN/RISK_OFF block new research entries. Other labels contextualize deterministic strategy signals; they are not forecasts, breadth measurements, VIX proxies or learned regimes. Mock scenarios exist only to test the pipeline.
