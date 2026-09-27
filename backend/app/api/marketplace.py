from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from app.api.intelligence import local_write
from app.api.routes import DbSession
from app.core.config import get_settings
from app.marketplace import pipeline as p
from app.marketplace.connectors import (
    CSVConnector,
    ManualJSONConnector,
    URLReferenceConnector,
    capabilities,
)
from app.models import MarketplaceListing
from app.models.marketplace import MarketplaceCalibrationRecord, MarketplaceNotification
from app.schemas.marketplace import (
    ComparableInput,
    HypotheticalInput,
    Input,
    ListingAction,
    ListingInput,
    PurchaseInput,
    SaleInput,
    SearchSettings,
)
from app.services.serialization import public

router = APIRouter(prefix="/marketplace", tags=["marketplace"])


def listing(session, identifier):
    row = session.get(MarketplaceListing, identifier)
    if row is None:
        raise HTTPException(404, "Marketplace listing not found")
    return row


def run(call):
    try:
        return call()
    except ValueError as exc:
        raise HTTPException(422, str(exc)[:500]) from exc


@router.get("/settings")
def settings(session: DbSession):
    return {
        **p.preferences(session).model_dump(mode="json"),
        "writes_enabled": get_settings().local_writes_enabled,
        "ai_status": "not_used",
        "vision_status": "unavailable",
    }


@router.put("/settings")
def save_settings(payload: SearchSettings, request: Request, session: DbSession):
    local_write(request)
    row = p.lock_writes(session)
    row.preferences = payload.model_dump(mode="json")
    session.commit()
    return settings(session)


@router.get("/connectors")
@router.get("/connectors/status")
def connectors():
    return capabilities()


@router.get("/listings")
def listings(
    session: DbSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0, le=10000)] = 0,
    sort: Literal[
        "freshness", "profit", "roi", "sell_through", "sale_time", "distance", "score"
    ] = "score",
    category: str | None = None,
    status: str | None = None,
    opportunities_only: bool = False,
):
    query = select(MarketplaceListing).order_by(MarketplaceListing.created_at.desc())
    if status:
        query = query.where(MarketplaceListing.status == status)
    rows = [p.listing_data(session, r) for r in session.scalars(query.limit(2000))]
    if category:
        rows = [r for r in rows if r["details"].get("category") == category]
    if opportunities_only:
        rows = [
            r
            for r in rows
            if r["active"]
            and r["status"] not in {"PASSED", "BOUGHT", "SOLD", "REMOVED", "EXPIRED"}
            and not r["duplicate_of_listing_id"]
        ]

    def key(row):
        a = row.get("analysis") or {}
        values = {
            "freshness": row["listing_age_minutes"],
            "profit": a.get("expected_net_profit"),
            "roi": a.get("roi_percent"),
            "sell_through": a.get("sell_through", {}).get("sell_through_probability_30d"),
            "sale_time": sum(a["sale_time"]["expected_days"]) / 2
            if a.get("sale_time", {}).get("expected_days")
            else None,
            "distance": row["details"].get("distance_miles"),
            "score": a.get("opportunity_score"),
        }
        value = values[sort]
        return (
            value is None,
            (float(value) if sort in {"freshness", "sale_time", "distance"} else -float(value))
            if value is not None
            else 0,
            row["id"],
        )

    rows.sort(key=key)
    return {
        "items": rows[offset : offset + limit],
        "total": len(rows),
        "limit": limit,
        "offset": offset,
        "scope": "Most recent 2,000 records; unknown values sort last",
    }


@router.post("/listings", status_code=201)
def create_listing(payload: ListingInput, request: Request, session: DbSession):
    local_write(request)
    p.lock_writes(session)
    row, _ = run(lambda: p.upsert(session, payload))
    session.commit()
    return p.listing_data(session, row, True)


@router.get("/listings/{identifier}")
def detail(identifier: UUID, session: DbSession):
    return p.listing_data(session, listing(session, identifier), True)


@router.put("/listings/{identifier}")
def update_listing(identifier: UUID, payload: ListingInput, request: Request, session: DbSession):
    local_write(request)
    p.lock_writes(session)
    row = listing(session, identifier)
    if payload.source != row.source or payload.source_listing_id != row.listing_id:
        raise HTTPException(422, "Source identity is immutable")
    row, _ = run(lambda: p.upsert(session, payload))
    session.commit()
    return p.listing_data(session, row, True)


class JSONImport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    listings: list = Field(max_length=100)
    dry_run: bool = True


class CSVImport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content: str = Field(max_length=1_000_000)
    dry_run: bool = True


class URLImport(Input):
    url: str = Field(max_length=2000)


@router.post("/import/url")
def url_import(payload: URLImport, request: Request):
    local_write(request)
    return run(lambda: URLReferenceConnector().capture(payload.url))


@router.post("/import/json")
def json_import(payload: JSONImport, request: Request, session: DbSession):
    local_write(request)
    return run(
        lambda: p.import_batch(session, ManualJSONConnector(payload.listings), payload.dry_run)
    )


@router.post("/import/csv")
def csv_import(payload: CSVImport, request: Request, session: DbSession):
    local_write(request)
    return run(lambda: p.import_batch(session, CSVConnector(payload.content), payload.dry_run))


@router.post("/listings/{identifier}/comps")
def add_comp(identifier: UUID, payload: ComparableInput, request: Request, session: DbSession):
    local_write(request)
    p.lock_writes(session)
    row = listing(session, identifier)
    item = p.normalized(row)
    item.comps = [payload]
    p.persist_evidence(session, row, item, datetime.now(UTC))
    p.evaluate(session, row)
    session.commit()
    return p.listing_data(session, row, True)


@router.post("/listings/{identifier}/bought")
def bought(identifier: UUID, payload: PurchaseInput, request: Request, session: DbSession):
    local_write(request)
    return run(lambda: p.record_purchase(session, listing(session, identifier), payload))


@router.post("/listings/{identifier}/sold")
def sold(identifier: UUID, payload: SaleInput, request: Request, session: DbSession):
    local_write(request)
    return run(lambda: p.record_sale(session, listing(session, identifier), payload))


@router.post("/listings/{identifier}/hypothetical")
def hypothetical(
    identifier: UUID, payload: HypotheticalInput, request: Request, session: DbSession
):
    local_write(request)
    p.lock_writes(session)
    row = listing(session, identifier)
    if not row.details.get("would_have_bought") or row.status != "PASSED":
        raise HTTPException(422, "Mark a passed listing would-have-bought first")
    if payload.sold and (
        payload.days_to_sell is None or payload.days_to_sell > payload.observation_days
    ):
        raise HTTPException(422, "Sold hypothesis requires observed days to sell")
    metrics = p.calibration_metrics(
        row.details.get("passed_prediction"),
        payload.actual_sale_price,
        None,
        payload.days_to_sell,
        payload.sold,
        payload.observation_days,
        row.details.get("category", "unknown"),
        row.source,
    )
    metrics["evidence_source"] = payload.source
    record = session.scalar(
        select(MarketplaceCalibrationRecord).where(
            MarketplaceCalibrationRecord.listing_id == row.id,
            MarketplaceCalibrationRecord.hypothetical.is_(True),
        )
    )
    if record:
        record.metrics = metrics
    else:
        session.add(
            MarketplaceCalibrationRecord(listing_id=row.id, hypothetical=True, metrics=metrics)
        )
    session.commit()
    return {"hypothetical": True, "metrics": metrics}


@router.post("/listings/{identifier}/{action}")
def action(
    identifier: UUID,
    action: Literal["track", "pass", "contacted", "reviewing"],
    payload: ListingAction,
    request: Request,
    session: DbSession,
):
    local_write(request)
    return run(lambda: p.record_action(session, listing(session, identifier), action, payload))


@router.get("/inventory")
def inventory(session: DbSession):
    return p.inventory_data(session)


@router.post("/inventory/refresh")
def refresh_inventory(request: Request, session: DbSession):
    local_write(request)
    return p.inventory_data(session, refresh=True)


@router.get("/performance")
def performance(session: DbSession):
    return p.performance(session)


@router.get("/calibration")
def calibration(session: DbSession):
    return p.MarketplaceCalibrationService().summary(session)


@router.get("/notifications")
def notifications(session: DbSession):
    return public(
        session.scalars(
            select(MarketplaceNotification)
            .order_by(MarketplaceNotification.created_at.desc())
            .limit(30)
        ).all()
    )


def development(request):
    local_write(request)
    if not get_settings().enable_development_actions:
        raise HTTPException(404, "Development actions disabled")


@router.post("/dev/fixture")
def demo_fixture(request: Request, session: DbSession):
    development(request)
    from app.marketplace.fixtures import fixtures

    return p.import_batch(session, ManualJSONConnector(fixtures()))


class DemoListing(Input):
    listing_id: UUID


@router.post("/dev/price-drop")
def demo_price_drop(payload: DemoListing, request: Request, session: DbSession):
    development(request)
    from decimal import Decimal

    p.lock_writes(session)
    row = listing(session, payload.listing_id)
    if row.source != "fixture":
        raise HTTPException(422, "Only explicitly fictional fixture listings can be demonstrated")
    item = p.normalized(row).model_dump(mode="json")
    item.update(
        asking_price=str((row.asking_price * Decimal(".9")).quantize(Decimal(".01"))),
        observed_at=None,
    )
    p.upsert(session, ListingInput.model_validate(item))
    session.commit()
    return p.listing_data(session, row, True)


@router.post("/dev/sale")
def demo_sale(payload: DemoListing, request: Request, session: DbSession):
    development(request)
    from datetime import timedelta

    row = listing(session, payload.listing_id)
    if row.source != "fixture":
        raise HTTPException(422, "Only explicitly fictional fixture listings can be demonstrated")
    result = p.record_purchase(
        session,
        row,
        PurchaseInput(
            purchase_price=row.asking_price, purchase_date=datetime.now(UTC) - timedelta(days=5)
        ),
    )
    value = result["analysis"]["conservative_resale_value"]
    if value is None:
        raise HTTPException(422, "Fixture needs a supplied comparable")
    return p.record_sale(session, row, SaleInput(sale_price=value, sale_date=datetime.now(UTC)))
