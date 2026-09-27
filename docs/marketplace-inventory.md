# Inventory and capital efficiency

Recording a completed purchase creates one inventory item. The inventory page reports cost basis/cash tied up, days held, current evidence-based resale/profit estimate, sale-time context, aging and suggested manual review. Expected profit subtracts actual purchase cost basis plus expected sale fees/shipping; it does not charge purchase repairs twice. Missing comps leave the estimate unknown.

Configurable age boundaries default to 7, 30, 60 and 90 days: FRESH, NORMAL, AGING, STALE, DEAD_INVENTORY. “Dead” is a review label, not proof the item cannot sell. Suggestions never automatically change external prices or contact buyers. Actual sale removes the item from active inventory and updates realized performance.

Reads compute current aging. Click refresh or explicitly run `python -m app.marketplace.cli refresh-inventory --apply` to persist aging transitions, deduplicated internal alerts and right-censored calibration. There is no scheduled source monitor or automatic background repricing. Fixtures remain visibly identified and excluded from actual capital/performance totals.
