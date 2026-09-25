from datetime import datetime, time
from functools import lru_cache
from zoneinfo import ZoneInfo

import exchange_calendars

NEW_YORK = ZoneInfo("America/New_York")


@lru_cache
def calendar():
    return exchange_calendars.get_calendar("XNYS", start="2020-01-01", end="2035-12-31")


def market_status(now: datetime) -> dict:
    if now.tzinfo is None:
        raise ValueError("Market clock must be timezone-aware")
    local = now.astimezone(NEW_YORK)
    day = local.date().isoformat()
    result = {
        "session": "closed",
        "timezone": "America/New_York",
        "timestamp": now.isoformat(),
        "regular_open": None,
        "regular_close": None,
    }
    try:
        cal = calendar()
        if not cal.is_session(day):
            return result
        opened = cal.session_open(day).to_pydatetime()
        closed = cal.session_close(day).to_pydatetime()
    except (ValueError, KeyError):
        return result  # Unknown calendar coverage fails closed.
    result.update(regular_open=opened.isoformat(), regular_close=closed.isoformat())
    if opened <= now < closed:
        result["session"] = "regular"
    elif time(4) <= local.time() and now < opened:
        result["session"] = "pre_market"
    elif now >= closed and local.time() < time(20):
        result["session"] = "after_hours"
    return result
