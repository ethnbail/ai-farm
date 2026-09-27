# Sell-through, demand and sale time

Asking-price comparisons cannot establish sell-through. Provide a source-attributed cohort with total listings, sold counts for fully observed 7/14/30/60-day windows, observation duration/time and local/national market. Counts must be monotonic, within cohort size and backed by complete observation windows. Stale cohorts (over 90 days) are not used. No denominator means unknown, not a fabricated probability.

`SellThroughEstimator` uses a Beta(1,1) prior: `(sold + 1) / (cohort size + 2)` for each available window, with explicit quality/confidence. Local evidence is preferred when present. These are cohort estimates, not a guarantee that this item will sell, and depend on honest representative input. Category/condition/price comparability still requires user judgment; no external market discovery occurs.

`DemandComparisonService` compares supplied local/national 30-day cohorts. It returns LOCAL/NATIONAL/EITHER only when evidence supports a comparison, otherwise UNKNOWN. Missing supply, demand or premium stays unknown. `SaleTimeEstimator` reports intervals where the cumulative probability crosses 25%, 50% and 80%; an unreached quantile stays unavailable. A first-window crossing gives 0–7 days, not a fabricated exact day.

Seasonality is separate low-confidence calendar context, not invented sales evidence. Add real observed outcomes over time before treating these estimates as calibrated. See [calibration](marketplace-calibration.md) for right-censoring and denominators.
