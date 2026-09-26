import json
from datetime import timedelta
from decimal import Decimal as D
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import func, select

from app.core.config import Settings, get_settings
from app.database.seed import seed_agents
from app.market_data.factory import get_provider
from app.market_data.mock import DEMO_TIME, MockMarketDataProvider
from app.market_data.tradier import TradierMarketDataProvider
from app.market_data.types import Bar, DataUnavailable
from app.models import (
    AIAnalysis,
    AIUsageRecord,
    ConfidenceRecord,
    EventRisk,
    MarketplaceOutcome,
    OpportunityCandidate,
    OpportunityQueueItem,
    Portfolio,
    ShadowReview,
    Trade,
)
from app.schemas.intelligence import MarketplaceOutcomeInput, ShadowReviewOutput, TradeAnalysis
from app.schemas.trading import OrderRequest
from app.services.ai import AIBudgetManager, ModelRouter
from app.services.marketplace import fixture_connector, import_listings, record_outcome
from app.services.paper_broker import PaperBroker
from app.services.reliability import reliability
from app.services.research import MarketRegimeService, rank_contracts
from app.services.shadow import ShadowAgent
from app.workers.intelligence import deterministic_analysis, run_intelligence


@pytest.fixture
def accounts(session):
    return seed_agents(session, get_settings())


def ai_settings(**overrides):
    return Settings(
        _env_file=None,
        **{
            **dict(
                ai_enabled=True,
                openai_api_key="test-not-a-real-key",
                ai_monthly_budget_usd="10",
                ai_daily_budget_usd="1",
                ai_cheap_model="test-cheap",
                ai_reasoning_model="test-reasoning",
                ai_shadow_model="test-cheap",
                ai_model_prices={
                    "test-cheap": {"input": "1", "output": "2"},
                    "test-reasoning": {"input": "20", "output": "40"},
                },
            ),
            **overrides,
        },
    )


def tradier(settings=None, handler=None):
    return TradierMarketDataProvider(
        settings or Settings(_env_file=None, market_data_api_key="test-only"),
        DEMO_TIME,
        httpx.MockTransport(handler),
    )


def raw_quote(**changes):
    return {
        **dict(
            symbol="NVDA",
            description="Fixture",
            type="stock",
            bid="99.99",
            ask="100.01",
            last="100",
            volume=100000,
            bid_date=int(DEMO_TIME.timestamp() * 1000),
            ask_date=int(DEMO_TIME.timestamp() * 1000),
        ),
        **changes,
    }


def test_provider_fallback_without_key(session):
    provider = get_provider(
        session,
        Settings(_env_file=None, market_data_provider="tradier", market_data_api_key=""),
        DEMO_TIME,
    )
    assert isinstance(provider, MockMarketDataProvider)
    assert provider.equity_quote("NVDA").mode == "mock"


def test_tradier_normalization_is_read_only():
    seen = []

    def handler(request):
        seen.append((request.method, request.url.path))
        return httpx.Response(200, json={"quotes": {"quote": raw_quote()}})

    provider = tradier(handler=handler)
    q = provider.equity_quote("NVDA")
    assert q.mode == "live" and q.bid == D("99.99") and q.timestamp == DEMO_TIME
    assert seen == [("GET", "/v1/markets/quotes")]
    with pytest.raises(DataUnavailable):
        provider._get("accounts/orders")


@pytest.mark.parametrize("response", [401, 429, 500])
def test_provider_http_failures_do_not_leak_keys(response):
    provider = tradier(handler=lambda request: httpx.Response(response, text="sensitive-payload"))
    with pytest.raises(DataUnavailable) as caught:
        provider.equity_quote("NVDA")
    assert "sensitive" not in str(caught.value) and "test-only" not in str(caught.value)


def test_provider_retries_timeout_and_limits_requests():
    calls = []

    def handler(request):
        calls.append(request)
        if len(calls) == 1:
            raise httpx.ReadTimeout("private", request=request)
        return httpx.Response(200, json={"quotes": {"quote": raw_quote()}})

    provider = tradier(handler=handler)
    assert provider.equity_quote("NVDA").mode == "live" and len(calls) == 2
    provider.requests = provider.settings.market_max_requests_per_scan
    with pytest.raises(DataUnavailable):
        provider.equity_quote("SPY")


def test_provider_stale_and_malformed():
    stale = raw_quote(bid_date=int((DEMO_TIME - timedelta(minutes=5)).timestamp() * 1000))
    provider = tradier(
        handler=lambda request: httpx.Response(200, json={"quotes": {"quote": stale}})
    )
    assert provider.equity_quote("NVDA").data_state(DEMO_TIME, 60) == "stale"
    malformed = tradier(
        handler=lambda request: httpx.Response(200, json={"quotes": {"quote": raw_quote(ask=None)}})
    )
    with pytest.raises(DataUnavailable):
        malformed.equity_quote("NVDA")


def test_tradier_option_chain_normalizes_greeks():
    symbol = "NVDA261016C00100000"

    def handler(request):
        if request.url.path.endswith("expirations"):
            return httpx.Response(200, json={"expirations": {"date": ["2026-10-16"]}})
        if request.url.path.endswith("chains"):
            return httpx.Response(
                200,
                json={
                    "options": {
                        "option": [
                            raw_quote(
                                symbol=symbol,
                                type="option",
                                underlying="NVDA",
                                strike="100",
                                expiration_date="2026-10-16",
                                option_type="call",
                                contract_size=100,
                                open_interest=1000,
                                greeks={
                                    "mid_iv": ".4",
                                    "delta": ".55",
                                    "gamma": ".02",
                                    "theta": "-.01",
                                    "vega": ".1",
                                    "updated_at": DEMO_TIME.isoformat(),
                                },
                            )
                        ]
                    }
                },
            )
        return httpx.Response(200, json={"quotes": {"quote": raw_quote()}})

    q = tradier(handler=handler).option_chain("NVDA")[0]
    assert q.symbol == symbol and q.delta == D(".55") and q.contract_multiplier == 100


@pytest.mark.parametrize("scenario,expected", [("target", "BULL_TREND"), ("stop", "BEAR_TREND")])
def test_regime_deterministic(session, scenario, expected):
    r = MarketRegimeService().detect(
        session, MockMarketDataProvider(scenario=scenario), get_settings(), DEMO_TIME
    )
    assert r.regime == expected and r.data_mode == "mock" and r.features["SPY"]["atr"]


def test_unknown_regime_on_missing_data(session):
    class Missing(MockMarketDataProvider):
        def equity_quote(self, symbol):
            raise DataUnavailable("Provider down")

    r = MarketRegimeService().detect(session, Missing(), get_settings(), DEMO_TIME)
    assert r.regime == "UNKNOWN" and r.data_mode == "unavailable"


def test_contract_ranking_retains_reasons():
    p = MockMarketDataProvider()
    rows = rank_contracts(
        p.option_chain("SPY") + p.option_chain("FARM"), get_settings(), DEMO_TIME, D(1000), "CALL"
    )
    assert rows[0]["quote"]["underlying_symbol"] == "FARM" and rows[0]["eligible"]
    assert any("full_premium_exceeds_risk" in r["rejection_reasons"] for r in rows)
    assert any("direction_mismatch" in r["rejection_reasons"] for r in rows)


@pytest.mark.parametrize("agent_index", [0, 1])
def test_full_intelligence_flow_paper_only(session, accounts, agent_index):
    candidates = run_intelligence(
        session, get_settings(), accounts[agent_index].id, DEMO_TIME, execute=True
    )
    assert candidates
    items = session.scalars(select(OpportunityQueueItem)).all()
    assert any(i.status == "EXECUTED" for i in items)
    assert session.scalar(select(func.count()).select_from(AIAnalysis)) >= 1
    assert session.scalar(select(func.count()).select_from(ShadowReview)) >= 1
    assert session.scalar(select(func.count()).select_from(AIUsageRecord)) == 0
    other = session.scalar(
        select(Portfolio).where(Portfolio.agent_id == accounts[1 - agent_index].id)
    )
    assert other.equity == D(1000)
    now = DEMO_TIME + timedelta(seconds=30)
    PaperBroker(session, get_settings(), MockMarketDataProvider(2, "target", now), now).monitor(
        accounts[agent_index].id
    )
    record = session.scalar(select(ConfidenceRecord).where(ConfidenceRecord.trade_id.is_not(None)))
    assert record.outcome is True and record.predicted_confidence is None
    assert reliability(session)["systems"][0]["win_rate"] is None


def test_final_risk_cannot_be_bypassed(session, accounts):
    settings = get_settings().model_copy(update={"max_risk_per_trade_percent": D(".01")})
    run_intelligence(session, settings, accounts[0].id, DEMO_TIME, execute=True)
    items = session.scalars(select(OpportunityQueueItem)).all()
    assert any(i.status == "RISK_REJECTED" for i in items)
    assert session.scalar(select(func.count()).select_from(Trade)) == 0


def test_event_risk_blocks_at_broker(session, accounts):
    session.add(
        EventRisk(
            symbol="NVDA",
            event_type="earnings",
            timestamp=DEMO_TIME + timedelta(minutes=5),
            importance="high",
            source="manual",
            warning="Test event",
        )
    )
    session.commit()
    run_intelligence(session, get_settings(), accounts[0].id, DEMO_TIME, execute=True)
    assert any(
        "event" in (i.rejection_reason or "").lower()
        for i in session.scalars(select(OpportunityQueueItem))
    )
    assert session.scalar(select(func.count()).select_from(Trade)) == 0


def test_shadow_has_no_execution_capability(session, accounts):
    candidates = run_intelligence(session, get_settings(), accounts[0].id, DEMO_TIME)
    candidate = next(c for c in candidates if c.eligible)
    analysis = deterministic_analysis(candidate).model_copy(update={"recommendation": "NO_TRADE"})
    review = ShadowAgent().review(candidate, analysis, {"status": "unavailable"})
    assert not review.approve_for_risk_review and not hasattr(ShadowAgent(), "execute")
    assert session.scalar(select(func.count()).select_from(Trade)) == 0


def test_budget_enforces_scan_daily_and_monthly_limits(session):
    settings = ai_settings(ai_max_calls_per_scan=1)
    manager = AIBudgetManager(session, settings)
    scan = uuid4()
    assert manager.reserve("test-cheap", "analysis", scan, 1000, 1000)
    assert manager.reserve("test-cheap", "shadow", scan, 1000, 1000) is None
    tiny = ai_settings(ai_daily_budget_usd=".001", ai_monthly_budget_usd=".001")
    assert (
        AIBudgetManager(session, tiny).reserve("test-cheap", "analysis", uuid4(), 1000, 1000)
        is None
    )
    assert manager.usage()["daily_spend"] == D(".003")
    assert manager.usage()["denied_calls"] == 2


def test_model_routing_downgrades_to_cheap(session, accounts):
    candidates = run_intelligence(session, get_settings(), accounts[0].id, DEMO_TIME)
    analysis = deterministic_analysis(next(c for c in candidates if c.eligible))

    def handler(request):
        body = json.loads(request.content)
        assert body["model"] == "test-cheap" and "tools" not in body
        assert body["text"]["format"]["strict"] is True
        return httpx.Response(
            200,
            json={
                "status": "completed",
                "output": [
                    {
                        "type": "message",
                        "content": [{"type": "output_text", "text": analysis.model_dump_json()}],
                    }
                ],
                "usage": {"input_tokens": 10, "output_tokens": 20},
            },
        )

    router = ModelRouter(
        session, ai_settings(ai_daily_budget_usd=".03"), httpx.MockTransport(handler)
    )
    result, model, status = router.analyze(
        TradeAnalysis, {"facts": "fixture"}, uuid4(), priority=True
    )
    assert result and model == "test-cheap" and status == "completed"


@pytest.mark.parametrize(
    "payload",
    [
        {"status": "incomplete"},
        {"status": "completed", "output": []},
        {
            "status": "completed",
            "output": [
                {"type": "message", "content": [{"type": "output_text", "text": "not json"}]}
            ],
        },
    ],
)
def test_malformed_ai_degrades_and_keeps_reservation(session, payload):
    router = ModelRouter(
        session, ai_settings(), httpx.MockTransport(lambda r: httpx.Response(200, json=payload))
    )
    result, model, status = router.analyze(TradeAnalysis, {}, uuid4())
    assert result is None and model == "deterministic" and status == "unavailable"
    assert AIBudgetManager(session, ai_settings()).usage()["daily_spend"] > 0


def test_ai_disabled_never_calls_network(session):
    def handler(request):
        raise AssertionError("Network should not run")

    router = ModelRouter(session, get_settings(), httpx.MockTransport(handler))
    assert router.analyze(ShadowReviewOutput, {}, uuid4())[2] == "disabled"


def test_marketplace_import_score_and_outcome(session):
    listing = import_listings(session, fixture_connector())[0]
    assert import_listings(session, fixture_connector())[0].id == listing.id
    outcome = record_outcome(
        session,
        listing.id,
        MarketplaceOutcomeInput(
            bought=True,
            acquisition_price="80",
            sale_price="150",
            fees="15",
            travel_cost="7",
            listing_date=DEMO_TIME,
            sale_date=DEMO_TIME + timedelta(days=10),
        ),
    )
    assert outcome.outcome["net_profit"] == "48.00" and outcome.outcome["days_to_sell"] == 10
    assert outcome.outcome["prediction"]["sell_through_probability"] is None
    assert session.scalar(select(func.count()).select_from(MarketplaceOutcome)) == 1


def test_intelligence_endpoints_and_watchlist_write_gate(client, session, accounts, monkeypatch):
    for endpoint in [
        f"agents/{accounts[0].id}/intelligence",
        "market/regime",
        "market/provider-status",
        "opportunities",
        "research",
        "ai/usage",
        "ai/status",
        "watchlists",
        "events/risk",
        "marketplace/opportunities",
        "reliability",
    ]:
        assert client.get("/api/" + endpoint).status_code == 200
    payload = dict(name="Test", agent_id=str(accounts[0].id), symbols=["qqq", "NVDA"])
    assert client.post("/api/watchlists", json=payload).status_code == 403
    monkeypatch.setenv("LOCAL_WRITES_ENABLED", "true")
    get_settings.cache_clear()
    response = client.post(
        "/api/watchlists", json=payload, headers={"Origin": "http://localhost:3000"}
    )
    assert response.status_code == 201 and response.json()["symbols"] == ["NVDA", "QQQ"]
    assert (
        client.delete(
            "/api/watchlists/" + response.json()["id"], headers={"Origin": "http://localhost:3000"}
        ).status_code
        == 204
    )
    candidates = run_intelligence(session, get_settings(), accounts[0].id, DEMO_TIME)
    detail = client.get("/api/research/" + str(candidates[0].id)).json()
    assert detail["analyses"] and detail["shadow_reviews"]
    listing = import_listings(session, fixture_connector())[0]
    assert client.get("/api/marketplace/opportunities/" + str(listing.id)).json()["analyses"]


def test_data_mode_switch_cannot_revalue_or_close(session, accounts):
    broker = PaperBroker(session, get_settings(), MockMarketDataProvider(), DEMO_TIME)
    request = OrderRequest(
        agent_id=accounts[0].id,
        symbol="NVDA",
        action="BUY",
        asset_type="equity",
        quantity=1,
        stop_loss=98,
        take_profit=104,
    )
    result = broker.execute(request)

    class Live(MockMarketDataProvider):
        def equity_quote(self, symbol):
            return super().equity_quote(symbol).model_copy(update={"mode": "live"})

    live = PaperBroker(session, get_settings(), Live(), DEMO_TIME)
    close = request.model_copy(update={"action": "SELL", "client_order_id": str(uuid4())})
    assert live.execute(close).status == "rejected"
    assert session.get(Trade, result.trade_id).status == "open"


@pytest.mark.parametrize("payload", [{"quotes": "bad"}, {"quotes": {"quote": [1, "bad"]}}])
def test_provider_malformed_containers_fail_closed(payload):
    with pytest.raises(DataUnavailable):
        tradier(handler=lambda r: httpx.Response(200, json=payload)).equity_quote("NVDA")


def test_rate_limit_prevents_further_requests():
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(429, headers={"Retry-After": "120"})

    provider = tradier(handler=handler)
    for _ in range(2):
        with pytest.raises(DataUnavailable):
            provider.equity_quote("NVDA")
    assert len(requests) == 1


@pytest.mark.parametrize("kind", ["monthly", "daily", "calls", "reserve"])
def test_each_budget_boundary_independently(session, kind):
    options = {
        "monthly": dict(ai_monthly_budget_usd=".002", ai_daily_budget_usd="10"),
        "daily": dict(ai_monthly_budget_usd="10", ai_daily_budget_usd=".002"),
        "calls": dict(ai_max_calls_per_day=1),
        "reserve": dict(ai_daily_budget_usd=".003", ai_priority_reserve_percent=10),
    }[kind]
    manager = AIBudgetManager(session, ai_settings(**options))
    if kind == "calls":
        assert manager.reserve("test-cheap", "analysis", uuid4(), 1000, 1000)
    assert manager.reserve("test-cheap", "analysis", uuid4(), 1000, 1000) is None
    if kind == "reserve":
        assert manager.reserve("test-cheap", "analysis", uuid4(), 1000, 1000, priority=True)


def test_unpriced_ai_cannot_send_request(session):
    router = ModelRouter(
        session,
        ai_settings(ai_model_prices={}),
        httpx.MockTransport(lambda _: pytest.fail("Unexpected paid request")),
    )
    assert router.analyze(TradeAnalysis, {}, uuid4())[2] == "budget_or_configuration_denied"
    assert AIBudgetManager(session, ai_settings()).usage()["daily_spend"] == 0


def test_stale_intelligence_and_lost_lease_never_execute(session, accounts):
    class Stale(MockMarketDataProvider):
        def equity_quote(self, symbol):
            return (
                super()
                .equity_quote(symbol)
                .model_copy(update={"timestamp": DEMO_TIME - timedelta(days=1)})
            )

    run_intelligence(
        session, get_settings(), accounts[0].id, DEMO_TIME, execute=True, provider=Stale()
    )
    assert session.scalar(select(func.count()).select_from(Trade)) == 0
    assert all(not c.eligible for c in session.scalars(select(OpportunityCandidate)))
    run_intelligence(
        session,
        get_settings(),
        accounts[0].id,
        DEMO_TIME,
        execute=True,
        execution_guard=lambda: False,
    )
    assert session.scalar(select(func.count()).select_from(Trade)) == 0
    assert any(
        i.rejection_reason == "Worker lease lost"
        for i in session.scalars(select(OpportunityQueueItem))
    )


def test_queue_supersedes_previous_scan(session, accounts):
    first = run_intelligence(session, get_settings(), accounts[0].id, DEMO_TIME)
    run_intelligence(session, get_settings(), accounts[0].id, DEMO_TIME + timedelta(minutes=6))
    items = session.scalars(
        select(OpportunityQueueItem).where(
            OpportunityQueueItem.candidate_id.in_([c.id for c in first])
        )
    ).all()
    assert all(i.status in {"EXPIRED", "DISMISSED"} for i in items)


def test_shadow_vetoes_opposite_option_direction(session, accounts):
    rows = run_intelligence(session, get_settings(), accounts[1].id, DEMO_TIME)
    candidate = next(c for c in rows if c.eligible)
    opposite = deterministic_analysis(candidate).model_copy(update={"recommendation": "PUT"})
    assert not ShadowAgent().review(candidate, opposite, {"status": "mock"}).approve_for_risk_review


@pytest.mark.parametrize(
    "change,reason",
    [
        ({"mode": "live", "greeks_timestamp": None}, "greeks_timestamp_unverified"),
        ({"volume": 0}, "poor_liquidity"),
        ({"bid": D(".001")}, "wide_spread"),
        ({"expiration": DEMO_TIME.date()}, "invalid_dte"),
        ({"iv": None}, "iv_missing_or_excessive"),
    ],
)
def test_contract_filters(change, reason):
    q = MockMarketDataProvider().option_chain("FARM")[0].model_copy(update=change)
    assert (
        reason
        in rank_contracts([q], get_settings(), DEMO_TIME, D(1000), "CALL")[0]["rejection_reasons"]
    )


def test_marketplace_rejects_naive_outcome_timestamps():
    with pytest.raises(ValueError):
        MarketplaceOutcomeInput(bought=False, listing_date="2026-09-24T12:00:00")


@pytest.mark.parametrize(
    "regime,width",
    [("LOW_VOLATILITY", ".1"), ("RANGE_BOUND", "1"), ("HIGH_VOLATILITY", "3"), ("RISK_OFF", "1")],
)
def test_remaining_regime_boundaries(session, regime, width):
    class Series(MockMarketDataProvider):
        def bars(self, symbol, count=30):
            values = [D(120 - i) if regime == "RISK_OFF" else D(100) for i in range(count)]
            return [
                Bar(
                    timestamp=DEMO_TIME - timedelta(days=count - i),
                    open=c,
                    close=c,
                    high=c + D(width),
                    low=c - D(width),
                    volume=10000,
                )
                for i, c in enumerate(values)
            ]

    assert (
        MarketRegimeService().detect(session, Series(), get_settings(), DEMO_TIME).regime == regime
    )


def test_live_context_does_not_consume_mock_events(session, accounts):
    from app.services.event_context import EventContextService

    session.add(
        EventRisk(
            symbol="NVDA",
            event_type="fixture",
            timestamp=DEMO_TIME,
            importance="high",
            source="mock",
            warning="Mock only",
        )
    )
    session.commit()
    settings = get_settings().model_copy(update={"event_data_provider": "mock"})
    service = EventContextService()
    assert service.blocked(session, settings, "NVDA", DEMO_TIME, "mock")
    assert service.context(session, settings, "NVDA", DEMO_TIME, "live")["risks"] == []
    required = settings.model_copy(update={"require_event_coverage": True})
    assert service.blocked(session, required, "NVDA", DEMO_TIME, "live")


def test_dashboard_latest_scan_keeps_both_agents(client, session, accounts):
    for agent in accounts:
        run_intelligence(session, get_settings(), agent.id, DEMO_TIME)
    response = client.get("/api/research?latest_scan=true&limit=6")
    assert response.status_code == 200
    rows = response.json()
    assert {r["agent_name"] for r in rows} == {"Agent A", "Agent B"}
    assert len(rows) <= 6
    for agent in accounts:
        selected = [r for r in rows if r["agent_id"] == str(agent.id)]
        assert len(selected) <= 3
        assert selected[0]["eligible"] is True


def test_reliability_waits_for_twenty_calibrated_outcomes(session, accounts):
    for i in range(20):
        candidate = OpportunityCandidate(
            scan_id=uuid4(),
            agent_id=accounts[0].id,
            symbol="NVDA",
            score=90,
            components={},
            regime="BULL_TREND",
            data_mode="mock",
            eligible=True,
            reasons=[],
            rejection_reasons=[],
            snapshot={},
            proposal={},
        )
        session.add(candidate)
        session.flush()
        session.add(
            ConfidenceRecord(
                candidate_id=candidate.id,
                agent_id=accounts[0].id,
                predicted_confidence=D(".5"),
                outcome=i % 2 == 0,
                return_percent=D(1 if i % 2 == 0 else -1),
                strategy_version="fixture-v1",
                model_version="fixture",
                regime="BULL_TREND",
            )
        )
        session.commit()
        result = reliability(session)["systems"][0]
        if i < 19:
            assert result["win_rate"] is None and result["brier_score"] is None
    assert D(result["win_rate"]) == D(".5") and D(result["brier_score"]) == D(".25")
    assert D(result["average_return"]) == 0
