"""One op called as an HTTP client of protocol 1 does (`POST /api/v1/call/<op>`), in-process through
the routes, with the key and the headers a page sends: the board's tests call this where they
called a route before."""

from __future__ import annotations

import json
from typing import Any

from chantier.board import key as keys
from chantier.board import routes
from chantier.board.context import Context, Request


def call_op(
    ctx: Context,
    secret: str | None,
    op: str,
    args: object = None,
    content_type: str = "application/json",
) -> tuple[int, Any]:
    """`(status, data)`: the op's `data` (the route's JSON answer of before), or `{"ok": False,
    "error"}` for a refusal that has none; `{}` for an answer that is not JSON (a 401)."""
    head = {"content-type": content_type, "host": "board"}
    if secret is not None:
        head[keys.HEADER] = secret
    raw = json.dumps({} if args is None else args).encode()
    reply = routes.handle(ctx, Request("POST", f"/api/v1/call/{op}", {}, head, raw))
    if not reply.body.startswith(b"{"):
        return reply.status, {}
    body = json.loads(reply.body)
    if body.get("data") is not None:
        return reply.status, body["data"]
    return reply.status, {"ok": False, "error": body.get("error")}


ROUTE_OPS = {
    ("POST", "backlog/new"): "backlog.new",
    ("POST", "backlog/move"): "backlog.move",
    ("POST", "backlog/labels"): "backlog.labels",
    ("POST", "backlog/group"): "backlog.group",
    ("POST", "backlog/ungroup"): "backlog.ungroup",
    ("PUT", "backlog/file"): "backlog.file",
    ("POST", "backlog/next-batch"): "backlog.next_batch",
    ("GET", "journal"): "journal.get",
    ("POST", "journal/rescan"): "journal.rescan",
    ("GET", "config"): "config.get",
    ("PUT", "config"): "config.put",
    ("GET", "prs"): "prs.get",
}


def call_route(  # noqa: PLR0913, PLR0917 - the old route call, spelled as it was
    ctx: Context,
    secret: str | None,
    method: str,
    project: str,
    route: str,
    body: object = None,
    content_type: str = "application/json",
) -> tuple[int, Any]:
    """The same call named as the route it replaced (`PUT`, `backlog/file`): its op's."""
    args = {"project": project, **(body if isinstance(body, dict) else {})}
    return call_op(ctx, secret, ROUTE_OPS[(method, route)], args, content_type)
