"""The board's autosync routes and the JSON shape of the group. It reads through `autosync/` and
acts through `autosync_tool.py`; the same object rides on `GET /api/board`."""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from chantier.autosync.reading import names_of, read_view
from chantier.autosync.site import AutosyncSite, find_site
from chantier.autosync.view import AutosyncView
from chantier.board.autosync_tool import ToolResult, run_action
from chantier.board.context import Context, Request
from chantier.board.reply import Reply, as_json, text
from chantier.core import clock

Handler = Callable[..., Reply]
BLOCKED_WORD = "blocked: the Chief of Staff integrates, then restarts the group"


def _site(ctx: Context) -> AutosyncSite | None:
    """The surface's autosync, when the served folder is a surface that names one."""
    site = find_site(ctx.projects.home)
    return None if site is None or site.script_missing else site


def _iso(epoch: float | None) -> str | None:
    if epoch is None:
        return None
    return datetime.fromtimestamp(epoch, UTC).isoformat(timespec="seconds")


def _shape(view: AutosyncView, last_push: float | None) -> dict[str, Any]:
    return {
        "present": True,
        "state": view.state,
        "reason": view.reason,
        "incident": (
            {"id": view.incident, "message": view.incident_message} if view.incident else None
        ),
        "leader": view.leader,
        "participants": [{"name": m.name, "role": m.role} for m in view.participants],
        "last_push": _iso(last_push),
        "local_only": view.local_only,
        "no_group": view.no_group,
    }


def _read(ctx: Context, site: AutosyncSite) -> tuple[AutosyncView, dict[str, Any]]:
    names = names_of((p.repo for p in ctx.projects.all()), os.getpid())
    view = read_view(site, names)
    return view, _shape(view, ctx.last_push.see(view.last_push))


def payload(ctx: Context) -> dict[str, Any]:
    """The group as the page draws it; `{"present": false}` with no autosync."""
    site = _site(ctx)
    return {"present": False} if site is None else _read(ctx, site)[1]


def _refused(code: str, word: str, shown: dict[str, Any]) -> Reply:
    return as_json({"error": word, "code": code, "autosync": shown}, status=409)


def _failed(ctx: Context, site: AutosyncSite, result: ToolResult) -> Reply:
    line = result.line or f"the tool ended with exit code {result.code}"
    return as_json({"error": line, "code": "failed", "autosync": _read(ctx, site)[1]}, status=502)


def _done(ctx: Context, site: AutosyncSite, result: ToolResult) -> Reply:
    return as_json({"autosync": _read(ctx, site)[1], "output": result.line, "now": clock.now()})


def _gate(ctx: Context, allowed: tuple[str, ...]) -> tuple[AutosyncSite, dict[str, Any]] | Reply:
    """The site and the group's shape, or the answer that refuses: 404 with no autosync, 409 when
    the state is not one the action runs in."""
    site = _site(ctx)
    if site is None:
        return text(404, "not found")
    view, shown = _read(ctx, site)
    if view.state in allowed:
        return site, shown
    word = BLOCKED_WORD if view.state == "blocked" else f"autosync is {view.state}"
    return _refused(view.state, word, shown)


def get(ctx: Context, req: Request) -> Reply:
    return as_json({**payload(ctx), "now": clock.now()})


def _single(ctx: Context, action: str, allowed: tuple[str, ...]) -> Reply:
    gate = _gate(ctx, allowed)
    if isinstance(gate, Reply):
        return gate
    site = gate[0]
    result = run_action(site, action)
    return _done(ctx, site, result) if result.code == 0 else _failed(ctx, site, result)


def start(ctx: Context, req: Request) -> Reply:
    return _single(ctx, "start", ("stopped",))


def stop(ctx: Context, req: Request) -> Reply:
    return _single(ctx, "stop", ("active", "approval"))


def _incident_of(req: Request) -> str | None:
    try:
        wanted = json.loads(req.body or b"{}").get("incident")
    except (ValueError, AttributeError):
        return None
    return wanted if isinstance(wanted, str) else None


def approve(ctx: Context, req: Request) -> Reply:
    """Approve the incident shown now, then restart the group (the guidelines' next step)."""
    wanted = _incident_of(req)
    if wanted is None:
        return text(400, 'bad request: {"incident": ...}')
    gate = _gate(ctx, ("approval",))
    if isinstance(gate, Reply):
        return gate
    site, shown = gate
    if shown["incident"]["id"] != wanted:
        return _refused("stale", "that incident is not the one waiting now", shown)
    result = run_action(site, "approve", wanted)
    if result.code == 0:
        result = run_action(site, "start")
    return _done(ctx, site, result) if result.code == 0 else _failed(ctx, site, result)


ROUTES: list[tuple[str, str, Handler]] = [
    ("GET", r"/api/autosync", get),
    ("POST", r"/api/autosync/start", start),
    ("POST", r"/api/autosync/stop", stop),
    ("POST", r"/api/autosync/approve", approve),
]
