"""The only execution implementation: transactional, long-only simulated accounting."""

import logging
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.market_data.types import DataUnavailable, MarketDataProvider, Quote
from app.models import (
    Agent,
    Fill,
    OptionContractSnapshot,
    Order,
    Portfolio,
    Position,
    RiskEvent,
    Trade,
)
from app.schemas.trading import ExecutionResult, OrderRequest
from app.services.accounting import (
    mark_portfolio,
    money,
    open_positions,
    percent,
    price,
)
from app.services.event_store import emit
from app.services.market_hours import market_status
from app.services.risk import RiskEngine, RiskRejected

logger = logging.getLogger(__name__)


class PaperModeError(RuntimeError):
    pass


def require_paper(settings: Settings) -> None:
    if settings.trading_mode != "paper":
        logger.error("Execution blocked: TRADING_MODE must be paper; no real executor exists")
        raise PaperModeError("Execution blocked: Phase 2 supports TRADING_MODE=paper only")


def simulated_price(quote: Quote, buying: bool, settings: Settings) -> Decimal:
    slip = (
        settings.option_slippage_percent / 100
        if quote.asset_type == "option"
        else settings.equity_slippage_bps / 10000
    )
    return price(quote.ask * (1 + slip) if buying else quote.bid * (1 - slip))


class PaperBroker:
    def __init__(
        self, session: Session, settings: Settings, provider: MarketDataProvider, now: datetime
    ):
        self.session, self.settings, self.provider, self.now = session, settings, provider, now

    def execute(self, request: OrderRequest, *, exit_reason: str = "manual") -> ExecutionResult:
        require_paper(self.settings)
        if self.now.tzinfo is None:
            raise ValueError("Execution clock must be timezone-aware")
        session = self.session
        try:
            # A PostgreSQL row lock serializes all fills and marks for this account.
            portfolio = session.scalar(
                select(Portfolio)
                .where(Portfolio.agent_id == request.agent_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if portfolio is None:
                raise ValueError("Portfolio not found; seed development accounts first")
            old = session.scalar(
                select(Order).where(
                    Order.portfolio_id == portfolio.id,
                    Order.client_order_id == request.client_order_id,
                )
            )
            if old is not None:
                if old.request != request.model_dump(mode="json"):
                    raise ValueError("Idempotency key reused for a different request")
                fill = session.scalar(select(Fill).where(Fill.order_id == old.id))
                result = ExecutionResult(
                    status=old.status,
                    order_id=old.id,
                    trade_id=fill.trade_id if fill else None,
                    reason=old.rejection_reason,
                )
                session.commit()
                return result
            order = Order(
                portfolio_id=portfolio.id,
                client_order_id=request.client_order_id,
                action=request.action,
                symbol=request.symbol,
                requested_price=request.requested_price,
                quantity=request.quantity or 0,
                status="rejected",
                request=request.model_dump(mode="json"),
                created_at=self.now,
            )
            session.add(order)
            session.flush()
            try:
                quote = self.provider.quote(request.symbol, request.asset_type)
                if quote.symbol != request.symbol or quote.asset_type != request.asset_type:
                    raise RiskRejected("instrument", "Quote does not match requested instrument")
                if quote.data_state(self.now, self.settings.quote_max_age_seconds) == "stale":
                    raise RiskRejected("data_quality", "Stale quote cannot execute")
                if request.action in {"BUY", "BUY_TO_OPEN"}:
                    fresh = mark_portfolio(
                        session,
                        portfolio,
                        self.provider,
                        self.now,
                        self.settings.quote_max_age_seconds,
                    )
                    fill_price = simulated_price(quote, True, self.settings)
                    quantity, calculation = RiskEngine(self.settings).approve(
                        session,
                        session.get(Agent, request.agent_id),
                        portfolio,
                        request,
                        quote,
                        fill_price,
                        self.now,
                        fresh,
                    )
                    trade = self._open(
                        portfolio, order, request, quote, fill_price, quantity, calculation
                    )
                else:
                    trade = self._close(portfolio, order, request, quote, exit_reason)
                order.status = "filled"
                mark_portfolio(
                    session,
                    portfolio,
                    self.provider,
                    self.now,
                    self.settings.quote_max_age_seconds,
                    snapshot=True,
                )
                emit(
                    session,
                    "portfolio_updated",
                    str(request.agent_id),
                    {
                        "agent_id": str(request.agent_id),
                        "equity": str(portfolio.equity),
                        "message": "Paper portfolio updated",
                    },
                )
                result = ExecutionResult(status="filled", order_id=order.id, trade_id=trade.id)
            except (RiskRejected, DataUnavailable) as error:
                rule = error.rule if isinstance(error, RiskRejected) else "data_unavailable"
                order.rejection_reason = str(error)
                session.add(
                    RiskEvent(
                        portfolio_id=portfolio.id,
                        order_id=order.id,
                        rule=rule,
                        details={"reason": str(error), "symbol": request.symbol},
                        created_at=self.now,
                    )
                )
                emit(
                    session,
                    "risk_trade_rejected",
                    str(request.agent_id),
                    {
                        "agent_id": str(request.agent_id),
                        "order_id": str(order.id),
                        "rule": rule,
                        "message": str(error),
                        "symbol": request.symbol,
                    },
                )
                result = ExecutionResult(status="rejected", order_id=order.id, reason=str(error))
            session.commit()
            return result
        except Exception:
            session.rollback()
            raise

    def _fill(self, order, trade, quote, fill_price, quantity, buying):
        requested = order.requested_price or quote.last
        notional = money(fill_price * quantity * quote.contract_multiplier)
        order.quantity, order.requested_price = quantity, requested
        self.session.add(
            Fill(
                order_id=order.id,
                trade_id=trade.id,
                action=order.action,
                quantity=quantity,
                requested_price=requested,
                price=fill_price,
                notional=notional,
                estimated_slippage=money(
                    abs(fill_price - (quote.ask if buying else quote.bid))
                    * quantity
                    * quote.contract_multiplier
                ),
                bid=quote.bid,
                ask=quote.ask,
                timestamp=self.now,
                data_timestamp=quote.timestamp,
                market_data_mode=quote.mode,
            )
        )
        return notional

    def _open(self, portfolio, order, request, quote, fill_price, quantity, calculation):
        cost = money(fill_price * quantity * quote.contract_multiplier)
        trade = Trade(
            agent_id=request.agent_id,
            portfolio_id=portfolio.id,
            asset_type=quote.asset_type,
            symbol=quote.symbol,
            company_name=quote.company_name,
            side="buy",
            quantity=quantity,
            entry_price=fill_price,
            requested_price=request.requested_price or quote.last,
            fill_price=fill_price,
            stop_loss=request.stop_loss,
            take_profit=request.take_profit,
            status="open",
            entry_time=self.now,
            reasoning=request.reasoning,
            position_size=cost,
            account_equity_at_entry=portfolio.equity,
            percent_allocated=percent(cost, portfolio.equity),
            maximum_planned_loss=Decimal(calculation["maximum_planned_loss"]),
            strategy_name=request.strategy_name,
            strategy_version=request.strategy_version,
            market_data_mode=quote.mode,
            data_timestamp=quote.timestamp,
            entry_snapshot=quote.snapshot(self.now),
            risk_calculation=calculation,
            realized_pnl=Decimal("0"),
        )
        self.session.add(trade)
        self.session.flush()
        value = money(quote.bid * quantity * quote.contract_multiplier)
        position = Position(
            portfolio_id=portfolio.id,
            trade_id=trade.id,
            asset_type=quote.asset_type,
            symbol=quote.symbol,
            company_name=quote.company_name,
            quantity=quantity,
            average_entry_price=fill_price,
            cost_basis=cost,
            current_price=quote.bid,
            market_value=value,
            unrealized_pnl=value - cost,
            stop_loss=request.stop_loss,
            take_profit=request.take_profit,
            status="open",
            opened_at=self.now,
            underlying_symbol=quote.underlying_symbol,
            option_type=quote.option_type,
            strike=quote.strike,
            expiration=quote.expiration,
            contract_multiplier=quote.contract_multiplier,
            entry_iv=quote.iv,
            entry_delta=quote.delta,
            entry_gamma=quote.gamma,
            entry_theta=quote.theta,
            entry_vega=quote.vega,
            bid=quote.bid,
            ask=quote.ask,
            data_timestamp=quote.timestamp,
            data_state=quote.mode,
        )
        self.session.add(position)
        if quote.asset_type == "option":
            self.session.add(
                OptionContractSnapshot(trade_id=trade.id, snapshot=quote.snapshot(self.now))
            )
        portfolio.cash_balance = money(
            portfolio.cash_balance - self._fill(order, trade, quote, fill_price, quantity, True)
        )
        emit(
            self.session,
            "trade_opened",
            str(request.agent_id),
            {
                "agent_id": str(request.agent_id),
                "trade_id": str(trade.id),
                "symbol": quote.symbol,
                "message": f"Opened paper {quote.symbol}",
                "data_mode": quote.mode,
            },
        )
        return trade

    def _close(self, portfolio, order, request, quote, exit_reason):
        statement = select(Position).where(
            Position.portfolio_id == portfolio.id, Position.status == "open"
        )
        statement = (
            statement.where(Position.id == request.position_id)
            if request.position_id
            else statement.where(Position.symbol == request.symbol)
        )
        position = self.session.scalar(statement)
        if (
            position is None
            or position.symbol != request.symbol
            or position.asset_type != request.asset_type
        ):
            raise RiskRejected("ownership", "No matching open position in this agent's portfolio")
        allowed = (
            {"SELL_TO_CLOSE", "CLOSE"} if position.asset_type == "option" else {"SELL", "CLOSE"}
        )
        if request.action not in allowed:
            raise RiskRejected("action", "Invalid closing action for this instrument")
        quantity = request.quantity or position.quantity
        if quantity > position.quantity:
            raise RiskRejected("quantity", "Cannot sell more than this portfolio owns")
        settlement = exit_reason == "expiration_cash_settlement"
        if settlement:
            if position.asset_type != "option" or not self._expired(position):
                raise RiskRejected(
                    "expiration", "Settlement is only allowed after option expiration"
                )
            underlying = self.provider.equity_quote(position.underlying_symbol)
            if underlying.data_state(self.now, self.settings.quote_max_age_seconds) == "stale":
                raise RiskRejected("data_quality", "Fresh underlying quote required for settlement")
            intrinsic = max(
                Decimal(0),
                underlying.last - position.strike
                if position.option_type == "CALL"
                else position.strike - underlying.last,
            )
            quote = quote.model_copy(update={"bid": intrinsic, "ask": intrinsic, "last": intrinsic})
        if quote.bid <= 0 and not settlement:
            raise RiskRejected("liquidity", "No executable bid; position remains open")
        trade = self.session.get(Trade, position.trade_id)
        fill_price = (
            price(quote.bid) if settlement else simulated_price(quote, False, self.settings)
        )
        if exit_reason == "stop_loss" and quote.bid > position.stop_loss:
            raise RiskRejected("trigger", "Stop is no longer crossed")
        if exit_reason == "take_profit" and quote.bid < position.take_profit:
            raise RiskRejected("trigger", "Target is no longer crossed")
        basis = (
            position.cost_basis
            if quantity == position.quantity
            else money(position.cost_basis * quantity / position.quantity)
        )
        proceeds = self._fill(order, trade, quote, fill_price, quantity, False)
        pnl = money(proceeds - basis)
        portfolio.cash_balance = money(portfolio.cash_balance + proceeds)
        portfolio.realized_pnl = money(portfolio.realized_pnl + pnl)
        previously_closed = int(trade.quantity) - position.quantity
        trade.exit_price = price(
            ((trade.exit_price or Decimal(0)) * previously_closed + fill_price * quantity)
            / (previously_closed + quantity)
        )
        trade.realized_pnl = money((trade.realized_pnl or Decimal(0)) + pnl)
        position.quantity -= quantity
        position.cost_basis = money(position.cost_basis - basis)
        position.current_price, position.bid, position.ask = quote.bid, quote.bid, quote.ask
        position.data_timestamp, position.data_state = quote.timestamp, quote.mode
        position.market_value = money(quote.bid * position.quantity * position.contract_multiplier)
        position.unrealized_pnl = money(position.market_value - position.cost_basis)
        trade.realized_return_percent = percent(
            trade.realized_pnl, trade.position_size - position.cost_basis
        )
        trade.exit_reason = exit_reason
        if position.quantity == 0:
            position.status, position.closed_at = "closed", self.now
            trade.status, trade.exit_time = "closed", self.now
        if exit_reason in {"stop_loss", "take_profit"}:
            emit(
                self.session,
                f"{exit_reason}_triggered",
                str(request.agent_id),
                {
                    "agent_id": str(request.agent_id),
                    "trade_id": str(trade.id),
                    "symbol": quote.symbol,
                    "message": (
                        f"{exit_reason.replace('_', ' ').title()} triggered for {quote.symbol}"
                    ),
                },
            )
        emit(
            self.session,
            "trade_closed" if position.quantity == 0 else "position_reduced",
            str(request.agent_id),
            {
                "agent_id": str(request.agent_id),
                "trade_id": str(trade.id),
                "symbol": quote.symbol,
                "realized_pnl": str(pnl),
                "message": f"Paper {quote.symbol} {exit_reason}: ${pnl}",
            },
        )
        return trade

    def _expired(self, position):
        if not position.expiration:
            return False
        if self.now.date() > position.expiration:
            return True
        close = market_status(self.now)["regular_close"]
        return (
            self.now.date() == position.expiration
            and close is not None
            and self.now >= datetime.fromisoformat(close)
        )

    def monitor(self, agent_id) -> list[ExecutionResult]:
        require_paper(self.settings)
        portfolio = self.session.scalar(
            select(Portfolio)
            .where(Portfolio.agent_id == agent_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if portfolio is None:
            return []
        mark_portfolio(
            self.session,
            portfolio,
            self.provider,
            self.now,
            self.settings.quote_max_age_seconds,
            snapshot=True,
        )
        # Capture triggers, release the marking transaction, then re-lock/recheck at execution.
        triggers = []
        for position in open_positions(self.session, portfolio):
            if position.data_state in {"stale", "unavailable"}:
                continue
            reason = (
                "expiration_cash_settlement"
                if self._expired(position)
                else "stop_loss"
                if position.current_price <= position.stop_loss
                else "take_profit"
                if position.current_price >= position.take_profit
                else None
            )
            if reason:
                triggers.append((position.id, position.symbol, position.asset_type, reason))
        emit(
            self.session,
            "portfolio_updated",
            str(agent_id),
            {"agent_id": str(agent_id), "message": "Paper positions marked"},
        )
        self.session.commit()
        return [
            self.execute(
                OrderRequest(
                    agent_id=agent_id,
                    position_id=pid,
                    symbol=symbol,
                    asset_type=asset,
                    action="CLOSE",
                    client_order_id=f"{pid}:{reason}:{int(self.now.timestamp())}",
                    reasoning=f"Automatic {reason}",
                ),
                exit_reason=reason,
            )
            for pid, symbol, asset, reason in triggers
        ]
