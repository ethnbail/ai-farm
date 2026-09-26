# Phase 3 intelligence

Phase 3 extends, rather than replaces, Phase 2. All execution is PAPER ONLY. No order API, real broker, autonomous code modification, training, scraping, seller contact or purchase automation is added.

## Flow and authority

```text
Normalized provider -> deterministic SPY/QQQ regime -> configured universe/watchlists
  -> features + original strategy -> ranked candidate / top-K queue
  -> optional structured AI -> deterministic + optional AI Shadow critique
  -> existing RiskEngine -> existing PaperBroker -> accounting / confidence / SSE
```

`run_intelligence` is research-only unless `execute=True`. Agent A uses the existing trend/momentum equity proposal; Agent B ranks option contracts before building the existing long-option proposal. Quotes, quantity, stop and target never come from AI prose. NO_TRADE, a Shadow veto, budget denial, data failure and a risk rejection are distinct persisted outcomes. Research-only approval is not risk approval.

The worker remains opt-in. `INTELLIGENCE_ENABLED=true` switches scheduled scans to the new pipeline; monitoring, portfolio locking, idempotent paper orders and Redis coordination remain. The 120-second lease is checked before each job and each intelligence submission; lost ownership prevents a new submission. Slow scans can lose their lease and stop without executing. There is no infinite retry of a paid call.

Migration `0003` adds 15 research/budget/event/watchlist/Marketplace tables and nullable matching-period benchmark fields. It preserves old trades/accounts/events. The budget guard row serializes reservations. Confidence attaches to the existing trade ID and is settled when monitoring closes that trade. Benchmark source modes cannot be mixed. Older benchmark records without an observed portfolio start remain N/A for matching-period comparison; no historical baseline is invented.

Agent A reports portfolio/benchmark return from the same observed start, excess return and sampled SPY drawdown. Portfolio lifetime drawdown is labeled separately. Agent B's strategy/version and persisted outcomes form a deterministic baseline framework; a comparable options benchmark remains unavailable. Reliability groups agent/strategy/model/regime, counts decisions and outcomes, and withholds win rate, average return and Brier score below 20 relevant outcomes. This is infrastructure, not proof of skill or a ranking.

## Market provider

`MarketDataProvider` composes equity/options protocols. `Quote`, `Bar`, `HistoricalSeries`, `OptionContract`, `OptionChain`, `MarketSnapshot`, and `MarketStatus` define internal structures. Existing strategies retain their normalized Quote/Bar interfaces. `TradierMarketDataProvider` implements only fixed-host read-only market endpoints: quotes, history, expirations and chains. No account or order endpoint exists in the adapter.

Set `MARKET_DATA_PROVIDER=tradier` and backend-only `MARKET_DATA_API_KEY`. Absent/blank credentials explicitly fall back to MOCK, reported by `/market/provider-status`; bad credentials or a failing configured provider do **not** silently fall back. Unknown providers fail closed. Defaults require no credentials.

Requests have bounded timeouts, transport/5xx retries, per-instance caching and a request budget. 429 and provider rate headers establish local backoff; no waiting through a long reset. Malformed payloads produce sanitized failures. Complete daily historical bars exclude today's partial session; histories older than five days are rejected. Daily bar date labels use UTC midnight and are not intraday observations. Bid/ask timestamps are the execution freshness basis; an option inherits the older underlying timestamp. Unsupported/adjusted option multipliers are rejected. Greeks without an explicit timezone are deliberately unverified and block live option entry. Tradier documentation includes naive Greek timestamps, so this conservative behavior may reject otherwise available contracts until a trustworthy timestamp interpretation is configured in a future change. LIVE describes source, not an entitlement guarantee; delayed quotes fail the age threshold.

Official references: [quotes and Greeks](https://docs.tradier.com/docs/quotes), [rate limits](https://docs.tradier.com/docs/rate-limiting), [historical data](https://docs.tradier.com/docs/historical-data). Credentialed Tradier access was not exercised. Tests use contract-shaped HTTP fixtures, not fabricated live observations.

## API and UI

These routes are available under `/api` and as unprefixed aliases:

```text
GET /market/regime              GET /market/status
GET /market/provider-status    GET /opportunities[?agent_id=&limit=]
GET /opportunities/{id}        GET /research[?agent_id=&limit=]
GET /research/{id}             GET /ai/usage
GET /ai/status                 GET /reliability
GET /agents/{id}/intelligence  GET /events/risk[?symbol=SPY]
GET /watchlists                POST /watchlists
DELETE /watchlists/{id}        GET /marketplace/opportunities
GET /marketplace/opportunities/{id}
```

Watchlist mutations default off. Enabling `LOCAL_WRITES_ENABLED=true` also requires an explicit trusted `Origin`; limits are 10 lists per agent and 30 symbols per list/universe. This is a local-development gate, **not authentication**. Do not expose the application publicly. Marketplace imports/outcomes are local service calls, not public mutation endpoints.

The warm dashboard is retained. Research links expose normalized facts, deterministic scoring/proposal, validated analysis, Shadow objections, risk result and executed trade link. Agent details include universe, versions, reliability, rejected risk rules and ranked option fields. All added business events reuse the durable event store and shared EventSource; polling remains fallback. Recorded research is historical, not an assertion that its quotes are still tradable. Regime/provider observations age on read, and pending queues expire.

## Exact scan commands

From `backend/`, after README setup, migrations and seed, with PostgreSQL/Redis running:

```sh
# Current-clock MOCK research, no paid AI and no paper order:
ENABLE_DEVELOPMENT_ACTIONS=true .venv/bin/python -m app.workers.cli research --demo
# Explicit paper execution; compounds existing balances, never resets them:
ENABLE_DEVELOPMENT_ACTIONS=true .venv/bin/python -m app.workers.cli research --demo --execute
# Import the clearly labeled manual/test Marketplace example:
ENABLE_DEVELOPMENT_ACTIONS=true .venv/bin/python -m app.workers.cli marketplace-fixture
# Configured provider/AI; research only (may make paid calls if explicitly enabled):
.venv/bin/python -m app.workers.cli research
# Configured provider/AI plus final risk-controlled paper submission:
.venv/bin/python -m app.workers.cli research --execute
# Optional scheduler, actual market hours; stop before manual demos:
PAPER_WORKER_ENABLED=true INTELLIGENCE_ENABLED=true .venv/bin/python -m app.workers.scheduler
```

`--demo` overrides provider to mock and AI to false in memory; it does not modify `.env` or reset balances. FARM is a synthetic affordable option fixture, not a live ticker recommendation. Replace the mock options universe before selecting real market data. Existing Phase 2 staged `demo --stage entry|mark|exit` remains available and uses its documented fixed clock. Do not mix staged fixture clocks with a running worker.

Read [routing](model-router.md), [budget](ai-budget.md), [Shadow](shadow-agent.md), [regime](market-regime.md), [scanner](opportunity-scanner.md), [events](event-context.md), [Marketplace](marketplace-intelligence.md), [verification](phase3-verification.md) and [inventory](phase3-files.md).
