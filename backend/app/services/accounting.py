from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.market_data.types import DataUnavailable, MarketDataProvider
from app.models import Agent, Benchmark, PerformanceSnapshot, Portfolio, Position, Trade
from app.services.market_hours import NEW_YORK

ZERO = Decimal("0")


def money(value: Decimal) -> Decimal:
    return value.quantize(Decimal(".01"), rounding=ROUND_HALF_UP)


def price(value: Decimal) -> Decimal:
    return value.quantize(Decimal(".0001"), rounding=ROUND_HALF_UP)


def percent(numerator: Decimal, denominator: Decimal) -> Decimal:
    return (numerator / denominator * 100).quantize(Decimal(".0001")) if denominator else ZERO


def ensure_portfolio(session: Session, agent: Agent) -> Portfolio:
    portfolio = session.scalar(select(Portfolio).where(Portfolio.agent_id == agent.id))
    if portfolio is None:
        portfolio = Portfolio(
            agent_id=agent.id,
            starting_balance=agent.starting_balance,
            cash_balance=agent.current_balance,
            equity=agent.current_balance,
            high_water_mark=max(agent.starting_balance, agent.current_balance),
            day_start_equity=agent.current_balance,
            week_start_equity=agent.current_balance,
            realized_pnl=ZERO,
            unrealized_pnl=ZERO,
            market_value=ZERO,
            total_return_percent=percent(
                agent.current_balance - agent.starting_balance, agent.starting_balance
            ),
        )
        session.add(portfolio)
        session.flush()
    return portfolio


def open_positions(session: Session, portfolio: Portfolio) -> list[Position]:
    return list(
        session.scalars(
            select(Position)
            .where(Position.portfolio_id == portfolio.id, Position.status == "open")
            .order_by(Position.opened_at, Position.id)
        )
    )


def roll_periods(portfolio: Portfolio, now: datetime) -> None:
    day = now.astimezone(NEW_YORK).date()
    week = day - timedelta(days=day.weekday())
    if portfolio.day != day:
        portfolio.day, portfolio.day_start_equity = day, portfolio.equity
    if portfolio.week != week:
        portfolio.week, portfolio.week_start_equity = week, portfolio.equity


def recalculate(session: Session, portfolio: Portfolio, now: datetime) -> None:
    session.flush()
    positions = open_positions(session, portfolio)
    portfolio.market_value = money(sum((p.market_value for p in positions), ZERO))
    portfolio.unrealized_pnl = money(sum((p.unrealized_pnl for p in positions), ZERO))
    portfolio.equity = money(portfolio.cash_balance + portfolio.market_value)
    portfolio.total_return_percent = percent(
        portfolio.equity - portfolio.starting_balance, portfolio.starting_balance
    )
    portfolio.high_water_mark = max(portfolio.high_water_mark, portfolio.equity)
    drawdown = percent(portfolio.high_water_mark - portfolio.equity, portfolio.high_water_mark)
    portfolio.max_drawdown_percent = max(portfolio.max_drawdown_percent, drawdown)
    portfolio.updated_at = now
    agent = session.get(Agent, portfolio.agent_id)
    agent.current_balance = portfolio.equity  # Compatibility with Phase 1 API.


def mark_portfolio(
    session: Session,
    portfolio: Portfolio,
    provider: MarketDataProvider,
    now: datetime,
    max_age: int,
    snapshot: bool = False,
) -> bool:
    roll_periods(portfolio, now)  # Capture previous equity before the new day's first mark.
    fresh = True
    states = []
    for position in open_positions(session, portfolio):
        try:
            quote = provider.quote(position.symbol, position.asset_type)
            trade = session.get(Trade, position.trade_id)
            if trade.market_data_mode and trade.market_data_mode != quote.mode:
                raise DataUnavailable("Cannot revalue a position with a different data source mode")
            state = quote.data_state(now, max_age)
            position.data_state = state
            if state == "stale":
                fresh = False
            else:
                position.current_price = quote.bid  # Conservative liquidation mark, not last.
                position.bid, position.ask = quote.bid, quote.ask
                position.data_timestamp = quote.timestamp
                position.market_value = money(
                    quote.bid * position.quantity * position.contract_multiplier
                )
                position.unrealized_pnl = money(position.market_value - position.cost_basis)
            states.append(state)
        except DataUnavailable:
            position.data_state = "unavailable"
            states.append("unavailable")
            fresh = False  # Preserve last known value; never mark missing quotes to zero.
    portfolio.valuation_state = (
        "unavailable"
        if "unavailable" in states
        else "stale"
        if "stale" in states
        else "mock"
        if not states or "mock" in states
        else "live"
    )
    recalculate(session, portfolio, now)
    if snapshot:
        session.add(
            PerformanceSnapshot(
                portfolio_id=portfolio.id,
                equity=portfolio.equity,
                cash=portfolio.cash_balance,
                market_value=portfolio.market_value,
                realized_pnl=portfolio.realized_pnl,
                unrealized_pnl=portfolio.unrealized_pnl,
                market_data_mode=portfolio.valuation_state,
                created_at=now,
            )
        )
        update_benchmark(session, portfolio, provider, now, max_age)
    return fresh


def update_benchmark(session, portfolio, provider, now, max_age):
    benchmark = session.scalar(select(Benchmark).where(Benchmark.portfolio_id == portfolio.id))
    agent = session.get(Agent, portfolio.agent_id)
    if benchmark is None:
        benchmark = Benchmark(
            portfolio_id=portfolio.id,
            name="SPY buy-and-hold"
            if agent.agent_type == "equities"
            else "Options baseline (not implemented)",
            data_state="unavailable",
            updated_at=now,
        )
        session.add(benchmark)
    if agent.agent_type == "equities":
        try:
            quote = provider.equity_quote("SPY")
            if benchmark.source_mode and benchmark.source_mode != quote.mode:
                raise DataUnavailable("Benchmark source-mode changed; matching period unavailable")
            benchmark.data_state = quote.data_state(now, max_age)
            if benchmark.data_state != "stale" and quote.last > 0:
                if benchmark.starting_price is None:
                    benchmark.started_at, benchmark.portfolio_equity_at_start = (
                        now,
                        portfolio.equity,
                    )
                benchmark.source_mode = benchmark.source_mode or quote.mode
                benchmark.high_water_price = max(
                    benchmark.high_water_price or quote.last, quote.last
                )
                benchmark.max_drawdown_percent = max(
                    benchmark.max_drawdown_percent or ZERO,
                    percent(benchmark.high_water_price - quote.last, benchmark.high_water_price),
                )
                benchmark.starting_price = benchmark.starting_price or quote.last
                benchmark.current_price = quote.last
                benchmark.equity = money(
                    portfolio.starting_balance * quote.last / benchmark.starting_price
                )
                benchmark.total_return_percent = percent(
                    quote.last - benchmark.starting_price, benchmark.starting_price
                )
        except DataUnavailable:
            benchmark.data_state = "unavailable"
    benchmark.updated_at = now
