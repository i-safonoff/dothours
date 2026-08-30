# Realtime (WebSocket)

🇬🇧 **English** · [🇷🇺 Русский](REALTIME.ru.md)

## Connecting

```
GET /api/v1/ws?token=<JWT>
```

The token rides in the query string because a browser `WebSocket` can't set
an `Authorization` header. It's the same JWT the REST API uses — a socket
never has more privilege than the session that opened it. An invalid or
missing token closes the connection with code **4401**.

The client can send `{"action": "ping"}` and gets `{"event": "pong"}` back.
Anything else it sends is ignored — that's not an error.

## Message format

```json
{ "event": "timer.stopped", "data": { "entry_id": "…", "minutes": 42 } }
```

## Events

| Event | To whom | When |
|---|---|---|
| `timer.started` | the owner | a timer started |
| `timer.stopped` | the owner | a timer stopped |
| `city.building_leveled_up` | the owner | a building leveled up |
| `notification.created` | the recipient | a notification was created |
| `friend.request_received` | the request's addressee | a friend request arrived |
| `friend.request_accepted` | the sender | the request was accepted |
| `paired_task.progress` | the participant | minutes were credited to a paired task |
| `paired_task.completed` | every participant | a task closed |

`city.building_leveled_up` fires for both a personal city
(`owner_type: "user"`) and a company city (`owner_type: "company"`) — in the
latter case, every member gets it at once, even the ones who tracked
nothing themselves.

## The core principle: an event is a hint, not data

An event says "something about you changed, re-read it," not "here's the
new state." Because of that:

- `data` is minimal — ids, not objects. The source of truth is REST.
- Publishing is cheap and safe: if it races a rolled-back transaction, the
  client makes one extra GET, not shows something untrue.
- The event schema can change without breaking clients — they re-read
  anyway.

## Channels and backends

A channel is "who should hear this," not "what happened":
`user:{id}`, `company:{id}`. A socket subscribes to its own channel and to
the channel of every company the user belongs to; the channel set is fixed
at connect time, so joining a new company means reconnecting.

`WS_BACKEND`:

- `redis` (in Docker) — pub/sub through Redis. Needed as soon as there's
  more than one process: a socket lives on one worker, and an event can be
  born on another one, or in Celery entirely.
- `memory` (default) — an in-process fan-out. Correct only for a single
  process: tests and `uvicorn --reload`.

If Redis is unreachable, the bus logs a warning and keeps working locally —
realtime is never a reason to fail a request.

## Limits

- A subscriber's queue holds 100 events; a slow client drops the extras
  instead of stalling publishing. That's fine for the client precisely
  because events are hints.
- A socket doesn't hold onto a DB connection: the session goes back to the
  pool right after authentication.
- There's no server-side heartbeat — the client pings.
