"""Low-frequency, single-flight jobs coordinated through Redis; fail closed on Redis loss."""

import logging
import time
from datetime import UTC, datetime

from redis import Redis
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database.session import get_engine
from app.market_data.factory import get_provider
from app.models import Agent, MarketState
from app.services.paper_broker import PaperBroker, require_paper
from app.workers.engine import scan_agent

logger = logging.getLogger(__name__)


def run_pending(redis, settings, now):
    require_paper(settings)
    lock = redis.lock("ai-farm:paper-engine", timeout=120, blocking=False)
    if not lock.acquire(blocking=False):
        return
    try:
        jobs = [
            ("monitor", settings.position_monitor_interval_seconds),
            ("equities", settings.equity_scan_interval_seconds),
            ("options", settings.options_scan_interval_seconds),
        ]
        for job, interval in jobs:
            key = f"ai-farm:paper-next:{job}"
            if float(redis.get(key) or 0) > now.timestamp():
                continue
            with Session(get_engine()) as session:
                agents = list(session.scalars(select(Agent).order_by(Agent.name)))
                if job == "monitor":
                    if settings.market_data_provider == "mock":
                        state = session.get(MarketState, 1, with_for_update=True)
                        # Cyclic fixed fixtures; a scheduler restart does not reset their phase.
                        state.tick = (state.tick + 1) % 3
                        session.commit()
                    provider = get_provider(session, settings, now)
                    for agent in agents:
                        PaperBroker(session, settings, provider, now).monitor(agent.id)
                else:
                    for agent in agents:
                        if agent.agent_type == job:
                            scan_agent(session, settings, agent.id, now)
            redis.set(key, now.timestamp() + interval)
    finally:
        if lock.owned():
            lock.release()


def main():
    logging.basicConfig(level=logging.INFO)
    settings = get_settings()
    require_paper(settings)
    if not settings.paper_worker_enabled:
        logger.info(
            "Paper worker disabled. Set PAPER_WORKER_ENABLED=true "
            "to opt into scheduled mock trades."
        )
        return
    with Redis.from_url(
        settings.redis_url.get_secret_value(), socket_timeout=3, socket_connect_timeout=3
    ) as redis:
        while True:
            try:
                run_pending(redis, settings, datetime.now(UTC))
            except Exception:
                logger.exception("Paper job failed; no fallback execution path")
            time.sleep(2)


if __name__ == "__main__":
    main()
