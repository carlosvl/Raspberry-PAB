"""Alert streaming routes."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import cast

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from raspberry_pab.models import Alert
from raspberry_pab.scheduler import AlertBroker, sse_payload

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


def get_broker(request: Request) -> AlertBroker:
    return cast(AlertBroker, request.app.state.alert_broker)


@router.get("/active")
def active_alert(request: Request) -> Alert | None:
    return get_broker(request).active_alert


@router.get("/stream")
async def alert_stream(request: Request) -> StreamingResponse:
    broker = get_broker(request)

    async def events() -> AsyncIterator[str]:
        yield ": connected\n\n"
        async with broker.subscribe() as queue:
            while True:
                if await request.is_disconnected():
                    break
                alert = await queue.get()
                yield sse_payload(alert)

    return StreamingResponse(events(), media_type="text/event-stream")
