"""Manual/fixture connector and explained estimates. No fetching, scraping or messaging."""

from decimal import Decimal as D
from typing import Protocol

from sqlalchemy import select

from app.models import MarketplaceAnalysis, MarketplaceListing, MarketplaceOutcome
from app.schemas.intelligence import MarketplaceListingInput, MarketplaceOutcomeInput
from app.services.accounting import money
from app.services.event_store import emit


class MarketplaceSourceConnector(Protocol):
    def listings(self) -> list[MarketplaceListingInput]: ...


class ManualJSONConnector:
    def __init__(self, payload):
        if not isinstance(payload, list) or len(payload) > 100:
            raise ValueError("Import requires a JSON array of at most 100 listings")
        self.payload = payload

    def listings(self):
        return [MarketplaceListingInput.model_validate(item) for item in self.payload]


class MarketplaceScore:
    def evaluate(self, listing):
        flags = ["Estimates only; not verified comparable sales", "Seller reliability unverified"]
        if not listing.authenticity_verified:
            flags.append("Authenticity unverified")
        if listing.accessories_complete is not True:
            flags.append("Completeness/accessories unverified")
        if listing.distance_miles is None:
            flags.append("Travel distance unavailable")
        drop = max(D(0), (listing.original_price or listing.asking_price) - listing.asking_price)
        age_priority = min(20, listing.listing_age_days or 0)
        motivation = (
            "Text mentions moving/urgent; unverified"
            if any(s in listing.description.lower() for s in ["moving", "urgent", "must sell"])
            else "Unknown"
        )
        travel = (
            money(listing.distance_miles * 2 * D(".70"))
            if listing.distance_miles is not None
            else None
        )
        low, high = listing.resale_low, listing.resale_high
        if low is not None and high is not None and low > high:
            raise ValueError("Resale range is reversed")
        # Supplied comps are estimates. Conservative low estimate, 10% illustrative fees.
        net = (
            money(low * D(".90") - listing.asking_price - travel)
            if low is not None and travel is not None
            else None
        )
        maximum = (
            money(max(D(0), low * D(".90") - travel - 25))
            if low is not None and travel is not None
            else None
        )
        return dict(
            estimated_resale_low=str(low) if low is not None else None,
            estimated_resale_high=str(high) if high is not None else None,
            expected_net_profit=str(net) if net is not None else None,
            maximum_recommended_buy_price=str(maximum) if maximum is not None else None,
            expected_sale_time=None,
            sell_through_probability=None,
            confidence=None,
            travel_cost=str(travel) if travel is not None else None,
            risk_flags=flags,
            explanation=(
                "Supplied resale estimates; illustrative 10% fees, $0.70/mile round trip "
                "and $25 target margin. No empirical demand model."
            ),
            direct_listing_url=str(listing.direct_url),
            data_mode="fixture" if listing.source == "fixture" else "manual_estimate",
            score_components={
                "listing_age_priority": age_priority,
                "observed_price_drop": str(drop),
                "seller_motivation": motivation,
                "repost_detection": "unknown",
                "sell_through": None,
                "local_vs_national_demand": "unknown",
                "sale_time_range": None,
                "completeness": listing.accessories_complete,
                "counterfeit_risk": "unverified",
                "seller_reliability": None,
                "travel_economics": str(travel) if travel is not None else None,
                "seasonality": "unknown",
            },
        )


def import_listings(session, connector):
    imported = []
    # Validate and score the entire batch before persistence; never partial imports.
    prepared = [(item, MarketplaceScore().evaluate(item)) for item in connector.listings()]
    for item, estimate in prepared:
        row = session.scalar(
            select(MarketplaceListing).where(
                MarketplaceListing.source == item.source,
                MarketplaceListing.listing_id == item.listing_id,
            )
        )
        if row is not None:
            imported.append(row)
            continue
        row = MarketplaceListing(
            source=item.source,
            listing_id=item.listing_id,
            title=item.title,
            asking_price=item.asking_price,
            direct_url=str(item.direct_url),
            details=item.model_dump(mode="json"),
        )
        session.add(row)
        session.flush()
        session.add(MarketplaceAnalysis(listing_id=row.id, analysis=estimate))
        emit(
            session,
            "marketplace_opportunity_created",
            "marketplace",
            {"listing_id": str(row.id), "message": "Manual marketplace estimate: " + item.title},
        )
        imported.append(row)
    session.commit()
    return imported


def record_outcome(session, listing_id, outcome: MarketplaceOutcomeInput):
    listing = session.get(MarketplaceListing, listing_id)
    if listing is None:
        raise ValueError("Listing not found")
    if outcome.bought and outcome.acquisition_price is None:
        raise ValueError("Acquisition price required")
    if outcome.sale_price is not None and (not outcome.bought or not outcome.sale_date):
        raise ValueError("Sale requires purchase and sale date")
    if outcome.sale_date and outcome.listing_date and outcome.sale_date < outcome.listing_date:
        raise ValueError("Sale precedes listing")
    prediction = session.scalar(
        select(MarketplaceAnalysis)
        .where(MarketplaceAnalysis.listing_id == listing_id)
        .order_by(MarketplaceAnalysis.created_at.desc())
    )
    value = outcome.model_dump(mode="json")
    value.update(
        net_profit=str(
            money(
                outcome.sale_price - outcome.acquisition_price - outcome.fees - outcome.travel_cost
            )
        )
        if outcome.sale_price is not None
        else None,
        days_to_sell=(outcome.sale_date - outcome.listing_date).days
        if outcome.sale_date and outcome.listing_date
        else None,
        prediction=prediction.analysis if prediction else None,
    )
    row = session.scalar(
        select(MarketplaceOutcome).where(MarketplaceOutcome.listing_id == listing_id)
    )
    if row is None:
        row = MarketplaceOutcome(listing_id=listing_id)
        session.add(row)
    row.outcome = value
    session.commit()
    return row


def fixture_connector():
    return ManualJSONConnector(
        [
            dict(
                source="fixture",
                listing_id="phase3-desk",
                title="Test oak desk",
                description="Moving; accessories included",
                asking_price="80",
                original_price="120",
                listing_age_days=14,
                distance_miles="5",
                resale_low="150",
                resale_high="200",
                category="furniture",
                condition="used",
                accessories_complete=True,
                direct_url="https://example.com/fixture/desk",
            )
        ]
    )
