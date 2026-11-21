"""The API's HTTP binding: `POST /api/v1/call/<op>`, the long-poll `POST /api/v1/poll`, the file
`GET /api/v1/projects/<id>/file` and `OPTIONS` (CORS). The key is judged here (`auth`); every
answer allows any origin and never credentials."""

from __future__ import annotations

import json
import re
from http import HTTPStatus
from typing import Any

from pydantic import ValidationError

from chantier.board import files, guard, reads
from chantier.board.api import auth, ops, protocol, times
from chantier.board.api.push import Want
from chantier.board.context import Context, Request
from chantier.board.reply import Reply, as_json, text
from chantier.core import clock
from chantier.core.errors import ChantierError

BAD_JSON = "the body is not JSON"
TOO_MANY = f"too many subscriptions: at most {times.MAX_SUBS}"


def is_v1(path: str) -> bool:
    return path.startswith(auth.PREFIX)


def _answer(result: ops.Result) -> Reply:
    """A result as the HTTP answer: its status, and the frame's fields but `t` and `id`."""
    body: dict[str, Any] = {"ok": result.ok, "status": result.status, "data": result.data}
    if not result.ok:
        body["error"] = result.error
    body["now"] = clock.now()
    return as_json(body, result.status)


def _json(req: Request) -> Any:
    """The body as JSON (`{}` for none); a text for a body that is not."""
    try:
        return json.loads(req.body) if req.body else {}
    except ValueError:
        return BAD_JSON


def _call(ctx: Context, req: Request, name: str) -> Reply:
    args = _json(req)
    if args == BAD_JSON:
        return _answer(ops.fail(400, BAD_JSON))
    return _answer(ops.call(ctx, name, args))


def _poll(ctx: Context, req: Request) -> Reply:
    body = _json(req)
    try:
        poll = protocol.Poll.model_validate(body)
    except ValidationError as e:
        return _answer(ops.fail(400, ops.problem(e) if isinstance(body, dict) else BAD_JSON))
    if len(poll.subs) > times.MAX_SUBS:
        return _answer(ops.fail(429, TOO_MANY))
    if ctx.push is None:
        return _answer(ops.fail(503, "the server's push is not running"))
    wants = [Want(s.key, s.topic, s.args, s.rev) for s in poll.subs]
    held = ctx.push.hold(wants)
    if isinstance(held, ops.Result):
        return _answer(held)
    return as_json({"events": held, "now": clock.now()})


def _file(ctx: Context, req: Request, project_id: str) -> Reply:
    project = reads.found(ctx, project_id)
    if project is None or "path" not in req.query:
        return text(404, "not found")
    return files.read(project.repo.store, project.repo.changes.resolve(), req.query["path"])


def _route(ctx: Context, req: Request) -> Reply:
    method = "GET" if req.method == "HEAD" else req.method
    path = req.path.removeprefix(auth.PREFIX)
    found = re.fullmatch(r"projects/([^/]+)/file", path)
    if found:
        return _file(ctx, req, found.group(1)) if method == "GET" else _not_allowed("GET")
    if path == "poll" or path.startswith("call/"):
        if method != "POST":
            return _not_allowed("POST")
        return _poll(ctx, req) if path == "poll" else _call(ctx, req, path.removeprefix("call/"))
    return text(404, "not found")


def _not_allowed(allow: str) -> Reply:
    reply = guard.not_allowed()
    reply.headers["Allow"] = allow
    return reply


def serve(ctx: Context, req: Request, key: str) -> Reply:
    """A request to `/api/v1/`: the preflight, the key, then the route."""
    if req.method == "OPTIONS":
        return auth.preflight()
    denied = auth.judge(req, key)
    if denied is not None:
        return auth.cors(denied)
    try:
        reply = _route(ctx, req)
    except (OSError, ValueError, KeyError, ChantierError):
        reply = text(HTTPStatus.INTERNAL_SERVER_ERROR, reads.UNREADABLE)
    return auth.cors(reply)
