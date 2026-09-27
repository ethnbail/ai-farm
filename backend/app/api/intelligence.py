from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request
from sqlalchemy import delete, func, select

from app.api.routes import DbSession
from app.core.config import get_settings
from app.market_data.types import effective_state
from app.models import (
    Agent,
    AIAnalysis,
    MarketplaceListing,
    MarketRegimeSnapshot,
    OpportunityCandidate,
    OpportunityQueueItem,
    Portfolio,
    ProviderStatus,
    RiskEvent,
    ShadowReview,
    Watchlist,
    WatchlistSymbol,
)
from app.schemas.intelligence import WatchlistInput
from app.services.ai import AIBudgetManager
from app.services.event_context import EventContextService, aware
from app.services.reliability import reliability
from app.services.research import universe
from app.services.serialization import public

router = APIRouter(tags=["intelligence"])


@router.get("/market/regime")
def regime(session: DbSession):
    row = session.scalar(
        select(MarketRegimeSnapshot).order_by(MarketRegimeSnapshot.created_at.desc()).limit(1)
    )
    return (
        {
            **public(row),
            "data_mode": effective_state(
                row.data_mode,
                row.data_timestamp,
                datetime.now(UTC),
                get_settings().quote_max_age_seconds,
            ),
        }
        if row
        else {
            "regime": "UNKNOWN",
            "data_mode": "unavailable",
            "data_timestamp": None,
            "features": {},
            "reasons": ["No research scan yet"],
        }
    )


@router.get("/market/provider-status")
def provider_status(session: DbSession):
    s = get_settings()
    missing = s.market_data_provider == "tradier" and not (
        s.market_data_api_key and s.market_data_api_key.get_secret_value().strip()
    )
    row = session.get(ProviderStatus, s.market_data_provider)
    return dict(
        provider=s.market_data_provider,
        effective_provider="mock" if missing else s.market_data_provider,
        state="mock"
        if missing or s.market_data_provider == "mock"
        else effective_state(row.state, row.updated_at, datetime.now(UTC), s.quote_max_age_seconds)
        if row
        else "unavailable",
        message="Credentials absent; explicitly using MOCK fixtures"
        if missing
        else "Deterministic MOCK fixtures; no live provider configured"
        if s.market_data_provider == "mock" and row is None
        else row.message
        if row
        else "Configured; no observed live scan yet",
        last_observation=public(row),
    )


def candidate_data(session, row):
    item = session.scalar(
        select(OpportunityQueueItem).where(OpportunityQueueItem.candidate_id == row.id)
    )
    queue = public(item)
    if (
        item
        and item.status not in {"EXECUTED", "RISK_REJECTED", "DISMISSED"}
        and aware(item.expires_at) <= datetime.now(UTC)
    ):
        queue["status"] = "EXPIRED"
    agent = session.get(Agent, row.agent_id)
    return {**public(row), "agent_name": agent.name if agent else "Unknown", "queue": queue}


@router.get("/opportunities")
@router.get("/research")
def opportunities(
    session: DbSession,
    agent_id: UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    latest_scan: bool = False,
):
    if latest_scan:
        identifiers = [agent_id] if agent_id else session.scalars(select(Agent.id)).all()
        result = []
        for identifier in identifiers:
            scan = session.scalar(
                select(OpportunityCandidate.scan_id)
                .where(OpportunityCandidate.agent_id == identifier)
                .order_by(OpportunityCandidate.created_at.desc())
                .limit(1)
            )
            rows = session.scalars(
                select(OpportunityCandidate)
                .where(
                    OpportunityCandidate.agent_id == identifier,
                    OpportunityCandidate.scan_id == scan,
                )
                .order_by(
                    OpportunityCandidate.eligible.desc(),
                    OpportunityCandidate.score.desc(),
                    OpportunityCandidate.symbol,
                )
                .limit(limit if agent_id else min(limit, 3))
            )
            result.extend(candidate_data(session, row) for row in rows)
        return result
    statement = (
        select(OpportunityCandidate)
        .order_by(OpportunityCandidate.created_at.desc(), OpportunityCandidate.score.desc())
        .limit(limit)
    )
    if agent_id:
        statement = statement.where(OpportunityCandidate.agent_id == agent_id)
    return [candidate_data(session, row) for row in session.scalars(statement)]


@router.get("/opportunities/{identifier}")
@router.get("/research/{identifier}")
def research_detail(identifier: UUID, session: DbSession):
    row = session.get(OpportunityCandidate, identifier)
    if row is None:
        raise HTTPException(404, "Research not found")
    return {
        **candidate_data(session, row),
        "analyses": public(
            session.scalars(select(AIAnalysis).where(AIAnalysis.candidate_id == identifier)).all()
        ),
        "shadow_reviews": public(
            session.scalars(
                select(ShadowReview).where(ShadowReview.candidate_id == identifier)
            ).all()
        ),
    }


@router.get("/ai/usage")
def ai_usage(session: DbSession):
    s = get_settings()
    return public(
        {
            **AIBudgetManager(session, s).usage(),
            "enabled": s.ai_enabled,
            "monthly_budget": s.ai_monthly_budget_usd,
            "daily_budget": s.ai_daily_budget_usd,
            "accounting": "Conservative reserved upper-bound spend; not a vendor invoice",
        }
    )


@router.get("/ai/status")
def ai_status():
    s = get_settings()
    ready = (
        s.ai_enabled
        and bool(s.openai_api_key and s.openai_api_key.get_secret_value().strip())
        and bool(s.ai_model_prices)
    )
    return dict(
        enabled=s.ai_enabled,
        mode="configured" if ready else "deterministic-only",
        cheap_model=s.ai_cheap_model or "unconfigured",
        reasoning_model=s.ai_reasoning_model or "unconfigured",
        shadow_model=s.ai_shadow_model or "unconfigured",
        message="Paid calls require enabled AI, key, priced model and available budget",
    )


@router.get("/reliability")
def reliability_summary(session: DbSession):
    return public(reliability(session))


@router.get("/events/risk")
def event_risks(session: DbSession, symbol: str = "SPY"):
    s = get_settings()
    live = s.market_data_provider == "tradier" and bool(
        s.market_data_api_key and s.market_data_api_key.get_secret_value().strip()
    )
    return EventContextService().context(
        session, s, symbol, datetime.now(UTC), "live" if live else "mock"
    )


@router.get("/agents/{identifier}/intelligence")
def agent_intelligence(identifier: UUID, session: DbSession):
    agent = session.get(Agent, identifier)
    if agent is None:
        raise HTTPException(404, "Agent not found")
    from app.agents.strategies import DirectionalMomentumOptionsStrategy, TrendMomentumStrategy

    strategy = (
        TrendMomentumStrategy
        if agent.agent_type == "equities"
        else DirectionalMomentumOptionsStrategy
    )
    latest = session.scalar(
        select(AIAnalysis)
        .join(OpportunityCandidate)
        .where(OpportunityCandidate.agent_id == identifier)
        .order_by(AIAnalysis.created_at.desc())
        .limit(1)
    )
    candidate = session.scalar(
        select(OpportunityCandidate)
        .where(OpportunityCandidate.agent_id == identifier)
        .order_by(OpportunityCandidate.created_at.desc(), OpportunityCandidate.score.desc())
        .limit(1)
    )
    return {
        "watchlist": universe(session, get_settings(), agent),
        "latest_research": research_detail(candidate.id, session) if candidate else None,
        "strategy_version": f"{strategy.name}:{strategy.version}",
        "model_version": latest.model if latest else "N/A",
        "risk_rejections": public(
            session.scalars(
                select(RiskEvent)
                .join(Portfolio)
                .where(Portfolio.agent_id == identifier)
                .order_by(RiskEvent.created_at.desc())
                .limit(5)
            ).all()
        ),
        "reliability": [
            r for r in reliability(session)["systems"] if r["agent_id"] == str(identifier)
        ],
        "baseline": "SPY matching-period comparison"
        if agent.agent_type == "equities"
        else "Deterministic strategy v1; no comparable live options benchmark claimed",
    }


@router.get("/watchlists")
def watchlists(session: DbSession, agent_id: UUID | None = None):
    statement = select(Watchlist).order_by(Watchlist.created_at).limit(100)
    if agent_id:
        statement = statement.where(Watchlist.agent_id == agent_id)
    return [
        {
            **public(w),
            "symbols": session.scalars(
                select(WatchlistSymbol.symbol).where(WatchlistSymbol.watchlist_id == w.id)
            ).all(),
        }
        for w in session.scalars(statement)
    ]


def local_write(request):
    s = get_settings()
    if not s.local_writes_enabled:
        raise HTTPException(403, "Local watchlist writes are disabled")
    if request.headers.get("origin") not in s.cors_origins:
        raise HTTPException(403, "Explicit trusted Origin required")


@router.post("/watchlists", status_code=201)
def add_watchlist(payload: WatchlistInput, request: Request, session: DbSession):
    local_write(request)
    if session.get(Agent, payload.agent_id) is None:
        raise HTTPException(404, "Agent not found")
    # Serialize per-agent capacity checks to bound local mutation endpoints.
    session.scalar(select(Agent).where(Agent.id == payload.agent_id).with_for_update())
    if (
        session.scalar(
            select(func.count())
            .select_from(Watchlist)
            .where(Watchlist.agent_id == payload.agent_id)
        )
        >= 10
    ):
        raise HTTPException(429, "At most 10 watchlists per agent")
    row = Watchlist(name=payload.name, agent_id=payload.agent_id)
    session.add(row)
    session.flush()
    session.add_all([WatchlistSymbol(watchlist_id=row.id, symbol=s) for s in payload.symbols])
    session.commit()
    return {**public(row), "symbols": payload.symbols}


@router.delete("/watchlists/{identifier}", status_code=204)
def delete_watchlist(identifier: UUID, request: Request, session: DbSession):
    local_write(request)
    row = session.get(Watchlist, identifier)
    if row is None:
        raise HTTPException(404, "Watchlist not found")
    session.execute(delete(WatchlistSymbol).where(WatchlistSymbol.watchlist_id == identifier))
    session.delete(row)
    session.commit()


@router.get("/marketplace/opportunities")
def marketplace_opportunities(session: DbSession, limit: Annotated[int, Query(ge=1, le=100)] = 10):
    from app.marketplace.pipeline import listing_data

    return [
        listing_data(session, row)
        for row in session.scalars(
            select(MarketplaceListing).order_by(MarketplaceListing.created_at.desc()).limit(limit)
        )
    ]


@router.get("/marketplace/opportunities/{identifier}")
def marketplace_detail(identifier: UUID, session: DbSession):
    from app.marketplace.pipeline import listing_data

    row = session.get(MarketplaceListing, identifier)
    if row is None:
        raise HTTPException(404, "Marketplace listing not found")
    return listing_data(session, row, True)
