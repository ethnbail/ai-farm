from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.market_data.types import effective_state
from app.models import Agent, Portfolio, Position, Trade
from app.schemas.dashboard import AgentSummary


def summarize_agents(session: Session, agent_id=None) -> list[AgentSummary]:
    counts = (
        select(
            Trade.agent_id,
            func.count().label("total"),
            func.sum(case((Trade.status == "open", 1), else_=0)).label("opened"),
            func.sum(case((Trade.status == "closed", 1), else_=0)).label("closed"),
        )
        .group_by(Trade.agent_id)
        .subquery()
    )
    statement = (
        select(Agent, counts.c.total, counts.c.opened, counts.c.closed)
        .outerjoin(counts, counts.c.agent_id == Agent.id)
        .order_by(Agent.name)
    )
    if agent_id is not None:
        statement = statement.where(Agent.id == agent_id)
    summaries = []
    for agent, total, opened, closed in session.execute(statement):
        change = agent.current_balance - agent.starting_balance
        positions = list(
            session.scalars(
                select(Position)
                .join(Portfolio)
                .where(Portfolio.agent_id == agent.id, Position.status == "open")
            )
        )
        states = [
            effective_state(
                p.data_state,
                p.data_timestamp,
                datetime.now(UTC),
                get_settings().quote_max_age_seconds,
            )
            for p in positions
        ]
        account = session.scalar(select(Portfolio).where(Portfolio.agent_id == agent.id))
        state = (
            "unavailable"
            if "unavailable" in states
            else (
                "stale"
                if "stale" in states
                else account.valuation_state
                if account
                else "unavailable"
            )
        )
        summaries.append(
            AgentSummary(
                id=agent.id,
                name=agent.name,
                agent_type=agent.agent_type,
                starting_balance=agent.starting_balance,
                current_balance=agent.current_balance,
                total_return=change,
                total_return_percent=(change / agent.starting_balance * 100).quantize(
                    Decimal("0.01")
                ),
                total_trades=total or 0,
                open_trades=opened or 0,
                completed_trades=closed or 0,
                open_positions=len(positions),
                valuation_state=state,
                status=agent.status,
                created_at=agent.created_at,
            )
        )
    return summaries
