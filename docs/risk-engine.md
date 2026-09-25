# Deterministic risk authority

The broker always calls RiskEngine for new entries. OrderRequest has no bypass/override field and rejects unknown fields. Future strategy or AI proposals may select inputs, not replace arithmetic, accounting or final risk decisions. Settings are operator-controlled backend configuration, never browser/strategy request data.

| Rule | Default |
| --- | --- |
| Per-trade planned risk | 2% of current equity |
| Position cost allocation | 20% |
| Open positions | 3 (options additionally ≤2) |
| Daily / weekly loss | 5% / 10% |
| Total gross long exposure | 60% |
| Cash reserve after entry | 10% |
| Full option premium at risk | 2% |
| Option DTE | 7–45, never 0DTE |
| Option spread / ask | ≤15% |
| Option volume / OI | ≥50 / ≥100 |

All values are configurable with validated bounds in `.env.example`. Cash borrowing, short stock, short options, multi-leg orders, nonstandard option multipliers and assets outside each agent's mandate have no supported execution path. Agent paused/error states block entries. Regular-hours opening is default. Quotes must be fresh, non-crossed and instrument-matched, all held positions must have fresh marks, and equity must be positive. Stops must be positive and below bid, with targets above the simulated buy fill.

For a stock, unit cost is simulated ask-plus-slippage and unit planned risk is fill minus stop. For a long option, both unit cost and unit risk are **the entire fill premium ×100**, not loss down to the stop. Automatic quantity is the whole-number floor of the minimum allowed by risk budget, position allocation, available cash after reserve, exposure headroom, and option premium cap. Explicit quantities are checked, not silently resized. The exact cost and risk are checked again after cent rounding.

At $1,000 equity a 2% risk budget is $20. A $6.06 SPY mock fill costs $606 per contract: it is rejected. A $0.1515 fictional FARM mock fill costs $15.15 and can fit. There is no fractional option contract, risk relaxation or transfer from Agent A to force Agent B to trade.

Daily/weekly loss compares current marked equity with the first baseline for the New York day/week (Monday start). Baselines capture previous equity before the first new-period mark. Limits include realized and unrealized losses, prohibit further entries at the threshold, and do not prevent reducing/closing owned positions. They are not a latched kill switch: recovering equity can restore entry eligibility. Mark-to-market gaps and bid/ask/slippage mean actual stock stop loss can exceed the planned entry-minus-stop risk. Long-option loss remains bounded by premium in this no-margin model.

Risk decisions are persisted with rule, reason and order. Successful trades retain sizing calculations and entry account equity. A failure is a normal NO_TRADE result, exposed through `risk_trade_rejected` activity; it is never a synthetic successful fill.
