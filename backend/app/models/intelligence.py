"""Research is separate from execution; immutable inputs and reviews remain auditable."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class Record:
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MarketRegimeSnapshot(Record, Base):
    __tablename__ = "market_regime_snapshots"
    regime: Mapped[str] = mapped_column(String(30))
    data_mode: Mapped[str] = mapped_column(String(20))
    data_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    features: Mapped[dict] = mapped_column(JSON)
    reasons: Mapped[list] = mapped_column(JSON)


class OpportunityCandidate(Record, Base):
    __tablename__ = "opportunity_candidates"
    scan_id: Mapped[UUID] = mapped_column(index=True)
    agent_id: Mapped[UUID] = mapped_column(ForeignKey("agents.id"), index=True)
    symbol: Mapped[str] = mapped_column(String(32))
    score: Mapped[Decimal] = mapped_column(Numeric(10, 4))
    components: Mapped[dict] = mapped_column(JSON)
    regime: Mapped[str] = mapped_column(String(30))
    data_mode: Mapped[str] = mapped_column(String(20))
    eligible: Mapped[bool]
    reasons: Mapped[list] = mapped_column(JSON)
    rejection_reasons: Mapped[list] = mapped_column(JSON)
    snapshot: Mapped[dict] = mapped_column(JSON)
    proposal: Mapped[dict] = mapped_column(JSON)


class OpportunityQueueItem(Record, Base):
    __tablename__ = "opportunity_queue"
    candidate_id: Mapped[UUID] = mapped_column(ForeignKey("opportunity_candidates.id"), unique=True)
    agent_id: Mapped[UUID] = mapped_column(ForeignKey("agents.id"), index=True)
    rank: Mapped[int]
    status: Mapped[str] = mapped_column(String(30), default="DISCOVERED")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    rejection_reason: Mapped[str | None] = mapped_column(String(1000))
    ai_status: Mapped[str] = mapped_column(String(40), default="pending")
    shadow_status: Mapped[str] = mapped_column(String(40), default="pending")
    risk_status: Mapped[str] = mapped_column(String(40), default="not_reviewed")
    trade_id: Mapped[UUID | None] = mapped_column(ForeignKey("trades.id"))
    order_id: Mapped[UUID | None] = mapped_column(ForeignKey("orders.id"))


class AIAnalysis(Record, Base):
    __tablename__ = "ai_analyses"
    candidate_id: Mapped[UUID] = mapped_column(ForeignKey("opportunity_candidates.id"), index=True)
    model: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(40))
    context: Mapped[dict] = mapped_column(JSON)
    analysis: Mapped[dict] = mapped_column(JSON)


class BudgetGuard(Base):
    __tablename__ = "ai_budget_guard"
    id: Mapped[int] = mapped_column(primary_key=True)
    revision: Mapped[int] = mapped_column(default=0)


class AIUsageRecord(Record, Base):
    __tablename__ = "ai_usage_records"
    scan_id: Mapped[UUID] = mapped_column(index=True)
    model: Mapped[str] = mapped_column(String(100))
    purpose: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(30))
    estimated_input_tokens: Mapped[int]
    estimated_output_tokens: Mapped[int]
    input_tokens: Mapped[int | None]
    output_tokens: Mapped[int | None]
    estimated_cost: Mapped[Decimal] = mapped_column(Numeric(18, 8))
    charged_cost: Mapped[Decimal] = mapped_column(Numeric(18, 8))
    reason: Mapped[str | None] = mapped_column(String(200))


class ShadowReview(Record, Base):
    __tablename__ = "shadow_reviews"
    candidate_id: Mapped[UUID] = mapped_column(ForeignKey("opportunity_candidates.id"), index=True)
    model: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(40))
    review: Mapped[dict] = mapped_column(JSON)


class ConfidenceRecord(Record, Base):
    __tablename__ = "confidence_records"
    candidate_id: Mapped[UUID] = mapped_column(ForeignKey("opportunity_candidates.id"), unique=True)
    trade_id: Mapped[UUID | None] = mapped_column(ForeignKey("trades.id"))
    agent_id: Mapped[UUID] = mapped_column(ForeignKey("agents.id"), index=True)
    predicted_confidence: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    outcome: Mapped[bool | None]
    return_percent: Mapped[Decimal | None] = mapped_column(Numeric(14, 4))
    strategy_version: Mapped[str] = mapped_column(String(100))
    model_version: Mapped[str] = mapped_column(String(100))
    regime: Mapped[str] = mapped_column(String(30))


class EventRisk(Record, Base):
    __tablename__ = "event_risks"
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    event_type: Mapped[str] = mapped_column(String(100))
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    importance: Mapped[str] = mapped_column(String(20))
    source: Mapped[str] = mapped_column(String(30))
    warning: Mapped[str] = mapped_column(String(500))


class Watchlist(Record, Base):
    __tablename__ = "watchlists"
    name: Mapped[str] = mapped_column(String(100))
    agent_id: Mapped[UUID] = mapped_column(ForeignKey("agents.id"), index=True)


class WatchlistSymbol(Base):
    __tablename__ = "watchlist_symbols"
    watchlist_id: Mapped[UUID] = mapped_column(ForeignKey("watchlists.id"), primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32), primary_key=True)


class ProviderStatus(Base):
    __tablename__ = "provider_status"
    provider: Mapped[str] = mapped_column(String(40), primary_key=True)
    state: Mapped[str] = mapped_column(String(30))
    message: Mapped[str] = mapped_column(String(300))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class MarketplaceListing(Record, Base):
    __tablename__ = "marketplace_listings"
    __table_args__ = (UniqueConstraint("source", "listing_id"),)
    source: Mapped[str] = mapped_column(String(40))
    listing_id: Mapped[str] = mapped_column(String(100))
    title: Mapped[str] = mapped_column(String(300))
    asking_price: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    direct_url: Mapped[str] = mapped_column(String(2000))
    details: Mapped[dict] = mapped_column(JSON)
    first_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    listed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="NEW", server_default="NEW")
    active: Mapped[bool] = mapped_column(default=True, server_default="true")
    duplicate_of_listing_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("marketplace_listings.id")
    )
    first_known_post: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    repost_count: Mapped[int] = mapped_column(default=0, server_default="0")
    repost_probability: Mapped[Decimal | None] = mapped_column(Numeric(6, 4))


class MarketplaceAnalysis(Record, Base):
    __tablename__ = "marketplace_analyses"
    listing_id: Mapped[UUID] = mapped_column(ForeignKey("marketplace_listings.id"), index=True)
    analysis: Mapped[dict] = mapped_column(JSON)


class MarketplaceOutcome(Record, Base):
    __tablename__ = "marketplace_outcomes"
    listing_id: Mapped[UUID] = mapped_column(ForeignKey("marketplace_listings.id"), unique=True)
    outcome: Mapped[dict] = mapped_column(JSON)
