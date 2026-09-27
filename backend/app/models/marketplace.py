"""Marketplace evidence and human-recorded outcomes, never execution accounts."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import JSON, DateTime, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.models.intelligence import Record


class MarketplaceSettings(Base):
    __tablename__ = "marketplace_settings"
    id: Mapped[int] = mapped_column(primary_key=True)
    preferences: Mapped[dict] = mapped_column(JSON)


class MarketplacePriceHistory(Record, Base):
    __tablename__ = "marketplace_price_history"
    listing_id: Mapped[UUID] = mapped_column(ForeignKey("marketplace_listings.id"), index=True)
    price: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class MarketplaceDuplicateMatch(Record, Base):
    __tablename__ = "marketplace_duplicate_matches"
    __table_args__ = (UniqueConstraint("listing_id", "candidate_id"),)
    listing_id: Mapped[UUID] = mapped_column(ForeignKey("marketplace_listings.id"))
    candidate_id: Mapped[UUID] = mapped_column(ForeignKey("marketplace_listings.id"))
    evidence: Mapped[dict] = mapped_column(JSON)


class MarketplaceSellerProfile(Record, Base):
    __tablename__ = "marketplace_seller_profiles"
    __table_args__ = (UniqueConstraint("source", "source_seller_id"),)
    source: Mapped[str] = mapped_column(String(40))
    source_seller_id: Mapped[str] = mapped_column(String(100))
    profile: Mapped[dict] = mapped_column(JSON)


class MarketplaceComparable(Record, Base):
    __tablename__ = "marketplace_comparables"
    listing_id: Mapped[UUID] = mapped_column(ForeignKey("marketplace_listings.id"), index=True)
    evidence: Mapped[dict] = mapped_column(JSON)


class MarketplaceDemandSnapshot(Record, Base):
    __tablename__ = "marketplace_demand_snapshots"
    listing_id: Mapped[UUID] = mapped_column(ForeignKey("marketplace_listings.id"), index=True)
    evidence: Mapped[dict] = mapped_column(JSON)


class MarketplaceInventoryItem(Record, Base):
    __tablename__ = "marketplace_inventory"
    listing_id: Mapped[UUID] = mapped_column(ForeignKey("marketplace_listings.id"), unique=True)
    purchase: Mapped[dict] = mapped_column(JSON)
    sold: Mapped[bool] = mapped_column(default=False)
    aging_bucket: Mapped[str] = mapped_column(String(30), default="FRESH")


class MarketplaceCalibrationRecord(Record, Base):
    __tablename__ = "marketplace_calibration"
    __table_args__ = (UniqueConstraint("listing_id", "hypothetical"),)
    listing_id: Mapped[UUID] = mapped_column(ForeignKey("marketplace_listings.id"))
    hypothetical: Mapped[bool] = mapped_column(default=False)
    metrics: Mapped[dict] = mapped_column(JSON)


class MarketplaceNotification(Record, Base):
    __tablename__ = "marketplace_notifications"
    listing_id: Mapped[UUID] = mapped_column(ForeignKey("marketplace_listings.id"), index=True)
    severity: Mapped[str] = mapped_column(String(12))
    event_type: Mapped[str] = mapped_column(String(60))
    dedup_key: Mapped[str] = mapped_column(String(100), unique=True)
    message: Mapped[str] = mapped_column(String(500))
