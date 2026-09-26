"""Paper-only accounting records. Cash and risk never cross portfolio boundaries."""

from datetime import date, datetime
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
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class Portfolio(Base):
    __tablename__ = "portfolios"
    __table_args__ = (CheckConstraint("cash_balance >= 0", name="nonnegative_cash"),)
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    agent_id: Mapped[UUID] = mapped_column(ForeignKey("agents.id"), unique=True)
    starting_balance: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    cash_balance: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    market_value: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0)
    equity: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    realized_pnl: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0)
    unrealized_pnl: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0)
    total_return_percent: Mapped[Decimal] = mapped_column(Numeric(14, 4), default=0)
    high_water_mark: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    max_drawdown_percent: Mapped[Decimal] = mapped_column(Numeric(14, 4), default=0)
    day_start_equity: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    week_start_equity: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    day: Mapped[date | None]
    week: Mapped[date | None]
    valuation_state: Mapped[str] = mapped_column(String(20), default="unavailable")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Position(Base):
    __tablename__ = "positions"
    __table_args__ = (
        CheckConstraint("quantity >= 0", name="nonnegative_quantity"),
        CheckConstraint("contract_multiplier > 0", name="positive_multiplier"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    portfolio_id: Mapped[UUID] = mapped_column(ForeignKey("portfolios.id"), index=True)
    trade_id: Mapped[UUID] = mapped_column(ForeignKey("trades.id"), unique=True)
    asset_type: Mapped[str] = mapped_column(String(30))
    symbol: Mapped[str] = mapped_column(String(100))
    company_name: Mapped[str] = mapped_column(String(200))
    quantity: Mapped[int]
    average_entry_price: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    cost_basis: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    current_price: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    market_value: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    unrealized_pnl: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    stop_loss: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    take_profit: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    status: Mapped[str] = mapped_column(String(20), default="open")
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    underlying_symbol: Mapped[str | None] = mapped_column(String(32))
    option_type: Mapped[str | None] = mapped_column(String(4))
    strike: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    expiration: Mapped[date | None]
    contract_multiplier: Mapped[int] = mapped_column(default=1)
    entry_iv: Mapped[Decimal | None] = mapped_column(Numeric(14, 6))
    entry_delta: Mapped[Decimal | None] = mapped_column(Numeric(14, 6))
    entry_gamma: Mapped[Decimal | None] = mapped_column(Numeric(14, 6))
    entry_theta: Mapped[Decimal | None] = mapped_column(Numeric(14, 6))
    entry_vega: Mapped[Decimal | None] = mapped_column(Numeric(14, 6))
    bid: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    ask: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    data_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    data_state: Mapped[str] = mapped_column(String(20))


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (UniqueConstraint("portfolio_id", "client_order_id"),)
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    portfolio_id: Mapped[UUID] = mapped_column(ForeignKey("portfolios.id"), index=True)
    client_order_id: Mapped[str] = mapped_column(String(100))
    action: Mapped[str] = mapped_column(String(30))
    symbol: Mapped[str] = mapped_column(String(100))
    quantity: Mapped[int] = mapped_column(default=0)
    requested_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    status: Mapped[str] = mapped_column(String(20))
    rejection_reason: Mapped[str | None] = mapped_column(String(500))
    request: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Fill(Base):
    __tablename__ = "fills"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    order_id: Mapped[UUID] = mapped_column(ForeignKey("orders.id"), unique=True)
    trade_id: Mapped[UUID] = mapped_column(ForeignKey("trades.id"), index=True)
    action: Mapped[str] = mapped_column(String(30))
    quantity: Mapped[int]
    requested_price: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    price: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    notional: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    estimated_slippage: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    bid: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    ask: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    data_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    market_data_mode: Mapped[str] = mapped_column(String(20))


class OptionContractSnapshot(Base):
    __tablename__ = "option_contract_snapshots"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    trade_id: Mapped[UUID] = mapped_column(ForeignKey("trades.id"), unique=True)
    # Immutable normalized quote: underlying, expiration, DTE, strike, Greeks, IV,
    # multiplier, liquidity, bid/ask, spread and provider timestamp are all preserved.
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSON)


class RiskEvent(Base):
    __tablename__ = "risk_events"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    portfolio_id: Mapped[UUID] = mapped_column(ForeignKey("portfolios.id"), index=True)
    order_id: Mapped[UUID] = mapped_column(ForeignKey("orders.id"))
    rule: Mapped[str] = mapped_column(String(80))
    details: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class PerformanceSnapshot(Base):
    __tablename__ = "performance_snapshots"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    portfolio_id: Mapped[UUID] = mapped_column(ForeignKey("portfolios.id"), index=True)
    equity: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    cash: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    market_value: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    realized_pnl: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    unrealized_pnl: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    market_data_mode: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Benchmark(Base):
    __tablename__ = "benchmarks"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    portfolio_id: Mapped[UUID] = mapped_column(ForeignKey("portfolios.id"), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    starting_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    current_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    equity: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    total_return_percent: Mapped[Decimal | None] = mapped_column(Numeric(14, 4))
    data_state: Mapped[str] = mapped_column(String(20), default="unavailable")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    source_mode: Mapped[str | None] = mapped_column(String(20))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    portfolio_equity_at_start: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    high_water_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    max_drawdown_percent: Mapped[Decimal | None] = mapped_column(Numeric(14, 4))


class MarketState(Base):
    __tablename__ = "market_state"
    id: Mapped[int] = mapped_column(primary_key=True)
    tick: Mapped[int] = mapped_column(default=0)
    scenario: Mapped[str] = mapped_column(String(20), default="target")


class EventCounter(Base):
    __tablename__ = "event_counter"
    id: Mapped[int] = mapped_column(primary_key=True)
    value: Mapped[int] = mapped_column(BigInteger, default=0)
