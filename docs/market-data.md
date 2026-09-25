# Market data and simulation clocks

`EquityMarketDataProvider` supplies equity/ETF quotes and OHLCV bars. `OptionsMarketDataProvider` supplies chains and contract quotes. The combined provider is injected into strategies, risk/valuation and the paper broker, keeping those components independent of any vendor SDK.

Normalized Quote records include symbol, asset type, company, bid/ask/last, volume, timezone-aware timestamp and source mode. Options add underlying symbol/price, type, strike, expiration, multiplier, IV, delta/gamma/theta/vega and OI. Crossed prices, invalid timestamps and incomplete/nonstandard contracts are rejected by the normalization boundary. Greek values are supplied fixtures, never AI-generated or falsely described as calculated live Greeks.

## Modes

- MOCK: deterministic synthetic fixture, never an externally observed price.
- LIVE: reserved normalized mode for a future validated real-data adapter; none is registered now.
- STALE: quote/mark older than QUOTE_MAX_AGE_SECONDS (60 by default), or more than five seconds in the future. Execution refuses stale quotes. Persisted position marks age on API reads even if the worker stops.
- UNAVAILABLE: missing quote or unsupported provider. Old values are preserved and labeled, not silently replaced with zeros or mock data.

`MARKET_DATA_PROVIDER=mock` is the sole implemented factory choice. Any other value fails explicitly; an API key does not activate an undocumented live integration. `MARKET_DATA_API_KEY` remains backend-only and unused. The market status route describes currently available provider data; account/position labels separately describe persisted valuation freshness.

## Fixtures

Base mids: NVDA $100, SPY $550, fictional FARM $3, with one-cent bid/ask offsets. Target equity path: 0%, +1%, +6%; stop path: 0%, −1%, −6%. OHLCV bars have transparent rising/falling trends. Option ask bases: FARM $0.15, SPY $6, with a one-cent spread. Target multipliers: 1, 1.2, 1.8; stop multipliers: 1, 0.9, 0.5. All Greeks/IV/volume/OI are fixed synthetic values. Calls and puts intentionally share premium paths to test bookkeeping, not option pricing realism. Their paths are not calibrated to an arbitrage-free model. New chains choose a Friday at least21 days from the supplied clock; persisted contracts retain their expiration.

The staged demo uses a fixed Thursday September24,2026 14:00UTC regular-session clock, then +15s and +30s. It requires ENABLE_DEVELOPMENT_ACTIONS=true. The real UI clock can be later or the actual market closed; this does not change the explicitly simulated demo clock. Older demo positions are correctly labeled STALE; replay still records MOCK. Scheduler/scan/monitor use actual UTC time and stamp freshly generated synthetic quotes, not historical live observations.

## Exchange hours

XNYS calendar from exchange_calendars provides New York regular opens/closes, US holidays, DST and early closes. Coverage is explicitly 2020–2035; unknown dates fail closed. Pre-market is from04:00 New York until open on a trading day, after-hours from close until20:00; these labels are informational. Both agents open only in regular hours by default. Calendar releases need deliberate dependency maintenance, not a hard-coded Pacific offset. See [NYSE hours](https://www.nyse.com/markets/hours-calendars) and [exchange_calendars](https://github.com/gerrymanoim/exchange_calendars).

## Adding a provider later

Implement the protocols, normalize vendor symbols/units/timestamps/Greeks, reject malformed/missing data, set true source mode and preserve source quote time. Register it explicitly in the factory and add contract tests for freshness, holidays, limits, throttling, outages and settlement. No strategy/accounting rewrite should be required. A live **market-data** adapter still must not introduce real execution: the only broker remains PaperBroker. Data subscriptions, licensing and credentials are out of Phase2 scope.
