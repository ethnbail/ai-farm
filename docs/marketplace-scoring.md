# Transparent opportunity scoring

Weights out of 100: freshness 25, expected net profit 20, ROI 15, 30-day sell-through 15, seller reliability 5, completeness 5, motivation 5, valuation confidence 10. Missing components contribute no positive evidence; their uncertainty remains visible. Component scores and rejection reasons are returned, not hidden in an AI answer.

Freshness default thresholds in minutes: NEW <15, VERY_FRESH <60, FRESH <360, RECENT <1440, AGING <4320, OLD thereafter. Settings persist these thresholds. Source publication time is preferred; first observation is the fallback, clearly identified. Reposts retain earliest-known age and receive no new-opportunity freshness boost. Observations older than the stale threshold cannot silently remain strong candidates.

STRONG_CANDIDATE requires the configured score and no blocking reason; REVIEW has missing/out-of-scope evidence; WEAK has a lower unblocked score; REJECT covers high authenticity risk or negative net profit. Radius, maximum pickup distance/time, price range, category, seller rating, listing age, minimum profit and ROI settings create explicit reasons. Freshness alone never makes a deal good.

## Economics

Travel = supplied one-way miles × 2 × configured cost per mile (default $0.70). No location lookup occurs. Missing distance means unknown travel and unknown net profit; explicit zero means no travel cost. Supplied round-trip driving minutes enable profit/hour.

Net = conservative resale × (1 − platform fee rate − payment fee rate) − asking price − travel − shipping − repairs − other costs − known missing-accessory reserve. ROI = net / (asking price + fixed costs). Profit margin, profit per invested dollar/day/mile/hour and break-even resale price use these same inputs. Unknown terms stay unknown; division by zero returns unavailable.

Maximum buy price is the nonnegative minimum of the minimum-profit and minimum-ROI constraints after fees, fixed costs and a risk reserve. Reserve percent = configured base + 10×(1−valuation confidence) +5 for unknown/medium authenticity +5 for seller red flags, capped at 100%. These additions are transparent conservative policy heuristics, not estimated loss probabilities. High authenticity risk suppresses a buy quote. Target = 90% of maximum; walk-away = maximum. Advisory prices never initiate a transaction. Risk reserve is used in buy limits, not disguised as an actual operating expense.

Seasonality is an explicitly low-confidence calendar context with user-selected hemisphere. Unknown hemisphere is neutral. It does not fabricate demand, change sold comps or inflate resale value.
