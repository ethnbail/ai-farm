from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models import EventCounter, SystemEvent


def emit(session: Session, event_type: str, source: str, payload: dict) -> SystemEvent:
    # This row lock is held until the caller's transaction commits, so sequence
    # order is also commit order. No event is visible for a rolled-back trade.
    sequence = session.scalar(
        update(EventCounter)
        .where(EventCounter.id == 1)
        .values(value=EventCounter.value + 1)
        .returning(EventCounter.value)
    )
    if sequence is None:
        raise RuntimeError("Event counter is missing; run migrations")
    event = SystemEvent(
        event_type=event_type,
        source=source,
        payload=payload,
        sequence=sequence,
        created_at=datetime.now(UTC),
    )
    session.add(event)
    return event


def events_after(session: Session, cursor: int, limit: int = 100) -> list[SystemEvent]:
    return list(
        session.scalars(
            select(SystemEvent)
            .where(SystemEvent.sequence > cursor)
            .order_by(SystemEvent.sequence)
            .limit(limit)
        )
    )
