from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class Agent(Base):
    __tablename__ = "agents"
    __table_args__ = (
        CheckConstraint("starting_balance > 0", name="positive_starting_balance"),
        CheckConstraint("agent_type IN ('equities', 'options')", name="agent_type"),
        CheckConstraint("status IN ('idle', 'running', 'paused', 'error')", name="status"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    agent_type: Mapped[str] = mapped_column(String(30))
    starting_balance: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    current_balance: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    status: Mapped[str] = mapped_column(String(30), default="idle")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Trade(Base):
    __tablename__ = "trades"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="positive_quantity"),
        CheckConstraint("entry_price >= 0", name="nonnegative_entry_price"),
        CheckConstraint("side IN ('buy', 'sell')", name="side"),
        CheckConstraint("status IN ('open', 'closed')", name="status"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    agent_id: Mapped[UUID] = mapped_column(ForeignKey("agents.id"), index=True)
    asset_type: Mapped[str] = mapped_column(String(30))
    symbol: Mapped[str] = mapped_column(String(32))
    company_name: Mapped[str] = mapped_column(String(200))
    side: Mapped[str] = mapped_column(String(10))
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    entry_price: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    stop_loss: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    take_profit: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    exit_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    realized_pnl: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    status: Mapped[str] = mapped_column(String(30), default="open")
    entry_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    exit_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reasoning: Mapped[str | None] = mapped_column(Text)
    portfolio_id: Mapped[UUID | None] = mapped_column(ForeignKey("portfolios.id"), index=True)
    requested_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    fill_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    realized_return_percent: Mapped[Decimal | None] = mapped_column(Numeric(14, 4))
    position_size: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    account_equity_at_entry: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    percent_allocated: Mapped[Decimal | None] = mapped_column(Numeric(14, 4))
    maximum_planned_loss: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    strategy_name: Mapped[str | None] = mapped_column(String(100))
    strategy_version: Mapped[str | None] = mapped_column(String(30))
    market_data_mode: Mapped[str | None] = mapped_column(String(20))
    data_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    exit_reason: Mapped[str | None] = mapped_column(String(100))
    entry_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    risk_calculation: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class MarketplaceOpportunity(Base):
    __tablename__ = "marketplace_opportunities"
    __table_args__ = (CheckConstraint("asking_price >= 0", name="nonnegative_asking_price"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    source: Mapped[str] = mapped_column(String(50))
    source_listing_id: Mapped[str | None] = mapped_column(String(200))
    title: Mapped[str] = mapped_column(String(500))
    asking_price: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    expected_resale_low: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    expected_resale_high: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    expected_profit: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    listing_url: Mapped[str | None] = mapped_column(Text)
    zip_code: Mapped[str | None] = mapped_column(String(10))
    distance_miles: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    listing_age_minutes: Mapped[int | None]
    status: Mapped[str] = mapped_column(String(30), default="new")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SystemEvent(Base):
    __tablename__ = "system_events"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    event_type: Mapped[str] = mapped_column(String(80), index=True)
    source: Mapped[str] = mapped_column(String(100))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    sequence: Mapped[int | None] = mapped_column(BigInteger, unique=True)
