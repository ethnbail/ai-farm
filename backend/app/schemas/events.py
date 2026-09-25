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
]


class LiveEvent(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    event_type: EventType
    source: str
    payload: dict[str, Any]
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def as_sse(self) -> str:
        return f"id: {self.id}\nevent: {self.event_type}\ndata: {self.model_dump_json()}\n\n"
