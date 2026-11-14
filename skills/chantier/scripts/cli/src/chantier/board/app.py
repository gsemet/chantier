"""The Starlette application: it hands every request to `routes.handle` and sends the answer.
`starlette` is imported here, when the board runs, and by no other command."""

from __future__ import annotations

from typing import Any

from chantier.board.context import Context, Request
from chantier.board.routes import handle

NOT_MODIFIED = 304
METHODS = ["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]


def build_app(ctx: Context) -> Any:
    """The ASGI application of a board."""
    from starlette.applications import Starlette
    from starlette.concurrency import run_in_threadpool
    from starlette.requests import Request as AsgiRequest
    from starlette.responses import Response
    from starlette.routing import Route

    async def endpoint(request: AsgiRequest) -> Response:
        req = Request(
            request.method,
            request.url.path,
            dict(request.query_params),
            {name.lower(): value for name, value in request.headers.items()},
            await request.body(),
        )
        reply = await run_in_threadpool(handle, ctx, req)
        head = request.method == "HEAD" or reply.status == NOT_MODIFIED
        return Response(
            b"" if head else reply.body,
            reply.status,
            reply.all_headers(),
            reply.kind,
        )

    return Starlette(routes=[Route("/{rest:path}", endpoint, methods=METHODS)])


def make_server(ctx: Context) -> Any:
    """The `uvicorn` server of a board, with nothing printed: the start lines are the command's."""
    import uvicorn

    config = uvicorn.Config(
        build_app(ctx),
        log_config=None,
        log_level="warning",
        access_log=False,
        lifespan="off",
        ws="none",
        server_header=False,
    )
    return uvicorn.Server(config)
