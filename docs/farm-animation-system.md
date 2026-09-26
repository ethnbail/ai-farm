# Farm animation system

`farm-state.ts` is the reusable deterministic controller. States are `IDLE`, `SCANNING`, `ANALYZING`, `WAITING`, `TRADE_ACTIVE`, `SUCCESS`, `LOSS`, `REJECTED`, `DATA_STALE` and `OFFLINE`. Areas are independent, with an optional target agent on review motions. No random status changes, AI decisions, financial calculations, order submission or network calls occur in the controller.

## Reconciliation and precedence

Agent identity is resolved from the backend agent ID in event source or payload, never from an assumed array position. Unknown agent IDs do not animate an arbitrary account. Base state follows actual API and connection health: unavailable/error → OFFLINE; stale market/held valuation → DATA_STALE; open positions → TRADE_ACTIVE; running → SCANNING; paused → WAITING; otherwise IDLE. AI disabled is a normal idle state, not an error. Exhausted enabled AI budgets yield research WAITING. Treasury/analytics expose database, backend, Redis and stream state.

Recent business events temporarily overlay that baseline. Most reactions last 6.5 seconds, Shadow inspection 8.5 seconds, budget warning 12 seconds, stale notification 20 seconds; expiration is checked each second. Persistent stale API data remains stale after notification expiration. Restoration removes the event latch and returns to the current data-derived state, not blindly to healthy. A `trade_closed` event immediately following profit/loss does not mask its existing reaction. Offline base state suppresses real event overrides; explicit development rehearsal may override it and is prominently labeled.

One layer owns each area's transient state: subsequent events replace earlier ones except the completion/profit-loss rule. Replayed events older than 60 seconds or over 5 seconds in the future refresh data without replaying animations. Stream IDs are deduplicated in a bounded 512-ID set. Server ordering and data polling ultimately reconcile state; this is a visual controller, not an authoritative event ledger.

## Motion vocabulary

Idle creatures breathe and gently shift; this is explicitly labeled ambience. Working states add a small walk/work motion. Success briefly bounces and shows small gold roof accents. Loss is a subdued lean and orange lamp; rejection closes a gate and steps back. Shadow flies toward the event's agent and returns to its perch. The raccoon carries a parcel during listing analysis; price-drop events flip its stall tag. A close event adds a small completion marker. Stale/offline buildings dim while textual labels explain their state. The windmill moves continuously, slightly faster in HIGH_VOLATILITY and slower in LOW_VOLATILITY; BEAR_TREND/RISK_OFF cool the environment mildly. Other regimes use neutral warm daylight. No flashing or constant particle systems.

React Three Fiber frame callbacks update object refs. The shared scene assets remain bounded for the browser session; subscriptions, timers, per-mount HTML labels, controls and observers clean up on unmount. Offscreen/hidden scenes pause frame rendering. Reduced motion uses the full 2D experience, with no mounted farm canvas. See the separate pure Node tests and browser tests for event isolation and fallback behavior.
