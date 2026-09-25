# Phase 2 trading engine

The only executor is `PaperBroker`. No credentials, broker SDK, network order adapter, AI client, or public execution endpoint exists. The original dashboard/API/health/heartbeat and seed behavior remain intact.

## Execution path and ownership

`Redis scheduler or explicit CLI → strategy proposal → PaperBroker → RiskEngine → atomic PostgreSQL transaction → durable SystemEvent → SSE → dashboard refresh`

An Agent has one Portfolio. All Positions, Orders, RiskEvents and PerformanceSnapshots are portfolio-scoped; Trades link the original Agent and new Portfolio. Fills link orders and trades. Each option trade stores an immutable OptionContractSnapshot and a replay-ready entry snapshot on Trade. Benchmarks have one record per account. Positions retain their identity after closure; partial exits accumulate realized P&L on the same round-trip Trade.

A portfolio row lock serializes execution and marking within that account. Cash cannot be negative; there is no cross-account transfer or borrowing. `(portfolio_id, client_order_id)` is unique: an identical retry returns the original result, a changed request with that key fails. Unexpected errors roll back orders, fills, positions, balances and events together. Deterministic risk rejections persist a rejected order and RiskEvent without a fill.

Equity is cash plus bid-marked open positions. Agent.current_balance mirrors equity for Phase 1 compatibility. Position sizing uses current equity so gains/losses compound. Seed only creates missing accounts; migrations preserve old Agent/Trade fields. Legacy closed trades remain visible, but historical balances are not fabricated into new fills or performance snapshots. Legacy open trades without a managed position block new entries until explicitly reconciled; migration does not guess their state.

## Strategies

`Strategy.evaluate(symbol)` returns BUY/SELL/HOLD, reason, proposed entry/stop/target, quote and indicator metadata. TrendMomentumStrategy compares configurable fast/slow SMAs (5/20) and the latest two closes, requiring positive volume for BUY. SELL closes an owned equity position; it never shorts. Default equity stop/target are 2%/4% from last price. The starter scans NVDA; the provider also includes the SPY ETF.

`OptionsPaperStrategy` is independently replaceable. DirectionalMomentumOptionsStrategy derives CALL/PUT direction from the underlying trend. OptionsScanner filters DTE, delta, IV, theta-decay, nonnegative gamma, spread and liquidity; OptionsSelector orders by spread, closeness to absolute delta 0.55, then symbol. Defaults are 7–45 DTE, absolute delta 0.40–0.70, IV ≤3.0, daily theta/ask decay ≤20%, volume ≥50, OI ≥100. Selection never overrides the broker's full-premium risk checks. Initial stops are 30% below bid and targets 50% above ask. SPY then fictional FARM are scanned. These are test strategies, not profitability claims. Trailing stops are deferred; stop/target fields and the monitor provide their future integration boundary.

## Scheduling

Worker is a separate opt-in process, not part of FastAPI startup. Redis stores the shared `ai-farm:paper-engine` 120-second lease and per-job next-due timestamps. Defaults: equity scan 60s, options scan 60s, monitor 15s; a 2-second coordinator loop does no high-frequency trading. A competing worker skips leased work. Redis failure fails closed; exceptions are logged and retried next iteration, never redirected to another executor. PostgreSQL locking/idempotency remains the accounting authority. These bounded local mock jobs are not a long-running distributed job framework; future remote providers need lease renewal, task identities and timeouts designed together.

Each monitoring pass marks positions, snapshots performance and evaluates stop/target/expiry. Quotes must be fresh. Monitor releases its marking transaction then re-locks and rechecks triggers before a closing fill. Scheduled mock data cycles through three fixed ticks; scans use the actual timezone-aware clock and exchange calendar. Disable the worker before manual staged demos; both use the same Redis lease. Use separate Redis databases for independent app environments.

## APIs and UI

All trading routes are GET-only, available with `/api` and unprefixed aliases:

| Path | Purpose |
| --- | --- |
| `/agents`, `/agents/{id}` | Compatible summary, equity, counts, valuation freshness |
| `/agents/{id}/portfolio` | Cash, equity, P&L and valuation state |
| `/agents/{id}/positions` | Open positions, option fields, current DTE and freshness |
| `/agents/{id}/trades` | Original paginated history, extended replay fields |
| `/agents/{id}/performance` | Independent statistics and benchmark |
| `/trades/{id}` | Full trade, immutable entry/risk snapshots, fills, timeline |
| `/activity` | Recent persisted events, bounded limit |
| `/market/status` | Actual exchange session, provider availability, paper-only status |

`/health` retains real database/Redis checks. `/api/events` sends an immediate heartbeat and polls committed business events every 0.5s. A singleton transactional counter assigns sequences in commit order; heartbeat frames have no SSE ID so they cannot overwrite the durable cursor. Last-Event-ID resumes subsequent business events; an initial connection gets up to the last 50. Events remain in PostgreSQL across worker/API restarts. Delivery is at-least-once across reconnects; UI events trigger idempotent reads. A shared EventSource coalesces refresh bursts and retains 15-second polling as a fallback. Heartbeat Live indicates transport health, not quote freshness or execution activity.

The warm dashboard now shows PAPER TRADING, MOCK/STALE/UNAVAILABLE/LIVE data states (LIVE is reserved for future adapters), independent equity/counts, activity, agent metrics, positions, history, and clickable replay pages. Quote age is reevaluated on reads without silently overwriting persisted marks. API failures keep old data with an explicit warning, not fake zeros. Trade Replay displays stored facts and event timestamps; no chart replay or current Greeks are invented.

## Performance

Rates/averages/expectancy/profit factor require at least five completed managed round trips. Win rate counts winners/all closed trades (breakevens remain in the denominator). Expectancy is mean realized P&L. Profit factor is gross wins/absolute gross losses, N/A if no losses. Drawdown compares sampled equity with its high-water mark; intratick extremes are not reconstructed. Best/worst trades and observed holding time remain factual even for a small sample. Sharpe/Sortino are N/A without an appropriate return series. SPY benchmark starts at the first observed mock quote, ignores fees/dividends and is labeled MOCK; the options baseline is explicitly unavailable.

Event/snapshot retention, authentication and production operations are later work. Keep this stack on a trusted local machine.
