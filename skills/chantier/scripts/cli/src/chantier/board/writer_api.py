"""The board's view of the surface's writer: the `writer` entry on `GET /api/board`, and the one
action, `POST /api/writer/sync` (behind the key like every write route): it touches
`writer.wake`. No start, stop or approve: the writer lives as long as the board does."""

from __future__ import annotations

from typing import Any

from chantier.board.context import Context, Request
from chantier.board.reply import Reply, as_json
from chantier.core import clock
from chantier.hub import lock
from chantier.writer import lines, record


def payload(ctx: Context) -> dict[str, Any]:
    """The `writer` entry as read, `{"state": "off"}` with none (project mode included)."""
    home = ctx.projects.home
    return record.read(home.git_dir) if home.external else {"state": record.OFF}


def sync(ctx: Context, req: Request) -> Reply:
    """Ask the writer for a cycle at once; 409 with the refusal's text when none is running."""
    home = ctx.projects.home
    shown = payload(ctx)
    if not home.external or shown.get("state") in (record.OFF, record.STOPPED):
        return as_json(
            {"error": lines.refusal("sync now", home.git_dir), "code": "off", "writer": shown},
            status=409,
        )
    lock.wake(home.git_dir)
    return as_json({"writer": shown, "now": clock.now()})


ROUTES: list[tuple[str, str, Any]] = [("POST", r"/api/writer/sync", sync)]
