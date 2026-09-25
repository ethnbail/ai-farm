from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database.session import get_session
from app.models import Agent, MarketplaceOpportunity, Trade
from app.schemas.dashboard import AgentSummary, AIUsage, Health, MarketplaceSummary, TradeRead
from app.services.agents import summarize_agents
from app.services.events import live_stream
from app.services.health import get_health

router = APIRouter()
DbSession = Annotated[Session, Depends(get_session)]


@router.get("/health", response_model=Health, tags=["system"])
def health(response: Response):
    result = get_health()
    if result.status != "ok":
        response.status_code = 503
    return result


@router.get("/api/agents", response_model=list[AgentSummary], tags=["agents"])
@router.get("/agents", response_model=list[AgentSummary], include_in_schema=False)
def list_agents(session: DbSession):
    return summarize_agents(session)


@router.get("/api/agents/{agent_id}", response_model=AgentSummary, tags=["agents"])
@router.get("/agents/{agent_id}", response_model=AgentSummary, include_in_schema=False)
def agent_detail(agent_id: UUID, session: DbSession):
    agents = summarize_agents(session, agent_id)
    if not agents:
        raise HTTPException(404, "Agent not found")
    return agents[0]


@router.get("/api/agents/{agent_id}/trades", response_model=list[TradeRead], tags=["agents"])
@router.get("/agents/{agent_id}/trades", response_model=list[TradeRead], include_in_schema=False)
def agent_trades(
    agent_id: UUID,
    session: DbSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    if session.get(Agent, agent_id) is None:
        raise HTTPException(404, "Agent not found")
    return session.scalars(
        select(Trade)
        .where(Trade.agent_id == agent_id)
        .order_by(Trade.entry_time.desc(), Trade.id)
        .offset(offset)
        .limit(limit)
    ).all()


@router.get("/api/marketplace", response_model=MarketplaceSummary, tags=["marketplace"])
def marketplace(session: DbSession):
    return MarketplaceSummary(
        opportunities_found=session.scalar(select(func.count()).select_from(MarketplaceOpportunity))
        or 0
    )


@router.get("/api/ai-usage", response_model=AIUsage, tags=["system"])
def ai_usage():
    return AIUsage(monthly_budget_usd=get_settings().ai_monthly_budget_usd)


@router.get("/api/events", tags=["system"])
async def live_events(last_event_id: Annotated[str | None, Header()] = None):
    if last_event_id is not None and (not last_event_id.isdigit() or len(last_event_id) > 18):
        raise HTTPException(422, "Last-Event-ID must be a nonnegative sequence number")
    return StreamingResponse(
        live_stream(
            get_settings().heartbeat_interval_seconds, int(last_event_id) if last_event_id else None
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
    )
