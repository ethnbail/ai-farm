"""Explicit developer controls. No HTTP execution endpoint or real broker exists."""

import argparse
import json
from datetime import UTC, datetime, timedelta

from redis import Redis
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database.seed import seed_agents
from app.database.session import get_engine
from app.market_data.factory import get_provider
from app.market_data.mock import DEMO_TIME
from app.models import Agent, MarketState, Portfolio, Position
from app.services.paper_broker import PaperBroker, require_paper
from app.workers.engine import scan_agent


def demo_step(session, settings, stage, outcome):
    require_paper(settings)
    if not settings.enable_development_actions or settings.market_data_provider != "mock":
        raise ValueError(
            "Demo requires ENABLE_DEVELOPMENT_ACTIONS=true and MARKET_DATA_PROVIDER=mock"
        )
    agents = seed_agents(session, settings)
    state = session.get(MarketState, 1, with_for_update=True)
    if stage == "entry":
        if session.scalar(
            select(func.count()).select_from(Position).where(Position.status == "open")
        ):
            raise ValueError(
                "Demo entry refuses to reset fixtures while positions are open; "
                "finish the existing run"
            )
        state.tick, state.scenario = 0, "target"
        session.commit()
        for agent in agents:
            scan_agent(session, settings, agent.id, DEMO_TIME)
    else:
        state.tick, state.scenario = (1 if stage == "mark" else 2), outcome
        session.commit()
        now = DEMO_TIME + timedelta(seconds=state.tick * 15)
        provider = get_provider(session, settings, now)
        for agent in agents:
            PaperBroker(session, settings, provider, now).monitor(agent.id)
    return [
        {
            "agent": a.name,
            "equity": str(p.equity),
            "cash": str(p.cash_balance),
            "realized_pnl": str(p.realized_pnl),
            "unrealized_pnl": str(p.unrealized_pnl),
        }
        for a, p in session.execute(select(Agent, Portfolio).join(Portfolio).order_by(Agent.name))
    ]


def main():
    parser = argparse.ArgumentParser(description="AI Farm deterministic PAPER trading controls")
    parser.add_argument(
        "command", choices=["demo", "scan", "monitor", "research", "marketplace-fixture"]
    )
    parser.add_argument("--execute", action="store_true", help="Submit approved PAPER proposals")
    parser.add_argument(
        "--demo", action="store_true", help="Current-clock mock research; no paid AI"
    )
    parser.add_argument("--stage", choices=["entry", "mark", "exit", "full"], default="full")
    parser.add_argument("--outcome", choices=["target", "stop"], default="target")
    args = parser.parse_args()
    settings = get_settings()
    require_paper(settings)
    # Same distributed lease as the worker. Failure to obtain it executes nothing.
    with Redis.from_url(
        settings.redis_url.get_secret_value(), socket_timeout=3, socket_connect_timeout=3
    ) as redis:
        with redis.lock("ai-farm:paper-engine", timeout=120, blocking_timeout=2) as lease:
            with Session(get_engine()) as session:
                if args.command == "research":
                    from app.workers.intelligence import run_intelligence

                    if args.demo:
                        if not settings.enable_development_actions:
                            raise ValueError("Mock demo requires ENABLE_DEVELOPMENT_ACTIONS=true")
                        settings = settings.model_copy(
                            update={
                                "market_data_provider": "mock",
                                "ai_enabled": False,
                                "regular_hours_only": False,
                            }
                        )
                    for agent in seed_agents(session, settings):
                        candidates = run_intelligence(
                            session,
                            settings,
                            agent.id,
                            execute=args.execute,
                            execution_guard=lease.owned,
                        )
                        print(
                            json.dumps(
                                {
                                    "agent": agent.name,
                                    "candidates": len(candidates),
                                    "paper_execution_requested": args.execute,
                                }
                            )
                        )
                elif args.command == "marketplace-fixture":
                    if not settings.enable_development_actions:
                        raise ValueError("Fixture import requires ENABLE_DEVELOPMENT_ACTIONS=true")
                    from app.services.marketplace import fixture_connector, import_listings

                    print(
                        json.dumps({"imported": len(import_listings(session, fixture_connector()))})
                    )
                elif args.command == "demo":
                    for stage in (
                        ["entry", "mark", "exit"] if args.stage == "full" else [args.stage]
                    ):
                        print(
                            json.dumps(
                                {
                                    "stage": stage,
                                    "clock": "MOCK SIMULATION",
                                    "accounts": demo_step(session, settings, stage, args.outcome),
                                }
                            )
                        )
                else:
                    now = datetime.now(UTC)
                    for agent in session.scalars(select(Agent).order_by(Agent.name)).all():
                        if args.command == "scan":
                            results = scan_agent(session, settings, agent.id, now)
                        else:
                            results = PaperBroker(
                                session, settings, get_provider(session, settings, now), now
                            ).monitor(agent.id)
                        print(
                            json.dumps(
                                {
                                    "agent": agent.name,
                                    "results": [r.model_dump(mode="json") for r in results],
                                }
                            )
                        )


if __name__ == "__main__":
    main()
