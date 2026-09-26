from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, HttpUrl, field_validator


class TradeAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")
    recommendation: Literal["BUY", "SELL", "CALL", "PUT", "HOLD", "NO_TRADE"]
    confidence: float = Field(ge=0, le=1)
    thesis: str = Field(max_length=2000)
    supporting_factors: list[str] = Field(max_length=10)
    risks: list[str] = Field(max_length=10)
    invalidation_conditions: list[str] = Field(max_length=10)
    event_risks: list[str] = Field(max_length=10)
    regime_fit: str
    data_quality: str
    uncertainty_notes: list[str] = Field(max_length=10)
    suggested_entry_context: str
    suggested_stop_context: str
    suggested_target_context: str


class ShadowReviewOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    approve_for_risk_review: bool
    objections: list[str] = Field(max_length=15)
    severity: Literal["low", "medium", "high"]
    confidence: float = Field(ge=0, le=1)
    missing_information: list[str] = Field(max_length=10)
    recommended_action: Literal["PROCEED", "REDUCE_SIZE", "WAIT", "NO_TRADE"]


class WatchlistInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=100)
    agent_id: UUID
    symbols: list[str] = Field(min_length=1, max_length=30)

    @field_validator("symbols")
    @classmethod
    def normalize(cls, symbols):
        import re

        values = sorted(set(s.strip().upper() for s in symbols))
        if any(not re.fullmatch(r"[A-Z][A-Z0-9.-]{0,9}", s) for s in values):
            raise ValueError("Invalid normalized symbol")
        return values


class MarketplaceListingInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: Literal["manual", "fixture"] = "manual"
    listing_id: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=300)
    description: str = Field(default="", max_length=5000)
    asking_price: Decimal = Field(ge=0, max_digits=18, decimal_places=2)
    original_price: Decimal | None = Field(default=None, ge=0)
    price_history: list[Decimal] = Field(default_factory=list, max_length=100)
    listing_age_days: int | None = Field(default=None, ge=0, le=3650)
    location: str = Field(default="Unknown", max_length=200)
    distance_miles: Decimal | None = Field(default=None, ge=0, le=1000)
    seller_info: str | None = Field(default=None, max_length=500)
    photos_metadata: list[str] = Field(default_factory=list, max_length=20)
    category: str = Field(default="unknown", max_length=100)
    condition: str = Field(default="unknown", max_length=100)
    direct_url: HttpUrl
    resale_low: Decimal | None = Field(default=None, ge=0)
    resale_high: Decimal | None = Field(default=None, ge=0)
    accessories_complete: bool | None = None
    authenticity_verified: bool = False


class MarketplaceOutcomeInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    bought: bool
    acquisition_price: Decimal | None = Field(default=None, ge=0)
    listing_date: AwareDatetime | None = None
    sale_date: AwareDatetime | None = None
    sale_price: Decimal | None = Field(default=None, ge=0)
    fees: Decimal = Field(default=Decimal(0), ge=0)
    travel_cost: Decimal = Field(default=Decimal(0), ge=0)
