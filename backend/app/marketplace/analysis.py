"""Transparent deterministic estimates; missing evidence never becomes invented sales."""

from datetime import UTC, datetime
from decimal import Decimal as D
from difflib import SequenceMatcher
from statistics import median
from typing import Protocol

from app.schemas.marketplace import ListingInput, SearchSettings
from app.services.event_context import aware


def cash(value):
    return str(D(str(value)).quantize(D("0.01"))) if value is not None else None


def clamp(value, low=0, high=100):
    return max(low, min(high, float(value)))


def freshness(listing, first_seen, settings, now, first_known=None):
    timestamp = first_known or listing.listed_at or first_seen
    minutes = max(0, (now - aware(timestamp)).total_seconds() / 60)
    index = sum(minutes >= threshold for threshold in settings.freshness_minutes)
    return {
        "age_minutes": round(minutes, 1),
        "bucket": ["NEW", "VERY_FRESH", "FRESH", "RECENT", "AGING", "OLD"][index],
        "score": [100, 90, 75, 55, 25, 5][index],
        "basis": "first_known_post"
        if first_known
        else "listed_at"
        if listing.listed_at
        else "first_seen_only",
    }


class MarketplaceDuplicateDetector:
    def compare(self, incoming, previous):
        a, b = incoming, previous
        title = SequenceMatcher(None, a.title.lower(), b.title.lower()).ratio()
        description = (
            SequenceMatcher(None, a.description.lower(), b.description.lower()).ratio()
            if a.description and b.description
            else 0
        )
        same_seller = bool(a.seller_id and a.source == b.source and a.seller_id == b.seller_id)
        fingerprints = {str(i["fingerprint"]) for i in a.image_metadata if i.get("fingerprint")}
        same_image = bool(
            fingerprints & {str(i["fingerprint"]) for i in b.image_metadata if i.get("fingerprint")}
        )
        same_location = bool(a.zip_code and a.zip_code == b.zip_code)
        same_model = bool(a.model and a.model.lower() == (b.model or "").lower())
        # Generic titles/model/price alone never establish a repost.
        probable = (
            same_seller and title >= 0.85 and (same_location or description >= 0.85 or same_image)
        ) or (same_image and title >= 0.85 and same_location)
        return {
            "probability": 0.95
            if probable and same_image
            else 0.85
            if probable
            else 0.25
            if title >= 0.85
            else 0,
            "likely_duplicate": probable,
            "title_similarity": round(title, 3),
            "same_seller": same_seller,
            "same_image": same_image,
            "same_location": same_location,
            "same_model": same_model,
            "same_price": a.asking_price == b.asking_price,
            "explanation": "Heuristic similarity, not verified identity",
        }


class SellerMotivationAnalyzer:
    def evaluate(self, listing, drops):
        phrases = [
            p
            for p in [
                "need gone",
                "moving",
                "must sell",
                "today only",
                "pickup today",
                "obo",
                "negotiable",
                "cash only",
                "clearing out",
            ]
            if p in listing.description.lower()
        ]
        signals = (
            phrases
            + (["observed price drop"] if drops else [])
            + (["multiple price drops"] if drops > 1 else [])
        )
        return {
            "motivation_score": min(100, len(phrases) * 12 + min(drops, 3) * 20),
            "signals": signals,
            "confidence": "low",
            "explanation": (
                "Text and observed pricing signals only; no inference about personal "
                "circumstances or willingness to negotiate"
            ),
        }


class SellerReliabilityAnalyzer:
    def evaluate(self, listing):
        flags = list(listing.seller_profile_metadata.get("red_flags", []))
        phrases = [
            p
            for p in [
                "wire transfer",
                "gift card",
                "deposit before viewing",
                "verification code",
                "crypto only",
            ]
            if p in listing.description.lower()
        ]
        flags.extend(f"Suspicious wording: {p}" for p in phrases)
        known = listing.seller_rating is not None and listing.seller_review_count is not None
        score = float(listing.seller_rating) * 20 if known else None
        if score is not None:
            score = clamp(score - len(flags) * 20)
        return {
            "reliability_score": score,
            "risk_flags": flags,
            "confidence": "medium"
            if known and listing.seller_review_count >= 20
            else "low"
            if known
            else "unknown",
            "explanation": (
                "Source-provided rating and explicit red flags; missing seller data is "
                "unknown, not a negative rating"
            ),
        }


class ItemCompletenessAnalyzer:
    checklists = {
        "gaming": {"controller": 35, "power cable": 15, "HDMI cable": 8},
        "laptop": {"charger": 30, "battery status": 0, "storage": 0, "RAM": 0, "model/year": 0},
        "camera": {"battery": 25, "charger": 25, "lens": 0, "body cap": 8},
    }

    def evaluate(self, listing):
        required = self.checklists.get(listing.category, {})
        supplied = listing.item_metadata.get("accessories", {})
        present = [k for k in required if supplied.get(k) is True]
        missing = [k for k in required if supplied.get(k) is False]
        unknown = [k for k in required if k not in present + missing]
        adjustment = sum(required[k] for k in missing)
        return {
            "completeness_score": round(len(present) / len(required) * 100)
            if required and not unknown
            else None,
            "present_items": present,
            "missing_items": missing,
            "unknown_items": unknown,
            "resale_value_adjustment": cash(-adjustment),
            "replacement_reserve": cash(adjustment),
            "explanation": (
                "Explicit metadata only. Replacement reserves are editable-code "
                "illustrative USD assumptions; unknown accessories are not asserted missing"
            ),
        }


class ValuationProvider(Protocol):
    def comparables(self, listing: ListingInput) -> list: ...


class ManualComparisonProvider:
    def comparables(self, listing):
        return listing.comps


class MarketplaceValuationService:
    def __init__(self, provider=None):
        self.provider = provider or ManualComparisonProvider()

    def evaluate(self, listing, now):
        supplied = self.provider.comparables(listing)
        comps = [
            c
            for c in supplied
            if c.sold
            and (now - c.observed_at).days <= 180
            and (not listing.model or (c.model or "").lower() == listing.model.lower())
            and c.category == listing.category
            and c.currency == listing.currency
            and c.condition == listing.condition
        ]
        prices = sorted(c.price for c in comps)
        n = len(prices)
        # Lower quartile and median bound avoid claiming an appraisal from the highest asking price.
        low = prices[(n - 1) // 4] if n else None
        high = prices[(3 * (n - 1)) // 4] if n else None
        return {
            "conservative_resale_value": cash(low),
            "expected_resale_low": cash(low),
            "expected_resale_high": cash(high),
            "median_comp": cash(median(prices)) if n else None,
            "comp_count": n,
            "excluded_comp_count": len(supplied) - n,
            "comp_recency_days": min((now - c.observed_at).days for c in comps) if n else None,
            "comp_quality": "fixture"
            if n and all(c.quality == "fixture" for c in comps)
            else "user_reported"
            if n
            else "insufficient_data",
            "valuation_confidence": min(0.8, 0.25 + n * 0.07) if n else 0,
            "sources": sorted({c.source for c in comps}),
            "comps": [c.model_dump(mode="json") for c in comps],
            "explanation": (
                "Matched sold comps only (model/category/condition/USD, observed within 180 "
                "days). Sources are supplied evidence, not independently verified external "
                "sales"
            ),
        }


class CounterfeitRiskAnalyzer:
    def evaluate(self, listing, valuation):
        relevant = listing.category in {"luxury", "sneakers", "phone", "gaming", "camera", "laptop"}
        factors = []
        value = valuation["conservative_resale_value"]
        if value and listing.asking_price < D(value) * D(".4"):
            factors.append("Asking price below 40% of supplied conservative comps")
        if any(
            word in listing.description.lower() for word in ["replica", "not authentic", "1:1 copy"]
        ):
            factors.append("Description contains authenticity warning")
        if any(i.get("stock_photo") is True for i in listing.image_metadata):
            factors.append("Reported stock photos; request item-specific photos")
        if relevant and not listing.model:
            factors.append("Exact model missing")
        verified = listing.item_metadata.get("authenticity_verified") is True
        risk = (
            "HIGH"
            if len(factors) >= 2 or any("authenticity warning" in f for f in factors)
            else "MEDIUM"
            if factors
            else "LOW"
            if verified
            else "UNKNOWN"
        )
        return {
            "risk": risk,
            "risk_factors": factors,
            "verification_checklist": [
                "Confirm model and serial",
                "Inspect proof of purchase",
                "Test item in person",
                "Verify accessories and authenticity marks",
            ]
            + (["Verify IMEI/activation status"] if listing.category == "phone" else []),
            "explanation": (
                "Screening indicators only, not a counterfeit probability or proof. LOW "
                "relies on user-reported verification"
            ),
        }


class SellThroughEstimator:
    def evaluate(self, listing, now):
        cohorts = [c for c in listing.demand if (now - c.observed_at).days <= 90]
        cohort = next((c for c in cohorts if c.market == "LOCAL"), cohorts[0] if cohorts else None)
        result = {f"sell_through_probability_{d}d": None for d in [7, 14, 30, 60]}
        if cohort:
            for d in [7, 14, 30, 60]:
                count = getattr(cohort, f"sold_{d}d")
                if count is not None:
                    result[f"sell_through_probability_{d}d"] = round(
                        (count + 1) / (cohort.cohort_size + 2), 4
                    )
        return {
            **result,
            "confidence": "low"
            if not cohort or cohort.cohort_size < 30 or cohort.quality != "verified"
            else "medium",
            "data_quality": cohort.quality if cohort else "insufficient_data",
            "sample_size": cohort.cohort_size if cohort else 0,
            "market": cohort.market if cohort else "UNKNOWN",
            "source": cohort.source if cohort else None,
            "explanation": (
                "Beta(1,1) smoothed sold/complete-cohort counts, including unsold items. "
                "Sold comps alone cannot identify true sell-through; no cohort means "
                "unknown. Not guaranteed"
            ),
        }


class DemandComparisonService:
    def evaluate(self, listing, now):
        metrics = {}
        for c in listing.demand:
            if c.sold_30d is not None and (now - c.observed_at).days <= 90:
                metrics[c.market] = {
                    "score": round(100 * (c.sold_30d + 1) / (c.cohort_size + 2), 1),
                    "supply": c.active_listing_count,
                }
        local, national = metrics.get("LOCAL"), metrics.get("NATIONAL")
        recommended = "UNKNOWN"
        if local and national:
            recommended = (
                "EITHER"
                if abs(local["score"] - national["score"]) < 10
                else "LOCAL"
                if local["score"] > national["score"]
                else "NATIONAL"
            )
        return {
            "local_demand_score": local["score"] if local else None,
            "national_demand_score": national["score"] if national else None,
            "local_supply": local["supply"] if local else None,
            "national_supply": national["supply"] if national else None,
            "local_premium_discount": None,
            "recommended_market_type": recommended,
            "explanation": (
                "Comparable complete 30-day cohorts required for both markets; shipping "
                "economics still need user estimates"
            ),
        }


class SaleTimeEstimator:
    def evaluate(self, sell_through):
        def crossing(probability):
            previous = 0
            for d in [7, 14, 30, 60]:
                p = sell_through[f"sell_through_probability_{d}d"]
                if p is not None and p >= probability:
                    return [previous, d]
                previous = d
            return None

        return {
            "best_case_days": crossing(0.25),
            "expected_days": crossing(0.5),
            "slow_case_days": crossing(0.8),
            "explanation": (
                "25th/50th/80th percentile windows from supplied full-cohort cumulative "
                "probabilities. Unreached quantiles remain unknown (possibly over 60 days)"
            ),
        }


class SeasonalityService:
    def evaluate(self, category, settings, now):
        if settings.hemisphere == "unknown":
            return {
                "seasonal_multiplier": 1,
                "seasonality_reason": "Climate/hemisphere not supplied",
                "confidence": "unknown",
            }
        month = now.month
        if settings.hemisphere == "southern":
            month = (month + 5) % 12 + 1
        months = {
            "gaming": [11, 12],
            "laptop": [8, 9],
            "bicycle": [4, 5, 6],
            "heater": [11, 12, 1],
            "air_conditioner": [6, 7, 8],
            "fitness": [1],
        }
        # Gaming/school/fitness calendar rules do not shift with hemisphere.
        check_month = now.month if category in {"gaming", "laptop", "fitness"} else month
        boost = check_month in months.get(category, [])
        return {
            "seasonal_multiplier": 1.1 if boost else 1,
            "seasonality_reason": "Illustrative category/calendar heuristic; not measured demand"
            if boost
            else "No configured seasonal boost",
            "confidence": "low",
        }


class TravelEconomicsService:
    def evaluate(self, listing, settings):
        miles = listing.distance_miles * 2 if listing.distance_miles is not None else None
        return {
            "round_trip_miles": str(miles) if miles is not None else None,
            "travel_cost": cash(miles * settings.cost_per_mile) if miles is not None else None,
            "driving_minutes_round_trip": listing.driving_minutes_round_trip,
            "cost_per_mile": str(settings.cost_per_mile),
            "basis": (
                "User-supplied one-way distance, doubled; mileage includes fuel. No GPS or "
                "routing lookup"
            ),
        }


class MarketplaceOpportunityScorer:
    weights = {
        "freshness": 25,
        "profit": 20,
        "roi": 15,
        "sell_through": 15,
        "reliability": 5,
        "completeness": 5,
        "motivation": 5,
        "confidence": 10,
    }

    def evaluate(self, components, reasons, settings, critical=False):
        # Unknown evidence contributes zero, never an optimistic neutral score.
        total = sum(self.weights[k] * (v or 0) / 100 for k, v in components.items())
        tier = (
            "REJECT"
            if critical
            else "REVIEW"
            if reasons
            else "STRONG_CANDIDATE"
            if total >= float(settings.strong_score_threshold)
            else "REVIEW"
            if total >= 40
            else "WEAK"
        )
        return {
            "total_score": round(total, 2),
            "tier": tier,
            "component_scores": components,
            "weights": self.weights,
            "reasons_for_rejection": reasons,
            "explanation": (
                "Freshness has 25% weight but cannot override missing comps, location, "
                "serious risk, or user limits. Unknown components earn no points"
            ),
        }


def analyze(
    listing: ListingInput,
    settings: SearchSettings,
    first_seen,
    history,
    now=None,
    duplicate=False,
    first_known=None,
):
    now = now or datetime.now(UTC)
    prices = [D(str(p)) for p in history] or [listing.asking_price]
    drops = sum(b < a for a, b in zip(prices, prices[1:]))
    age = freshness(listing, first_seen, settings, now, first_known)
    valuation = MarketplaceValuationService().evaluate(listing, now)
    motivation = SellerMotivationAnalyzer().evaluate(listing, drops)
    reliability = SellerReliabilityAnalyzer().evaluate(listing)
    completeness = ItemCompletenessAnalyzer().evaluate(listing)
    counterfeit = CounterfeitRiskAnalyzer().evaluate(listing, valuation)
    sell = SellThroughEstimator().evaluate(listing, now)
    demand = DemandComparisonService().evaluate(listing, now)
    time = SaleTimeEstimator().evaluate(sell)
    season = SeasonalityService().evaluate(listing.category, settings, now)
    travel = TravelEconomicsService().evaluate(listing, settings)
    resale = (
        D(valuation["conservative_resale_value"])
        if valuation["conservative_resale_value"] is not None
        else None
    )
    fee_rate = (settings.platform_fee_percent + settings.payment_fee_percent) / 100
    reserve = D(completeness["replacement_reserve"])
    fixed = (
        (
            D(travel["travel_cost"])
            + listing.shipping_cost
            + listing.repair_cost
            + listing.other_costs
            + reserve
        )
        if travel["travel_cost"] is not None
        else None
    )
    net = (
        resale * (1 - fee_rate) - listing.asking_price - fixed
        if resale is not None and fixed is not None
        else None
    )
    invested = listing.asking_price + fixed if fixed is not None else None
    roi = net / invested * 100 if net is not None and invested else None
    # Transparent advisory reserves, not calibrated probabilities of loss.
    risk_adjustments = {
        "valuation_uncertainty": D(str(1 - valuation["valuation_confidence"])) * 10,
        "authenticity": D(5) if counterfeit["risk"] in {"UNKNOWN", "MEDIUM"} else D(0),
        "seller_red_flags": D(5) if reliability["risk_flags"] else D(0),
    }
    effective_risk_percent = min(
        D(100), settings.risk_buffer_percent + sum(risk_adjustments.values())
    )
    risk_buffer = resale * effective_risk_percent / 100 if resale is not None else None
    maximum = (
        max(
            D(0),
            min(
                resale * (1 - fee_rate) - fixed - risk_buffer - settings.min_expected_profit,
                (resale * (1 - fee_rate) - risk_buffer) / (1 + settings.min_roi_percent / 100)
                - fixed,
            ),
        )
        if resale is not None and fixed is not None and counterfeit["risk"] != "HIGH"
        else None
    )
    expected_days = sum(time["expected_days"]) / 2 if time["expected_days"] else None
    reasons, flags = [], list(reliability["risk_flags"])
    if not valuation["comp_count"]:
        reasons.append("Insufficient matched sold comparables")
    if travel["travel_cost"] is None:
        reasons.append("Travel distance unavailable")
    if not listing.active:
        reasons.append("Listing inactive")
    if duplicate:
        reasons.append("Likely repost; not a new opportunity")
    if listing.category in settings.excluded_categories or (
        settings.preferred_categories and listing.category not in settings.preferred_categories
    ):
        reasons.append("Outside category preferences")
    if not settings.min_asking_price <= listing.asking_price <= settings.max_asking_price:
        reasons.append("Outside asking-price range")
    if listing.distance_miles is not None and listing.distance_miles > min(
        settings.radius_miles, settings.max_pickup_miles
    ):
        reasons.append("Outside pickup radius")
    if settings.max_pickup_time_minutes is not None and (
        listing.driving_minutes_round_trip is None
        or listing.driving_minutes_round_trip > settings.max_pickup_time_minutes
    ):
        reasons.append("Pickup time exceeds limit or is unknown")
    if settings.max_listing_age_hours and age["age_minutes"] > settings.max_listing_age_hours * 60:
        reasons.append("Outside listing-age limit")
    if settings.min_seller_rating is not None and (
        listing.seller_rating is None or listing.seller_rating < settings.min_seller_rating
    ):
        reasons.append("Seller rating below filter or unavailable")
    if net is not None and net < settings.min_expected_profit:
        reasons.append("Below minimum net profit")
    if roi is not None and roi < settings.min_roi_percent:
        reasons.append("Below minimum ROI")
    if reliability["risk_flags"]:
        reasons.append("Seller red flags require review")
    if counterfeit["risk"] == "HIGH":
        reasons.append("High authenticity risk; verify before considering")
    if completeness["unknown_items"]:
        flags.append("Accessories unverified")
    if sell["sample_size"] == 0:
        flags.append("True sell-through unknown: no complete cohort")
    if not listing.listed_at:
        flags.append("Age based on first observation, not verified publication")
    if reliability["reliability_score"] is None:
        flags.append("Seller reliability unknown")
    if counterfeit["risk"] == "UNKNOWN":
        flags.append("Authenticity unknown")
    components = {
        "freshness": 0 if duplicate else age["score"],
        "profit": clamp(net / max(D(1), settings.min_expected_profit) * 50)
        if net is not None
        else None,
        "roi": clamp(roi) if roi is not None else None,
        "sell_through": (sell["sell_through_probability_30d"] * 100)
        if sell["sell_through_probability_30d"] is not None
        else None,
        "reliability": reliability["reliability_score"],
        "completeness": completeness["completeness_score"],
        "motivation": motivation["motivation_score"],
        "confidence": valuation["valuation_confidence"] * 100,
    }
    score = MarketplaceOpportunityScorer().evaluate(
        components,
        reasons,
        settings,
        counterfeit["risk"] == "HIGH" or (net is not None and net < 0),
    )
    absolute_drop = max(D(0), prices[0] - prices[-1])
    return {
        "version": "phase5-v1",
        "analyzed_at": now.isoformat(),
        "asking_price": cash(listing.asking_price),
        **valuation,
        "estimated_resale_low": valuation["expected_resale_low"],
        "estimated_resale_high": valuation["expected_resale_high"],
        "expected_net_profit": cash(net),
        "roi_percent": cash(roi),
        "profit_margin_percent": cash(net / resale * 100) if net is not None and resale else None,
        "profit_per_dollar_invested": cash(net / invested)
        if net is not None and invested
        else None,
        "profit_per_expected_day_held": cash(net / D(str(expected_days)))
        if net is not None and expected_days
        else None,
        "profit_per_mile": cash(net / D(travel["round_trip_miles"]))
        if net is not None and travel["round_trip_miles"] and D(travel["round_trip_miles"])
        else None,
        "profit_per_hour": cash(net / (D(listing.driving_minutes_round_trip) / 60))
        if net is not None and listing.driving_minutes_round_trip
        else None,
        "break_even_resale_price": cash(invested / (1 - fee_rate))
        if invested is not None
        else None,
        "platform_fee_percent": str(settings.platform_fee_percent),
        "payment_fee_percent": str(settings.payment_fee_percent),
        "estimated_fees": cash(resale * fee_rate) if resale is not None else None,
        "shipping_cost": cash(listing.shipping_cost),
        "repair_cost": cash(listing.repair_cost),
        "other_costs": cash(listing.other_costs),
        "max_buy_price": cash(maximum),
        "maximum_recommended_buy_price": cash(maximum),
        "target_buy_price": cash(maximum * D(".9")) if maximum is not None else None,
        "walk_away_price": cash(maximum),
        "risk_buffer": cash(risk_buffer),
        "risk_buffer_percent_effective": cash(effective_risk_percent),
        "risk_buffer_adjustments_percent": {k: cash(v) for k, v in risk_adjustments.items()},
        "capital_required": cash(invested),
        "travel_cost": travel["travel_cost"],
        "travel": travel,
        "freshness": age,
        "price_history_summary": {
            "initial_price": cash(prices[0]),
            "current_price": cash(prices[-1]),
            "absolute_drop": cash(absolute_drop),
            "percent_drop": cash(absolute_drop / prices[0] * 100) if prices[0] else None,
            "drop_count": drops,
        },
        "seller_motivation": motivation,
        "seller_reliability": reliability,
        "completeness": completeness,
        "counterfeit": counterfeit,
        "sell_through": sell,
        "sale_time": time,
        "expected_sale_time": f"{time['expected_days'][0]}–{time['expected_days'][1]} days"
        if time["expected_days"]
        else None,
        "sell_through_probability": sell["sell_through_probability_30d"],
        "demand": demand,
        "seasonality": season,
        "opportunity_score": score["total_score"],
        "tier": score["tier"],
        "scoring": score,
        "confidence": valuation["valuation_confidence"],
        "data_quality": valuation["comp_quality"],
        "risk_flags": flags + counterfeit["risk_factors"],
        "reasoning": reasons,
        "explanation": (
            "Advisory manual-evidence analysis. Fees and reserves are explicit "
            "assumptions; no guarantee or automatic action. Seasonality is context, not "
            "a resale-price multiplier"
        ),
        "direct_listing_url": listing.source_url,
        "data_mode": "fixture" if listing.source == "fixture" else "manual_evidence",
        "ai_status": "not_used",
        "vision_status": "unavailable",
    }
