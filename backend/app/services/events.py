import asyncio
from collections.abc import AsyncIterator

from app.schemas.events import LiveEvent


async def heartbeat_stream(interval_seconds: float) -> AsyncIterator[str]:
    # A heartbeat is ephemeral: it does not create a database row every five seconds.
    # StreamingResponse cancels this generator when the client disconnects.
    yield "retry: 3000\n\n"
    while True:
        yield LiveEvent(
            event_type="heartbeat", source="backend", payload={"status": "alive"}
        ).as_sse()
        await asyncio.sleep(interval_seconds)
