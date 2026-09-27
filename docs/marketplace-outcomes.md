# User-controlled outcomes

TRACK, REVIEWING, CONTACTED and PASS are local recordkeeping actions. CONTACTED does not send a message. Passing can record “would have bought”; separately supplied hypothetical results never count as actual profit. Updating observations preserves this annotation and its frozen prediction.

BOUGHT records a transaction the user already completed, with actual price, purchase time, travel/repair/other costs and notes. SOLD requires existing inventory, a non-future sale after purchase, actual sale price, fees/shipping/other costs, platform and optional authenticity result. The UI requires a fresh user confirmation for each form. No button places an order or moves money. Exact repeated submissions are idempotent; conflicting duplicates are rejected.

Actual net profit = sale price − purchase price − purchase travel/repair/other costs − sale platform/payment/shipping/other costs. Actual ROI uses total actual cost as denominator. Days held uses timestamps, retaining fractional days. Actual costs never substitute estimated reserves. Fixture sales are excluded from real realized-profit totals.

Purchase snapshots select only persisted analysis recorded at or before the actual purchase time. Backdated purchases without a prior prediction are recordable but marked as having no pre-purchase prediction. Later comps or outcomes cannot retroactively create an accurate forecast. Existing Agent A/B balances, trades, broker and risk engine are not modified by any Marketplace workflow.
