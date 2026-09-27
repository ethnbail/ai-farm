# Outcome calibration

Actual records, fictional fixtures and hypothetical observations remain distinguishable. Aggregate actual metrics exclude fixtures and hypotheticals. The page shows actual, hypothetical and excluded-fixture counts. Fewer than 20 actual sales reports `insufficient_sample`; larger samples remain descriptive, not causal or guaranteed. No autonomous retraining or parameter modification exists.

Stored metrics include conservative resale error, expected-net-profit error, resale-range coverage, sale-time error/range coverage, predicted/actual authenticity and resolved sell-through outcomes. Summary shows mean absolute error, signed bias by category/source and per-window Brier score with its own denominator. Missing historical predictions contribute no fabricated accuracy values. A sale count can exceed an individual metric's eligible sample size.

Unsold inventory is right-censored: a 10-day unsold item resolves only the 7-day window, not 14/30/60. A sale at day 10 resolves 7 days as no sale and later windows as a sale. Explicit inventory refresh records mature no-sale observations; later sale replaces the unsold calibration record rather than double-counting it. User-supplied hypothetical outcomes remain separately labeled and do not affect actual-profit or accuracy aggregates.

Representative completed cohorts and prospectively recorded predictions are prerequisites for useful calibration. User selection bias, incomplete cost recording and incorrect source data remain limitations. Twenty sales is a display threshold, not proof of statistical reliability.
