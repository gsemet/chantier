"""The API's WebSocket binding (`GET /api/v1/ws`): the upgrade judged as a request, the `hello`
handshake, then `call`, `sub` and `unsub` frames, with `event` and `tick` frames pushed back.
`starlette` is imported inside `build`, as `app.py` does: the board imports it when it serves."""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import threading
from typing import Any

from pydantic import ValidationError

from chantier.board import guard
from chantier.board import key as keys
from chantier.board.api import auth, ops, protocol, times
from chantier.board.api.push import Subscription
from chantier.board.context import Context
from chantier.core import clock

PATH = "/api/v1/ws"
ID_MAX = 64  # characters of a frame's `id`
GOING_AWAY, TRY_AGAIN = 1001, 1013
BAD_FRAME, BAD_KEY, TIMED_OUT, OTHER_PROTOCOL = 4400, 4401, 4408, 4426
HELLO_REFUSED = "the first frame is a hello: " + '{"t": "hello", "protocol": 1, "client": "..."}'
NO_ID = "a frame of the protocol is a JSON object with its kind in `t`"
SUBS_FULL = f"too many subscriptions: at most {times.MAX_SUBS}"
TOO_MANY_CLIENTS = "too many clients"
Frame = dict[str, Any]


def other_protocol(version: str, asked: int) -> str:
    return (
        f"this is chantier {version}, protocol {protocol.PROTOCOL}; the client speaks protocol "
        f"{asked}: use a client of chantier {version}"
    )


class Gate:
    """The events of a new subscription are held until its `result` is queued: a `result`
    always comes before the first `event`."""

    def __init__(self, post: Any) -> None:
        self._post, self._held = post, list[Frame]()
        self._open = False
        self._lock = threading.Lock()

    def sink(self, event: Frame) -> None:
        with self._lock:
            if not self._open:
                self._held.append(event)
                return
        self._post({"t": "event", **event})

    def release(self) -> None:
        with self._lock:
            self._open = True
            for event in self._held:
                self._post({"t": "event", **event})
            self._held.clear()


class Connection:
    """One open WebSocket. `post` and `drop` may be called from any thread."""

    def __init__(self, ctx: Context, ws: Any) -> None:
        self.ctx, self.ws = ctx, ws
        self.loop = asyncio.get_running_loop()
        self.welcomed = False
        self.credential: str | None = None  # the key this socket was let in with
        self.out: asyncio.Queue[Frame | None] = asyncio.Queue()
        self.subs: dict[str, Subscription | None] = {}  # None: reserved, being made
        self.tasks: set[asyncio.Task[None]] = set()

    def post(self, frame: Frame) -> None:
        self.loop.call_soon_threadsafe(self.out.put_nowait, frame)

    async def close(self, code: int, reason: str = "") -> None:
        with contextlib.suppress(Exception):  # already closing
            await self.ws.close(code, reason)

    def drop(self, code: int) -> None:
        with contextlib.suppress(RuntimeError):  # the loop is gone: the server is stopping
            asyncio.run_coroutine_threadsafe(self.close(code), self.loop)

    async def fault(self, code: str, error: str, close: int) -> None:
        with contextlib.suppress(Exception):
            await self.ws.send_text(json.dumps({"t": "error", "code": code, "error": error}))
        await self.close(close, code)

    def spawn(self, work: Any) -> None:
        task = asyncio.ensure_future(work)
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)


def _frame(message: Frame) -> Frame | None:
    """A received message as a protocol frame: None for anything but a JSON object in a text
    frame."""
    text = message.get("text")
    try:
        data = json.loads(text) if isinstance(text, str) else None
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def _result(frame_id: str, found: ops.Result) -> Frame:
    out: Frame = {
        "t": "result",
        "id": frame_id,
        "ok": found.ok,
        "status": found.status,
        "data": found.data,
    }
    if not found.ok:
        out["error"] = found.error
    out["now"] = clock.now()
    return out


def _welcome(ctx: Context) -> Frame:
    info = protocol.ServerInfo(
        version=ctx.version,
        pid=os.getpid(),
        served=ctx.projects.served.as_posix(),
        surface=bool(ctx.projects.surface_mode),
    )
    return protocol.Welcome(
        t="welcome",
        protocol=1,
        server=info,
        ops=list(protocol.OPS),
        topics=list(protocol.TOPICS),
        now=clock.now(),
    ).model_dump()


def _refusal(
    ctx: Context, hello: protocol.Hello, source: str | None
) -> tuple[str, str, int] | None:
    """Why this hello is refused, as (code, text, close code); None when it is let in."""
    if hello.protocol != protocol.PROTOCOL:
        return "protocol", other_protocol(ctx.version, hello.protocol), OTHER_PROTOCOL
    if source is None and not keys.is_good(hello.key, ctx.key.current()):
        return "key", guard.NEEDS_KEY, BAD_KEY
    if sum(1 for c in ctx.sockets if c.welcomed) >= times.MAX_CLIENTS:
        return "busy", TOO_MANY_CLIENTS, TRY_AGAIN
    return None


async def _hello(conn: Connection, source: str | None) -> bool:
    """The handshake: True once `welcome` is sent; else the socket has been answered and closed."""
    ctx = conn.ctx
    try:
        message = await asyncio.wait_for(conn.ws.receive(), times.hello_s())
    except TimeoutError:
        await conn.close(TIMED_OUT, "no hello")
        return False
    if message.get("type") == "websocket.disconnect":
        return False
    try:
        hello = protocol.Hello.model_validate(_frame(message))
    except ValidationError:
        await conn.fault("frame", HELLO_REFUSED, BAD_FRAME)
        return False
    refused = _refusal(ctx, hello, source)
    if refused is not None:
        await conn.fault(*refused)
        return False
    conn.credential = source if source is not None else hello.key
    conn.welcomed = True
    conn.post(_welcome(ctx))
    return True


def _run(ctx: Context, name: str, args: Any) -> ops.Result:
    found = ops.call(ctx, name, args)
    if ctx.seats.gone():  # as every request of the routes: a board whose seats left stops
        ctx.stop()
    return found


def _checked(model: Any, data: Frame, conn: Connection) -> Any:
    """The frame as its model; else a 400 `result` when it has an id to answer to, or a fault."""
    try:
        return model.model_validate(data)
    except ValidationError as e:
        frame_id = data.get("id")
        if isinstance(frame_id, str) and len(frame_id) <= ID_MAX:
            conn.post(_result(frame_id, ops.fail(400, ops.problem(e))))
            return None
        raise


async def _call(conn: Connection, frame: protocol.Call, run: Any) -> None:
    try:
        found = await run(_run, conn.ctx, frame.op, frame.args)
    except Exception:  # a handler's bug is that call's 500, never the connection's end
        found = ops.fail(500, "the call failed")
    conn.post(_result(frame.id, found))


async def _sub(conn: Connection, frame: protocol.Sub, run: Any) -> None:
    gate = Gate(conn.post)
    push = conn.ctx.push
    try:
        got = (
            ops.fail(503, "the server's push is not running")
            if push is None
            else await run(push.subscribe, frame.topic, frame.args, gate.sink, None, frame.id)
        )
    except Exception:  # the first reading failed (record unreadable): that sub's 500, slot freed
        got = ops.fail(500, "the subscription failed")
    if isinstance(got, ops.Result):
        conn.subs.pop(frame.id, None)
        conn.post(_result(frame.id, got))
        return
    if frame.id not in conn.subs:  # an `unsub` came while the first reading was made
        push.unsubscribe(got)
    else:
        conn.subs[frame.id] = got
    conn.post(_result(frame.id, ops.Result(200, {})))
    gate.release()


def _unsub(conn: Connection, frame: protocol.Unsub) -> None:
    if frame.id not in conn.subs:
        conn.post(_result(frame.id, ops.fail(404, f"no subscription {frame.id!r}")))
        return
    sub = conn.subs.pop(frame.id)
    if sub is not None and conn.ctx.push is not None:
        conn.ctx.push.unsubscribe(sub)
    conn.post(_result(frame.id, ops.Result(200, {})))


async def _handle(conn: Connection, data: Frame, run: Any) -> bool:
    """One frame of a welcomed socket; False when the connection is closed on it."""
    kind = data.get("t")
    if kind == "call":
        frame = _checked(protocol.Call, data, conn)
        if frame is not None:
            conn.spawn(_call(conn, frame, run))
    elif kind == "sub":
        frame = _checked(protocol.Sub, data, conn)
        if frame is None:
            return True
        if frame.id in conn.subs:
            conn.post(_result(frame.id, ops.fail(400, f"the id {frame.id!r} is in use")))
        elif len(conn.subs) >= times.MAX_SUBS:
            conn.post(_result(frame.id, ops.fail(429, SUBS_FULL)))
        else:
            conn.subs[frame.id] = None
            conn.spawn(_sub(conn, frame, run))
    elif kind == "unsub":
        frame = _checked(protocol.Unsub, data, conn)
        if frame is not None:
            _unsub(conn, frame)
    else:
        raise ValueError(NO_ID)
    return True


async def _frames(conn: Connection, run: Any) -> None:
    while True:
        message = await conn.ws.receive()
        if message.get("type") == "websocket.disconnect":
            return
        data = _frame(message)
        try:
            if data is None:
                raise ValueError(NO_ID)
            await _handle(conn, data, run)
        except (ValidationError, ValueError):
            await conn.fault("frame", NO_ID, BAD_FRAME)
            return


async def _send(conn: Connection) -> None:
    while True:
        frame = await conn.out.get()
        if frame is None:
            return
        try:
            await conn.ws.send_text(json.dumps(frame, ensure_ascii=False))
        except Exception:  # the socket is gone: the frame loop ends on its disconnect
            return


async def _tick(conn: Connection) -> None:
    while True:
        await asyncio.sleep(times.tick_s())
        conn.post({"t": "tick", "now": clock.now()})


async def _open(ctx: Context, ws: Any, run: Any, response: Any) -> None:
    headers = {name.lower(): value for name, value in ws.headers.items()}
    allowed, credential = auth.upgrade(headers, ctx.key.current(), ctx.cookie)
    if not allowed:
        await ws.send_denial_response(response(guard.NEEDS_KEY + "\n", 401))
        return
    if sum(1 for c in ctx.sockets if not c.welcomed) >= times.MAX_WAITING:
        await ws.send_denial_response(response(TOO_MANY_CLIENTS + "\n", 503))
        return
    conn = Connection(ctx, ws)
    conn.credential = credential
    ctx.sockets.append(conn)  # before the first await: the cap counts it
    workers: list[asyncio.Task[None]] = []
    try:
        await ws.accept()
        if not await _hello(conn, credential):
            return
        workers = [asyncio.ensure_future(_send(conn)), asyncio.ensure_future(_tick(conn))]
        await _frames(conn, run)
    finally:
        ctx.sockets.remove(conn)
        for task in [*workers, *conn.tasks]:
            task.cancel()
        for sub in conn.subs.values():
            if sub is not None and ctx.push is not None:
                ctx.push.unsubscribe(sub)


def build(ctx: Context) -> Any:
    """The endpoint of `/api/v1/ws` for Starlette's `WebSocketRoute`."""
    from starlette.concurrency import run_in_threadpool
    from starlette.responses import Response
    from starlette.websockets import WebSocket

    def response(body: str, status: int) -> Any:
        return Response(body, status, media_type="text/plain; charset=utf-8")

    async def endpoint(ws: WebSocket) -> None:
        await _open(ctx, ws, run_in_threadpool, response)

    return endpoint
