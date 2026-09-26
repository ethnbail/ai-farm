from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Bar(BaseModel):
    timestamp: datetime
    open: Decimal = Field(gt=0, allow_inf_nan=False)
    high: Decimal = Field(gt=0, allow_inf_nan=False)
    low: Decimal = Field(gt=0, allow_inf_nan=False)
    close: Decimal = Field(gt=0, allow_inf_nan=False)
    volume: int = Field(ge=0)

    @model_validator(mode="after")
    def valid_bar(self):
        if (
            self.timestamp.tzinfo is None
            or self.low > min(self.open, self.close)
            or self.high < max(self.open, self.close)
        ):
            raise ValueError("Bars require aware timestamps and valid OHLC ranges")
        return self


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
    underlying_price: Decimal | None = Field(default=None, ge=0, allow_inf_nan=False)
    option_type: Literal["CALL", "PUT"] | None = None
    strike: Decimal | None = Field(default=None, gt=0, allow_inf_nan=False)
    expiration: date | None = None
    contract_multiplier: int = Field(default=1, ge=1)
    iv: Decimal | None = Field(default=None, ge=0, allow_inf_nan=False)
    delta: Decimal | None = Field(default=None, ge=-1, le=1, allow_inf_nan=False)
    gamma: Decimal | None = Field(default=None, ge=0, allow_inf_nan=False)
    theta: Decimal | None = Field(default=None, allow_inf_nan=False)
    vega: Decimal | None = Field(default=None, ge=0, allow_inf_nan=False)
    open_interest: int = Field(default=0, ge=0)
    greeks_timestamp: datetime | None = None

    @model_validator(mode="after")
    def valid_quote(self):
        if self.timestamp.tzinfo is None or self.ask < self.bid:
            raise ValueError("Quotes require aware timestamps and non-crossed bid/ask")
        if self.greeks_timestamp is not None and self.greeks_timestamp.tzinfo is None:
            raise ValueError("Greek timestamps must be timezone aware")
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


class HistoricalSeries(BaseModel):
    symbol: str
    bars: list[Bar]
    interval: str = "daily"
    data_mode: str
    timestamp: datetime


class OptionContract(Quote):
    asset_type: Literal["option"] = "option"


class OptionChain(BaseModel):
    underlying: str
    contracts: list[OptionContract]
    timestamp: datetime
    data_mode: str


class MarketSnapshot(BaseModel):
    quote: Quote
    features: dict[str, str | int | None]
    data_state: str
    timestamp: datetime


class MarketStatus(BaseModel):
    provider: str
    effective_provider: str
    state: str
    message: str
    timestamp: datetime | None = None


def effective_state(state: str, stamp: datetime | None, now: datetime, max_age: int) -> str:
    """Age persisted marks on read without changing the recorded source mode."""
    if state in {"stale", "unavailable"} or stamp is None:
        return state
    aware = stamp.replace(tzinfo=UTC) if stamp.tzinfo is None else stamp
    age = (now - aware).total_seconds()
    return "stale" if age > max_age or age < -5 else state
