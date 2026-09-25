"""Run explicitly with python -m app.database.seed after migrations."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.database.session import get_engine
from app.models import Agent


def seed_agents(session: Session, settings: Settings) -> list[Agent]:
    """Add missing agents only; never reset balances, status, or trade history."""
    for name, agent_type, balance in (
        ("Agent A", "equities", settings.agent_a_starting_balance),
        ("Agent B", "options", settings.agent_b_starting_balance),
    ):
        if session.scalar(select(Agent).where(Agent.name == name)) is None:
            session.add(
                Agent(
                    name=name,
                    agent_type=agent_type,
                    starting_balance=balance,
                    current_balance=balance,
                    status="idle",
                )
            )
    session.commit()
    return list(session.scalars(select(Agent).order_by(Agent.name)))


def main() -> None:
    with Session(get_engine()) as session:
        for agent in seed_agents(session, get_settings()):
            print(f"{agent.name}: {agent.agent_type}, paper balance ${agent.current_balance:.2f}")


if __name__ == "__main__":
    main()
