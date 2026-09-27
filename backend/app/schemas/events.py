from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

EventType = Literal[
    "heartbeat",
    "trade_opened",
    "trade_closed",
    "marketplace_deal_found",
    "price_drop_detected",
    "agent_status_changed",
    "risk_limit_triggered",
    "risk_trade_rejected",
    "stop_loss_triggered",
    "take_profit_triggered",
    "portfolio_updated",
    "position_reduced",
    "market_regime_changed",
    "opportunity_discovered",
    "opportunity_shortlisted",
    "ai_analysis_completed",
    "ai_budget_warning",
    "shadow_review_completed",
    "market_data_stale",
    "market_data_restored",
    "marketplace_opportunity_created",
    "marketplace_listing_imported",
    "marketplace_strong_candidate",
    "marketplace_price_drop",
    "marketplace_duplicate_detected",
    "marketplace_listing_passed",
    "marketplace_item_bought",
    "marketplace_item_sold",
    "marketplace_inventory_aging",
    "marketplace_analysis_updated",
]


class LiveEvent(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    event_type: EventType
    source: str
    payload: dict[str, Any]
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def as_sse(self) -> str:
        return f"id: {self.id}\nevent: {self.event_type}\ndata: {self.model_dump_json()}\n\n"
