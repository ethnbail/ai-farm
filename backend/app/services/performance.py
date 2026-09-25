from datetime import UTC
from decimal import Decimal

from sqlalchemy import select

from app.models import Trade
from app.services.accounting import money, open_positions, percent


def performance(session, portfolio, minimum_trades=5):
    trades = list(
        session.scalars(
            select(Trade).where(Trade.portfolio_id == portfolio.id, Trade.status == "closed")
        )
    )
    pnls = [t.realized_pnl for t in trades if t.realized_pnl is not None]
    winners, losers = [p for p in pnls if p > 0], [p for p in pnls if p < 0]
    enough = len(pnls) >= minimum_trades
    holdings = [
        (aware(t.exit_time) - aware(t.entry_time)).total_seconds() for t in trades if t.exit_time
    ]
    return {
        "starting_balance": portfolio.starting_balance,
        "equity": portfolio.equity,
        "cash": portfolio.cash_balance,
        "market_value": portfolio.market_value,
        "realized_pnl": portfolio.realized_pnl,
        "unrealized_pnl": portfolio.unrealized_pnl,
        "total_return_percent": portfolio.total_return_percent,
        "total_trades": len(trades) + len(open_positions(session, portfolio)),
        "completed_trades": len(trades),
        "winning_trades": len(winners),
        "losing_trades": len(losers),
        "open_positions": len(open_positions(session, portfolio)),
        "win_rate": percent(Decimal(len(winners)), Decimal(len(pnls))) if enough else None,
        "average_winner": money(sum(winners) / len(winners)) if enough and winners else None,
        "average_loser": money(sum(losers) / len(losers)) if enough and losers else None,
        "expectancy": money(sum(pnls) / len(pnls)) if enough else None,
        "profit_factor": (sum(winners, Decimal(0)) / abs(sum(losers))).quantize(Decimal(".0001"))
        if enough and losers
        else None,
        "max_drawdown_percent": portfolio.max_drawdown_percent,
        "current_drawdown_percent": percent(
            portfolio.high_water_mark - portfolio.equity, portfolio.high_water_mark
        ),
        "best_trade": max(pnls) if pnls else None,
        "worst_trade": min(pnls) if pnls else None,
        "average_holding_seconds": sum(holdings) / len(holdings) if holdings else None,
        "exposure_percent": percent(portfolio.market_value, portfolio.equity),
        "sharpe": None,
        "sortino": None,
        "minimum_trades": minimum_trades,
        "statistics_note": None
        if enough
        else f"Rate/expectancy metrics require {minimum_trades} completed trades",
    }


def aware(stamp):
    return stamp.replace(tzinfo=UTC) if stamp.tzinfo is None else stamp.astimezone(UTC)
