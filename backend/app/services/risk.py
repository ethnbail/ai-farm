"""Final, deterministic entry authority. No strategy or request can skip these checks."""

from datetime import datetime
from decimal import ROUND_DOWN, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.market_data.types import Quote
from app.models import Agent, Portfolio, Trade
from app.schemas.trading import OrderRequest
from app.services.accounting import money, open_positions, percent
from app.services.market_hours import market_status


class RiskRejected(ValueError):
    def __init__(self, rule: str, message: str):
        self.rule = rule
        super().__init__(message)


class RiskEngine:
    def __init__(self, settings: Settings):
        self.settings = settings

    def approve(
        self,
        session: Session,
        agent: Agent,
        portfolio: Portfolio,
        request: OrderRequest,
        quote: Quote,
        fill: Decimal,
        now: datetime,
        fresh_portfolio: bool,
    ) -> tuple[int, dict]:
        s = self.settings

        def require(condition, rule, message):
            if not condition:
                raise RiskRejected(rule, message)

        require(s.trading_mode == "paper", "paper_mode", "Only paper execution is supported")
        require(
            agent.status not in {"paused", "error"},
            "agent_status",
            "Agent is not accepting entries",
        )
        require(
            quote.symbol == request.symbol and quote.asset_type == request.asset_type,
            "instrument",
            "Provider instrument does not match order",
        )
        require(
            (
                agent.agent_type == "equities"
                and quote.asset_type in {"equity", "etf"}
                and request.action == "BUY"
            )
            or (
                agent.agent_type == "options"
                and quote.asset_type == "option"
                and request.action == "BUY_TO_OPEN"
            ),
            "asset_type",
            "Agent cannot trade this asset or action",
        )
        require(
            fresh_portfolio and quote.data_state(now, s.quote_max_age_seconds) != "stale",
            "data_quality",
            "Fresh quotes and portfolio marks are required",
        )
        require(
            not s.regular_hours_only or market_status(now)["session"] == "regular",
            "market_hours",
            "New entries require a regular US market session",
        )
        require(portfolio.equity > 0, "equity", "Account equity must be positive")
        require(
            request.stop_loss is not None
            and request.take_profit is not None
            and 0 < request.stop_loss < quote.bid <= fill < request.take_profit,
            "exit_levels",
            "Entry requires a stop below the bid and target above the fill",
        )
        require(
            session.scalar(
                select(Trade.id)
                .where(
                    Trade.agent_id == agent.id, Trade.status == "open", Trade.portfolio_id.is_(None)
                )
                .limit(1)
            )
            is None,
            "legacy_position",
            "Reconcile legacy open trades before trading this account",
        )
        positions = open_positions(session, portfolio)
        require(
            len(positions) < s.max_open_positions,
            "position_limit",
            "Maximum open positions reached",
        )
        require(
            not any(p.symbol == request.symbol for p in positions),
            "duplicate_position",
            "Position already open",
        )
        for name, baseline, limit in (
            ("daily_loss", portfolio.day_start_equity, s.max_daily_loss_percent),
            ("weekly_loss", portfolio.week_start_equity, s.max_weekly_loss_percent),
        ):
            require(
                percent(baseline - portfolio.equity, baseline) < limit,
                name,
                f"{name} limit reached",
            )
        unit_cost = fill * quote.contract_multiplier
        # The entire long-option premium is at risk, irrespective of a tighter stop.
        unit_risk = unit_cost if quote.asset_type == "option" else fill - request.stop_loss
        budget = portfolio.equity * s.max_risk_per_trade_percent / 100
        available = portfolio.cash_balance - portfolio.equity * s.min_cash_reserve_percent / 100
        limits = [
            budget / unit_risk,
            portfolio.equity * s.max_position_size_percent / 100 / unit_cost,
            available / unit_cost,
            (portfolio.equity * s.max_total_exposure_percent / 100 - portfolio.market_value)
            / unit_cost,
        ]
        if quote.asset_type == "option":
            dte = (quote.expiration - now.date()).days
            require(
                s.min_option_dte <= dte <= s.max_option_dte,
                "option_dte",
                "Option DTE outside allowed range; no 0DTE",
            )
            require(
                quote.spread_percent <= s.max_option_spread_percent,
                "option_spread",
                "Option spread too wide",
            )
            require(
                quote.bid > 0
                and quote.volume >= s.min_option_volume
                and quote.open_interest >= s.min_option_open_interest,
                "option_liquidity",
                "Option liquidity below configured thresholds",
            )
            require(
                len(positions) < s.max_options_positions,
                "options_position_limit",
                "Maximum options positions reached",
            )
            limits.append(portfolio.equity * s.max_option_premium_at_risk_percent / 100 / unit_cost)
        quantity = (
            request.quantity
            if request.quantity is not None
            else max(0, int(min(limits).to_integral_value(rounding=ROUND_DOWN)))
        )
        require(
            quantity > 0,
            "position_size",
            "One whole share/contract exceeds account limits: NO_TRADE",
        )
        cost, risk = money(unit_cost * quantity), money(unit_risk * quantity)
        require(
            cost <= portfolio.cash_balance,
            "buying_power",
            "Insufficient buying power; borrowing is prohibited",
        )
        require(risk <= budget, "risk_per_trade", "Maximum risk per trade exceeded")
        require(
            cost <= portfolio.equity * s.max_position_size_percent / 100,
            "position_size",
            "Maximum position allocation exceeded",
        )
        require(
            portfolio.market_value + cost <= portfolio.equity * s.max_total_exposure_percent / 100,
            "exposure",
            "Total portfolio exposure limit exceeded",
        )
        require(
            portfolio.cash_balance - cost >= portfolio.equity * s.min_cash_reserve_percent / 100,
            "cash_reserve",
            "Minimum cash reserve would be breached",
        )
        if quote.asset_type == "option":
            require(
                cost <= portfolio.equity * s.max_option_premium_at_risk_percent / 100,
                "option_premium",
                "Maximum full premium at risk exceeded",
            )
        return quantity, {
            "quantity": quantity,
            "unit_cost": str(unit_cost),
            "cost": str(cost),
            "maximum_planned_loss": str(risk),
            "risk_budget": str(money(budget)),
            "equity_at_entry": str(portfolio.equity),
            "allocation_percent": str(percent(cost, portfolio.equity)),
            "risk_basis": "full_premium" if quote.asset_type == "option" else "entry_minus_stop",
            "limits": s.model_dump(
                mode="json",
                include={
                    "max_risk_per_trade_percent",
                    "max_position_size_percent",
                    "max_total_exposure_percent",
                    "min_cash_reserve_percent",
                    "max_option_premium_at_risk_percent",
                },
            ),
        }
