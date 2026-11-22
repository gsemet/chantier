"""The board's routes: the probe, the frame, the API of protocol 1 (`api/`), and the order in which
a request is judged."""

from __future__ import annotations

import os

from chantier.board import guard, reads, static
from chantier.board.api import http as api_http
from chantier.board.api import ops, protocol
from chantier.board.context import Context, Request
from chantier.board.reply import Reply, as_json, text
from chantier.core import clock
from chantier.core.errors import ChantierError

PROBE = "/api/board"


def _unknown() -> Reply:
    return text(404, "not found")


def probe(ctx: Context) -> dict[str, object]:
    """`GET /api/board`, frozen outside the versioning: what every chantier version's probe reads
    to find a running board and to refuse one of another version."""
    return {
        "board": True,
        "version": ctx.version,
        "pid": os.getpid(),
        "served": ctx.projects.served.as_posix(),
        "surface": ctx.projects.surface_mode,
        "protocols": [protocol.PROTOCOL],
    }


def _dispatch(ctx: Context, req: Request) -> Reply:
    """The probe, else the frame's file; any other `/api/` path is unknown."""
    method = "GET" if req.method == "HEAD" else req.method
    if req.path == PROBE:
        return as_json(probe(ctx)) if method == "GET" else guard.not_allowed()
    if req.path.startswith("/api/"):
        return _unknown()
    if method != "GET":
        return guard.not_allowed()
    return static.serve(ctx.ui, req.path, req.headers.get("if-none-match"))


def _frame(ctx: Context, req: Request, key: str) -> Reply:
    """The probe and the page's files: the cookie or the header, the method, the rule for
    writes, then the route."""
    held = guard.access(req, key, ctx.cookie, ctx.key.read_current())
    if held is None:
        return guard.refused_key(req)
    if req.path.startswith("/api/") and req.path != PROBE:
        return _unknown()  # a route of an older version, whatever its method
    if req.method not in guard.ALLOWED:
        return guard.not_allowed()
    if held == "read" and req.method in guard.WRITE:
        return text(403, ops.READ_ONLY)  # a write needs the private key, whatever its route
    refused = guard.refusal(req) if req.method in guard.WRITE else None
    return refused or _dispatch(ctx, req)


def _judged(ctx: Context, req: Request) -> Reply:
    key = ctx.key.current()
    if "k" in req.query:
        done = guard.exchange(req, key, ctx.cookie, ctx.key.read_current())
        if done:
            return done
    try:
        reply = api_http.serve(ctx, req, key) if api_http.is_v1(req.path) else _frame(ctx, req, key)
    except (OSError, ValueError, KeyError, ChantierError):
        reply = text(500, reads.UNREADABLE)
    if ctx.seats.gone():
        ctx.stop()
    return reply


def handle(ctx: Context, req: Request) -> Reply:
    """Judge a request: the key, the method, the rule for writes, then the route. Every answer
    carries the server's instant in `X-Chantier-Now`, a `304`'s too."""
    reply = _judged(ctx, req)
    reply.headers.setdefault("X-Chantier-Now", clock.now())
    return reply
