"""The board's Configuration routes: the view of the configuration and the change of a role's
`agent` or `model` in the planning surface's project file. The reading, the checks and the writing
are the CLI's (`playbook/edit.py`); this module only routes to them and adds the journal's line."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from chantier.board import journal, write_api
from chantier.board.context import Context, Request
from chantier.board.reply import Reply, as_json, text
from chantier.core.errors import EXIT_USAGE, ChantierError
from chantier.core.repo import Repo
from chantier.playbook import edit

APPLIES = "applies at the next batch"


def config_of(ctx: Context, req: Request, project_id: str) -> Reply:
    project = write_api.project_of(ctx, project_id)
    if project is None:
        return text(404, "not found")
    return as_json(edit.config_view(project.repo))


def _word(change: dict[str, Any], view: dict[str, Any]) -> str:
    """One change as the journal says it: `coder.model = gpt-6.1-terra (copilot)`, and where the
    code repository's file overrides it, `, overridden by <path>`."""
    value = change["value"] if change["value"] is not None else "inherited"
    words = f"{change['role']}.{change['key']} = {value} ({change['host']})"
    row: dict[str, Any] = next(
        (r for r in view["hosts"][change["host"]]["roles"] if r["role"] == change["role"]), {}
    )
    if change["key"] in row.get("overridden_keys", []):
        words += f", overridden by {row['overridden_by']}"
    return words


def _put(repo: Repo, data: dict[str, Any]) -> tuple[dict[str, Any], int]:
    base, dry = data.get("base_sha256"), data.get("dry_run", False)
    if base is not None and not isinstance(base, str):
        raise ChantierError("'base_sha256' is a text, or null for a file not there yet", EXIT_USAGE)
    if not isinstance(dry, bool):
        raise ChantierError("'dry_run' is true or false", EXIT_USAGE)
    view = edit.edit_surface_file(repo, data.get("changes"), base, dry)
    body: dict[str, Any] = {
        "ok": True,
        "dry_run": dry,
        "lines": [],
        "journal": [],
        "view": view,
        "sha256": view["sha256"],
    }
    if not dry:
        words = "; ".join(_word(c, view) for c in data["changes"])
        body["lines"] = [f"wrote {view['file']}", APPLIES]
        body["journal"] = [journal.record(repo, "config", [], words)]
    return body, 200


ROUTES: list[tuple[str, str, Callable[..., Reply]]] = [
    ("GET", write_api.P + "config", config_of),
    ("PUT", write_api.P + "config", write_api.writer(_put)),
]
