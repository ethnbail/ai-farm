"""Deterministic orchestration; strategies propose and the broker always applies risk."""

from datetime import datetime

from sqlalchemy import select

from app.agents.strategies import DirectionalMomentumOptionsStrategy, TrendMomentumStrategy
from app.market_data.factory import get_provider
from app.market_data.types import DataUnavailable
from app.models import Agent
from app.schemas.trading import OrderRequest
from app.services.event_store import emit
from app.services.market_hours import market_status
from app.services.paper_broker import PaperBroker, require_paper


def scan_agent(session, settings, agent_id, now: datetime):
    require_paper(settings)
    agent = session.get(Agent, agent_id)
    if agent.status in {"paused", "error"}:
        return []
    if settings.regular_hours_only and market_status(now)["session"] != "regular":
        agent.status = "idle"
        emit(
            session,
            "agent_status_changed",
            str(agent.id),
            {"agent_id": str(agent.id), "message": f"{agent.name}: market closed"},
        )
        session.commit()
        return []
    try:
        provider = get_provider(session, settings, now)
    except DataUnavailable as error:
        emit(
            session,
            "agent_status_changed",
            str(agent.id),
            {"agent_id": str(agent.id), "message": str(error)},
        )
        session.commit()
        return []
    agent.status = "running"
    emit(
        session,
        "agent_status_changed",
        str(agent.id),
        {"agent_id": str(agent.id), "message": f"{agent.name} scanning mock market"},
    )
    session.commit()
    strategy = (
        TrendMomentumStrategy(provider, settings)
        if agent.agent_type == "equities"
        else DirectionalMomentumOptionsStrategy(provider, settings, now)
    )
    symbols = ["NVDA"] if agent.agent_type == "equities" else ["SPY", "FARM"]
    results = []
    for symbol in symbols:
        signal = strategy.evaluate(symbol)
        if signal.action == "BUY":
            results.append(
                PaperBroker(session, settings, provider, now).execute(
                    OrderRequest(
                        agent_id=agent.id,
                        symbol=signal.quote.symbol,
                        asset_type=signal.quote.asset_type,
                        action="BUY" if agent.agent_type == "equities" else "BUY_TO_OPEN",
                        requested_price=signal.proposed_entry,
                        stop_loss=signal.stop_loss,
                        take_profit=signal.target,
                        reasoning=signal.reason,
                        strategy_name=strategy.name,
                        strategy_version=strategy.version,
                    )
                )
            )
        elif signal.action == "SELL" and agent.agent_type == "equities":
            from app.models import Portfolio, Position

            owned = session.scalar(
                select(Position)
                .join(Portfolio)
                .where(
                    Portfolio.agent_id == agent.id,
                    Position.symbol == symbol,
                    Position.status == "open",
                )
            )
            if owned:
                results.append(
                    PaperBroker(session, settings, provider, now).execute(
                        OrderRequest(
                            agent_id=agent.id,
                            symbol=symbol,
                            asset_type=owned.asset_type,
                            action="SELL",
                            position_id=owned.id,
                            reasoning=signal.reason,
                            strategy_name=strategy.name,
                            strategy_version=strategy.version,
                        ),
                        exit_reason="strategy_signal",
                    )
                )
        else:
            emit(
                session,
                "agent_status_changed",
                str(agent.id),
                {"agent_id": str(agent.id), "message": signal.reason},
            )
            session.commit()
    agent.status = "idle"
    emit(
        session,
        "agent_status_changed",
        str(agent.id),
        {"agent_id": str(agent.id), "message": f"{agent.name} scan complete"},
    )
    session.commit()
    return results
