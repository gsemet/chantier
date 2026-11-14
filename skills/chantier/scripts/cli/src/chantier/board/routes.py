"""The board's routes: the JSON API, the frame, and the order in which a request is judged."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import Any

from chantier.board import costs, files, guard, static, write_api
from chantier.board.context import Context, Request
from chantier.board.fingerprint import fingerprint
from chantier.board.projects import Project
from chantier.board.reply import Reply, as_json, matches, text
from chantier.board.state import project_line, project_state
from chantier.core import clock
from chantier.core.errors import ChantierError

Handler = Callable[..., Reply]
UNREADABLE = "the record could not be read just now"


def _etag(print_: str) -> str:
    return f'"{print_[:32]}"'


def _state_of(ctx: Context, project: Project, ask: bool) -> tuple[dict[str, Any], str]:
    """The project's state and its fingerprint. `ask`: a page looks, so the 5-minute rule runs."""
    live = ctx.live(project)
    last = ctx.cache.peek(project.id)
    running = bool(last and last["batch"] and last["batch"]["state"] == "running")
    if ask:
        live.ask(running)
    print_ = fingerprint(project.repo.changes, live.mark())
    state = ctx.cache.get(
        project.id,
        print_,
        lambda: project_state(project.id, project.repo, ctx.projects.surface_mode, live.snapshot()),
    )
    if ask and not last:
        live.ask(bool(state["batch"] and state["batch"]["state"] == "running"))
    return state, print_


def _found(ctx: Context, project_id: str) -> Project | None:
    ctx.projects.refresh()
    return ctx.projects.get(project_id)


def _unknown() -> Reply:
    return text(404, "not found")


def board(ctx: Context, req: Request) -> Reply:
    ctx.projects.refresh()
    lines = [project_line(p.id, _state_of(ctx, p, ask=False)[0]) for p in ctx.projects.all()]
    return as_json(
        {
            "board": True,
            "version": ctx.version,
            "surface": ctx.projects.surface_mode,
            "served": ctx.projects.served.as_posix(),
            "seats": ctx.seats.count(),
            "projects": lines,
            "now": clock.now(),
        }
    )


def state(ctx: Context, req: Request, project_id: str) -> Reply:
    project = _found(ctx, project_id)
    if project is None:
        return _unknown()
    data, print_ = _state_of(ctx, project, ask=True)
    etag = {"ETag": _etag(print_)}
    if matches(req.headers.get("if-none-match"), etag["ETag"]):
        return Reply(304, b"", headers=etag)
    return as_json({**data, "now": clock.now()}, headers=etag)


def tree(ctx: Context, req: Request, project_id: str) -> Reply:
    project = _found(ctx, project_id)
    if project is None:
        return _unknown()
    rel = req.query.get("path", "")
    found = files.tree(project.repo.changes.resolve(), rel)
    if isinstance(found, Reply):
        return found
    return as_json({"path": rel, "files": found, "now": clock.now()})


def file(ctx: Context, req: Request, project_id: str) -> Reply:
    project = _found(ctx, project_id)
    if project is None or "path" not in req.query:
        return _unknown()
    return files.read(project.repo.changes.resolve(), req.query["path"])


def costs_of(ctx: Context, req: Request, project_id: str) -> Reply:
    project = _found(ctx, project_id)
    if project is None:
        return _unknown()
    data, _ = _state_of(ctx, project, ask=True)
    return as_json(
        {
            "recorded": costs.recorded(data),
            "live": ctx.live(project).snapshot(),
            "now": clock.now(),
        }
    )


def recompute(ctx: Context, req: Request, project_id: str) -> Reply:
    project = _found(ctx, project_id)
    if project is None:
        return _unknown()
    ctx.live(project).start()
    return as_json({"computing": True, "now": clock.now()}, status=202)


def seats(ctx: Context, req: Request) -> Reply:
    try:
        data = json.loads(req.body or b"{}")
        project_id = str(data.get("project") or ctx.projects.home_id)
        session = str(data["session"])
    except (ValueError, KeyError, AttributeError):
        return text(400, 'bad request: {"project": ..., "session": ...}')
    if not ctx.seats.add(project_id, session):
        return _unknown()
    return as_json({"seats": ctx.seats.count(), "now": clock.now()})


ROUTES: list[tuple[str, str, Handler]] = [
    ("GET", r"/api/board", board),
    ("GET", r"/api/projects/([^/]+)/state", state),
    ("GET", r"/api/projects/([^/]+)/tree", tree),
    ("GET", r"/api/projects/([^/]+)/file", file),
    ("GET", r"/api/projects/([^/]+)/costs", costs_of),
    ("POST", r"/api/projects/([^/]+)/costs/recompute", recompute),
    ("POST", r"/api/seats", seats),
    *write_api.ROUTES,
]


def _dispatch(ctx: Context, req: Request) -> Reply:
    """The route of a request: the API's, else the frame's file."""
    known = False
    method = "GET" if req.method == "HEAD" else req.method
    for verb, pattern, handler in ROUTES:
        found = re.fullmatch(pattern, req.path)
        if found and verb == method:
            return handler(ctx, req, *found.groups())
        known = known or bool(found)
    if known or (method != "GET" and not req.path.startswith("/api/")):
        return guard.not_allowed()
    if req.path.startswith("/api/"):
        return _unknown()
    return static.serve(req.path, req.headers.get("if-none-match"))


def _judged(ctx: Context, req: Request) -> Reply:
    key = ctx.key.current()
    if "k" in req.query:
        done = guard.exchange(req, key)
        if done:
            return done
    if not guard.authorised(req, key):
        return text(401, guard.NEEDS_KEY)
    if req.method not in guard.ALLOWED:
        return guard.not_allowed()
    refused = guard.refusal(req) if req.method in guard.WRITE else None
    if refused:
        return refused
    try:
        reply = _dispatch(ctx, req)
    except (OSError, ValueError, KeyError, ChantierError):
        reply = text(500, UNREADABLE)
    if ctx.seats.gone():
        ctx.stop()
    return reply


def handle(ctx: Context, req: Request) -> Reply:
    """Judge a request: the key, the method, the rule for writes, then the route. Every answer
    carries the server's instant in `X-Chantier-Now`, a `304`'s too."""
    reply = _judged(ctx, req)
    reply.headers.setdefault("X-Chantier-Now", clock.now())
    return reply
