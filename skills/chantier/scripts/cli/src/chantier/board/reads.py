"""What the routes and the API's ops read in common: a project's state with its fingerprint, the
project lookup and the whole board's payload. No `Request`, no `Reply`: plain data."""

from __future__ import annotations

import os
from typing import Any

from chantier.board import costs, writer_api
from chantier.board.address import local_url
from chantier.board.context import Context
from chantier.board.fingerprint import fingerprint
from chantier.board.projects import Project
from chantier.board.state import origin_of, project_line, project_paths, project_state
from chantier.core import clock

UNREADABLE = "the record could not be read just now"


def local_link(ctx: Context) -> str | None:
    """The 127.0.0.1 link of a board that listens on every address (the key as it is now)."""
    return local_url(*ctx.bound, ctx.key.current()) if ctx.bound else None


def state_of(ctx: Context, project: Project, ask: bool) -> tuple[dict[str, Any], str]:
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


def found(ctx: Context, project_id: str) -> Project | None:
    ctx.projects.refresh()
    return ctx.projects.get(project_id)


def board_data(ctx: Context) -> dict[str, Any]:
    """The whole board: its identity, the projects' lines, the seats and the writer."""
    ctx.projects.refresh()
    lines = [
        {**project_line(p.id, state_of(ctx, p, ask=False)[0]), **project_paths(p.repo)}
        for p in ctx.projects.all()
    ]
    return {
        "board": True,
        "version": ctx.version,
        "surface": ctx.projects.surface_mode,
        "pid": os.getpid(),
        "served": ctx.projects.served.as_posix(),
        "served_origin": origin_of(ctx.projects.served),
        "local_url": local_link(ctx),
        "seats": ctx.seats.count(),
        "projects": lines,
        "writer": writer_api.payload(ctx),
        "protocols": [1],
        "now": clock.now(),
    }


def costs_data(ctx: Context, project: Project) -> dict[str, Any]:
    """The recorded figures, the live one and the instant (the 5-minute rule runs)."""
    data, _ = state_of(ctx, project, ask=True)
    return {
        "recorded": costs.recorded(data),
        "live": ctx.live(project).snapshot(),
        "now": clock.now(),
    }


def state_data(ctx: Context, project: Project) -> tuple[dict[str, Any], str]:
    """The state a client is shown (the 5-minute rule runs), with its `rev` and the instant, and
    that `rev` (the fingerprint, as the ETag was)."""
    data, print_ = state_of(ctx, project, ask=True)
    return {**data, "rev": print_, "now": clock.now()}, print_
