"""Transactional listing evidence and user-recorded lifecycle; never purchases anything."""

import hashlib
from datetime import UTC, datetime
from decimal import Decimal as D
from statistics import mean

from pydantic import ValidationError
from sqlalchemy import select

from app.core.config import get_settings
from app.marketplace.analysis import MarketplaceDuplicateDetector, analyze, cash, freshness
from app.marketplace.connectors import validate_row
from app.models import MarketplaceAnalysis, MarketplaceListing, MarketplaceOutcome
from app.models.marketplace import (
    MarketplaceCalibrationRecord,
    MarketplaceComparable,
    MarketplaceDemandSnapshot,
    MarketplaceDuplicateMatch,
    MarketplaceInventoryItem,
    MarketplaceNotification,
    MarketplacePriceHistory,
    MarketplaceSellerProfile,
    MarketplaceSettings,
)
from app.schemas.marketplace import ListingInput, SearchSettings
from app.services.event_context import aware
from app.services.event_store import emit
from app.services.serialization import public


def preferences(session):
    config = get_settings()
    defaults = dict(
        zip_code=config.marketplace_default_zip or None,
        radius_miles=config.marketplace_default_radius_miles,
        min_expected_profit=config.marketplace_min_expected_profit,
        min_roi_percent=config.marketplace_min_roi_percent,
        max_pickup_miles=config.marketplace_max_pickup_miles,
        max_pickup_time_minutes=config.marketplace_max_pickup_time_minutes,
        cost_per_mile=config.marketplace_cost_per_mile,
        freshness_minutes=[
            15,
            config.marketplace_fresh_minutes,
            360,
            config.marketplace_recent_hours * 60,
            4320,
        ],
        strong_score_threshold=config.marketplace_strong_score_threshold,
    )
    row = session.get(MarketplaceSettings, 1)
    return SearchSettings.model_validate({**defaults, **(row.preferences if row else {})})


def lock_writes(session):
    # Single-user local app: serialize Marketplace mutations and event/notification dedup in PG.
    row = session.scalar(
        select(MarketplaceSettings).where(MarketplaceSettings.id == 1).with_for_update()
    )
    if row is None:
        raise ValueError("Run Marketplace migrations before writing")
    return row


def notice(session, listing, event_type, message, fingerprint, severity="INFO", now=None):
    now = now or datetime.now(UTC)
    key = hashlib.sha256(f"{listing.id}:{event_type}:{fingerprint}".encode()).hexdigest()
    exists = session.scalar(
        select(MarketplaceNotification.id).where(MarketplaceNotification.dedup_key == key)
    )
    if exists:
        return False
    # No title/seller payload dump into the event stream.
    session.add(
        MarketplaceNotification(
            listing_id=listing.id,
            severity=severity,
            event_type=event_type,
            dedup_key=key,
            message=message[:500],
            created_at=now,
        )
    )
    emit(
        session,
        event_type,
        "marketplace",
        {"listing_id": str(listing.id), "severity": severity, "message": message[:500]},
    )
    session.flush()
    return True


def normalized(row, session=None):
    details = {k: v for k, v in row.details.items() if k in ListingInput.model_fields}
    details.update(
        source=row.source,
        source_listing_id=row.listing_id,
        source_url=row.direct_url,
        title=row.title,
        asking_price=str(row.asking_price),
        active=row.active,
        listed_at=public(row.listed_at) if row.listed_at else details.get("listed_at"),
    )
    if session is not None:
        details["comps"] = [
            r.evidence
            for r in session.scalars(
                select(MarketplaceComparable).where(MarketplaceComparable.listing_id == row.id)
            )
        ]
        observations = session.scalars(
            select(MarketplaceDemandSnapshot)
            .where(MarketplaceDemandSnapshot.listing_id == row.id)
            .order_by(MarketplaceDemandSnapshot.created_at.desc())
        ).all()
        markets = {}
        for item in observations:
            markets.setdefault(item.evidence["market"], item.evidence)
        details["demand"] = list(markets.values())
    return ListingInput.model_validate(details)


def price_history(session, identifier):
    return session.scalars(
        select(MarketplacePriceHistory)
        .where(MarketplacePriceHistory.listing_id == identifier)
        .order_by(
            MarketplacePriceHistory.observed_at,
            MarketplacePriceHistory.created_at,
            MarketplacePriceHistory.id,
        )
    ).all()


def latest_analysis(session, identifier):
    return session.scalar(
        select(MarketplaceAnalysis)
        .where(MarketplaceAnalysis.listing_id == identifier)
        .order_by(MarketplaceAnalysis.created_at.desc(), MarketplaceAnalysis.id.desc())
        .limit(1)
    )


def evaluate(session, row, now=None, persist=True):
    now = now or datetime.now(UTC)
    listing = normalized(row, session)
    history = price_history(session, row.id)
    settings = preferences(session)
    value = analyze(
        listing,
        settings,
        row.first_seen_at or row.created_at,
        [h.price for h in history],
        now,
        bool(row.duplicate_of_listing_id),
        row.first_known_post if row.duplicate_of_listing_id else None,
    )
    last_drop = next(
        (b.observed_at for a, b in reversed(list(zip(history, history[1:]))) if b.price < a.price),
        None,
    )
    value["price_history_summary"]["minutes_since_last_drop"] = (
        round((now - aware(last_drop)).total_seconds() / 60, 1) if last_drop else None
    )
    stale = (
        now - aware(row.last_seen_at or row.created_at)
    ).total_seconds() > settings.stale_after_hours * 3600
    value["listing_stale"] = stale
    if stale:
        value["risk_flags"].append(
            "Listing observation stale; manually confirm price and availability"
        )
        if value["tier"] == "STRONG_CANDIDATE":
            value["tier"] = value["scoring"]["tier"] = "REVIEW"
        value["reasoning"].append("Stale listing observation")
    if persist:
        session.add(MarketplaceAnalysis(listing_id=row.id, analysis=value, created_at=now))
        # Analysis updates are internally throttled to one notification per 15-minute bucket.
        bucket = int(now.timestamp() // 900)
        notice(
            session,
            row,
            "marketplace_analysis_updated",
            f"Analysis refreshed: {row.title}",
            bucket,
            now=now,
        )
        if value["tier"] == "STRONG_CANDIDATE" and row.status not in {
            "PASSED",
            "BOUGHT",
            "SOLD",
            "REMOVED",
            "EXPIRED",
        }:
            notice(
                session,
                row,
                "marketplace_strong_candidate",
                f"Review strong candidate: {row.title}",
                f"{row.asking_price}:{bucket}",
                "IMPORTANT",
                now,
            )
    return value


def persist_evidence(session, row, item, now):
    for model, supplied in [
        (MarketplaceComparable, item.comps),
        (MarketplaceDemandSnapshot, item.demand),
    ]:
        existing = [
            r.evidence for r in session.scalars(select(model).where(model.listing_id == row.id))
        ]
        for comp in supplied:
            evidence = comp.model_dump(mode="json")
            if evidence not in existing:
                session.add(model(listing_id=row.id, evidence=evidence, created_at=now))
                existing.append(evidence)
    if item.seller_id:
        seller = session.scalar(
            select(MarketplaceSellerProfile).where(
                MarketplaceSellerProfile.source == item.source,
                MarketplaceSellerProfile.source_seller_id == item.seller_id,
            )
        )
        profile = {
            "rating": str(item.seller_rating) if item.seller_rating is not None else None,
            "review_count": item.seller_review_count,
            "joined_date": public(item.seller_joined_date),
            "metadata": item.seller_profile_metadata,
            "observed_at": now.isoformat(),
        }
        if seller:
            seller.profile = profile
        else:
            session.add(
                MarketplaceSellerProfile(
                    source=item.source, source_seller_id=item.seller_id, profile=profile
                )
            )
    session.flush()


def upsert(session, item: ListingInput, now=None):
    now = now or datetime.now(UTC)
    observed = item.observed_at or now
    row = session.scalar(
        select(MarketplaceListing).where(
            MarketplaceListing.source == item.source,
            MarketplaceListing.listing_id == item.source_listing_id,
        )
    )
    created = row is None
    previous_price = row.asking_price if row else None
    if row and row.last_seen_at and observed < aware(row.last_seen_at):
        raise ValueError("Observation predates last seen; current price was not overwritten")
    if row:
        previous = normalized(row).model_dump(mode="json")
        previous.update(item.model_dump(mode="json", exclude_unset=True))
        item = ListingInput.model_validate(previous)
    if not row:
        row = MarketplaceListing(
            source=item.source,
            listing_id=item.source_listing_id,
            title=item.title,
            asking_price=item.asking_price,
            direct_url=item.source_url,
            details={},
            first_seen_at=observed,
            first_known_post=item.listed_at or observed,
            created_at=now,
            status="NEW",
            active=item.active,
        )
        session.add(row)
        session.flush()
    row.title, row.asking_price, row.direct_url = item.title, item.asking_price, item.source_url
    lifecycle = {
        k: row.details[k] for k in ["would_have_bought", "passed_prediction"] if k in row.details
    }
    row.details = {**item.model_dump(mode="json", exclude={"comps", "demand"}), **lifecycle}
    row.listed_at = item.listed_at
    row.last_seen_at, row.updated_at, row.active = observed, now, item.active
    if not item.active and row.status not in {"BOUGHT", "SOLD", "PASSED"}:
        row.status = "REMOVED"
    if not row.first_seen_at:
        row.first_seen_at = row.created_at
    if not row.first_known_post:
        row.first_known_post = item.listed_at or row.first_seen_at
    # Every user-observed price is retained, even when unchanged. Original advertised
    # price is not fabricated history.
    session.add(
        MarketplacePriceHistory(
            listing_id=row.id, price=item.asking_price, observed_at=observed, created_at=now
        )
    )
    persist_evidence(session, row, item, now)
    if created:
        candidates = session.scalars(
            select(MarketplaceListing)
            .where(MarketplaceListing.id != row.id)
            .order_by(MarketplaceListing.created_at)
            .limit(2000)
        ).all()
        for candidate in candidates:
            match = MarketplaceDuplicateDetector().compare(item, normalized(candidate))
            if not match["likely_duplicate"]:
                continue
            root = (
                session.get(MarketplaceListing, candidate.duplicate_of_listing_id)
                if candidate.duplicate_of_listing_id
                else candidate
            )
            row.duplicate_of_listing_id = root.id
            row.repost_probability = D(str(match["probability"]))
            root.repost_count += 1
            row.repost_count = root.repost_count
            row.first_known_post = (
                root.first_known_post or root.listed_at or root.first_seen_at or root.created_at
            )
            session.add(
                MarketplaceDuplicateMatch(
                    listing_id=row.id, candidate_id=candidate.id, evidence=match
                )
            )
            notice(
                session,
                row,
                "marketplace_duplicate_detected",
                f"Likely repost: {row.title}",
                str(root.id),
                "NOTICE",
                now,
            )
            break
        notice(
            session,
            row,
            "marketplace_listing_imported",
            f"Imported supplied listing: {row.title}",
            "initial",
            now=now,
        )
        if not row.duplicate_of_listing_id:
            notice(
                session,
                row,
                "marketplace_opportunity_created",
                f"New listing for review: {row.title}",
                "initial",
                "NOTICE",
                now,
            )
    session.flush()
    evaluate(session, row, now)
    if previous_price is not None and item.asking_price < previous_price:
        notice(
            session,
            row,
            "marketplace_price_drop",
            f"Observed price drop: {row.title}",
            f"{previous_price}:{item.asking_price}:{int(now.timestamp() // 900)}",
            "NOTICE",
            now,
        )
    session.flush()
    return row, created


def import_batch(session, connector, dry_run=False):
    lock_writes(session)
    report = {"dry_run": dry_run, "created": 0, "updated": 0, "errors": [], "results": []}
    # One outer savepoint makes dry-run genuinely non-persistent, including notices/evidence.
    transaction = session.begin_nested()
    for index, raw in enumerate(connector.rows(), 1):
        try:
            with session.begin_nested():
                item = validate_row(raw)
                row, created = upsert(session, item)
                report["created" if created else "updated"] += 1
                report["results"].append(
                    {
                        "row": index,
                        "id": str(row.id),
                        "title": row.title,
                        "duplicate_of_listing_id": public(row.duplicate_of_listing_id),
                        "tier": latest_analysis(session, row.id).analysis["tier"],
                    }
                )
        except (ValueError, ValidationError) as exc:
            message = (
                "; ".join(
                    f"{'.'.join(map(str, e['loc']))}: {e['msg']}"
                    for e in exc.errors(include_input=False, include_url=False)
                )
                if isinstance(exc, ValidationError)
                else str(exc)
            )
            report["errors"].append({"row": index, "error": message[:500]})
    if dry_run:
        transaction.rollback()
        session.rollback()
    else:
        transaction.commit()
        session.commit()
    return report


def listing_data(session, row, detail=False):
    analyses = session.scalars(
        select(MarketplaceAnalysis)
        .where(MarketplaceAnalysis.listing_id == row.id)
        .order_by(MarketplaceAnalysis.created_at.desc(), MarketplaceAnalysis.id.desc())
        .limit(20 if detail else 1)
    ).all()
    # Read-time projection ages freshness/staleness without writing or spamming events.
    value = (
        evaluate(session, row, persist=False)
        if row.details.get("source_listing_id")
        else (analyses[0].analysis if analyses else None)
    )
    data = {
        **public(row),
        "source_listing_id": row.listing_id,
        "source_url": row.direct_url,
        "analysis": value,
        "analyses": [{**public(analyses[0]), "analysis": value}] if analyses else [],
        "listing_age_minutes": freshness(
            normalized(row),
            row.first_seen_at or row.created_at,
            preferences(session),
            datetime.now(UTC),
            row.first_known_post if row.duplicate_of_listing_id else None,
        )["age_minutes"],
        "refresh": {
            "supports_refresh": False,
            "refresh_interval": None,
            "requires_manual_update": True,
        },
    }
    if detail:
        data.update(
            price_history=public(price_history(session, row.id)),
            historical_analyses=public(analyses),
            outcome=public(
                session.scalar(
                    select(MarketplaceOutcome).where(MarketplaceOutcome.listing_id == row.id)
                )
            ),
            inventory=public(
                session.scalar(
                    select(MarketplaceInventoryItem).where(
                        MarketplaceInventoryItem.listing_id == row.id
                    )
                )
            ),
            duplicate_matches=public(
                session.scalars(
                    select(MarketplaceDuplicateMatch).where(
                        MarketplaceDuplicateMatch.listing_id == row.id
                    )
                ).all()
            ),
            comps=public(
                session.scalars(
                    select(MarketplaceComparable).where(MarketplaceComparable.listing_id == row.id)
                ).all()
            ),
        )
    return data


def record_action(session, row, action, payload):
    lock_writes(session)
    if row.status in {"BOUGHT", "SOLD"}:
        raise ValueError("Purchased inventory cannot be tracked, contacted or passed again")
    target = {
        "track": "TRACKING",
        "reviewing": "REVIEWING",
        "contacted": "CONTACTED",
        "pass": "PASSED",
    }[action]
    row.status = target
    row.details = {
        **row.details,
        "notes": payload.notes or row.details.get("notes", ""),
        "would_have_bought": payload.would_have_bought
        or row.details.get("would_have_bought", False),
    }
    row.updated_at = datetime.now(UTC)
    if action == "pass":
        prediction = latest_analysis(session, row.id)
        row.details = {
            **row.details,
            "passed_prediction": prediction.analysis if prediction else None,
        }
        notice(
            session,
            row,
            "marketplace_listing_passed",
            f"User passed: {row.title}",
            "passed",
            "NOTICE",
        )
    else:
        notice(
            session,
            row,
            "marketplace_analysis_updated",
            f"User marked {target.lower()}: {row.title}",
            target,
        )
    session.commit()
    return listing_data(session, row, True)


def record_purchase(session, row, payload):
    lock_writes(session)
    existing = session.scalar(
        select(MarketplaceInventoryItem).where(MarketplaceInventoryItem.listing_id == row.id)
    )
    purchase = payload.model_dump(mode="json")
    if existing:
        if all(existing.purchase.get(k) == v for k, v in purchase.items()):
            return listing_data(session, row, True)
        raise ValueError("Purchase already recorded; conflicting purchase rejected")
    if payload.purchase_date > datetime.now(UTC):
        raise ValueError("Purchase date cannot be in the future")
    if row.status == "SOLD":
        raise ValueError("Already sold")
    prior = session.scalar(
        select(MarketplaceAnalysis)
        .where(
            MarketplaceAnalysis.listing_id == row.id,
            MarketplaceAnalysis.created_at <= payload.purchase_date,
        )
        .order_by(MarketplaceAnalysis.created_at.desc())
        .limit(1)
    )
    prediction = prior.analysis if prior else {}
    purchase["prediction"] = prediction
    purchase["prediction_status"] = (
        "prospective_snapshot"
        if prior
        else "No pre-purchase prediction; accuracy metrics unavailable"
    )
    purchase["category"] = row.details.get("category", "unknown")
    purchase["source"] = row.source
    purchase["cost_basis"] = cash(
        payload.purchase_price + payload.travel_cost + payload.repair_cost + payload.other_costs
    )
    session.add(
        MarketplaceInventoryItem(
            listing_id=row.id, purchase=purchase, sold=False, aging_bucket="FRESH"
        )
    )
    outcome = session.scalar(
        select(MarketplaceOutcome).where(MarketplaceOutcome.listing_id == row.id)
    )
    if not outcome:
        outcome = MarketplaceOutcome(listing_id=row.id, outcome={})
        session.add(outcome)
    outcome.outcome = {
        "bought": True,
        "purchase": purchase,
        "prediction": prediction,
        "net_profit": None,
    }
    row.status = "BOUGHT"
    row.updated_at = datetime.now(UTC)
    notice(
        session,
        row,
        "marketplace_item_bought",
        f"User recorded purchase: {row.title}",
        "bought",
        "NOTICE",
    )
    session.commit()
    return listing_data(session, row, True)


def calibration_metrics(
    prediction, sale_price, actual_profit, days, sold, observation_days, category, source
):
    prediction = prediction or {}
    low, high = prediction.get("expected_resale_low"), prediction.get("expected_resale_high")
    predicted_profit = prediction.get("expected_net_profit")
    sale_range = prediction.get("sale_time", {}).get("expected_days")
    probabilities = {}
    for window in [7, 14, 30, 60]:
        probability = prediction.get("sell_through", {}).get(f"sell_through_probability_{window}d")
        # An early sale resolves all horizons. Unsold/late outcomes resolve only fully
        # observed horizons.
        resolved = (sold and days is not None and days <= window) or observation_days >= window
        if probability is not None and resolved:
            outcome = bool(sold and days is not None and days <= window)
            probabilities[str(window)] = {
                "predicted": probability,
                "actual": int(outcome),
                "brier": round((probability - int(outcome)) ** 2, 6),
            }
    return {
        "category": category,
        "source": source,
        "sold": sold,
        "days_held": days,
        "resale_error": cash(D(sale_price) - D(low))
        if sale_price is not None and low is not None
        else None,
        "profit_error": cash(D(actual_profit) - D(predicted_profit))
        if actual_profit is not None and predicted_profit is not None
        else None,
        "resale_range_accurate": bool(D(low) <= D(sale_price) <= D(high))
        if sale_price is not None and low is not None and high is not None
        else None,
        "sale_time_error": round(days - mean(sale_range), 2)
        if days is not None and sold and sale_range
        else None,
        "sale_time_accurate": bool(sale_range[0] <= days <= sale_range[1])
        if days is not None and sold and sale_range
        else None,
        "probabilities": probabilities,
    }


def record_sale(session, row, payload):
    lock_writes(session)
    inventory = session.scalar(
        select(MarketplaceInventoryItem).where(MarketplaceInventoryItem.listing_id == row.id)
    )
    if not inventory:
        raise ValueError("Record a purchase before a sale")
    outcome = session.scalar(
        select(MarketplaceOutcome).where(MarketplaceOutcome.listing_id == row.id)
    )
    sale = payload.model_dump(mode="json")
    if inventory.sold:
        if outcome.outcome.get("sale") == sale:
            return listing_data(session, row, True)
        raise ValueError("Sale already recorded; conflicting sale rejected")
    purchased = datetime.fromisoformat(inventory.purchase["purchase_date"])
    if payload.sale_date < purchased or payload.sale_date > datetime.now(UTC):
        raise ValueError("Sale date must follow purchase and cannot be in the future")
    costs = (
        D(inventory.purchase["cost_basis"])
        + payload.platform_fees
        + payload.shipping_cost
        + payload.payment_fees
        + payload.other_costs
    )
    net = payload.sale_price - costs
    days = round((payload.sale_date - purchased).total_seconds() / 86400, 3)
    prediction = inventory.purchase["prediction"]
    value = {
        **outcome.outcome,
        "sale": sale,
        "net_profit": cash(net),
        "actual_roi_percent": cash(net / costs * 100) if costs else None,
        "days_to_sell": days,
        "actual_costs": cash(costs),
    }
    outcome.outcome = value
    metrics = calibration_metrics(
        prediction,
        payload.sale_price,
        net,
        days,
        True,
        days,
        inventory.purchase["category"],
        inventory.purchase["source"],
    )
    metrics["authenticity_outcome"] = payload.authenticity_outcome
    metrics["predicted_counterfeit_risk"] = prediction.get("counterfeit", {}).get("risk", "UNKNOWN")
    record = session.scalar(
        select(MarketplaceCalibrationRecord).where(
            MarketplaceCalibrationRecord.listing_id == row.id,
            MarketplaceCalibrationRecord.hypothetical.is_(False),
        )
    )
    if record:
        record.metrics = metrics
    else:
        session.add(
            MarketplaceCalibrationRecord(listing_id=row.id, hypothetical=False, metrics=metrics)
        )
    inventory.sold, row.status, row.active = True, "SOLD", False
    row.updated_at = datetime.now(UTC)
    notice(
        session, row, "marketplace_item_sold", f"User recorded sale: {row.title}", "sold", "NOTICE"
    )
    session.commit()
    return listing_data(session, row, True)


def aging(days, settings):
    index = sum(days >= n for n in settings.inventory_days)
    return ["FRESH", "NORMAL", "AGING", "STALE", "DEAD_INVENTORY"][index]


def inventory_data(session, refresh=False):
    now, settings = datetime.now(UTC), preferences(session)
    rows = []
    if refresh:
        lock_writes(session)
    for item in session.scalars(
        select(MarketplaceInventoryItem).where(MarketplaceInventoryItem.sold.is_(False))
    ):
        row = session.get(MarketplaceListing, item.listing_id)
        days = max(
            0,
            (now - datetime.fromisoformat(item.purchase["purchase_date"])).total_seconds() / 86400,
        )
        bucket = aging(days, settings)
        value = evaluate(session, row, persist=False)
        resale = value["conservative_resale_value"]
        expected = (
            D(resale)
            - D(item.purchase["cost_basis"])
            - D(value["estimated_fees"])
            - D(value["shipping_cost"])
            if resale is not None
            else None
        )
        if refresh:
            if bucket != item.aging_bucket and bucket in {"AGING", "STALE", "DEAD_INVENTORY"}:
                notice(
                    session,
                    row,
                    "marketplace_inventory_aging",
                    f"Review aging inventory: {row.title}",
                    bucket,
                    "NOTICE",
                )
            item.aging_bucket = bucket
            prediction = item.purchase["prediction"]
            metrics = calibration_metrics(
                prediction,
                None,
                None,
                days,
                False,
                days,
                item.purchase["category"],
                item.purchase["source"],
            )
            record = session.scalar(
                select(MarketplaceCalibrationRecord).where(
                    MarketplaceCalibrationRecord.listing_id == row.id,
                    MarketplaceCalibrationRecord.hypothetical.is_(False),
                )
            )
            if record:
                record.metrics = metrics
            else:
                session.add(
                    MarketplaceCalibrationRecord(
                        listing_id=row.id, hypothetical=False, metrics=metrics
                    )
                )
        rows.append(
            {
                "id": str(item.id),
                "listing_id": str(row.id),
                "title": row.title,
                "purchase": item.purchase,
                "days_held": round(days, 1),
                "aging_status": bucket,
                "estimated_resale_value": resale,
                "expected_profit": cash(expected),
                "expected_sale_window": value["sale_time"],
                "suggestions": [
                    "Review price against new comps",
                    "Consider manual relisting or cross-listing",
                    "Consider bundling or accepting a lower margin",
                ]
                if bucket in {"AGING", "STALE", "DEAD_INVENTORY"}
                else [],
            }
        )
    if refresh:
        session.commit()
    return rows


class MarketplaceCalibrationService:
    def summary(self, session):
        rows = session.scalars(select(MarketplaceCalibrationRecord)).all()
        actual = [
            r.metrics for r in rows if not r.hypothetical and r.metrics.get("source") != "fixture"
        ]
        hypothetical = [r.metrics for r in rows if r.hypothetical]
        sold = [r for r in actual if r["sold"]]

        def errors(items, key):
            values = [float(r[key]) for r in items if r.get(key) is not None]
            return {
                "sample_size": len(values),
                "mae": round(mean(abs(v) for v in values), 2) if values else None,
                "bias": round(mean(values), 2) if values else None,
            }

        groups = {}
        for dimension in ["category", "source"]:
            groups[dimension] = {
                key: errors([r for r in sold if r[dimension] == key], "resale_error")
                for key in sorted({r[dimension] for r in sold})
            }
        probability = {}
        for window in ["7", "14", "30", "60"]:
            resolved = [r["probabilities"][window] for r in actual if window in r["probabilities"]]
            probability[window] = {
                "sample_size": len(resolved),
                "brier": round(mean(r["brier"] for r in resolved), 4) if resolved else None,
                "predicted_mean": mean(r["predicted"] for r in resolved) if resolved else None,
                "observed_rate": mean(r["actual"] for r in resolved) if resolved else None,
            }
        return {
            "sample_size": len(sold),
            "fixture_sample_size": sum(r.metrics.get("source") == "fixture" for r in rows),
            "observed_inventory_count": len(actual),
            "hypothetical_sample_size": len(hypothetical),
            "status": "insufficient_sample" if len(sold) < 20 else "descriptive_only",
            "resale": errors(sold, "resale_error"),
            "profit": errors(sold, "profit_error"),
            "sale_time": errors(sold, "sale_time_error"),
            "probabilities": probability,
            "bias_by": groups,
            "explanation": (
                "Actual and hypothetical records never combine. Below 20 sold outcomes no "
                "calibration conclusion is justified. Unsold windows are right-censored "
                "until observed. No model retraining or self-modification"
            ),
        }


def performance(session):
    listings = session.scalars(select(MarketplaceListing)).all()
    all_inventory = inventory_data(session)
    inventory = [i for i in all_inventory if i["purchase"].get("source") != "fixture"]
    outcomes = [o.outcome for o in session.scalars(select(MarketplaceOutcome))]
    sold = [
        o
        for o in outcomes
        if o.get("sale")
        and o.get("net_profit") is not None
        and o.get("purchase", {}).get("source") != "fixture"
    ]
    expected = [D(i["expected_profit"]) for i in inventory if i["expected_profit"] is not None]
    return {
        "active_tracked_listings": sum(
            r.active and r.status in {"NEW", "TRACKING", "REVIEWING", "CONTACTED"} for r in listings
        ),
        "strong_candidates": sum(
            listing_data(session, r)["analysis"].get("tier") == "STRONG_CANDIDATE"
            for r in listings
            if r.active
            and r.status not in {"PASSED", "BOUGHT", "SOLD"}
            and latest_analysis(session, r.id)
        ),
        "inventory_count": len(inventory),
        "fixture_inventory_count": len(all_inventory) - len(inventory),
        "capital_tied_up": cash(sum(D(i["purchase"]["cost_basis"]) for i in inventory)),
        "expected_inventory_profit": cash(sum(expected))
        if len(expected) == len(inventory)
        else None,
        "realized_profit": cash(sum(D(o["net_profit"]) for o in sold)),
        "average_days_to_sell": round(mean(o["days_to_sell"] for o in sold), 2) if sold else None,
        "calibration": MarketplaceCalibrationService().summary(session),
        "scope": (
            "Human-recorded Marketplace flips only; completely separate from Agent A/B portfolios"
        ),
    }
