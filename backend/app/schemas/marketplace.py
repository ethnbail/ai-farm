"""Bounded, evidence-first imports. URLs are references, never fetch instructions."""

import json
import re
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator

Money = Annotated[Decimal, Field(ge=0, max_digits=14, decimal_places=2)]
Percent = Annotated[Decimal, Field(ge=0, le=100, max_digits=7, decimal_places=3)]
Status = Literal[
    "NEW", "TRACKING", "REVIEWING", "CONTACTED", "BOUGHT", "PASSED", "SOLD", "EXPIRED", "REMOVED"
]


def safe_url(value: str) -> str:
    value = value.strip()
    parts = urlsplit(value)
    if (
        len(value) > 2000
        or parts.scheme not in {"http", "https"}
        or not parts.hostname
        or parts.username
        or parts.password
        or any(ord(c) < 32 for c in value)
    ):
        raise ValueError("Use a public http(s) listing URL without credentials")
    # Never fetch even apparently public URLs; this is not an SSRF allowlist.
    return value


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    @model_validator(mode="before")
    @classmethod
    def bounded_plain_data(cls, value):
        if len(json.dumps(value, default=str)) > 64_000:
            raise ValueError("Record exceeds 64 KB")

        def clean(v):
            if isinstance(v, str):
                return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", re.sub(r"<[^>]*>", "", v))
            if isinstance(v, dict):
                return {k: clean(x) for k, x in v.items()}
            if isinstance(v, list):
                return [clean(x) for x in v]
            return v

        return clean(value)


class SearchSettings(Input):
    zip_code: str | None = Field(default=None, pattern=r"^\d{5}$")
    radius_miles: int = Field(default=25, ge=1, le=100)
    preferred_categories: list[str] = Field(default_factory=list, max_length=30)
    excluded_categories: list[str] = Field(default_factory=list, max_length=30)
    min_asking_price: Money = Decimal(0)
    max_asking_price: Money = Decimal(10000)
    min_expected_profit: Money = Decimal(25)
    min_roi_percent: Percent = Decimal(20)
    max_pickup_miles: Decimal = Field(default=Decimal(30), ge=0, le=1000)
    max_pickup_time_minutes: int | None = Field(default=None, ge=0, le=1440)
    max_listing_age_hours: int | None = Field(default=None, ge=1, le=8760)
    min_seller_rating: Decimal | None = Field(default=None, ge=0, le=5)
    cost_per_mile: Money = Decimal("0.70")
    platform_fee_percent: Percent = Decimal(10)
    payment_fee_percent: Percent = Decimal(0)
    risk_buffer_percent: Percent = Decimal(10)
    strong_score_threshold: Percent = Decimal(75)
    freshness_minutes: list[int] = Field(
        default=[15, 60, 360, 1440, 4320], min_length=5, max_length=5
    )
    inventory_days: list[int] = Field(default=[7, 30, 60, 90], min_length=4, max_length=4)
    stale_after_hours: int = Field(default=72, ge=1, le=8760)
    hemisphere: Literal["northern", "southern", "unknown"] = "unknown"

    @model_validator(mode="after")
    def ordered(self):
        if self.min_asking_price > self.max_asking_price:
            raise ValueError("Minimum asking price exceeds maximum")
        if self.platform_fee_percent + self.payment_fee_percent >= 100:
            raise ValueError("Combined fee percentage must be below 100")
        for values in [self.freshness_minutes, self.inventory_days]:
            if values[0] <= 0 or values != sorted(set(values)):
                raise ValueError("Thresholds must be positive and strictly increasing")
        return self


class ComparableInput(Input):
    price: Money
    source: str = Field(min_length=1, max_length=100)
    source_url: str | None = None
    observed_at: AwareDatetime
    sold: bool = True
    sold_at: AwareDatetime | None = None
    days_to_sell: int | None = Field(default=None, ge=0, le=3650)
    market: Literal["LOCAL", "NATIONAL", "UNKNOWN"] = "UNKNOWN"
    category: str = Field(default="unknown", max_length=60)
    model: str | None = Field(default=None, max_length=100)
    condition: str = Field(default="unknown", max_length=60)
    quality: Literal["verified", "user_reported", "fixture"] = "user_reported"
    currency: Literal["USD"] = "USD"
    notes: str = Field(default="", max_length=1000)
    _url = field_validator("source_url")(lambda v: safe_url(v) if v else None)

    @model_validator(mode="after")
    def valid_dates(self):
        now = datetime.now(UTC)
        if self.observed_at > now + timedelta(minutes=5) or (self.sold_at and self.sold_at > now):
            raise ValueError("Comparable timestamps cannot be in the future")
        if self.sold_at and not self.sold:
            raise ValueError("Unsold comparable cannot have a sale timestamp")
        return self


class DemandInput(Input):
    source: str = Field(min_length=1, max_length=100)
    observed_at: AwareDatetime
    market: Literal["LOCAL", "NATIONAL"]
    # Cohort denominator must include sold AND unsold items observed for each complete window.
    cohort_size: int = Field(ge=1, le=1000000)
    observation_days: int = Field(ge=1, le=3650)
    sold_7d: int | None = Field(default=None, ge=0)
    sold_14d: int | None = Field(default=None, ge=0)
    sold_30d: int | None = Field(default=None, ge=0)
    sold_60d: int | None = Field(default=None, ge=0)
    active_listing_count: int | None = Field(default=None, ge=0)
    quality: Literal["user_reported", "verified", "fixture"] = "user_reported"

    @model_validator(mode="after")
    def valid_cohort(self):
        previous = 0
        if self.observed_at > datetime.now(UTC) + timedelta(minutes=5):
            raise ValueError("Demand observation cannot be in the future")
        for days in [7, 14, 30, 60]:
            count = getattr(self, f"sold_{days}d")
            if count is not None:
                if count < previous or count > self.cohort_size or days > self.observation_days:
                    raise ValueError(
                        "Sold counts must be monotone, within cohort, and fully observed"
                    )
                previous = count
        return self


class ListingInput(Input):
    source: str = Field(default="manual", min_length=1, max_length=40, pattern=r"^[a-z0-9_-]+$")
    source_listing_id: str = Field(min_length=1, max_length=100)
    source_url: str
    title: str = Field(min_length=1, max_length=300)
    description: str = Field(default="", max_length=5000)
    asking_price: Money
    original_price: Money | None = None
    currency: Literal["USD"] = "USD"
    category: str = Field(default="unknown", max_length=60)
    subcategory: str | None = Field(default=None, max_length=60)
    brand: str | None = Field(default=None, max_length=100)
    model: str | None = Field(default=None, max_length=100)
    condition: str = Field(default="unknown", max_length=100)
    listed_at: AwareDatetime | None = None
    observed_at: AwareDatetime | None = None
    location_text: str = Field(default="Unknown", max_length=200)
    zip_code: str | None = Field(default=None, pattern=r"^\d{5}$")
    latitude: Decimal | None = Field(default=None, ge=-90, le=90)
    longitude: Decimal | None = Field(default=None, ge=-180, le=180)
    distance_miles: Decimal | None = Field(default=None, ge=0, le=1000)
    driving_minutes_round_trip: int | None = Field(default=None, ge=0, le=1440)
    seller_id: str | None = Field(default=None, max_length=100)
    seller_name: str | None = Field(default=None, max_length=100)
    seller_rating: Decimal | None = Field(default=None, ge=0, le=5)
    seller_review_count: int | None = Field(default=None, ge=0, le=1000000)
    seller_joined_date: date | None = None
    seller_profile_metadata: dict = Field(default_factory=dict)
    item_metadata: dict = Field(default_factory=dict)
    image_metadata: list[dict] = Field(default_factory=list, max_length=20)
    raw_source_metadata: dict = Field(default_factory=dict)
    shipping_cost: Money = Decimal(0)
    repair_cost: Money = Decimal(0)
    other_costs: Money = Decimal(0)
    comps: list[ComparableInput] = Field(default_factory=list, max_length=100)
    demand: list[DemandInput] = Field(default_factory=list, max_length=2)
    active: bool = True
    notes: str = Field(default="", max_length=2000)
    _url = field_validator("source_url")(safe_url)

    @model_validator(mode="after")
    def evidence_checks(self):
        now = datetime.now(UTC)
        if any(
            value and value > now + timedelta(minutes=5)
            for value in [self.listed_at, self.observed_at]
        ):
            raise ValueError("Listing timestamps cannot be in the future")
        if self.listed_at and self.observed_at and self.listed_at > self.observed_at:
            raise ValueError("Listing date cannot follow observation date")
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("Provide both coordinates or neither")
        if self.seller_joined_date and self.seller_joined_date > now.date():
            raise ValueError("Seller join date cannot be in the future")
        allowed_seller = {"red_flags", "listing_count", "consistent_details"}
        if set(self.seller_profile_metadata) - allowed_seller:
            raise ValueError(
                "Seller metadata allows only red_flags, listing_count, consistent_details"
            )
        flags = self.seller_profile_metadata.get("red_flags", [])
        if (
            not isinstance(flags, list)
            or len(flags) > 20
            or any(not isinstance(f, str) or len(f) > 200 for f in flags)
        ):
            raise ValueError("Seller red_flags must be at most 20 short strings")
        accessories = self.item_metadata.get("accessories", {})
        if (
            not isinstance(accessories, dict)
            or len(accessories) > 30
            or any(
                not isinstance(k, str) or not isinstance(v, bool) for k, v in accessories.items()
            )
        ):
            raise ValueError("Accessories must be a bounded object of explicit booleans")
        # Do not retain cookies, credentials, private contact information or raw page HTML.
        if set(self.raw_source_metadata) - {
            "connector",
            "exported_at",
            "capture_method",
            "provenance",
        }:
            raise ValueError("Raw metadata must contain only acquisition provenance")
        for image in self.image_metadata:
            if set(image) - {"url", "fingerprint", "stock_photo", "caption"}:
                raise ValueError("Unsupported image metadata")
            if image.get("url"):
                image["url"] = safe_url(image["url"])
        if len({d.market for d in self.demand}) != len(self.demand):
            raise ValueError("Only one demand cohort per market per submission")
        return self


class ListingAction(Input):
    notes: str = Field(default="", max_length=2000)
    would_have_bought: bool = False


class PurchaseInput(Input):
    purchase_price: Money
    purchase_date: AwareDatetime
    travel_cost: Money = Decimal(0)
    repair_cost: Money = Decimal(0)
    other_costs: Money = Decimal(0)
    notes: str = Field(default="", max_length=2000)


class SaleInput(Input):
    sale_price: Money
    sale_date: AwareDatetime
    selling_platform: str = Field(default="manual", max_length=100)
    platform_fees: Money = Decimal(0)
    shipping_cost: Money = Decimal(0)
    payment_fees: Money = Decimal(0)
    other_costs: Money = Decimal(0)
    authenticity_outcome: Literal["authentic", "counterfeit", "unknown"] = "unknown"
    notes: str = Field(default="", max_length=2000)


class HypotheticalInput(Input):
    actual_sale_price: Money | None = None
    days_to_sell: int | None = Field(default=None, ge=0, le=3650)
    sold: bool
    observation_days: int = Field(ge=1, le=3650)
    source: str = Field(min_length=1, max_length=200)
