from dataclasses import dataclass
from decimal import Decimal
from typing import Literal, Protocol

from app.core.config import Settings
from app.market_data.types import EquityMarketDataProvider, OptionsMarketDataProvider, Quote


@dataclass(frozen=True)
class Signal:
    action: Literal["BUY", "SELL", "HOLD"]
    reason: str
    proposed_entry: Decimal | None = None
    stop_loss: Decimal | None = None
    target: Decimal | None = None
    quote: Quote | None = None
    metadata: dict | None = None


class Strategy(Protocol):
    name: str
    version: str

    def evaluate(self, symbol: str) -> Signal: ...


class TrendMomentumStrategy:
    name, version = "TrendMomentumStrategy", "1.0"

    def __init__(self, provider: EquityMarketDataProvider, settings: Settings):
        self.provider, self.settings = provider, settings

    def evaluate(self, symbol: str) -> Signal:
        s = self.settings
        bars = self.provider.bars(symbol, s.strategy_slow_window)
        if len(bars) < s.strategy_slow_window:
            return Signal("HOLD", "Insufficient bars")
        fast = (
            sum((b.close for b in bars[-s.strategy_fast_window :]), Decimal(0))
            / s.strategy_fast_window
        )
        slow = (
            sum((b.close for b in bars[-s.strategy_slow_window :]), Decimal(0))
            / s.strategy_slow_window
        )
        quote = self.provider.equity_quote(symbol)
        meta = {"fast_sma": str(fast), "slow_sma": str(slow)}
        if fast > slow and bars[-1].close > bars[-2].close and bars[-1].volume > 0:
            return Signal(
                "BUY",
                "Fast SMA above slow SMA; latest close rising",
                quote.ask,
                quote.last * (1 - s.equity_stop_percent / 100),
                quote.last * (1 + s.equity_target_percent / 100),
                quote,
                meta,
            )
        if fast < slow and bars[-1].close < bars[-2].close:
            return Signal(
                "SELL", "Fast SMA below slow SMA; latest close falling", quote=quote, metadata=meta
            )
        return Signal("HOLD", "Momentum is not confirmed", quote=quote, metadata=meta)


class OptionsScanner:
    def __init__(self, provider: OptionsMarketDataProvider, settings: Settings):
        self.provider, self.settings = provider, settings

    def candidates(self, underlying, kind, now) -> list[Quote]:
        s = self.settings
        return [
            q
            for q in self.provider.option_chain(underlying)
            if q.option_type == kind
            and s.min_option_dte <= (q.expiration - now.date()).days <= s.max_option_dte
            and q.delta is not None
            and s.target_option_delta_min <= abs(q.delta) <= s.target_option_delta_max
            and q.iv is not None
            and 0 < q.iv <= s.max_option_iv
            and q.gamma is not None
            and q.gamma >= 0
            and q.theta is not None
            and q.theta <= 0
            and abs(q.theta) / q.ask * 100 <= s.max_option_theta_decay_percent
            and q.bid > 0
            and q.spread_percent <= s.max_option_spread_percent
            and q.volume >= s.min_option_volume
            and q.open_interest >= s.min_option_open_interest
            and q.data_state(now, s.quote_max_age_seconds) != "stale"
        ]


class OptionsSelector:
    def select(self, candidates: list[Quote]) -> Quote | None:
        return min(
            candidates,
            key=lambda q: (q.spread_percent, abs(abs(q.delta) - Decimal(".55")), q.symbol),
            default=None,
        )


class OptionsPaperStrategy(Protocol):
    name: str
    version: str

    def evaluate(self, underlying: str) -> Signal: ...


class DirectionalMomentumOptionsStrategy:
    name, version = "DirectionalMomentumOptionsStrategy", "1.0"

    def __init__(self, provider, settings, now):
        self.provider, self.settings, self.now = provider, settings, now

    def evaluate(self, underlying: str) -> Signal:
        trend = TrendMomentumStrategy(self.provider, self.settings).evaluate(underlying)
        if trend.action == "HOLD":
            return Signal("HOLD", trend.reason)
        kind = "CALL" if trend.action == "BUY" else "PUT"
        quote = OptionsSelector().select(
            OptionsScanner(self.provider, self.settings).candidates(underlying, kind, self.now)
        )
        if quote is None:
            return Signal("HOLD", "NO_TRADE: no contract meets DTE, Greeks and liquidity filters")
        return Signal(
            "BUY",
            f"{trend.reason}; long {kind}; risk engine must approve full premium",
            quote.ask,
            quote.bid * (1 - self.settings.option_stop_percent / 100),
            quote.ask * (1 + self.settings.option_target_percent / 100),
            quote,
            trend.metadata,
        )
