"""Read-only market endpoints. No account/order URLs or configurable host exist."""

import time
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import httpx

from app.market_data.types import Bar, DataUnavailable, Quote


def rows(value):
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def collection(payload, container, key):
    value = payload.get(container) or {}
    if not isinstance(value, dict):
        raise DataUnavailable("Malformed market response container")
    return rows(value.get(key))


class TradierMarketDataProvider:
    name = "tradier"
    wall_clock = True

    def __init__(self, settings, now, transport=None):
        self.settings, self.now, self.transport = settings, now, transport
        self.requests = 0
        self.blocked_until = 0.0
        self.cache = {}
        self.state, self.message = "unavailable", "No quote retrieved yet"

    def _get(self, path, **params):
        if path not in {"quotes", "history", "options/chains", "options/expirations"}:
            raise DataUnavailable("Unsupported market-data resource")
        if time.time() < self.blocked_until:
            raise DataUnavailable("Market provider rate limit active")
        key = (path, tuple(sorted(params.items())))
        if key in self.cache:
            return self.cache[key]
        for attempt in range(self.settings.market_retries + 1):
            if self.requests >= self.settings.market_max_requests_per_scan:
                raise DataUnavailable("Market request budget exhausted")
            self.requests += 1
            try:
                with httpx.Client(
                    timeout=self.settings.market_timeout_seconds,
                    transport=self.transport,
                    follow_redirects=False,
                ) as client:
                    response = client.get(
                        f"https://api.tradier.com/v1/markets/{path}",
                        params=params,
                        headers={
                            "Authorization": "Bearer "
                            + self.settings.market_data_api_key.get_secret_value(),
                            "Accept": "application/json",
                        },
                    )
                if (
                    response.status_code == 429
                    or response.headers.get("X-Ratelimit-Available") == "0"
                ):
                    # Bound local backoff; no busy retries or waiting through a long reset.
                    delay = 60.0
                    try:
                        delay = max(
                            delay,
                            float(response.headers.get("Retry-After", 0)),
                            float(response.headers.get("X-Ratelimit-Expiry", 0)) / 1000
                            - time.time(),
                        )
                    except ValueError:
                        pass
                    self.blocked_until = time.time() + min(delay, 3600)
                if response.status_code == 429:
                    raise DataUnavailable("Market provider rate limit hit")
                if response.status_code >= 500 and attempt < self.settings.market_retries:
                    time.sleep(0.2 * (attempt + 1))
                    continue
                if response.status_code != 200:
                    raise DataUnavailable(f"Market provider HTTP {response.status_code}")
                if len(response.content) > 5_000_000:
                    raise DataUnavailable("Market response exceeds size limit")
                payload = response.json()
                if not isinstance(payload, dict):
                    raise DataUnavailable("Malformed market response")
                self.cache[key] = payload
                return payload
            except (httpx.HTTPError, ValueError, AttributeError) as error:
                if isinstance(error, DataUnavailable):
                    self.state, self.message = "unavailable", str(error)
                    raise
                if (
                    isinstance(error, httpx.TransportError)
                    and attempt < self.settings.market_retries
                ):
                    time.sleep(0.2 * (attempt + 1))
                    continue
                self.state, self.message = (
                    "unavailable",
                    "Market request failed or malformed response",
                )
                raise DataUnavailable(self.message) from None
        raise DataUnavailable("Market request failed")

    def _quote(self, raw, underlying=None):
        try:
            asset = {"stock": "equity", "etf": "etf", "option": "option"}[raw["type"]]
            timestamp = min(
                datetime.fromtimestamp(int(raw[k]) / 1000, UTC) for k in ["bid_date", "ask_date"]
            )
            extra = {}
            if asset == "option":
                base = underlying or self.equity_quote(raw["underlying"])
                greeks = raw.get("greeks") or {}
                stamp = None
                if greeks.get("updated_at"):
                    parsed = datetime.fromisoformat(greeks["updated_at"])
                    stamp = parsed if parsed.tzinfo else None
                extra = dict(
                    underlying_symbol=raw["underlying"],
                    underlying_price=base.last,
                    option_type=raw["option_type"].upper(),
                    strike=raw["strike"],
                    expiration=raw["expiration_date"],
                    contract_multiplier=raw["contract_size"],
                    open_interest=raw.get("open_interest") or 0,
                    iv=greeks.get("mid_iv"),
                    delta=greeks.get("delta"),
                    gamma=greeks.get("gamma"),
                    theta=greeks.get("theta"),
                    vega=greeks.get("vega"),
                    greeks_timestamp=stamp,
                )
                timestamp = min(timestamp, base.timestamp)
            quote = Quote(
                symbol=raw["symbol"],
                company_name=raw.get("description", raw["symbol"]),
                asset_type=asset,
                bid=raw["bid"],
                ask=raw["ask"],
                last=raw["last"],
                volume=raw["volume"],
                timestamp=timestamp,
                mode="live",
                **extra,
            )
            self.state = quote.data_state(self.now, self.settings.quote_max_age_seconds)
            self.message = (
                "Observed market quote" if self.state == "live" else "Provider quote is stale"
            )
            return quote
        except (KeyError, ValueError, TypeError, OverflowError, AttributeError):
            self.state, self.message = "unavailable", "Invalid or incomplete normalized quote"
            raise DataUnavailable(self.message) from None

    def quote(self, symbol, asset_type):
        response = self._get("quotes", symbols=symbol, greeks="true")
        quotes = collection(response, "quotes", "quote")
        matching = [q for q in quotes if isinstance(q, dict) and q.get("symbol") == symbol]
        if len(matching) != 1:
            raise DataUnavailable("Requested quote unavailable")
        result = self._quote(matching[0])
        if asset_type == "option" and result.asset_type != "option":
            raise DataUnavailable("Wrong instrument returned")
        return result

    def equity_quote(self, symbol):
        quote = self.quote(symbol, "equity")
        if quote.asset_type not in {"equity", "etf"}:
            raise DataUnavailable("Expected an equity or ETF")
        return quote

    def option_quote(self, symbol):
        return self.quote(symbol, "option")

    def bars(self, symbol, count=30):
        response = self._get(
            "history",
            symbol=symbol,
            interval="daily",
            start=(self.now.date() - timedelta(days=count * 3)).isoformat(),
            end=self.now.date().isoformat(),
        )
        try:
            result = [
                Bar(
                    timestamp=datetime.fromisoformat(r["date"]).replace(tzinfo=UTC),
                    open=Decimal(str(r["open"])),
                    high=Decimal(str(r["high"])),
                    low=Decimal(str(r["low"])),
                    close=Decimal(str(r["close"])),
                    volume=int(r["volume"]),
                )
                for r in collection(response, "history", "day")
                if r["date"] < self.now.date().isoformat()
            ]
            result.sort(key=lambda b: b.timestamp)
            if not result or (self.now - result[-1].timestamp).total_seconds() > 5 * 86400:
                raise ValueError("History stale")
            if any(
                b.close <= 0
                or b.volume < 0
                or b.low > min(b.open, b.close)
                or b.high < max(b.open, b.close)
                for b in result
            ):
                raise ValueError("Invalid OHLC")
            return result[-count:]
        except (ValueError, KeyError, TypeError):
            raise DataUnavailable("Historical bars unavailable, malformed or stale") from None

    def option_chain(self, underlying):
        base = self.equity_quote(underlying)
        response = self._get("options/expirations", symbol=underlying)
        try:
            dates = sorted(
                d
                for d in collection(response, "expirations", "date")
                if self.settings.min_option_dte
                <= (datetime.fromisoformat(d).date() - self.now.date()).days
                <= self.settings.max_option_dte
            )
            result = []
            for expiration in dates[: self.settings.market_max_chain_expirations]:
                response = self._get(
                    "options/chains", symbol=underlying, expiration=expiration, greeks="true"
                )
                for raw in collection(response, "options", "option"):
                    try:
                        q = self._quote(raw, base)
                        if q.underlying_symbol == underlying:
                            result.append(q)
                    except DataUnavailable:
                        continue
            if not result:
                raise DataUnavailable("Options chain unavailable or no valid contracts")
            return result
        except (ValueError, KeyError, TypeError):
            raise DataUnavailable("Options chain unavailable or malformed") from None
