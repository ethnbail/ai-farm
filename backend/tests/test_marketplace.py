from datetime import UTC, datetime, timedelta
from decimal import Decimal as D

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select

from app.core.config import get_settings
from app.marketplace.analysis import (
    CounterfeitRiskAnalyzer,
    DemandComparisonService,
    ItemCompletenessAnalyzer,
    MarketplaceDuplicateDetector,
    MarketplaceValuationService,
    SaleTimeEstimator,
    SeasonalityService,
    SellerMotivationAnalyzer,
    SellerReliabilityAnalyzer,
    SellThroughEstimator,
    TravelEconomicsService,
    analyze,
    freshness,
)
from app.marketplace.connectors import (
    CSVConnector,
    ManualJSONConnector,
    URLReferenceConnector,
    capabilities,
)
from app.marketplace.fixtures import fixtures
from app.marketplace.pipeline import (
    MarketplaceCalibrationService,
    aging,
    calibration_metrics,
    import_batch,
    inventory_data,
    record_action,
    record_purchase,
    record_sale,
)
from app.models import Agent, MarketplaceListing, SystemEvent, Trade
from app.models.marketplace import (
    MarketplaceCalibrationRecord,
    MarketplaceNotification,
    MarketplacePriceHistory,
)
from app.schemas.marketplace import (
    DemandInput,
    ListingAction,
    ListingInput,
    PurchaseInput,
    SaleInput,
    SearchSettings,
)

NOW = datetime(2026, 1, 15, 12, tzinfo=UTC)
ORIGIN = {"Origin": "http://localhost:3000"}


def example(**overrides):
    return ListingInput.model_validate({**fixtures(NOW)[0], **overrides})


def imported(session, **overrides):
    report = import_batch(
        session, ManualJSONConnector([example(**overrides).model_dump(mode="json")])
    )
    from uuid import UUID

    return session.get(MarketplaceListing, UUID(report["results"][0]["id"]))


@pytest.mark.parametrize(
    "minutes,bucket",
    [
        (0, "NEW"),
        (14, "NEW"),
        (15, "VERY_FRESH"),
        (60, "FRESH"),
        (360, "RECENT"),
        (1440, "AGING"),
        (4320, "OLD"),
    ],
)
def test_freshness_boundaries(minutes, bucket):
    item = example(listed_at=NOW - timedelta(minutes=minutes))
    assert freshness(item, NOW, SearchSettings(), NOW)["bucket"] == bucket


@pytest.mark.parametrize(
    "overrides",
    [
        {"source_url": "javascript:alert(1)"},
        {"source_url": "https://user:secret@example.com/x"},
        {"asking_price": "NaN"},
        {"asking_price": "-1"},
        {"zip_code": "abc"},
        {"currency": "EUR"},
        {"listed_at": "2026-01-01T12:00:00"},
        {"raw_source_metadata": {"cookie": "secret"}},
        {"seller_profile_metadata": {"phone": "secret"}},
        {"item_metadata": {"accessories": []}},
        {"seller_profile_metadata": {"red_flags": "bad"}},
        {"latitude": 10},
        {"image_metadata": [{"url": "file:///etc/passwd"}]},
    ],
)
def test_normalization_rejects_unsafe_or_invalid_data(overrides):
    with pytest.raises(ValidationError):
        example(**overrides)


def test_text_sanitized_and_url_is_not_fetched():
    item = example(title="<b>Console</b>\x00")
    assert item.title == "Console"
    value = URLReferenceConnector().capture("https://example.com/listing")
    assert value["extracted"] is False and value["requires_manual_details"] is True
    assert all(not c["supports_refresh"] for c in capabilities())


def test_settings_ranges_and_thresholds():
    for invalid in [
        dict(min_asking_price=30, max_asking_price=10),
        dict(freshness_minutes=[15, 10, 60, 100, 200]),
        dict(platform_fee_percent=90, payment_fee_percent=10),
        dict(zip_code="123"),
    ]:
        with pytest.raises(ValidationError):
            SearchSettings(**invalid)


def test_valuation_matching_and_no_comps():
    item = example()
    value = MarketplaceValuationService().evaluate(item, NOW)
    assert value["comp_count"] == 5 and value["conservative_resale_value"] == "305.00"
    assert (
        MarketplaceValuationService().evaluate(example(comps=[]), NOW)["conservative_resale_value"]
        is None
    )
    item.comps[0].sold = False
    item.comps[1].model = "wrong"
    item.comps[2].condition = "new"
    assert MarketplaceValuationService().evaluate(item, NOW)["comp_count"] == 2


def test_motivation_and_unknown_seller_are_not_personal_inferences():
    assert SellerMotivationAnalyzer().evaluate(example(), 2)["motivation_score"] > 50
    result = SellerReliabilityAnalyzer().evaluate(
        example(seller_rating=None, seller_review_count=None)
    )
    assert result["reliability_score"] is None and result["risk_flags"] == []
    risky = SellerReliabilityAnalyzer().evaluate(
        example(description="gift card deposit before viewing")
    )
    assert len(risky["risk_flags"]) == 2


def test_completeness_and_counterfeit():
    assert ItemCompletenessAnalyzer().evaluate(example())["completeness_score"] == 100
    missing = ItemCompletenessAnalyzer().evaluate(
        example(item_metadata={"accessories": {"controller": False}})
    )
    assert missing["completeness_score"] is None and missing["replacement_reserve"] == "35.00"
    risky = example(category="luxury", asking_price=20, description="replica", item_metadata={})
    assert (
        CounterfeitRiskAnalyzer().evaluate(risky, {"conservative_resale_value": "300"})["risk"]
        == "HIGH"
    )
    assert (
        CounterfeitRiskAnalyzer().evaluate(
            example(item_metadata={}), {"conservative_resale_value": None}
        )["risk"]
        == "UNKNOWN"
    )


def test_true_sell_through_requires_denominator_and_completed_windows():
    missing = SellThroughEstimator().evaluate(example(demand=[]), NOW)
    assert missing["sell_through_probability_30d"] is None
    result = SellThroughEstimator().evaluate(example(), NOW)
    assert result["sell_through_probability_7d"] == round(61 / 102, 4)
    assert result["sell_through_probability_7d"] <= result["sell_through_probability_30d"]
    assert SaleTimeEstimator().evaluate(result)["expected_days"] == [0, 7]
    for extra in [{"sold_7d": 101}, {"sold_14d": 10}, {"observation_days": 6}]:
        with pytest.raises(ValidationError):
            DemandInput.model_validate({**example().demand[0].model_dump(), **extra})


def test_demand_and_seasonality_do_not_invent_missing_evidence():
    assert (
        DemandComparisonService().evaluate(example(), NOW)["recommended_market_type"] == "UNKNOWN"
    )
    season = SeasonalityService().evaluate("heater", SearchSettings(hemisphere="northern"), NOW)
    assert season["seasonal_multiplier"] == 1.1 and season["confidence"] == "low"
    assert (
        SeasonalityService().evaluate("heater", SearchSettings(), NOW)["seasonal_multiplier"] == 1
    )


def test_travel_net_profit_and_advisory_maximum_exact_math():
    item = example()
    settings = SearchSettings()
    result = analyze(item, settings, NOW, [170], NOW)
    # lower quartile 305, 10% fees, 6 round-trip miles at .70, purchase 170
    assert result["travel_cost"] == "4.20"
    assert result["expected_net_profit"] == "100.30"
    assert D(result["max_buy_price"]) <= D("305") * D(".9") - D("4.20") - 25
    assert result["tier"] == "STRONG_CANDIDATE"
    assert (
        analyze(example(distance_miles=None), settings, NOW, [170], NOW)["expected_net_profit"]
        is None
    )
    assert (
        TravelEconomicsService().evaluate(example(distance_miles=0), settings)["travel_cost"]
        == "0.00"
    )


def test_duplicate_requires_specific_evidence_and_suppresses_freshness():
    a = example()
    b = example(source_listing_id="second")
    assert MarketplaceDuplicateDetector().compare(a, b)["likely_duplicate"]
    b.seller_id = "different"
    assert not MarketplaceDuplicateDetector().compare(a, b)["likely_duplicate"]
    value = analyze(a, SearchSettings(), NOW, [170], NOW, True, NOW - timedelta(days=20))
    assert value["scoring"]["component_scores"]["freshness"] == 0
    assert value["tier"] != "STRONG_CANDIDATE"


def test_risk_adjusted_buy_limit_and_high_risk_suppression():
    value = analyze(example(), SearchSettings(), NOW, [170], NOW)
    assert D(value["risk_buffer_percent_effective"]) > 10
    risky = example(description="replica gift card only", asking_price=20)
    value = analyze(risky, SearchSettings(), NOW, [20], NOW)
    assert value["counterfeit"]["risk"] == "HIGH"
    assert value["max_buy_price"] is None and value["tier"] == "REJECT"


def test_calibration_right_censoring_and_resolved_sale_windows():
    prediction = {"sell_through": {f"sell_through_probability_{n}d": 0.6 for n in [7, 14, 30, 60]}}
    pending = calibration_metrics(prediction, None, None, 10, False, 10, "gaming", "manual")
    assert set(pending["probabilities"]) == {"7"}
    assert pending["probabilities"]["7"]["actual"] == 0
    sold = calibration_metrics(prediction, 200, 70, 10, True, 10, "gaming", "manual")
    assert set(sold["probabilities"]) == {"7", "14", "30", "60"}
    assert sold["probabilities"]["7"]["actual"] == 0
    assert sold["probabilities"]["14"]["actual"] == 1


def test_backdated_purchase_has_no_retrospective_forecast(session):
    row = imported(session, source="manual")
    result = record_purchase(session, row, PurchaseInput(purchase_price=100, purchase_date=NOW))
    assert result["inventory"]["purchase"]["prediction"] == {}


def test_fixture_outcomes_excluded_from_actual_calibration(session):
    row = imported(session)
    record_purchase(session, row, PurchaseInput(purchase_price=100, purchase_date=NOW))
    record_sale(session, row, SaleInput(sale_price=200, sale_date=NOW + timedelta(days=1)))
    result = MarketplaceCalibrationService().summary(session)
    assert result["sample_size"] == 0 and result["fixture_sample_size"] == 1


def test_ranking_limits_and_missing_evidence():
    for changes in [dict(distance_miles=90), dict(comps=[]), dict(category="excluded")]:
        value = analyze(
            example(**changes), SearchSettings(excluded_categories=["excluded"]), NOW, [170], NOW
        )
        assert value["tier"] != "STRONG_CANDIDATE" and value["reasoning"]


def test_import_partial_success_dry_run_price_history_and_duplicate(session):
    now = datetime.now(UTC)
    items = fixtures(now)
    report = import_batch(session, ManualJSONConnector([items[0], {"title": "invalid"}]), True)
    assert report["created"] == 1 and len(report["errors"]) == 1
    assert session.scalar(select(func.count()).select_from(MarketplaceListing)) == 0
    assert session.scalar(select(func.count()).select_from(SystemEvent)) == 0
    result = import_batch(session, ManualJSONConnector([items[0], items[3], {"asking_price": -2}]))
    assert result["created"] == 2 and result["results"][1]["duplicate_of_listing_id"]
    update = {**items[0], "asking_price": "150"}
    import_batch(session, ManualJSONConnector([update]))
    event_types = session.scalars(select(SystemEvent.event_type)).all()
    assert event_types.count("marketplace_opportunity_created") == 1
    assert (
        "marketplace_price_drop" in event_types and "marketplace_duplicate_detected" in event_types
    )
    assert session.scalar(select(func.count()).select_from(MarketplacePriceHistory)) == 3
    before = session.scalar(select(func.count()).select_from(MarketplaceNotification))
    import_batch(session, ManualJSONConnector([update]))
    assert session.scalar(select(func.count()).select_from(MarketplaceNotification)) == before


def test_outdated_observation_does_not_overwrite(session):
    row = imported(session)
    report = import_batch(
        session,
        ManualJSONConnector([example(asking_price=2, observed_at=NOW).model_dump(mode="json")]),
    )
    assert report["errors"] and session.get(MarketplaceListing, row.id).asking_price == 170


def test_csv_partial_rows_and_size_limits(session):
    text = "source_listing_id,source_url,title,asking_price\ncsv-1,https://example.com/csv,Test,80\ninvalid,javascript:bad,Nope,-1\n"
    result = import_batch(session, CSVConnector(text))
    assert result["created"] == 1 and len(result["errors"]) == 1
    for payload in [None, [{}] * 101]:
        with pytest.raises(ValueError):
            ManualJSONConnector(payload)
    with pytest.raises(ValueError):
        CSVConnector("x" * 1_000_001)


def test_connector_failure_cannot_save_partial_data(session):
    class FailedConnector:
        def rows(self):
            raise ValueError("Connector unavailable")

    with pytest.raises(ValueError, match="Connector unavailable"):
        import_batch(session, FailedConnector())
    session.rollback()
    assert session.scalar(select(func.count()).select_from(MarketplaceListing)) == 0
    assert session.scalar(select(func.count()).select_from(SystemEvent)) == 0


def test_bought_sold_calibration_exact_costs_and_no_agent_mutations(session):
    row = imported(session, source="manual")
    agents_before = session.scalars(select(Agent)).all()
    purchase = PurchaseInput(
        purchase_price=100, purchase_date=NOW, travel_cost=5, repair_cost=10, other_costs=2
    )
    record_purchase(session, row, purchase)
    record_purchase(session, row, purchase)  # Idempotent duplicate click.
    with pytest.raises(ValueError):
        record_action(session, row, "pass", ListingAction())
    sale = SaleInput(
        sale_price=200,
        sale_date=NOW + timedelta(days=10),
        platform_fees=20,
        shipping_cost=10,
        payment_fees=3,
        other_costs=2,
    )
    value = record_sale(session, row, sale)
    assert value["outcome"]["outcome"]["net_profit"] == "48.00"
    assert value["outcome"]["outcome"]["days_to_sell"] == 10
    assert row.status == "SOLD" and not row.active and inventory_data(session) == []
    record_sale(session, row, sale)
    assert session.scalar(select(func.count()).select_from(MarketplaceCalibrationRecord)) == 1
    assert MarketplaceCalibrationService().summary(session)["status"] == "insufficient_sample"
    assert session.scalars(select(Agent)).all() == agents_before
    assert session.scalar(select(func.count()).select_from(Trade)) == 0


def test_sale_rejects_without_purchase_or_invalid_dates(session):
    row = imported(session)
    with pytest.raises(ValueError):
        record_sale(session, row, SaleInput(sale_price=200, sale_date=NOW))
    record_purchase(session, row, PurchaseInput(purchase_price=100, purchase_date=NOW))
    with pytest.raises(ValueError):
        record_sale(session, row, SaleInput(sale_price=200, sale_date=NOW - timedelta(days=1)))


def test_inventory_aging_and_unsold_calibration(session):
    row = imported(session)
    record_purchase(
        session,
        row,
        PurchaseInput(purchase_price=100, purchase_date=datetime.now(UTC) - timedelta(days=100)),
    )
    inventory = inventory_data(session, refresh=True)
    assert inventory[0]["aging_status"] == "DEAD_INVENTORY"
    assert "marketplace_inventory_aging" in session.scalars(select(SystemEvent.event_type)).all()
    inventory_data(session, refresh=True)
    assert session.scalar(select(func.count()).select_from(MarketplaceCalibrationRecord)) == 1
    assert aging(30, SearchSettings()) == "AGING"


def test_api_write_gate_settings_and_manual_flow(client, monkeypatch):
    data = fixtures(datetime.now(UTC))[0]
    assert client.post("/api/marketplace/listings", json=data, headers=ORIGIN).status_code == 403
    monkeypatch.setenv("LOCAL_WRITES_ENABLED", "true")
    get_settings.cache_clear()
    assert client.post("/api/marketplace/listings", json=data).status_code == 403
    response = client.post("/api/marketplace/listings", json=data, headers=ORIGIN)
    assert response.status_code == 201, response.text
    identifier = response.json()["id"]
    for action, expected in [("track", "TRACKING"), ("contacted", "CONTACTED"), ("pass", "PASSED")]:
        result = client.post(
            f"/api/marketplace/listings/{identifier}/{action}", json={}, headers=ORIGIN
        )
        assert result.json()["status"] == expected
    settings = SearchSettings(zip_code="94103", radius_miles=15).model_dump(mode="json")
    assert client.put("/api/marketplace/settings", json=settings, headers=ORIGIN).status_code == 200
    assert client.get("/api/marketplace/settings").json()["radius_miles"] == 15
    assert client.get("/api/marketplace/listings?sort=profit").json()["total"] == 1
    assert client.get("/api/marketplace/calibration").json()["sample_size"] == 0
    assert client.get("/api/marketplace/opportunities").status_code == 200
    assert client.post("/api/marketplace/dev/fixture", headers=ORIGIN).status_code == 404


def test_api_imports_limits_missing_data_and_ai_disabled(client, monkeypatch):
    monkeypatch.setenv("LOCAL_WRITES_ENABLED", "true")
    get_settings.cache_clear()
    result = client.post(
        "/api/marketplace/import/json",
        json={
            "listings": [
                {
                    "source_listing_id": "x",
                    "source_url": "https://example.com/x",
                    "title": "Unknown",
                    "asking_price": "80",
                }
            ],
            "dry_run": False,
        },
        headers=ORIGIN,
    )
    assert result.status_code == 200 and result.json()["created"] == 1
    data = client.get("/api/marketplace/listings").json()["items"][0]
    assert data["analysis"]["expected_net_profit"] is None
    assert data["analysis"]["ai_status"] == "not_used"
    assert (
        client.post(
            "/api/marketplace/import/url",
            json={"url": "https://example.com/reference"},
            headers=ORIGIN,
        ).json()["extracted"]
        is False
    )
    assert (
        client.post(
            "/api/marketplace/import/csv",
            json={
                "content": "source_listing_id,source_url,title,asking_price\ny,https://example.com/y,Manual,40\n",
                "dry_run": True,
            },
            headers=ORIGIN,
        ).json()["created"]
        == 1
    )
    huge = client.post("/api/marketplace/import/csv", content=b"x" * 1_100_001, headers=ORIGIN)
    assert huge.status_code == 413
