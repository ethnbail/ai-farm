from collections import defaultdict
from decimal import Decimal as D

from sqlalchemy import func, select

from app.models import ConfidenceRecord, OpportunityQueueItem, RiskEvent, ShadowReview


def reliability(session, minimum=20):
    groups = defaultdict(list)
    for record in session.scalars(select(ConfidenceRecord)):
        groups[
            (str(record.agent_id), record.strategy_version, record.model_version, record.regime)
        ].append(record)
    summaries = []
    for key, rows in groups.items():
        closed = [r for r in rows if r.outcome is not None]
        calibrated = [r for r in closed if r.predicted_confidence is not None]
        enough = len(closed) >= minimum
        summaries.append(
            dict(
                agent_id=key[0],
                strategy_version=key[1],
                model_version=key[2],
                regime=key[3],
                decisions=len(rows),
                completed=len(closed),
                wins=sum(r.outcome for r in closed),
                win_rate=str(sum(r.outcome for r in closed) / D(len(closed))) if enough else None,
                average_return=str(
                    sum((r.return_percent or D(0) for r in closed), D(0)) / len(closed)
                )
                if enough
                else None,
                brier_score=str(
                    sum(((r.predicted_confidence - int(r.outcome)) ** 2 for r in calibrated), D(0))
                    / len(calibrated)
                )
                if len(calibrated) >= minimum
                else None,
                calibration_sample=len(calibrated),
                minimum_samples=minimum,
                note=None if enough else "Insufficient outcomes; no reliability ranking",
            )
        )
    risk = dict(
        session.execute(select(RiskEvent.rule, func.count()).group_by(RiskEvent.rule)).all()
    )
    outcomes = dict(
        session.execute(
            select(OpportunityQueueItem.status, func.count()).group_by(OpportunityQueueItem.status)
        ).all()
    )
    shadows = dict(
        session.execute(select(ShadowReview.model, func.count()).group_by(ShadowReview.model)).all()
    )
    shadow_outcomes = defaultdict(lambda: dict(decisions=0, completed=0, wins=0))
    for review, confidence in session.execute(
        select(ShadowReview, ConfidenceRecord).outerjoin(
            ConfidenceRecord, ConfidenceRecord.candidate_id == ShadowReview.candidate_id
        )
    ):
        key = review.model + ":" + review.review["recommended_action"]
        group = shadow_outcomes[key]
        group["decisions"] += 1
        if confidence and confidence.outcome is not None:
            group["completed"] += 1
            group["wins"] += int(confidence.outcome)
    return dict(
        systems=summaries,
        risk_rejections=risk,
        decision_outcomes=outcomes,
        shadow_decisions=shadows,
        shadow_outcomes=dict(shadow_outcomes),
        minimum_samples=minimum,
    )
