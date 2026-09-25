import asyncio
import json
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from alembic import command
from pydantic import ValidationError
from sqlalchemy import func, inspect, select
from sqlalchemy.exc import OperationalError

from app.core.config import Settings, get_settings
from app.database.seed import seed_agents
from app.models import Trade
from app.services.events import heartbeat_stream


def test_seed_is_idempotent_and_preserves_existing_balances(session):
    agents = seed_agents(session, get_settings())
    assert [(a.name, a.agent_type, a.current_balance) for a in agents] == [
        ("Agent A", "equities", Decimal("1000.00")),
        ("Agent B", "options", Decimal("1000.00")),
    ]
    agents[0].current_balance = Decimal("1050.00")
    agents[0].status = "paused"
    session.commit()
    again = seed_agents(session, get_settings())
    assert len(again) == 2
    assert again[0].current_balance == Decimal("1050.00")
    assert again[0].status == "paused"
    assert session.scalar(select(func.count()).select_from(Trade)) == 0


def test_configurable_seed_balance(session):
    settings = Settings(_env_file=None, agent_a_starting_balance="2500.25")
    agents = seed_agents(session, settings)
    assert agents[0].starting_balance == Decimal("2500.25")


def test_agents_and_empty_details(client, session):
    seed_agents(session, get_settings())
    response = client.get("/api/agents")
    assert response.status_code == 200
    agents = response.json()
    assert [a["name"] for a in agents] == ["Agent A", "Agent B"]
    for agent in agents:
        assert agent["current_balance"] == "1000.00"
        assert agent["total_return_percent"] == "0.00"
        assert agent["total_trades"] == agent["open_trades"] == agent["completed_trades"] == 0
        assert client.get(f"/api/agents/{agent['id']}").json() == agent
        assert client.get(f"/api/agents/{agent['id']}/trades").json() == []


def test_summary_counts_and_decimal_return(client, session):
    agent = seed_agents(session, get_settings())[0]
    agent.current_balance = Decimal("1012.34")
    # Test fixtures only, never development seed data or trading logic.
    for status in ("open", "closed"):
        session.add(
            Trade(
                agent_id=agent.id,
                asset_type="equity",
                symbol="TEST",
                company_name="Test fixture",
                side="buy",
                quantity=Decimal("1"),
                entry_price=Decimal("10.1234"),
                status=status,
                entry_time=datetime.now(UTC),
            )
        )
    session.commit()
    summary = client.get(f"/api/agents/{agent.id}").json()
    assert summary["total_trades"] == 2
    assert summary["open_trades"] == summary["completed_trades"] == 1
    assert summary["total_return"] == "12.34"
    assert summary["total_return_percent"] == "1.23"
    trades = client.get(f"/api/agents/{agent.id}/trades?limit=1&offset=1").json()
    assert len(trades) == 1
    assert trades[0]["entry_price"] == "10.1234"


@pytest.mark.parametrize(
    "path",
    [
        "/api/agents/not-a-uuid",
        "/api/agents/not-a-uuid/trades",
        f"/api/agents/{uuid4()}/trades?limit=101",
        f"/api/agents/{uuid4()}/trades?offset=-1",
    ],
)
def test_invalid_inputs(client, path):
    assert client.get(path).status_code == 422


def test_missing_agent(client):
    for suffix in ("", "/trades"):
        assert client.get(f"/api/agents/{uuid4()}{suffix}").status_code == 404


def test_no_write_endpoints(client):
    assert client.post("/api/agents", json={"name": "unexpected"}).status_code == 405


def test_health_and_service_failure(client, monkeypatch):
    assert client.get("/health").json() == {
        "status": "ok",
        "backend": "ok",
        "database": "ok",
        "redis": "ok",
    }
    monkeypatch.setattr("app.services.health.check_database", lambda: False)
    response = client.get("/health")
    assert response.status_code == 503
    assert response.json()["database"] == "unavailable"
    monkeypatch.setattr("app.services.health.check_redis", lambda: False)
    assert client.get("/health").json()["redis"] == "unavailable"


def test_database_errors_do_not_leak_secrets(client, monkeypatch):
    def fail(*args):
        raise OperationalError("SELECT secret", {}, Exception("private_password"))

    monkeypatch.setattr("app.api.routes.summarize_agents", fail)
    response = client.get("/api/agents")
    assert response.status_code == 503
    assert response.json() == {"detail": "Database temporarily unavailable"}


def test_cors_is_limited_to_local_development(client):
    good = client.get("/health", headers={"Origin": "http://localhost:3000"})
    assert good.headers["access-control-allow-origin"] == "http://localhost:3000"
    bad = client.get("/health", headers={"Origin": "https://untrusted.example"})
    assert "access-control-allow-origin" not in bad.headers


def test_inactive_services_and_no_secrets(client):
    marketplace = client.get("/api/marketplace").json()
    assert marketplace["opportunities_found"] == 0
    assert marketplace["zip_code"] is None
    usage = client.get("/api/ai-usage").json()
    assert usage["status"] == "disabled"
    assert usage["model_calls"] is None
    assert usage["amount_used_usd"] is None
    assert "openai_api_key" not in usage


def test_migration_round_trip_and_model_parity(database):
    engine, config = database
    assert set(inspect(engine).get_table_names()) == {
        "agents",
        "trades",
        "marketplace_opportunities",
        "system_events",
        "alembic_version",
        "portfolios",
        "positions",
        "orders",
        "fills",
        "option_contract_snapshots",
        "risk_events",
        "performance_snapshots",
        "benchmarks",
        "market_state",
        "event_counter",
    }
    command.check(config)
    command.downgrade(config, "base")
    assert inspect(engine).get_table_names() == ["alembic_version"]
    command.upgrade(config, "head")
    command.check(config)


def test_heartbeat_has_valid_event_envelope_and_can_disconnect():
    async def read():
        stream = heartbeat_stream(1)
        assert await anext(stream) == "retry: 3000\n\n"
        frame = await anext(stream)
        await stream.aclose()
        return frame

    frame = asyncio.run(read())
    assert "event: heartbeat\n" in frame
    event = json.loads(next(line[6:] for line in frame.splitlines() if line.startswith("data: ")))
    assert event["event_type"] == "heartbeat"
    assert event["payload"] == {"status": "alive"}
    assert event["source"] == "backend"
    assert event["id"]
    assert datetime.fromisoformat(event["created_at"]).tzinfo is not None


def test_settings_validation_and_optional_future_keys():
    assert Settings(_env_file=None, ai_monthly_budget_usd="").ai_monthly_budget_usd is None
    with pytest.raises(ValidationError):
        Settings(_env_file=None, agent_a_starting_balance="-1")
    with pytest.raises(ValidationError):
        Settings(_env_file=None, cors_origins=["*"])
