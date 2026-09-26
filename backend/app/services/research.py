"""Deterministic features, regimes, contract ranking and persisted shortlists."""

from dataclasses import replace
from datetime import timedelta
from decimal import Decimal as D
from uuid import uuid4

from sqlalchemy import select

from app.agents.strategies import DirectionalMomentumOptionsStrategy, TrendMomentumStrategy
from app.market_data.types import DataUnavailable
from app.models import (
    MarketRegimeSnapshot,
    OpportunityCandidate,
    OpportunityQueueItem,
    Portfolio,
    ProviderStatus,
    Watchlist,
    WatchlistSymbol,
)
from app.services.event_context import aware
from app.services.event_store import emit


def features(bars):
    if len(bars) < 20:
        raise DataUnavailable("At least 20 completed bars required")
    closes = [b.close for b in bars]
    if any(c <= 0 for c in closes):
        raise DataUnavailable("Invalid bar close")

    def mean(values):
        return sum(values, D(0)) / len(values)

    differences = [b - a for a, b in zip(closes, closes[1:])][-14:]
    gain, loss = (
        mean([max(d, D(0)) for d in differences]),
        mean([max(-d, D(0)) for d in differences]),
    )
    returns = [(b / a - 1) * 100 for a, b in zip(closes, closes[1:])]
    mu = mean(returns)
    atr = mean(
        [
            max(b.high - b.low, abs(b.high - a.close), abs(b.low - a.close))
            for a, b in zip(bars[-15:], bars[-14:])
        ]
    )
    result = dict(
        fast_sma=mean(closes[-5:]),
        slow_sma=mean(closes[-20:]),
        rsi=100 - 100 / (1 + gain / loss) if loss else D(100) if gain else D(50),
        atr=atr,
        atr_percent=atr / closes[-1] * 100,
        realized_volatility=mean([(r - mu) ** 2 for r in returns]).sqrt(),
        momentum=(closes[-1] / closes[-5] - 1) * 100,
        relative_volume=D(bars[-1].volume) / max(1, mean([D(b.volume) for b in bars[-20:]])),
        breakout_percent=(closes[-1] / max(b.high for b in bars[-20:-1]) - 1) * 100,
        drawdown_percent=(1 - closes[-1] / max(closes)) * 100,
    )
    return {k: str(v.quantize(D(".0001"))) for k, v in result.items()}


def record_provider(session, name, state, message, now):
    row = session.get(ProviderStatus, name)
    previous = row.state if row else None
    if row is None:
        row = ProviderStatus(provider=name)
        session.add(row)
    row.state, row.message, row.updated_at = state, message[:300], now
    if previous != state:
        emit(
            session,
            "market_data_restored" if state in {"mock", "live"} else "market_data_stale",
            "market_data",
            {"message": message[:300], "provider": name, "state": state},
        )


class MarketRegimeService:
    def detect(self, session, provider, settings, now):
        data, reasons, mode, regime = {}, [], "unavailable", "UNKNOWN"
        data_timestamp = now
        try:
            quotes = [provider.equity_quote(s) for s in ["SPY", "QQQ"]]
            data_timestamp = min(q.timestamp for q in quotes)
            if any(q.data_state(now, settings.quote_max_age_seconds) == "stale" for q in quotes):
                mode = "stale"
                raise DataUnavailable("Regime quotes stale")
            data = {s: features(provider.bars(s, 30)) for s in ["SPY", "QQQ"]}
            mode = "mock" if any(q.mode == "mock" for q in quotes) else "live"
            f = list(data.values())
            up = all(D(x["fast_sma"]) > D(x["slow_sma"]) for x in f)
            down = all(D(x["fast_sma"]) < D(x["slow_sma"]) for x in f)
            if down and max(D(x["drawdown_percent"]) for x in f) >= 8:
                regime = "RISK_OFF"
            elif max(D(x["atr_percent"]) for x in f) >= 4:
                regime = "HIGH_VOLATILITY"
            elif up:
                regime = "BULL_TREND"
            elif down:
                regime = "BEAR_TREND"
            elif max(D(x["atr_percent"]) for x in f) < D(".5"):
                regime = "LOW_VOLATILITY"
            else:
                regime = "RANGE_BOUND"
            reasons = ["SPY/QQQ SMA direction, ATR and observed drawdown; deterministic v1"]
        except DataUnavailable as error:
            reasons = [str(error)]
        snapshot = MarketRegimeSnapshot(
            regime=regime,
            data_mode=mode,
            data_timestamp=data_timestamp,
            features=data,
            reasons=reasons,
        )
        session.add(snapshot)
        emit(
            session,
            "market_regime_changed",
            "regime",
            {"message": f"Regime: {regime}", "data_mode": mode},
        )
        record_provider(session, settings.market_data_provider, mode, reasons[0], now)
        session.commit()
        return snapshot


def universe(session, settings, agent):
    base = (
        settings.agent_a_universe if agent.agent_type == "equities" else settings.agent_b_universe
    )
    custom = session.scalars(
        select(WatchlistSymbol.symbol).join(Watchlist).where(Watchlist.agent_id == agent.id)
    ).all()
    return list(dict.fromkeys([*base, *custom]))[:30]


def rank_contracts(contracts, settings, now, equity, direction):
    ranked = []
    for q in contracts:
        reasons = []
        dte = (q.expiration - now.date()).days
        if q.option_type != direction:
            reasons.append("direction_mismatch")
        if q.data_state(now, settings.quote_max_age_seconds) == "stale":
            reasons.append("stale_quote")
        if not settings.min_option_dte <= dte <= settings.max_option_dte:
            reasons.append("invalid_dte")
        if q.bid <= 0 or q.spread_percent > settings.max_option_spread_percent:
            reasons.append("wide_spread")
        if (
            q.volume < settings.min_option_volume
            or q.open_interest < settings.min_option_open_interest
        ):
            reasons.append("poor_liquidity")
        if (
            q.delta is None
            or not settings.target_option_delta_min
            <= abs(q.delta)
            <= settings.target_option_delta_max
        ):
            reasons.append("delta_fit")
        if q.iv is None or not 0 < q.iv <= settings.max_option_iv:
            reasons.append("iv_missing_or_excessive")
        if (
            q.gamma is None
            or q.gamma < 0
            or q.theta is None
            or q.theta > 0
            or abs(q.theta) / q.ask * 100 > settings.max_option_theta_decay_percent
        ):
            reasons.append("greeks_quality")
        if q.mode == "live" and (
            q.greeks_timestamp is None
            or not -5 <= (now - q.greeks_timestamp).total_seconds() <= 86400
        ):
            reasons.append("greeks_timestamp_unverified")
        premium = q.ask * (1 + settings.option_slippage_percent / 100) * 100
        cap = (
            equity
            * min(settings.max_risk_per_trade_percent, settings.max_option_premium_at_risk_percent)
            / 100
        )
        if premium > cap:
            reasons.append("full_premium_exceeds_risk")
        components = dict(
            delta_fit=max(D(0), 20 - abs(abs(q.delta or 0) - D(".55")) * 100),
            dte_fit=max(D(0), 15 - abs(dte - 21) / D(3)),
            spread_quality=max(D(0), 25 - q.spread_percent),
            liquidity=min(D(20), D(q.volume) / 50 + D(q.open_interest) / 100),
            affordability=D(20) if premium <= cap else D(0),
        )
        ranked.append(
            dict(
                quote=q.snapshot(now),
                score=str(sum(components.values()).quantize(D(".0001"))),
                components={k: str(v) for k, v in components.items()},
                rejection_reasons=reasons,
                eligible=not reasons,
            )
        )
    return sorted(ranked, key=lambda r: (not r["eligible"], -D(r["score"]), r["quote"]["symbol"]))


class OpportunityScanner:
    def scan(self, session, settings, provider, agent, regime, now, scan_id=None):
        scan_id = scan_id or uuid4()
        # One active generation per agent. Preserve terminal execution/risk audit records.
        for previous in session.scalars(
            select(OpportunityQueueItem).where(
                OpportunityQueueItem.agent_id == agent.id,
                OpportunityQueueItem.status.in_(["SHORTLISTED", "AI_ANALYZED", "SHADOW_REVIEWED"]),
            )
        ):
            previous.status = "EXPIRED" if aware(previous.expires_at) <= now else "DISMISSED"
            previous.rejection_reason = "Superseded by a newer research scan"
        account = session.scalar(select(Portfolio).where(Portfolio.agent_id == agent.id))
        candidates = []
        for symbol in universe(session, settings, agent):
            data, components, proposal, reasons, rejected = {}, {}, {}, [], []
            mode, score = "unavailable", D(0)
            try:
                quote = provider.equity_quote(symbol)
                mode = quote.data_state(now, settings.quote_max_age_seconds)
                if mode == "stale":
                    raise DataUnavailable("stale_quote")
                f = features(provider.bars(symbol, max(30, settings.strategy_slow_window + 10)))
                strategy = TrendMomentumStrategy(provider, settings)
                signal = strategy.evaluate(symbol)
                if agent.agent_type == "options":
                    contracts = rank_contracts(
                        provider.option_chain(symbol),
                        settings,
                        now,
                        account.equity,
                        "PUT" if signal.action == "SELL" else "CALL",
                    )
                    data["ranked_contracts"] = contracts[:20]
                    valid = [c for c in contracts if c["eligible"]]
                    signal = DirectionalMomentumOptionsStrategy(provider, settings, now).evaluate(
                        symbol
                    )
                    if not valid:
                        rejected.append("No eligible option contract")
                    else:
                        from app.market_data.types import Quote

                        q = Quote.model_validate(
                            {
                                k: v
                                for k, v in valid[0]["quote"].items()
                                if k not in {"dte", "spread_percent"}
                            }
                        )
                        signal = replace(
                            signal,
                            quote=q,
                            proposed_entry=q.ask,
                            stop_loss=q.bid * (1 - settings.option_stop_percent / 100),
                            target=q.ask * (1 + settings.option_target_percent / 100),
                        )
                if signal.action != "BUY":
                    rejected.append("No entry signal")
                if regime.regime in {"UNKNOWN", "RISK_OFF"}:
                    rejected.append("Regime blocks new risk")
                components = {
                    "trend": 35 if signal.action == "BUY" else 0,
                    "momentum": 15 if abs(D(f["momentum"])) > 0 else 0,
                    "volume": 15 if D(f["relative_volume"]) >= 1 else 5,
                    "liquidity": 15 if quote.volume >= 10000 else 0,
                    "regime_fit": 10 if regime.regime != "UNKNOWN" else 0,
                }
                score = D(sum(components.values()))
                reasons = [signal.reason]
                data.update(
                    quote=quote.snapshot(now),
                    features=f,
                    regime=regime.regime,
                    event_coverage=settings.event_data_provider,
                )
                if signal.quote and signal.action == "BUY":
                    proposal = dict(
                        symbol=signal.quote.symbol,
                        asset_type=signal.quote.asset_type,
                        action="BUY_TO_OPEN" if agent.agent_type == "options" else "BUY",
                        requested_price=str(signal.proposed_entry),
                        stop_loss=str(signal.stop_loss),
                        take_profit=str(signal.target),
                        reasoning=signal.reason,
                        strategy_name="DirectionalMomentumOptionsStrategy"
                        if agent.agent_type == "options"
                        else strategy.name,
                        strategy_version=strategy.version,
                    )
                if score < settings.opportunity_min_score:
                    rejected.append("Below deterministic score threshold")
            except DataUnavailable as error:
                rejected.append(str(error))
            candidate = OpportunityCandidate(
                scan_id=scan_id,
                agent_id=agent.id,
                symbol=symbol,
                score=score,
                components=components,
                regime=regime.regime,
                data_mode=mode,
                eligible=not rejected,
                reasons=reasons,
                rejection_reasons=rejected,
                snapshot=data,
                proposal=proposal,
            )
            session.add(candidate)
            candidates.append(candidate)
        session.flush()
        candidates.sort(key=lambda c: (not c.eligible, -c.score, c.symbol))
        for rank, candidate in enumerate(candidates, 1):
            status = (
                "SHORTLISTED"
                if candidate.eligible and rank <= settings.opportunity_top_k
                else "DISMISSED"
            )
            session.add(
                OpportunityQueueItem(
                    candidate_id=candidate.id,
                    agent_id=agent.id,
                    rank=rank,
                    status=status,
                    expires_at=now + timedelta(seconds=settings.opportunity_ttl_seconds),
                    rejection_reason="; ".join(candidate.rejection_reasons) or None,
                )
            )
            emit(
                session,
                "opportunity_shortlisted" if status == "SHORTLISTED" else "opportunity_discovered",
                str(agent.id),
                {
                    "candidate_id": str(candidate.id),
                    "message": f"{agent.name}: {candidate.symbol} {status}",
                },
            )
        session.commit()
        return candidates
