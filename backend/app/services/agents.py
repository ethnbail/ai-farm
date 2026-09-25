from decimal import Decimal

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.models import Agent, Trade
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
                status=agent.status,
                created_at=agent.created_at,
            )
        )
    return summaries
