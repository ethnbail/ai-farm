from datetime import UTC
from typing import Protocol

from sqlalchemy import select

from app.models import EventRisk


class EventSource(Protocol):
    def events(self, symbol, now) -> list[dict]: ...


def aware(stamp):
    return stamp.replace(tzinfo=UTC) if stamp.tzinfo is None else stamp


class EventContextService:
    def context(self, session, settings, symbol, now, data_mode="mock"):
        rows = session.scalars(select(EventRisk).where(EventRisk.symbol.in_([symbol, "*"]))).all()
        risks = [
            dict(
                symbol=r.symbol,
                event_type=r.event_type,
                timestamp=aware(r.timestamp).isoformat(),
                importance=r.importance,
                time_until_event=(aware(r.timestamp) - now).total_seconds(),
                source=r.source,
                warning=r.warning,
            )
            for r in rows
            if r.source == "manual"
            or (
                data_mode == "mock"
                and settings.event_data_provider == "mock"
                and r.source == "mock"
            )
        ]
        return dict(
            status="mock"
            if settings.event_data_provider == "mock" and data_mode == "mock"
            else "unavailable",
            risks=risks,
            warning="No verified live event calendar configured",
        )

    def blocked(self, session, settings, symbol, now, data_mode="mock"):
        context = self.context(session, settings, symbol, now, data_mode)
        if settings.require_event_coverage and context["status"] == "unavailable":
            return "Required event calendar unavailable"
        if settings.block_high_impact_events:
            for event in context["risks"]:
                if (
                    event["importance"] == "high"
                    and abs(event["time_until_event"]) <= settings.event_block_window_minutes * 60
                ):
                    return "High-impact event proximity: " + event["event_type"]
        return None
