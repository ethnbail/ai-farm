from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AgentSummary(BaseModel):
    id: UUID
    name: str
    agent_type: Literal["equities", "options"]
    starting_balance: Decimal
    current_balance: Decimal
    total_return: Decimal
    total_return_percent: Decimal
    total_trades: int
    open_trades: int
    completed_trades: int
    status: Literal["idle", "running", "paused", "error"]
    created_at: datetime


class TradeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    agent_id: UUID
    asset_type: str
    symbol: str
    company_name: str
    side: str
    quantity: Decimal
    entry_price: Decimal
    stop_loss: Decimal | None
    take_profit: Decimal | None
    exit_price: Decimal | None
    realized_pnl: Decimal | None
    status: str
    entry_time: datetime
    exit_time: datetime | None
    reasoning: str | None


class MarketplaceSummary(BaseModel):
    status: Literal["not_configured"] = "not_configured"
    zip_code: str | None = None
    radius_miles: int | None = None
    opportunities_found: int


class AIUsage(BaseModel):
    status: Literal["disabled"] = "disabled"
    monthly_budget_usd: Decimal | None
    amount_used_usd: Decimal | None = None
    model_calls: int | None = None


class Health(BaseModel):
    status: Literal["ok", "degraded"]
    backend: Literal["ok"] = "ok"
    database: Literal["ok", "unavailable"]
    redis: Literal["ok", "unavailable"]
