"""Forward migration preservation and native Marketplace workflow in a NEW disposable PG DB."""

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import MetaData, inspect, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database.seed import seed_agents
from app.database.session import get_engine
from app.marketplace.connectors import CSVConnector, ManualJSONConnector
from app.marketplace.fixtures import fixtures
from app.marketplace.pipeline import import_batch, listing_data, record_purchase, record_sale
from app.models import Agent, MarketplaceListing
from app.schemas.marketplace import PurchaseInput, SaleInput
from app.services.serialization import public


def main():
    settings = get_settings()
    url = make_url(settings.database_url.get_secret_value())
    if not (url.database or "").startswith("ai_farm_phase5_verify") or settings.ai_enabled:
        raise RuntimeError("Requires a dedicated ai_farm_phase5_verify* DB with AI disabled")
    engine = get_engine()
    if inspect(engine).get_table_names():
        raise RuntimeError(
            "Use a NEW empty verification database; existing records are never deleted"
        )
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    command.upgrade(config, "0003")
    with Session(engine) as session:
        seed_agents(session, settings)
    metadata = MetaData()
    metadata.reflect(bind=engine)
    original_id = uuid4()
    with engine.begin() as connection:
        connection.execute(
            metadata.tables["marketplace_listings"]
            .insert()
            .values(
                id=original_id,
                source="manual",
                listing_id="prior-phase-listing",
                title="Prior record",
                asking_price=Decimal("80"),
                direct_url="https://example.com/prior",
                details={"category": "furniture"},
            )
        )
        before = {
            name: sorted(
                [
                    json.dumps(public(dict(r)), sort_keys=True)
                    for r in connection.execute(select(table)).mappings()
                ]
            )
            for name, table in metadata.tables.items()
            if name != "alembic_version"
        }
    command.upgrade(config, "head")
    command.check(config)
    with engine.connect() as connection:
        after = {
            name: sorted(
                [
                    json.dumps(public(dict(r)), sort_keys=True)
                    for r in connection.execute(select(table)).mappings()
                ]
            )
            for name, table in metadata.tables.items()
            if name != "alembic_version"
        }
    assert before == after, "Preexisting columns changed"
    with Session(engine) as session:
        old = session.get(MarketplaceListing, original_id)
        assert listing_data(session, old, True)["price_history"][0]["price"] == "80.00"
        before_agents = public(session.scalars(select(Agent).order_by(Agent.name)).all())
        rows = fixtures()
        report = import_batch(session, ManualJSONConnector(rows))
        assert report["created"] == 10 and not report["errors"]
        assert report["results"][3]["duplicate_of_listing_id"]
        from uuid import UUID

        row = session.get(MarketplaceListing, UUID(report["results"][0]["id"]))
        import_batch(session, ManualJSONConnector([{**rows[0], "asking_price": "150"}]))
        assert listing_data(session, row)["analysis"]["price_history_summary"]["drop_count"] == 1
        csv = (
            "source_listing_id,source_url,title,asking_price\n"
            "csv-native,https://example.com/csv,Native CSV,50\n"
        )
        assert import_batch(session, CSVConnector(csv), dry_run=True)["created"] == 1
        purchase_time = datetime.now(UTC)
        record_purchase(
            session,
            row,
            PurchaseInput(purchase_price=100, purchase_date=purchase_time, travel_cost=5),
        )
        sale_time = datetime.now(UTC)
        value = record_sale(
            session, row, SaleInput(sale_price=200, sale_date=sale_time, platform_fees=20)
        )
        assert value["outcome"]["outcome"]["net_profit"] == "75.00"
        assert public(session.scalars(select(Agent).order_by(Agent.name)).all()) == before_agents
    print(
        "PASS: 0003→0004 preserved every old column; metadata parity; legacy price backfill; "
        "10 fixtures; duplicate; price drop; CSV dry run; bought/sold costs; agents unchanged"
    )


if __name__ == "__main__":
    main()
