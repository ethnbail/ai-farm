"""Auditable intelligence pipeline; only the existing broker may execute orders."""

import time
from datetime import UTC, datetime, timedelta
from decimal import Decimal as D
from uuid import uuid4

from sqlalchemy import select

from app.market_data.factory import get_provider
from app.models import (
    Agent,
    AIAnalysis,
    ConfidenceRecord,
    OpportunityQueueItem,
    Portfolio,
    ShadowReview,
    Trade,
)
from app.schemas.intelligence import ShadowReviewOutput, TradeAnalysis
from app.schemas.trading import OrderRequest
from app.services.ai import ModelRouter
from app.services.event_context import EventContextService, aware
from app.services.event_store import emit
from app.services.market_hours import market_status
from app.services.paper_broker import PaperBroker, require_paper
from app.services.research import MarketRegimeService, OpportunityScanner
from app.services.shadow import ShadowAgent


def deterministic_analysis(candidate):
    contract = next(
        (r for r in candidate.snapshot.get("ranked_contracts", []) if r["eligible"]), None
    )
    recommendation = contract["quote"]["option_type"] if contract else "BUY"
    return TradeAnalysis(
        recommendation=recommendation if candidate.eligible else "NO_TRADE",
        confidence=0.5,
        thesis="; ".join(candidate.reasons) or "Insufficient data",
        supporting_factors=candidate.reasons,
        risks=["Paper simulation, not a profitability prediction"],
        invalidation_conditions=["Stale data", "Risk engine rejection"],
        event_risks=[],
        regime_fit=candidate.regime,
        data_quality=candidate.data_mode,
        uncertainty_notes=["Deterministic fallback; confidence is not calibrated"],
        suggested_entry_context="Use existing deterministic strategy proposal",
        suggested_stop_context="Risk engine checks proposed stop",
        suggested_target_context="No AI price changes",
    )


def run_intelligence(
    session,
    settings,
    agent_id,
    now=None,
    execute=False,
    provider=None,
    router=None,
    execution_guard=None,
):
    require_paper(settings)
    started = time.monotonic()
    now = now or datetime.now(UTC)
    agent = session.get(Agent, agent_id)
    if agent is None:
        raise ValueError("Unknown agent")
    provider = provider or get_provider(session, settings, now)
    router = router or ModelRouter(session, settings)
    regime = MarketRegimeService().detect(session, provider, settings, now)
    scan_id = uuid4()
    candidates = OpportunityScanner().scan(session, settings, provider, agent, regime, now, scan_id)
    account = session.scalar(select(Portfolio).where(Portfolio.agent_id == agent_id))
    for candidate in candidates:
        item = session.scalar(
            select(OpportunityQueueItem).where(OpportunityQueueItem.candidate_id == candidate.id)
        )
        if item.status != "SHORTLISTED":
            continue
        if execute and (
            agent.status in {"paused", "error"}
            or (settings.regular_hours_only and market_status(now)["session"] != "regular")
        ):
            item.status, item.rejection_reason = "DISMISSED", "Agent inactive or market closed"
            session.commit()
            continue
        events = EventContextService().context(
            session, settings, candidate.symbol, now, candidate.data_mode
        )
        context = dict(
            market=candidate.snapshot,
            score=str(candidate.score),
            regime=candidate.regime,
            account={
                "equity": str(account.equity),
                "cash": str(account.cash_balance),
                "exposure": str(account.market_value),
            },
            events=events,
            proposal=candidate.proposal,
        )
        analysis, model, status = router.analyze(
            TradeAnalysis, context, scan_id, priority=candidate.score >= 90 and item.rank == 1
        )
        analysis = analysis or deterministic_analysis(candidate)
        session.add(
            AIAnalysis(
                candidate_id=candidate.id,
                model=model,
                status=status,
                context=context,
                analysis=analysis.model_dump(mode="json"),
            )
        )
        item.ai_status, item.status = status, "AI_ANALYZED"
        emit(
            session,
            "ai_analysis_completed",
            str(agent_id),
            {
                "candidate_id": str(candidate.id),
                "message": f"{candidate.symbol}: {analysis.recommendation} ({status})",
            },
        )
        session.commit()
        review = ShadowAgent().review(candidate, analysis, events)
        ai_review, shadow_model, shadow_status = router.analyze(
            ShadowReviewOutput,
            {
                **context,
                "analysis": analysis.model_dump(mode="json"),
                "deterministic_objections": review.objections,
            },
            scan_id,
            purpose="shadow",
            priority=item.rank == 1,
        )
        if ai_review:
            # AI may add a veto, never erase deterministic objections or approval gates.
            permitted = (
                review.approve_for_risk_review
                and ai_review.approve_for_risk_review
                and ai_review.recommended_action == "PROCEED"
            )
            review = review.model_copy(
                update={
                    "approve_for_risk_review": permitted,
                    "objections": list(dict.fromkeys(review.objections + ai_review.objections))[
                        :15
                    ],
                    "recommended_action": "PROCEED" if permitted else "WAIT",
                }
            )
        session.add(
            ShadowReview(
                candidate_id=candidate.id,
                model=shadow_model,
                status=shadow_status,
                review=review.model_dump(mode="json"),
            )
        )
        item.shadow_status, item.status = (
            "approved" if review.approve_for_risk_review else "vetoed",
            "SHADOW_REVIEWED",
        )
        emit(
            session,
            "shadow_review_completed",
            str(agent_id),
            {
                "candidate_id": str(candidate.id),
                "message": f"{candidate.symbol}: Shadow {review.recommended_action}",
            },
        )
        confidence = ConfidenceRecord(
            candidate_id=candidate.id,
            agent_id=agent_id,
            predicted_confidence=D(str(analysis.confidence)) if status == "completed" else None,
            strategy_version=candidate.proposal.get("strategy_name", "unknown")
            + ":"
            + candidate.proposal.get("strategy_version", "unknown"),
            model_version=model,
            regime=candidate.regime,
        )
        session.add(confidence)
        session.commit()
        decision_now = now + timedelta(seconds=time.monotonic() - started)
        if not review.approve_for_risk_review:
            item.status, item.rejection_reason = "DISMISSED", "; ".join(review.objections)[:1000]
        elif not execute:
            item.rejection_reason = "Research-only run: no order submitted"
        elif aware(item.expires_at) <= decision_now:
            item.status = "EXPIRED"
        elif settings.regular_hours_only and market_status(decision_now)["session"] != "regular":
            item.status, item.rejection_reason = "DISMISSED", "Market closed; no new paper entry"
        else:
            # Price/quantity/risk are never parsed from AI text.
            if execution_guard is not None and not execution_guard():
                item.status, item.rejection_reason = "DISMISSED", "Worker lease lost"
                session.commit()
                continue
            result = PaperBroker(session, settings, provider, decision_now).execute(
                OrderRequest(
                    agent_id=agent_id,
                    client_order_id=f"research:{candidate.id}",
                    **candidate.proposal,
                )
            )
            item.order_id, item.trade_id = result.order_id, result.trade_id
            item.risk_status = "approved" if result.status == "filled" else "rejected"
            item.status = "EXECUTED" if result.status == "filled" else "RISK_REJECTED"
            item.rejection_reason = result.reason
            confidence.trade_id = result.trade_id
        session.commit()
    sync_confidence(session)
    return candidates


def sync_confidence(session):
    for record, trade in session.execute(
        select(ConfidenceRecord, Trade)
        .join(Trade, ConfidenceRecord.trade_id == Trade.id)
        .where(ConfidenceRecord.outcome.is_(None), Trade.status == "closed")
    ):
        record.outcome = trade.realized_pnl > 0
        record.return_percent = trade.realized_return_percent
    session.commit()
