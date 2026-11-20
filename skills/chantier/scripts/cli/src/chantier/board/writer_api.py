"""The board's view of the surface's writer: the `writer` entry of `board.get`, and the one
action, the `writer.sync` op (behind the key like every write): it touches
`writer.wake`. No start, stop or approve: the writer lives as long as the board does."""

from __future__ import annotations

from typing import Any

from chantier.board.context import Context
from chantier.core import clock
from chantier.hub import lock
from chantier.writer import lines, record


def payload(ctx: Context) -> dict[str, Any]:
    """The `writer` entry as read, `{"state": "off"}` with none (project mode included)."""
    home = ctx.projects.home
    return record.read(home.git_dir) if home.external else {"state": record.OFF}


def sync_data(ctx: Context) -> tuple[dict[str, Any], int]:
    """Ask the writer for a cycle at once; 409 with the refusal's text when none is running."""
    home = ctx.projects.home
    shown = payload(ctx)
    if not home.external or shown.get("state") in (record.OFF, record.STOPPED):
        refusal = lines.refusal("sync now", home.git_dir)
        return {"error": refusal, "code": "off", "writer": shown}, 409
    lock.wake(home.git_dir)
    return {"writer": shown, "now": clock.now()}, 200
