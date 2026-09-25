# Paper broker and accounting

Only long positions exist. Agent A accepts BUY/SELL/CLOSE for equity or ETF. Agent B accepts BUY_TO_OPEN/SELL_TO_CLOSE (and the internal generic CLOSE) for a long CALL or PUT. Ownership is checked against the selected agent's portfolio; sales cannot exceed that position's quantity.

## Fills and rounding

- Equity buy: ask × (1 + EQUITY_SLIPPAGE_BPS / 10,000); sell: bid × (1 − bps/10,000). Default 5 bps.
- Option buy: ask × (1 + OPTION_SLIPPAGE_PERCENT / 100); sell: bid × (1 − percent/100). Default 1%.
- Execution prices round half-up to four decimal places. Notionals, cash, basis and P&L round half-up to cents, using Decimal, not binary floats.
- Fill captures requested reference price, simulated price, quantity, notional, bid/ask, dollar slippage beyond bid/ask, source mode, simulation time and quote timestamp. `requested_price` is a reference, not a limit-order instruction. Only simulated market orders are implemented.
- Options multiply premium by 100. Marks use bid × quantity × multiplier, excluding hypothetical exit slippage. Unrealized P&L is marked value minus remaining cost basis.

Purchases subtract cost from that portfolio's cash. Sales add proceeds and realize proceeds minus allocated basis. Partial exits round allocated basis to cents and assign all remaining basis to the final exit, avoiding residual pennies. Trade quantity remains original size; remaining quantity lives on Position. Trade exit price is quantity-weighted across exits; individual Fill rows retain exact executions. Equity is cash plus open market value, including unrealized gains/losses. Zero/unavailable exit bids are rejected, not magically filled; missing/stale quotes preserve the last known valuation and are visibly flagged.

## Golden fixtures from a fresh account

| Scenario | Buy fill | Exit fill | Cash P&L | Final equity |
| --- | --- | --- | --- | --- |
| A: one NVDA, target | 100.0600 | 105.9370 | +5.88 | 1,005.88 |
| A: one NVDA, stop gap | 100.0600 | 93.9430 | −6.12 | 993.88 |
| B: one FARM call, target | 0.1515 ×100 | 0.2574 ×100 | +10.59 | 1,010.59 |
| B: one FARM call, stop | 0.1515 ×100 | 0.0644 ×100 | −8.71 | 991.29 |

Immediately after entry A has cash $899.94, value $99.99 and equity $999.93. B has cash $984.85, value $14.00 and equity $998.85. Spread/slippage costs appear immediately. A second target demo can size two shares after the first gain: accumulated A equity becomes $1,017.63, not a repeated fixed-dollar outcome. B becomes $1,021.18. Reseeding preserves both.

## Stops, targets and expiration

Monitor checks bid against stored stop/target, then rechecks when closing under the account lock. Fill is at the available simulated bid minus slippage, not exactly at the trigger. Exit reason, triggered event, closing event and refreshed portfolio are persisted. Exits remain possible outside regular opening hours in this simulation; this is not a promise of real exchange execution availability.

At or after the expiration session close, this model settles standard long options at nonnegative intrinsic value using a fresh underlying quote: CALL=max(underlying−strike,0), PUT=max(strike−underlying,0), multiplied by100. OTM settles at zero, losing premium only. This is explicitly **synthetic cash settlement**, not a representation of physical delivery, exercise, assignment, broker liquidation, or OCC processing. The mock provider supplies expired-contract quotes; a future provider without them needs a dedicated validated settlement-data path before deployment. Unknown/stale data defers settlement rather than inventing a price.

No commissions, fees, taxes, dividends, splits, order-book depth, partial liquidity fills or real option valuation model are implemented. These simplifications are explicit and tested; no results imply tradable performance.
