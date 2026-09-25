from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Bar(BaseModel):
    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int


class Quote(BaseModel):
    model_config = ConfigDict(frozen=True)
    symbol: str
    company_name: str
    asset_type: Literal["equity", "etf", "option"]
    bid: Decimal = Field(ge=0, allow_inf_nan=False)
    ask: Decimal = Field(gt=0, allow_inf_nan=False)
    last: Decimal = Field(ge=0, allow_inf_nan=False)
    volume: int = Field(ge=0)
    timestamp: datetime
    mode: Literal["mock", "live"]
    underlying_symbol: str | None = None
    underlying_price: Decimal | None = None
    option_type: Literal["CALL", "PUT"] | None = None
    strike: Decimal | None = None
    expiration: date | None = None
    contract_multiplier: int = Field(default=1, ge=1)
    iv: Decimal | None = None
    delta: Decimal | None = None
    gamma: Decimal | None = None
    theta: Decimal | None = None
    vega: Decimal | None = None
    open_interest: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def valid_quote(self):
        if self.timestamp.tzinfo is None or self.ask < self.bid:
            raise ValueError("Quotes require aware timestamps and non-crossed bid/ask")
        if self.asset_type == "option":
            if (
                not self.underlying_symbol
                or not self.option_type
                or not self.expiration
                or self.strike is None
                or self.strike <= 0
                or self.underlying_price is None
                or self.underlying_price < 0
                or self.contract_multiplier != 100
            ):
                raise ValueError(
                    "Only fully specified standard 100-share long options are supported"
                )
        elif self.contract_multiplier != 1:
            raise ValueError("Equity multiplier must be one")
        return self

    @property
    def spread_percent(self) -> Decimal:
        return (self.ask - self.bid) / self.ask * 100

    def data_state(self, now: datetime, max_age: int) -> str:
        age = (now - self.timestamp).total_seconds()
        return "stale" if age > max_age or age < -5 else self.mode

    def snapshot(self, now: datetime) -> dict:
        return {
            **self.model_dump(mode="json"),
            "spread_percent": str(self.spread_percent),
            "dte": (self.expiration - now.date()).days if self.expiration else None,
        }


class EquityMarketDataProvider(Protocol):
    def equity_quote(self, symbol: str) -> Quote: ...
    def bars(self, symbol: str, count: int = 30) -> list[Bar]: ...


class OptionsMarketDataProvider(Protocol):
    def option_chain(self, underlying: str) -> list[Quote]: ...
    def option_quote(self, symbol: str) -> Quote: ...


class MarketDataProvider(EquityMarketDataProvider, OptionsMarketDataProvider, Protocol):
    def quote(self, symbol: str, asset_type: str) -> Quote: ...


class DataUnavailable(ValueError):
    pass


def effective_state(state: str, stamp: datetime | None, now: datetime, max_age: int) -> str:
    """Age persisted marks on read without changing the recorded source mode."""
    if state in {"stale", "unavailable"} or stamp is None:
        return state
    aware = stamp.replace(tzinfo=UTC) if stamp.tzinfo is None else stamp
    age = (now - aware).total_seconds()
    return "stale" if age > max_age or age < -5 else state
