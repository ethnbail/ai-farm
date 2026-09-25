import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal as D
from uuid import uuid4

import pytest
from alembic import command
from pydantic import ValidationError
from sqlalchemy import func, select, text

from app.agents.strategies import (
    DirectionalMomentumOptionsStrategy,
    OptionsScanner,
    TrendMomentumStrategy,
)
from app.core.config import Settings, get_settings
from app.database.seed import seed_agents
from app.market_data.factory import get_provider
from app.market_data.mock import DEMO_TIME, MockMarketDataProvider
from app.market_data.types import DataUnavailable
from app.models import Fill, Order, Portfolio, Position, RiskEvent, SystemEvent, Trade
from app.schemas.trading import OrderRequest
from app.services.event_store import emit, events_after
from app.services.events import live_stream
from app.services.market_hours import market_status
from app.services.paper_broker import PaperBroker, PaperModeError
from app.services.performance import performance
from app.workers.cli import demo_step
from app.workers.scheduler import run_pending


@pytest.fixture
def accounts(session):
    return seed_agents(session, get_settings())


def portfolio(session, agent):
    return session.scalar(select(Portfolio).where(Portfolio.agent_id == agent.id))


def stock(agent, **overrides):
    return OrderRequest(
        **{
            **dict(
                agent_id=agent.id,
                action="BUY",
                asset_type="equity",
                symbol="NVDA",
                stop_loss="98",
                take_profit="104",
                quantity=1,
            ),
            **overrides,
        }
    )


def option(agent, provider=None, **overrides):
    provider = provider or MockMarketDataProvider()
    quote = provider.option_chain("FARM")[0]
    return OrderRequest(
        **{
            **dict(
                agent_id=agent.id,
                action="BUY_TO_OPEN",
                asset_type="option",
                symbol=quote.symbol,
                stop_loss=".098",
                take_profit=".225",
                quantity=1,
            ),
            **overrides,
        }
    )


def broker(session, provider=None, settings=None, now=DEMO_TIME):
    return PaperBroker(
        session, settings or get_settings(), provider or MockMarketDataProvider(now=now), now
    )


def test_portfolio_seed_and_isolation(session, accounts):
    a, b = accounts
    pa, pb = portfolio(session, a), portfolio(session, b)
    assert pa.id != pb.id
    assert pa.cash_balance == pb.cash_balance == D("1000.00")
    assert broker(session).execute(stock(a)).status == "filled"
    session.refresh(pb)
    assert pb.equity == pb.cash_balance == D("1000.00")
    assert broker(session).execute(option(b)).status == "filled"
    session.refresh(pa)
    assert pa.cash_balance == D("899.94")
    assert pa.equity == D("999.93")
    assert pb.cash_balance == D("984.85")
    assert pb.equity == D("998.85")
    assert session.scalar(select(func.count()).select_from(Fill)) == 2


def test_equity_fill_and_trade_snapshot(session, accounts):
    result = broker(session).execute(stock(accounts[0], requested_price="100"))
    trade = session.get(Trade, result.trade_id)
    fill = session.scalar(select(Fill).where(Fill.trade_id == trade.id))
    assert trade.entry_price == fill.price == D("100.0600")
    assert fill.price > fill.ask > fill.bid
    assert fill.estimated_slippage == D(".05")
    assert trade.position_size == D("100.06")
    assert trade.maximum_planned_loss == D("2.06")
    assert trade.account_equity_at_entry == D("1000")
    assert trade.entry_snapshot["mode"] == "mock"
    assert trade.risk_calculation["risk_basis"] == "entry_minus_stop"


@pytest.mark.parametrize("kind", ["CALL", "PUT"])
def test_option_fill_greeks_and_multiplier(session, accounts, kind):
    request = option(accounts[1])
    request = request.model_copy(update={"symbol": request.symbol.replace("CALL", kind)})
    result = broker(session).execute(request)
    trade = session.get(Trade, result.trade_id)
    assert trade.entry_price == D(".1515")
    assert trade.position_size == trade.maximum_planned_loss == D("15.15")
    assert trade.entry_snapshot["contract_multiplier"] == 100
    assert trade.entry_snapshot["option_type"] == kind
    assert all(
        trade.entry_snapshot[g] is not None for g in ["iv", "delta", "gamma", "theta", "vega"]
    )


@pytest.mark.parametrize(
    "is_option,outcome,expected",
    [
        (False, "target", "5.88"),
        (False, "stop", "-6.12"),
        (True, "target", "10.59"),
        (True, "stop", "-8.71"),
    ],
)
def test_full_lifecycle_stop_target_pnl(session, accounts, is_option, outcome, expected):
    agent = accounts[int(is_option)]
    result = broker(session).execute(option(agent) if is_option else stock(agent))
    t1 = DEMO_TIME + timedelta(seconds=15)
    broker(session, MockMarketDataProvider(1, outcome, t1), now=t1).monitor(agent.id)
    p = portfolio(session, agent)
    assert p.unrealized_pnl != 0
    assert p.equity == p.cash_balance + p.market_value
    t2 = DEMO_TIME + timedelta(seconds=30)
    broker(session, MockMarketDataProvider(2, outcome, t2), now=t2).monitor(agent.id)
    trade = session.get(Trade, result.trade_id)
    assert trade.status == "closed"
    assert trade.exit_reason == ("take_profit" if outcome == "target" else "stop_loss")
    assert trade.realized_pnl == D(expected)
    assert p.equity == p.cash_balance == D("1000") + D(expected)
    assert p.market_value == p.unrealized_pnl == 0
    assert p.realized_pnl == D(expected)
    events = [e.event_type for e in session.scalars(select(SystemEvent))]
    assert "trade_opened" in events and "trade_closed" in events
    assert f"{trade.exit_reason}_triggered" in events
    assert session.scalar(select(func.count()).select_from(Fill)) == 2


def test_compounding_and_seed_preservation(session, accounts):
    settings = Settings(_env_file=None, enable_development_actions=True)
    for _ in range(2):
        for stage in ["entry", "mark", "exit"]:
            demo_step(session, settings, stage, "target")
    # The first gain allows two shares under the 20% allocation cap on run two.
    assert portfolio(session, accounts[0]).equity == D("1017.63")
    assert portfolio(session, accounts[1]).equity == D("1021.18")
    seed_agents(session, settings)
    assert portfolio(session, accounts[0]).cash_balance == D("1017.63")


@pytest.mark.parametrize(
    "kind,outcome,pnl",
    [("CALL", "target", "2.85"), ("PUT", "target", "-15.15"), ("PUT", "stop", "2.85")],
)
def test_expiration_settles_intrinsic_without_margin(session, accounts, kind, outcome, pnl):
    request = option(accounts[1])
    request = request.model_copy(update={"symbol": request.symbol.replace("CALL", kind)})
    result = broker(session).execute(request)
    trade = session.get(Trade, result.trade_id)
    expiry = datetime.fromisoformat(trade.entry_snapshot["expiration"])
    now = expiry.replace(hour=20, tzinfo=UTC)
    broker(session, MockMarketDataProvider(2, outcome, now), now=now).monitor(accounts[1].id)
    session.refresh(trade)
    assert trade.status == "closed"
    assert trade.exit_reason == "expiration_cash_settlement"
    assert trade.realized_pnl == D(pnl)
    assert portfolio(session, accounts[1]).cash_balance == D("1000") + D(pnl)


def test_execution_failure_rolls_back_all_bookkeeping(session, accounts, monkeypatch):
    executor = broker(session)

    def fail(*args, **kwargs):
        raise RuntimeError("Simulated storage failure")

    monkeypatch.setattr(executor, "_fill", fail)
    with pytest.raises(RuntimeError, match="storage failure"):
        executor.execute(stock(accounts[0]))
    for model in [Order, Trade, Fill, Position, SystemEvent]:
        assert session.scalar(select(func.count()).select_from(model)) == 0
    assert portfolio(session, accounts[0]).cash_balance == D("1000")


def test_statistics_after_five_closed_trades(session, accounts):
    for outcome in ["target", "stop", "target", "stop", "target"]:
        assert broker(session).execute(stock(accounts[0])).status == "filled"
        now = DEMO_TIME + timedelta(seconds=30)
        broker(session, MockMarketDataProvider(2, outcome, now), now=now).monitor(accounts[0].id)
    metrics = performance(session, portfolio(session, accounts[0]))
    assert metrics["win_rate"] == D("60")
    assert metrics["average_winner"] == D("5.88")
    assert metrics["average_loser"] == D("-6.12")
    assert metrics["expectancy"] == D("1.08")
    assert metrics["profit_factor"] == D("1.4412")
    assert metrics["statistics_note"] is None


@pytest.mark.parametrize(
    "field,value", [("iv", D("4")), ("gamma", D("-.01")), ("theta", D("-.05")), ("delta", None)]
)
def test_options_scanner_rejects_invalid_greek_profile(field, value):
    class Altered(MockMarketDataProvider):
        def option_chain(self, underlying):
            return [q.model_copy(update={field: value}) for q in super().option_chain(underlying)]

    assert OptionsScanner(Altered(), get_settings()).candidates("FARM", "CALL", DEMO_TIME) == []


@pytest.mark.parametrize(
    "change,fragment",
    [
        ({"quantity": 20}, "buying power"),
        ({"quantity": 3}, "allocation"),
        ({"stop_loss": "50"}, "risk per trade"),
        ({"stop_loss": "101"}, "stop below"),
    ],
)
def test_hard_risk_rejections(session, accounts, change, fragment):
    result = broker(session).execute(stock(accounts[0], **change))
    assert result.status == "rejected" and fragment in result.reason
    assert portfolio(session, accounts[0]).cash_balance == D("1000")
    assert session.scalar(select(func.count()).select_from(Fill)) == 0
    assert session.scalar(select(func.count()).select_from(RiskEvent)) == 1


def test_unaffordable_contract_and_auto_size_reject(session, accounts):
    quote = MockMarketDataProvider().option_chain("SPY")[0]
    result = broker(session).execute(
        option(accounts[1], symbol=quote.symbol, quantity=None, stop_loss="4", take_profit="10")
    )
    assert result.status == "rejected" and "NO_TRADE" in result.reason
    assert portfolio(session, accounts[1]).cash_balance == D("1000")


@pytest.mark.parametrize(
    "limit,value,fragment",
    [
        ("max_daily_loss_percent", "5", "daily_loss"),
        ("max_weekly_loss_percent", "10", "weekly_loss"),
        ("max_total_exposure_percent", "5", "exposure"),
        ("min_cash_reserve_percent", "95", "reserve"),
        ("max_option_premium_at_risk_percent", "1", "premium"),
    ],
)
def test_portfolio_limits(session, accounts, limit, value, fragment):
    p = portfolio(session, accounts[0])
    from app.services.accounting import roll_periods

    roll_periods(p, DEMO_TIME)
    if limit == "max_daily_loss_percent":
        p.day_start_equity = D("1100")
    if limit == "max_weekly_loss_percent":
        p.week_start_equity = D("1200")
    session.commit()
    settings = get_settings().model_copy(update={limit: D(value)})
    request = option(accounts[1]) if "premium" in limit else stock(accounts[0])
    result = broker(session, settings=settings).execute(request)
    assert result.status == "rejected" and fragment in result.reason


def test_max_open_positions_and_duplicate_position(session, accounts):
    assert broker(session).execute(stock(accounts[0])).status == "filled"
    result = broker(
        session, settings=get_settings().model_copy(update={"max_open_positions": 1})
    ).execute(stock(accounts[0]))
    assert "Maximum open positions" in result.reason
    assert "already open" in broker(session).execute(stock(accounts[0])).reason


def test_max_options_positions(session, accounts):
    assert broker(session).execute(option(accounts[1])).status == "filled"
    request = option(accounts[1])
    request = request.model_copy(update={"symbol": request.symbol.replace("CALL", "PUT")})
    result = broker(
        session, settings=get_settings().model_copy(update={"max_options_positions": 1})
    ).execute(request)
    assert "Maximum options positions" in result.reason


def test_asset_isolation_and_uncovered_sell(session, accounts):
    assert broker(session).execute(option(accounts[0])).status == "rejected"
    assert broker(session).execute(stock(accounts[1])).status == "rejected"
    assert broker(session).execute(stock(accounts[0], action="SELL")).status == "rejected"
    trade = broker(session).execute(stock(accounts[0]))
    position = session.scalar(select(Position).where(Position.trade_id == trade.trade_id))
    result = broker(session).execute(stock(accounts[1], action="CLOSE", position_id=position.id))
    assert result.status == "rejected"
    assert position.status == "open"


def test_partial_closes_and_idempotency(session, accounts):
    settings = get_settings().model_copy(update={"max_position_size_percent": D("25")})
    request = stock(accounts[0], quantity=2)
    first = broker(session, settings=settings).execute(request)
    assert broker(session, settings=settings).execute(request) == first
    assert session.scalar(select(func.count()).select_from(Fill)) == 1
    for i in range(2):
        result = broker(session, settings=settings).execute(
            stock(accounts[0], action="SELL", quantity=1)
        )
        assert result.status == "filled"
    p = portfolio(session, accounts[0])
    assert p.cash_balance == D("999.76")
    assert session.get(Trade, first.trade_id).realized_pnl == D("-.24")
    assert p.realized_pnl == D("-.24")
    assert session.scalar(select(func.count()).select_from(Fill)) == 3
    with pytest.raises(ValueError, match="Idempotency"):
        broker(session).execute(request.model_copy(update={"quantity": 1}))


@pytest.mark.parametrize(
    "changes,fragment",
    [
        ({"volume": 0}, "liquidity"),
        ({"open_interest": 0}, "liquidity"),
        ({"ask": D(".20")}, "spread"),
        ({"expiration": DEMO_TIME.date()}, "DTE"),
        ({"expiration": DEMO_TIME.date() + timedelta(days=80)}, "DTE"),
        ({"timestamp": DEMO_TIME - timedelta(minutes=5)}, "Stale"),
    ],
)
def test_option_quote_rejections(session, accounts, changes, fragment):
    class Altered(MockMarketDataProvider):
        def option_quote(self, symbol):
            return super().option_quote(symbol).model_copy(update=changes)

    result = broker(session, Altered()).execute(option(accounts[1]))
    assert result.status == "rejected" and fragment in result.reason


def test_stale_marks_block_entries_and_preserve_value(session, accounts):
    broker(session).execute(stock(accounts[0]))
    p = portfolio(session, accounts[0])
    previous = p.market_value
    old = MockMarketDataProvider(now=DEMO_TIME - timedelta(minutes=2))
    broker(session, old).monitor(accounts[0].id)
    assert p.market_value == previous and p.valuation_state == "stale"
    assert broker(session, old).execute(stock(accounts[0])).status == "rejected"
    with pytest.raises(DataUnavailable):
        get_provider(
            session,
            get_settings().model_copy(update={"market_data_provider": "unimplemented"}),
            DEMO_TIME,
        )


@pytest.mark.parametrize(
    "now,expected",
    [
        (datetime(2026, 9, 24, 12, tzinfo=UTC), "pre_market"),
        (DEMO_TIME, "regular"),
        (datetime(2026, 9, 24, 21, tzinfo=UTC), "after_hours"),
        (datetime(2026, 9, 26, 14, tzinfo=UTC), "closed"),
        (datetime(2026, 12, 25, 15, tzinfo=UTC), "closed"),
        (datetime(2026, 11, 27, 19, tzinfo=UTC), "after_hours"),
        (datetime(2026, 1, 5, 14, tzinfo=UTC), "pre_market"),
        (datetime(2026, 7, 6, 14, tzinfo=UTC), "regular"),
    ],
)
def test_market_hours_dst_holidays_and_early_close(now, expected):
    assert market_status(now)["session"] == expected


def test_opening_hours_enforced(session, accounts):
    closed = datetime(2026, 9, 26, 14, tzinfo=UTC)
    assert "regular US market" in broker(session, now=closed).execute(stock(accounts[0])).reason
    settings = get_settings().model_copy(update={"regular_hours_only": False})
    assert (
        broker(session, settings=settings, now=closed).execute(stock(accounts[0])).status
        == "filled"
    )


def test_paper_only_and_input_validation(session, accounts, caplog):
    with pytest.raises(PaperModeError, match="paper only"):
        broker(
            session, settings=get_settings().model_copy(update={"trading_mode": "live"})
        ).execute(stock(accounts[0]))
    assert "Execution blocked" in caplog.text
    assert session.scalar(select(func.count()).select_from(Order)) == 0
    for field in [
        {"action": "SELL_TO_OPEN"},
        {"quantity": 1.5},
        {"risk_override": True},
        {"stop_loss": "NaN"},
    ]:
        with pytest.raises(ValidationError):
            stock(accounts[0], **field)


def test_strategies_and_scanner(session):
    settings = get_settings()
    assert (
        TrendMomentumStrategy(MockMarketDataProvider(), settings).evaluate("NVDA").action == "BUY"
    )
    assert (
        TrendMomentumStrategy(MockMarketDataProvider(scenario="stop"), settings)
        .evaluate("NVDA")
        .action
        == "SELL"
    )
    signal = DirectionalMomentumOptionsStrategy(
        MockMarketDataProvider(scenario="stop"), settings, DEMO_TIME
    ).evaluate("FARM")
    assert signal.quote.option_type == "PUT"
    strict = settings.model_copy(update={"min_option_volume": 1000})
    assert (
        OptionsScanner(MockMarketDataProvider(), strict).candidates("FARM", "CALL", DEMO_TIME) == []
    )


def test_performance_insufficient_sample_and_drawdown(session, accounts):
    settings = get_settings().model_copy(update={"enable_development_actions": True})
    for stage in ["entry", "exit"]:
        demo_step(session, settings, stage, "stop")
    metrics = performance(session, portfolio(session, accounts[0]))
    assert metrics["losing_trades"] == 1 and metrics["winning_trades"] == 0
    assert metrics["win_rate"] is metrics["expectancy"] is metrics["profit_factor"] is None
    assert metrics["max_drawdown_percent"] == D(".6120")
    assert metrics["worst_trade"] == D("-6.12")


def test_events_atomic_and_live_stream(session, database):
    emit(session, "portfolio_updated", "test", {"message": "committed"})
    session.commit()
    emit(session, "trade_opened", "test", {"message": "rolled back"})
    session.rollback()
    assert len(events_after(session, 0)) == 1

    async def read():
        stream = live_stream(5, 0)
        assert await anext(stream) == "retry: 3000\n\n"
        assert "id:" not in await anext(stream)
        event = await anext(stream)
        await stream.aclose()
        return event

    frame = asyncio.run(read())
    assert "event: portfolio_updated" in frame and "id: 1" in frame


def test_extended_read_api(client, session, accounts):
    result = broker(session).execute(option(accounts[1]))
    for route in ["portfolio", "positions", "performance"]:
        response = client.get(f"/api/agents/{accounts[1].id}/{route}")
        assert response.status_code == 200
    detail = client.get(f"/api/trades/{result.trade_id}").json()
    assert detail["entry_snapshot"]["option_type"] == "CALL"
    assert len(detail["fills"]) == 1 and detail["timeline"]
    assert client.get("/api/activity").json()
    assert client.get("/market/status").json()["data_state"] == "mock"
    assert client.get(f"/trades/{uuid4()}").status_code == 404
    assert client.post("/api/orders", json={}).status_code == 404


def test_read_api_labels_old_marks_stale_without_revaluing(client, session, accounts):
    result = broker(session).execute(stock(accounts[0]))
    position = session.scalar(select(Position).where(Position.trade_id == result.trade_id))
    position.data_timestamp = datetime.now(UTC) - timedelta(minutes=5)
    session.commit()
    identifier = accounts[0].id
    assert client.get(f"/api/agents/{identifier}").json()["valuation_state"] == "stale"
    assert client.get(f"/api/agents/{identifier}/portfolio").json()["valuation_state"] == "stale"
    assert client.get(f"/api/agents/{identifier}/positions").json()[0]["data_state"] == "stale"
    session.refresh(position)
    assert position.market_value == D("99.99") and position.data_state == "mock"


def test_scheduler_deduplicates_jobs_with_redis(session, accounts):
    class Lock:
        def acquire(self, **kwargs):
            return True

        def owned(self):
            return True

        def release(self):
            pass

    class Redis:
        values = {}

        def lock(self, *args, **kwargs):
            return Lock()

        def get(self, key):
            return self.values.get(key)

        def set(self, key, value):
            self.values[key] = value

    redis = Redis()
    run_pending(redis, get_settings(), DEMO_TIME)
    orders = session.scalar(select(func.count()).select_from(Order))
    run_pending(redis, get_settings(), DEMO_TIME)
    assert session.scalar(select(func.count()).select_from(Order)) == orders
    assert len(redis.values) == 3


def test_forward_migration_preserves_phase1_data(database):
    engine, config = database
    command.downgrade(config, "0001")
    identifier = uuid4().hex
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO agents (id,name,agent_type,starting_balance,current_balance,status) "
                "VALUES (:id,'Legacy','equities',1000,1050,'idle')"
            ),
            {"id": identifier},
        )
    command.upgrade(config, "head")
    with engine.connect() as connection:
        assert (
            connection.scalar(text("SELECT current_balance FROM agents WHERE name='Legacy'"))
            == 1050
        )
        assert connection.scalar(text("SELECT cash_balance FROM portfolios")) == 1050
