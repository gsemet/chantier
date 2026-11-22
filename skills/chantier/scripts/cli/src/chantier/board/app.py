"""The Starlette application: it hands every request to `routes.handle` and sends the answer.
`starlette` is imported here, when the board runs, and by no other command."""

from __future__ import annotations

import asyncio
from typing import Any

from chantier.board.api import times, ws
from chantier.board.api.auth import PREFIX, cors
from chantier.board.context import Context, Request
from chantier.board.reply import text
from chantier.board.routes import handle

NOT_MODIFIED = 304
METHODS = ["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
TOO_LARGE = f"too large: a body is at most {times.MAX_FRAME} bytes"
GOING_AWAY = 1001


def build_app(ctx: Context) -> Any:
    """The ASGI application of a board."""
    from starlette.applications import Starlette
    from starlette.concurrency import run_in_threadpool
    from starlette.requests import Request as AsgiRequest
    from starlette.responses import Response
    from starlette.routing import Route, WebSocketRoute

    async def body_of(request: AsgiRequest) -> bytes | None:
        """The body, None when it is more than `MAX_FRAME` (by its length or as it streams)."""
        declared = request.headers.get("content-length", "")
        if declared.isdigit() and int(declared) > times.MAX_FRAME:
            return None
        body = bytearray()
        async for chunk in request.stream():
            body += chunk
            if len(body) > times.MAX_FRAME:
                return None
        return bytes(body)

    async def endpoint(request: AsgiRequest) -> Response:
        body = await body_of(request)
        if body is None:
            large = text(413, TOO_LARGE)
            reply = cors(large) if request.url.path.startswith(PREFIX) else large
            return Response(reply.body, reply.status, reply.all_headers(), reply.kind)
        req = Request(
            request.method,
            request.url.path,
            dict(request.query_params),
            {name.lower(): value for name, value in request.headers.items()},
            body,
        )
        reply = await run_in_threadpool(handle, ctx, req)
        head = request.method == "HEAD" or reply.status == NOT_MODIFIED
        return Response(
            b"" if head else reply.body,
            reply.status,
            reply.all_headers(),
            reply.kind,
        )

    return Starlette(
        routes=[
            WebSocketRoute(ws.PATH, ws.build(ctx)),
            Route("/{rest:path}", endpoint, methods=METHODS),
        ]
    )


def make_server(ctx: Context) -> Any:
    """The `uvicorn` server of a board, with nothing printed: the start lines are the command's.
    Its shutdown first closes every open WebSocket with 1001 (going away), so a client sees a
    clean close and not uvicorn's own 1012."""
    import uvicorn

    class Server(uvicorn.Server):
        async def shutdown(self, sockets: list[Any] | None = None) -> None:
            if ctx.griller is not None:  # a running turn ends first, `stopped`
                await asyncio.to_thread(ctx.griller.stop_all, "the board stopped")
            await asyncio.gather(*(conn.close(GOING_AWAY) for conn in list(ctx.sockets)))
            await super().shutdown(sockets)

    config = uvicorn.Config(
        build_app(ctx),
        log_config=None,
        log_level="warning",
        access_log=False,
        lifespan="off",
        ws="websockets-sansio",
        ws_max_size=times.MAX_FRAME,
        ws_ping_interval=times.PING_S,
        ws_ping_timeout=times.PING_S,
        server_header=False,
    )
    return Server(config)
