from decimal import Decimal
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class OrderRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    agent_id: UUID
    client_order_id: str = Field(default_factory=lambda: str(uuid4()), min_length=1, max_length=100)
    action: Literal["BUY", "SELL", "CLOSE", "BUY_TO_OPEN", "SELL_TO_CLOSE"]
    asset_type: Literal["equity", "etf", "option"]
    symbol: str = Field(min_length=1, max_length=32, pattern=r"^[A-Z0-9_.-]+$")
    quantity: int | None = Field(default=None, gt=0, le=1_000_000, strict=True)
    position_id: UUID | None = None
    requested_price: Decimal | None = Field(default=None, gt=0, allow_inf_nan=False)
    stop_loss: Decimal | None = Field(default=None, gt=0, allow_inf_nan=False)
    take_profit: Decimal | None = Field(default=None, gt=0, allow_inf_nan=False)
    reasoning: str = Field(default="Controlled paper order", max_length=4000)
    strategy_name: str = Field(default="manual-paper", max_length=100)
    strategy_version: str = Field(default="1", max_length=30)


class ExecutionResult(BaseModel):
    status: Literal["filled", "rejected"]
    order_id: UUID
    trade_id: UUID | None = None
    reason: str | None = None
