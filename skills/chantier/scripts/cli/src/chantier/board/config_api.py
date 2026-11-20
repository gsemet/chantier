"""The board's Configuration routes: the view of the configuration and the change of a role's
`agent`, `model` or `escalation`, or of the two limits, in the planning surface's project file.
The reading, the checks and the writing are the CLI's (`playbook/edit.py`); this module only
routes to them and adds the journals' lines: the board's own, and, for each key whose effective
value changed, one `config@1` line in the forge journal (a signal the watcher and `status` carry to
the Chief of Staff). A `config@1` event its model refuses is set aside: the save stays written
and the reply's `error` says `skipped: <message>`."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from chantier.board import journal, write_api
from chantier.board.context import Context, Request
from chantier.board.reply import Reply, as_json, text
from chantier.core.errors import EXIT_USAGE, ChantierError
from chantier.core.records import read_batch_json
from chantier.core.repo import Repo
from chantier.hub import journal as forge_journal
from chantier.playbook import edit
from chantier.playbook.limits_check import LIMIT_KEYS

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
    if "host" not in change:
        held = view["limits"][change["key"]]
        overridden = f", overridden by {held['overridden_by']}" if held["overridden_by"] else ""
        return f"{change['key']} = {value}{overridden}"
    words = f"{change['role']}.{change['key']} = {value} ({change['host']})"
    row: dict[str, Any] = next(
        (r for r in view["hosts"][change["host"]]["roles"] if r["role"] == change["role"]), {}
    )
    if change["key"] in row.get("overridden_keys", []):
        words += f", overridden by {row['overridden_by']}"
    return words


def _open_batch(repo: Repo) -> tuple[str, int] | None:
    """The id and the recorded slots of the batch running or paused, None with none."""
    path = repo.batches / "batch.json"
    if not path.is_file():
        return None
    try:
        d = read_batch_json(path)
    except (OSError, ValueError, ChantierError):
        return None
    return (d.id, d.slots) if d.status in ("running", "paused") else None


def _shown(value: Any) -> str:
    return "not set" if value is None else str(value)


def _limit_line(key: str, old: Any, new: Any, batch: tuple[str, int] | None) -> str:
    """What happens next for a limit that changed, role-free."""
    move = f"{_shown(old)} -> {_shown(new)}"
    if key == "specifying.parallel":
        return f"specifying {move}: from the next start"
    if batch:
        return f"slots {move}: {batch[0]} keeps {batch[1]} until an order slots"
    return f"slots {move}: from the next open"


def _printable(value: Any) -> Any:
    """A model's `{id, name}` is written as its id (its name without one), a text as it is."""
    if isinstance(value, dict):
        return value.get("id") or value.get("name")
    return value


def _held(view: dict[str, Any], change: dict[str, Any]) -> Any:
    """The effective value the view shows for a change's key (a role's `agent`, `model` or
    `escalation`, or a limit), printable; None when nothing applies."""
    if "host" not in change:
        return view["limits"][change["key"]]["effective"]
    row: dict[str, Any] = next(
        (r for r in view["hosts"][change["host"]]["roles"] if r["role"] == change["role"]), {}
    )
    return _printable((row.get(change["key"]) or {}).get("effective"))


def _dotted(change: dict[str, Any]) -> str:
    if "host" not in change:
        return str(change["key"])
    return f"hosts.{change['host']}.roles.{change['role']}.{change['key']}"


def _config_changes(
    changes: list[dict[str, Any]], before: dict[str, Any], after: dict[str, Any]
) -> list[tuple[str, Any, Any]]:
    """The keys of the changes whose effective value moved: `(dotted key, old, new)`, in the
    order of the changes, one per key."""
    out: list[tuple[str, Any, Any]] = []
    for c in changes:
        key = _dotted(c)
        if any(o[0] == key for o in out):
            continue
        old, new = _held(before, c), _held(after, c)
        if old != new:
            out.append((key, old, new))
    return out


def _event(key: str, old: Any, new: Any, batch: tuple[str, int] | None) -> dict[str, Any]:
    """The forge journal's `config@1` event of one key."""
    return {
        "type": "config@1",
        "key": key,
        "old": old,
        "new": new,
        "batch": batch[0] if batch else None,
    }


def _put(repo: Repo, data: dict[str, Any]) -> tuple[dict[str, Any], int]:
    base, dry = data.get("base_sha256"), data.get("dry_run", False)
    if base is not None and not isinstance(base, str):
        raise ChantierError("'base_sha256' is a text, or null for a file not there yet", EXIT_USAGE)
    if not isinstance(dry, bool):
        raise ChantierError("'dry_run' is true or false", EXIT_USAGE)
    before = edit.config_view(repo)
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
        moved = _config_changes(data["changes"], before, view)
        batch = _open_batch(repo)
        accepted, refused = forge_journal.set_aside([_event(k, o, n, batch) for k, o, n in moved])
        forge_journal.append(repo, accepted, "board")
        if refused:
            body["error"] = forge_journal.skipped(refused)
        roles = any("host" in c for c in data["changes"])
        body["lines"] = [
            f"wrote {view['file']}",
            *(_limit_line(k, o, n, batch) for k, o, n in moved if k in LIMIT_KEYS),
            *([APPLIES] if roles else []),
        ]
        body["journal"] = [journal.record(repo, "config", [], words)]
    return body, 200


ROUTES: list[tuple[str, str, Callable[..., Reply]]] = [
    ("GET", write_api.P + "config", config_of),
    ("PUT", write_api.P + "config", write_api.writer(_put)),
]
