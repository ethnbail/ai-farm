# Event awareness

`EventSource` defines the future calendar connector boundary. Phase 3 reads persistent manually entered `EventRisk` rows and explicit test/mock rows; **no live earnings/macro calendar is claimed**. Fields include symbol (`*` for market-wide), event type, aware timestamp, importance, source, warning and computed seconds until event. Calendar types can represent earnings, FOMC, CPI, jobs or other announcements.

Mock rows are visible only when `EVENT_DATA_PROVIDER=mock` and market context is MOCK. They are not silently reused with LIVE quotes. Manual rows apply to their symbol/wildcard but do not constitute complete coverage. Coverage remains unavailable unless explicitly mock. `EVENT_DATA_API_KEY` is reserved backend-side; no credentialed event adapter exists.

The final RiskEngine calls `EventContextService.blocked`, including orders submitted outside research. `BLOCK_HIGH_IMPACT_EVENTS=true` rejects entries inside ±`EVENT_BLOCK_WINDOW_MINUTES` (default 60) of a high-impact event. `REQUIRE_EVENT_COVERAGE=true` also blocks absent coverage. Default false permits otherwise-valid paper entries with visible missing-calendar warnings. Existing positions can still be closed. Unit fixtures inject a near-term high-impact event and prove that final risk rejects the order; no public event injection endpoint was added.
