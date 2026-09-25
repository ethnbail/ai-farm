from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from app.api.routes import DbSession
from app.core.config import get_settings
from app.market_data.factory import get_provider
from app.market_data.types import DataUnavailable, effective_state
from app.models import Benchmark, Fill, Portfolio, Position, SystemEvent, Trade
from app.services.accounting import percent
from app.services.market_hours import market_status
from app.services.performance import performance
from app.services.serialization import public

router = APIRouter(tags=["paper trading"])


def portfolio_for(session, agent_id):
    portfolio = session.scalar(select(Portfolio).where(Portfolio.agent_id == agent_id))
    if portfolio is None:
        raise HTTPException(404, "Portfolio not found; run development seed")
    return portfolio


@router.get("/agents/{agent_id}/portfolio")
def portfolio(agent_id: UUID, session: DbSession):
    account = portfolio_for(session, agent_id)
    states = [
        effective_state(
            p.data_state, p.data_timestamp, datetime.now(UTC), get_settings().quote_max_age_seconds
        )
        for p in session.scalars(
            select(Position).where(Position.portfolio_id == account.id, Position.status == "open")
        )
    ]
    state = (
        "unavailable"
        if "unavailable" in states
        else ("stale" if "stale" in states else account.valuation_state)
    )
    return {**public(account), "valuation_state": state}


@router.get("/agents/{agent_id}/positions")
def positions(agent_id: UUID, session: DbSession):
    account = portfolio_for(session, agent_id)
    positions = session.scalars(
        select(Position)
        .where(Position.portfolio_id == account.id, Position.status == "open")
        .order_by(Position.opened_at, Position.id)
    ).all()
    return [
        {
            **public(p),
            "data_state": effective_state(
                p.data_state,
                p.data_timestamp,
                datetime.now(UTC),
                get_settings().quote_max_age_seconds,
            ),
            "return_percent": str(percent(p.unrealized_pnl, p.cost_basis)),
            "dte": max(0, (p.expiration - datetime.now(UTC).date()).days) if p.expiration else None,
        }
        for p in positions
    ]


@router.get("/agents/{agent_id}/performance")
def performance_metrics(agent_id: UUID, session: DbSession):
    account = portfolio_for(session, agent_id)
    benchmark = session.scalar(select(Benchmark).where(Benchmark.portfolio_id == account.id))
    return public(
        {
            **performance(session, account, get_settings().minimum_performance_trades),
            "benchmark": benchmark,
        }
    )


@router.get("/trades/{trade_id}")
def trade_detail(trade_id: UUID, session: DbSession):
    trade = session.get(Trade, trade_id)
    if trade is None:
        raise HTTPException(404, "Trade not found")
    fills = session.scalars(
        select(Fill).where(Fill.trade_id == trade_id).order_by(Fill.timestamp, Fill.id)
    ).all()
    events = session.scalars(
        select(SystemEvent)
        .where(SystemEvent.payload["trade_id"].as_string() == str(trade_id))
        .order_by(SystemEvent.sequence)
    ).all()
    return {**public(trade), "fills": public(fills), "timeline": public(events)}


@router.get("/activity")
def activity(session: DbSession, limit: Annotated[int, Query(ge=1, le=100)] = 20):
    return public(
        session.scalars(
            select(SystemEvent)
            .order_by(SystemEvent.created_at.desc(), SystemEvent.sequence.desc())
            .limit(limit)
        ).all()
    )


@router.get("/market/status")
def market(session: DbSession):
    settings, now = get_settings(), datetime.now(UTC)
    try:
        quote = get_provider(session, settings, now).equity_quote("SPY")
        state = quote.data_state(now, settings.quote_max_age_seconds)
        stamp = quote.timestamp.isoformat()
    except DataUnavailable:
        state, stamp = "unavailable", None
    return {
        **market_status(now),
        "trading_mode": settings.trading_mode,
        "paper_only": True,
        "data_state": state,
        "provider": settings.market_data_provider,
        "data_timestamp": stamp,
        "worker_enabled": settings.paper_worker_enabled,
        "execution_enabled": settings.trading_mode == "paper" and state in {"mock", "live"},
    }
