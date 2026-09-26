# Backend event → farm reaction

All recognized business events also trigger the existing resource refresh. This table describes additional short-lived visuals; none authorizes trading or calls an AI provider.

| Event | State / visual response |
| --- | --- |
| `trade_opened` | Target agent TRADE_ACTIVE; work motion and active lamp |
| `trade_closed` | Target IDLE/completion marker; preserves a preceding SUCCESS/LOSS reaction |
| `take_profit_triggered` | Target SUCCESS; brief bounce and gold accents |
| `stop_loss_triggered` | Target LOSS; lean and subdued orange lamp |
| `risk_trade_rejected`, `risk_limit_triggered` | Target REJECTED; gate closes, creature steps back |
| `opportunity_discovered` | Target and research SCANNING |
| `opportunity_shortlisted` | Research ANALYZING; target WAITING |
| `ai_analysis_completed` | Research ANALYZING; mole works and lamp activates |
| `shadow_review_completed` | Shadow ANALYZING; crow inspects the target agent and returns |
| `marketplace_opportunity_created`, `marketplace_deal_found` | Marketplace ANALYZING; raccoon carries parcel and stall activates |
| `price_drop_detected` | Marketplace ANALYZING; stall price-tag flip (compatible visual hook; no live emitter added) |
| `market_data_stale` | Target DATA_STALE, or A/B/research when global; dimmed buildings and status text |
| `market_data_restored` | Remove affected event override; reconcile current API data |
| `ai_budget_warning` | Research WAITING / amber activity warning |
| `portfolio_updated`, `position_reduced` | Refresh genuine balances/positions; no fabricated success celebration |
| `agent_status_changed` | Refresh; derive current base state from agent status/positions |
| `market_regime_changed` | Refresh regime; subtle cooler light or windmill speed change |
| `heartbeat` | Shared Live indicator and last-heartbeat time, not a business animation |

`LiveEventsProvider` parses the event envelope, rejects malformed/oversized/unknown records, deduplicates IDs, and dispatches `ai-farm:event` plus the existing `ai-farm:update`. One EventSource serves the app; buildings do not open their own streams. Native EventSource reconnect/resume remains intact. The provider reports reconnecting or missing heartbeats; no optimistic live status is inferred from a running animation.

Development replay supplies a local timestamp, UUID and actual chosen agent ID, then directly calls the same transition function. It does not publish Redis/SSE records, issue POSTs, refresh account data, or persist fake activity. Portfolio numbers and existing activity feeds never contain simulator events.
