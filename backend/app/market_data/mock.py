"""Synthetic fixtures, not historical observations or external live prices."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal as D

from app.market_data.types import Bar, DataUnavailable, Quote

DEMO_TIME = datetime(2026, 9, 24, 14, 0, tzinfo=UTC)


class MockMarketDataProvider:
    def __init__(self, tick: int = 0, scenario: str = "target", now: datetime = DEMO_TIME):
        self.tick, self.scenario, self.now = tick, scenario, now

    def equity_quote(self, symbol: str) -> Quote:
        bases = {"NVDA": D("100"), "SPY": D("550"), "FARM": D("3")}
        if symbol not in bases:
            raise DataUnavailable(f"No mock equity fixture for {symbol}")
        # Fixed paths support both gains and losses. They never claim profitability.
        steps = (
            [D("0"), D(".01"), D(".06")]
            if self.scenario == "target"
            else [D("0"), D("-.01"), D("-.06")]
        )
        mid = bases[symbol] * (1 + steps[min(self.tick, 2)])
        return Quote(
            symbol=symbol,
            company_name=f"{symbol} (synthetic fixture)",
            asset_type="etf" if symbol == "SPY" else "equity",
            bid=mid - D(".01"),
            ask=mid + D(".01"),
            last=mid,
            volume=1_000_000,
            timestamp=self.now,
            mode="mock",
        )

    def bars(self, symbol: str, count: int = 30) -> list[Bar]:
        last = self.equity_quote(symbol).last
        direction = D("1") if self.scenario == "target" else D("-1")
        closes = [last * (1 - direction * D(".002") * (count - i - 1)) for i in range(count)]
        return [
            Bar(
                timestamp=self.now - timedelta(minutes=count - i),
                open=c,
                high=c * D("1.001"),
                low=c * D(".999"),
                close=c,
                volume=100_000 + i * 100,
            )
            for i, c in enumerate(closes)
        ]

    def option_chain(self, underlying: str) -> list[Quote]:
        self.equity_quote(underlying)
        expiration = self.now.date() + timedelta(days=21)
        expiration += timedelta(days=(4 - expiration.weekday()) % 7)
        strike = "3" if underlying == "FARM" else "550"
        return [
            self.option_quote(f"{underlying}_{expiration:%Y%m%d}_{kind}_{strike}")
            for kind in ("CALL", "PUT")
        ]

    def option_quote(self, symbol: str) -> Quote:
        try:
            underlying, expiry, kind, strike = symbol.split("_")
            expiration = datetime.strptime(expiry, "%Y%m%d").date()
            if underlying not in {"FARM", "SPY"} or kind not in {"CALL", "PUT"}:
                raise ValueError("Unknown fixture")
        except (ValueError, TypeError) as exc:
            raise DataUnavailable("No matching mock option contract") from exc
        # FARM is a fictional $3 underlying, so one 100-share contract can genuinely
        # fit a $20 full-premium risk cap. SPY's costly fixture must be rejected.
        base = D(".15") if underlying == "FARM" else D("6")
        moves = (
            [D("1"), D("1.2"), D("1.8")]
            if self.scenario == "target"
            else [D("1"), D(".9"), D(".5")]
        )
        ask = base * moves[min(self.tick, 2)]
        return Quote(
            symbol=symbol,
            company_name=f"{underlying} mock {kind.lower()}",
            asset_type="option",
            bid=ask - D(".01"),
            ask=ask,
            last=ask - D(".005"),
            volume=250,
            timestamp=self.now,
            mode="mock",
            underlying_symbol=underlying,
            underlying_price=self.equity_quote(underlying).last,
            option_type=kind,
            strike=D(strike),
            expiration=expiration,
            contract_multiplier=100,
            iv=D(".40"),
            delta=D(".55") if kind == "CALL" else D("-.55"),
            gamma=D(".08"),
            theta=D("-.005"),
            vega=D(".03"),
            open_interest=1000,
        )

    def quote(self, symbol: str, asset_type: str) -> Quote:
        return self.option_quote(symbol) if asset_type == "option" else self.equity_quote(symbol)
