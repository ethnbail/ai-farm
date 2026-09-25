import asyncio
import json
import time
from collections.abc import AsyncIterator

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database.session import get_engine
from app.models import SystemEvent
from app.schemas.events import LiveEvent
from app.services.event_store import events_after
from app.services.serialization import public


async def heartbeat_stream(interval_seconds: float) -> AsyncIterator[str]:
    # A heartbeat is ephemeral: it does not create a database row every five seconds.
    # StreamingResponse cancels this generator when the client disconnects.
    yield "retry: 3000\n\n"
    while True:
        yield LiveEvent(
            event_type="heartbeat", source="backend", payload={"status": "alive"}
        ).as_sse()
        await asyncio.sleep(interval_seconds)


def read_events(cursor: int | None):
    with Session(get_engine()) as session:
        if cursor is None:
            latest = session.scalar(select(func.max(SystemEvent.sequence))) or 0
            cursor = max(0, latest - 50)
        return cursor, [public(event) for event in events_after(session, cursor)]


async def live_stream(interval_seconds: float, cursor: int | None = None):
    yield "retry: 3000\n\n"
    next_heartbeat = 0.0
    while True:
        if time.monotonic() >= next_heartbeat:
            heartbeat = LiveEvent(
                event_type="heartbeat", source="backend", payload={"status": "alive"}
            )
            # Heartbeats must not overwrite EventSource's last durable event cursor.
            yield f"event: heartbeat\ndata: {heartbeat.model_dump_json()}\n\n"
            next_heartbeat = time.monotonic() + interval_seconds
        try:
            cursor, events = await asyncio.to_thread(read_events, cursor)
            for event in events:
                yield (
                    f"id: {event['sequence']}\nevent: {event['event_type']}\n"
                    f"data: {json.dumps(event)}\n\n"
                )
                cursor = event["sequence"]
        except SQLAlchemyError:
            pass  # Health reports DB outage; preserve cursor and reconnect automatically.
        await asyncio.sleep(0.5)
