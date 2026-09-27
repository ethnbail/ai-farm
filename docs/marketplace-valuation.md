# Resale valuation

`MarketplaceValuationService` depends on a comparison-provider interface; `ManualComparisonProvider` uses supplied sold-comparable evidence. There is no external price feed. Each comparable records source, observation time, price, currency, category/model/condition, market and quality (`verified`, `user_reported`, `fixture`). User-entered labels are not independently authenticated.

Matching requires compatible USD/category/model/condition and recent sold evidence (180-day window). Conservative value / expected low is the lower quartile; expected high is the upper quartile. Median, count, recency, quality and confidence are exposed. Confidence is capped; a handful of comps is not a precise appraisal. No matched sold comps returns insufficient data and no resale, profit or buy-price assertion.

The detail form accepts manual comps; imports support a `comps` array. Do not relabel asking prices as completed sales. Fixture comps are fictional and visibly attributed. Photo-analysis interfaces exist but report unavailable. Listing and outcome history remain auditable; future approved data providers can implement the interface without replacing normalization or arithmetic.
