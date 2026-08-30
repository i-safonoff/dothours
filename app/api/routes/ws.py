"""The realtime socket.

Auth goes through `?token=` because a browser `WebSocket` cannot set an
Authorization header. The token is the same JWT the REST API uses, so a socket
is never more privileged than the session that opened it.
"""

import asyncio
import json
import logging
import uuid

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.security import decode_access_token
from app.events.bus import bus, company_channel, user_channel
from app.models.user import User
from app.services.companies import user_company_ids

logger = logging.getLogger("dothours.ws")

router = APIRouter(tags=["realtime"])

INVALID_TOKEN_CODE = 4401


def _authenticate(db: Session, token: str | None) -> User | None:
    if not token:
        return None
    subject = decode_access_token(token)
    if subject is None:
        return None
    try:
        user_id = uuid.UUID(subject)
    except ValueError:
        return None
    return db.get(User, user_id)


def _channels_for(db: Session, user: User) -> list[str]:
    """Own channel plus one per company — a shared city changes for everyone at once."""
    return [user_channel(user.id)] + [company_channel(cid) for cid in user_company_ids(db, user.id)]


@router.websocket("/ws")
async def realtime(
    websocket: WebSocket,
    token: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> None:
    user = await asyncio.to_thread(_authenticate, db, token)
    if user is None:
        await websocket.close(code=INVALID_TOKEN_CODE)
        return

    channels = await asyncio.to_thread(_channels_for, db, user)
    # A socket can live for hours; hand the pooled connection back now that the
    # queries it needed are done. The session stays usable, it just reconnects.
    await asyncio.to_thread(db.rollback)

    await websocket.accept()

    async with bus.subscribe(channels) as events:
        pump = asyncio.create_task(_pump(websocket, events))
        try:
            await _read_client(websocket)
        except WebSocketDisconnect:
            pass
        finally:
            pump.cancel()


async def _pump(websocket: WebSocket, events) -> None:
    """Forward bus events to the socket until it is closed."""
    try:
        async for message in events:
            await websocket.send_text(message)
    except (WebSocketDisconnect, RuntimeError):
        pass
    except asyncio.CancelledError:
        raise


async def _read_client(websocket: WebSocket) -> None:
    """The client only ever pings; anything else is ignored, not an error."""
    while True:
        raw = await websocket.receive_text()
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if payload.get("action") == "ping":
            await websocket.send_text(json.dumps({"event": "pong", "data": {}}))
