"""Native PostgreSQL verification. Requires a NEW database named ai_farm_phase3_verify*.

Run from backend with PYTHONPATH=. and DATABASE_URL pointing at the disposable database.
Refuses nonempty databases; never resets, drops, truncates, or contacts paid providers.
"""

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from decimal import Decimal as D
from uuid import uuid4

from alembic import command
from alembic.config import Config
from redis import Redis
from sqlalchemy import MetaData, func, inspect, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database.seed import seed_agents
from app.database.session import get_engine
from app.market_data.mock import MockMarketDataProvider
from app.models import AIUsageRecord, ConfidenceRecord, Portfolio, Trade
from app.services.ai import AIBudgetManager
from app.services.marketplace import fixture_connector, import_listings
from app.services.paper_broker import PaperBroker
from app.workers.intelligence import run_intelligence


def main():
    engine, settings = get_engine(), get_settings()
    if engine.dialect.name != "postgresql" or not engine.url.database.startswith(
        "ai_farm_phase3_verify"
    ):
        raise ValueError("Use a NEW isolated ai_farm_phase3_verify* PostgreSQL database")
    if inspect(engine).get_table_names():
        raise ValueError("Verification refuses nonempty databases; choose a new name")
    config = Config("alembic.ini")
    command.upgrade(config, "0002")
    safe = settings.model_copy(
        update={
            "market_data_provider": "mock",
            "ai_enabled": False,
            "regular_hours_only": False,
            "agent_a_starting_balance": D(1000),
            "agent_b_starting_balance": D(1000),
        }
    )
    with Session(engine) as session:
        agents = seed_agents(session, safe)
        identifiers = [a.id for a in agents]
    metadata = MetaData()
    metadata.reflect(engine)
    with engine.connect() as conn:
        before = {
            name: sorted((tuple(map(str, row)) for row in conn.execute(select(table))), key=str)
            for name, table in metadata.tables.items()
            if name != "alembic_version"
        }
    command.upgrade(config, "head")
    with engine.connect() as conn:
        after = {
            name: sorted(
                (tuple(map(str, row)) for row in conn.execute(select(metadata.tables[name]))),
                key=str,
            )
            for name in before
        }
    assert before == after, "Forward migration changed Phase 2 data"
    command.check(config)
    with Redis.from_url(settings.redis_url.get_secret_value()) as redis:
        assert redis.ping()
    now = datetime.now(UTC)
    with Session(engine) as session:
        for identifier in identifiers:
            run_intelligence(session, safe, identifier, now, execute=True)
        assert session.scalar(select(func.count()).select_from(Trade)) >= 2
        for identifier in identifiers:
            PaperBroker(
                session,
                safe,
                MockMarketDataProvider(2, "target", now + timedelta(seconds=30)),
                now + timedelta(seconds=30),
            ).monitor(identifier)
        assert (
            session.scalar(
                select(func.count())
                .select_from(ConfidenceRecord)
                .where(ConfidenceRecord.outcome.is_not(None))
            )
            >= 2
        )
        assert len(import_listings(session, fixture_connector())) == 1
        assert session.scalar(select(func.count()).select_from(AIUsageRecord)) == 0
        accounts = [
            str(p.equity) for p in session.scalars(select(Portfolio).order_by(Portfolio.agent_id))
        ]
    # All ten connections compete for a single $0.003 reservation. No HTTP requests.
    priced = safe.model_copy(
        update={
            "ai_enabled": True,
            "openai_api_key": settings.openai_api_key,
            "ai_daily_budget_usd": D(".003"),
            "ai_monthly_budget_usd": D(".003"),
            "ai_model_prices": {"test-only": {"input": D(1), "output": D(2)}},
            "ai_priority_reserve_percent": D(0),
        }
    )
    from pydantic import SecretStr

    priced = priced.model_copy(update={"openai_api_key": SecretStr("fixture-not-a-key")})

    def reserve(_):
        with Session(engine) as session:
            return (
                AIBudgetManager(session, priced).reserve("test-only", "test", uuid4(), 1000, 1000)
                is not None
            )

    with ThreadPoolExecutor(max_workers=10) as pool:
        allowed = list(pool.map(reserve, range(10)))
    assert sum(allowed) == 1
    with Session(engine) as session:
        usage = AIBudgetManager(session, priced).usage()
        assert usage["daily_spend"] == D(".003") and usage["denied_calls"] == 9
    print(
        json.dumps(
            {
                "forward_migration_preserved_phase2": True,
                "metadata_parity": True,
                "redis": "ok",
                "agents_completed_intelligence": 2,
                "paper_equities": accounts,
                "concurrent_reservations": "1 approved / 9 denied",
                "paid_network_calls": 0,
            }
        )
    )


if __name__ == "__main__":
    main()
