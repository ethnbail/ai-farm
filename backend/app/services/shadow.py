"""Critique only: no broker, account mutation, or order-submission dependency."""

from decimal import Decimal as D

from app.schemas.intelligence import ShadowReviewOutput


class ShadowAgent:
    def review(self, candidate, analysis, events):
        objections = list(candidate.rejection_reasons)
        blocked = not candidate.eligible or candidate.data_mode not in {"mock", "live"}
        if candidate.regime in {"UNKNOWN", "RISK_OFF"}:
            objections.append("Regime does not justify new risk")
            blocked = True
        proposal = candidate.proposal
        if proposal:
            entry, stop, target = map(
                D, [proposal["requested_price"], proposal["stop_loss"], proposal["take_profit"]]
            )
            if not 0 < stop < entry < target or target - entry < entry - stop:
                objections.append(
                    "Stop/target proposal has inadequate reward relative to planned risk"
                )
                blocked = True
        if analysis.confidence > 0.8:
            objections.append("High stated confidence is not calibrated evidence")
        if analysis.recommendation in {"HOLD", "NO_TRADE", "SELL"}:
            objections.append("Analysis does not support a new long entry")
            blocked = True
        contracts = candidate.snapshot.get("ranked_contracts", [])
        selected = next(
            (c for c in contracts if c["quote"]["symbol"] == proposal.get("symbol")), None
        )
        expected = selected["quote"]["option_type"] if selected else "BUY"
        if analysis.recommendation != expected:
            objections.append("Analysis direction disagrees with deterministic proposal")
            blocked = True
        if events["status"] == "unavailable":
            objections.append("Live event coverage is unavailable")
        if not objections:
            objections.append("Spread, slippage and gaps can invalidate the setup")
        return ShadowReviewOutput(
            approve_for_risk_review=not blocked,
            objections=objections,
            severity="high" if blocked else "medium",
            confidence=0.5,
            missing_information=[
                "Statistically calibrated outcome history",
                "Verified forward liquidity",
            ],
            recommended_action="NO_TRADE" if blocked else "PROCEED",
        )
