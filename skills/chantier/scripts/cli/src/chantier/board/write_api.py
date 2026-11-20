"""The board's write routes and the journal's: the backlog only, through the same functions the
`file` and `triage` commands run (`lifecycle/backlog.py`, `summaries/edit.py`), one JSON answer
`{"ok", "lines", "results", "journal"}` and the status of the CLI's exit code (400 usage, 409
precondition or conflict, 500 otherwise). Each write adds one line to the journal, and one `board`
line to the project's forge journal (`hub/journal.py`), which the Chief of Staff's watcher reads."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from functools import partial
from pathlib import Path
from typing import Any

from chantier.board import journal
from chantier.board.projects import Project
from chantier.core.errors import (
    EXIT_CONFLICT,
    EXIT_PRECONDITION,
    EXIT_USAGE,
    ChantierError,
)
from chantier.core.files import inside
from chantier.core.records import GROUP_MAX
from chantier.core.repo import Repo
from chantier.hub import journal as forge_journal
from chantier.lifecycle import backlog
from chantier.lifecycle.stages import PRIORITIES
from chantier.summaries.edit import change_group, change_labels, label_set, one_line
from chantier.summaries.view import summary_view

COLUMNS = ("inbox", *PRIORITIES, "3-ready")
STATUS = {EXIT_USAGE: 400, EXIT_PRECONDITION: 409, EXIT_CONFLICT: 409}
Op = Callable[[Repo, dict[str, Any]], tuple[dict[str, Any], int]]


def _text(data: dict[str, Any], key: str, default: str | None = None) -> str:
    value = data.get(key, default)
    if not isinstance(value, str):
        raise ChantierError(f"{key!r} is a string of the JSON body", EXIT_USAGE)
    return value


def _texts(data: dict[str, Any], key: str) -> list[str]:
    value = data.get(key)
    if not isinstance(value, list) or not value or not all(isinstance(x, str) for x in value):
        raise ChantierError(f"{key!r} is a list of slugs in the JSON body", EXIT_USAGE)
    return list(dict.fromkeys(value))


def _refused(item: str, error: str, status: int) -> dict[str, Any]:
    return {"item": item, "ok": False, "error": error, "status": status}


def _attempt(
    item: str, run: Callable[[], tuple[list[str], str]], items: list[str] | None = None
) -> dict[str, Any]:
    """One write: its result, whatever happens. `words` is what the journal says and `items` the
    slugs it touched (the item itself by default)."""
    try:
        lines, words = run()
        return {"item": item, "items": items or [item], "ok": True, "lines": lines, "words": words}
    except ChantierError as e:
        return _refused(item, str(e), STATUS.get(e.code, 500))
    except (OSError, ValueError) as e:
        return _refused(item, f"not written: {e}", 500)


def _answer(
    repo: Repo, kind: str, results: list[dict[str, Any]], extra: dict[str, Any] | None = None
) -> tuple[dict[str, Any], int]:
    """The answer of a write, and its journal line when something was written: refusals are
    listed, they undo nothing and stop nothing. A `board@1` event its model refuses is set aside:
    the file stays written, the reply keeps its `ok` and status, and its `error` says
    `skipped: <message>`."""
    written = [r for r in results if r["ok"] and r["words"]]
    entries = []
    skipped = None
    if written:
        words = "; ".join(r["words"] for r in written)
        slugs = list(dict.fromkeys(s for r in written for s in r["items"]))
        entries.append(journal.record(repo, kind, slugs, words))
        accepted, refused = forge_journal.set_aside([forge_journal.board_event(kind, slugs, words)])
        forge_journal.append(repo, accepted, "board")
        skipped = forge_journal.skipped(refused)
    failed = next((r for r in results if not r["ok"]), None)
    body = {
        "ok": failed is None,
        "lines": [line for r in results if r["ok"] for line in r["lines"]],
        "results": [{k: v for k, v in r.items() if k not in ("words", "items")} for r in results],
        "journal": entries,
        **(extra or {}),
    }
    if failed or skipped:
        body["error"] = "; ".join(m for m in (failed and failed["error"], skipped) if m)
    return body, failed["status"] if failed else 200


def _new(repo: Repo, data: dict[str, Any]) -> tuple[dict[str, Any], int]:
    idea = _text(data, "text")
    slug, title = data.get("slug"), data.get("title")
    for key, value in (("slug", slug), ("title", title)):
        if value is not None and not isinstance(value, str):
            raise ChantierError(f"{key!r} is a string of the JSON body", EXIT_USAGE)
    filed, _ = backlog.titled_request(idea, idea.encode("utf-8"), title, slug)

    def run() -> tuple[list[str], str]:
        return backlog.file_idea(repo, idea, filed, None, title), f"new idea in 1-inbox/{filed}"

    return _answer(repo, "new", [_attempt(filed, run)], {"item": filed})


def _rel(repo: Repo, folder: Path) -> str:
    return folder.relative_to(repo.changes.resolve()).as_posix()


def _moved(slug: str, before: str, to: str, folder: Path) -> str:
    if to == "inbox":
        return f"{slug} → inbox"
    if to == "3-ready":
        if (folder / "03-change-spec.md").is_file():
            return f"{slug} → 3-ready (specified)"
        return f"{slug} → 3-ready (automatable, no specification: your call)"
    if before in PRIORITIES:
        return f"{slug}: priority {before} → {to}"
    return f"{slug} → {to}"


def _group_of(folder: Path) -> str | None:
    view = summary_view(folder)
    return view.group if view else None


def _move_one(repo: Repo, slug: str, to: str, alone: bool) -> tuple[list[str], str]:
    folder = backlog.backlog_folder(repo, slug)
    before = backlog.column_of(repo, folder)
    if before == to:  # a drop on the item's own column writes nothing
        return [], ""
    lines = backlog.move_item(repo, _rel(repo, folder), to)
    target = backlog.backlog_folder(repo, slug)
    if alone and _group_of(target):
        lines += change_group(repo, [target], None)  # it left its group's column
    return lines, _moved(slug, before, to, target)


def group_members(repo: Repo, name: str) -> list[Path]:
    """The backlog's CR folders that carry this group name."""
    found = []
    for folder in backlog.backlog_folders(repo):
        view = summary_view(folder)
        if view and view.group == name:
            found.append(folder)
    return found


def _move(repo: Repo, data: dict[str, Any]) -> tuple[dict[str, Any], int]:
    to = _text(data, "to")
    if to not in COLUMNS:
        raise ChantierError(f"'to' is one of {', '.join(COLUMNS)}", EXIT_USAGE)
    if "group" in data:
        name = _text(data, "group")
        slugs = [f.name for f in group_members(repo, name)]
        if not slugs:
            raise ChantierError(f"no CR is in the group {name!r}", EXIT_PRECONDITION)
    else:
        slugs = _texts(data, "items")
    alone = "group" not in data and len(slugs) == 1
    done = [_attempt(s, partial(_move_one, repo, s, to, alone)) for s in slugs]
    return _answer(repo, "move", done)


def _resolve(repo: Repo, slugs: list[str]) -> tuple[dict[str, Path], list[dict[str, Any]]]:
    """The folders of the slugs that are in the backlog, and the refusals of the others."""
    folders: dict[str, Path] = {}
    refused = []
    for slug in slugs:
        try:
            folders[slug] = backlog.backlog_folder(repo, slug)
        except ChantierError as e:
            refused.append(_refused(slug, str(e), STATUS.get(e.code, 500)))
    return folders, refused


def _labels(repo: Repo, data: dict[str, Any]) -> tuple[dict[str, Any], int]:
    raw = data.get("add")
    add = label_set(",".join(raw) if isinstance(raw, list) else _text(data, "add"))
    folders, refused = _resolve(repo, _texts(data, "items"))
    names = ", ".join(folders)
    words = f"label {', '.join(repr(x) for x in sorted(add))} on {names}"

    def run() -> tuple[list[str], str]:
        return change_labels(repo, list(folders.values()), add), words

    done = [_attempt(names, run, list(folders))] if folders else []
    return _answer(repo, "label", [*refused, *done])


def _group(repo: Repo, data: dict[str, Any]) -> tuple[dict[str, Any], int]:
    name = one_line(_text(data, "name"), "group", GROUP_MAX)  # checked before anything moves
    folders, refused = _resolve(repo, _texts(data, "items"))
    results = list(refused)
    column = backlog.column_of(repo, next(iter(folders.values()))) if folders else "inbox"
    for slug in list(folders):  # the first item's column, as `groupOf` does
        moved = _attempt(slug, partial(_move_one, repo, slug, column, False))
        if moved["ok"]:
            moved["words"] = ""  # the group's own words say where they are
        else:
            del folders[slug]
        results.append(moved)
    members = [backlog.backlog_folder(repo, s) for s in folders]

    def run() -> tuple[list[str], str]:
        words = f"group {name!r}: {', '.join(folders)} (in {column})"
        return change_group(repo, members, name), words

    done = [_attempt(name, run, list(folders))] if members else []
    return _answer(repo, "group", [*results, *done])


def _ungroup(repo: Repo, data: dict[str, Any]) -> tuple[dict[str, Any], int]:
    name = _text(data, "name")
    members = group_members(repo, name)
    if not members:
        raise ChantierError(f"no CR is in the group {name!r}", EXIT_PRECONDITION)
    names = ", ".join(f.name for f in members)

    def run() -> tuple[list[str], str]:
        return change_group(repo, members, None), f"group {name!r} undone: {names}"

    return _answer(repo, "ungroup", [_attempt(names, run, [f.name for f in members])])


def _file(repo: Repo, data: dict[str, Any]) -> tuple[dict[str, Any], int]:
    item, path = _text(data, "item"), _text(data, "path")
    idea, base = _text(data, "text"), _text(data, "base_sha256")

    def run() -> tuple[list[str], str]:
        return backlog.edit_markdown(repo, item, path, idea, base), f"{item}/{path} edited"

    body, status = _answer(repo, "edit", [_attempt(item, run)])
    if body["ok"]:  # the new hash, for the next save of the same editor
        target = inside(backlog.backlog_folder(repo, item).resolve(), path)
        body["sha256"] = backlog.sha256_of(target.read_bytes()) if target else None
    return body, status


def _next_batch(repo: Repo, data: dict[str, Any]) -> tuple[dict[str, Any], int]:
    def run() -> tuple[list[str], str]:
        lines = backlog.declare_next_batch(repo)
        return lines, lines[0]

    body, status = _answer(repo, "next-batch", [_attempt("next-batch", run)])
    body["next_batch"] = backlog.next_batch(repo)
    return body, status


def _rescan(repo: Repo, data: dict[str, Any]) -> tuple[dict[str, Any], int]:
    return {
        "ok": True,
        "lines": [],
        "results": [],
        "journal": [journal.rescan(repo)],
        "count": 0,
    }, 200


def execute(
    project: Project, op: Op, command: str, data: dict[str, Any]
) -> tuple[dict[str, Any], int]:
    """A write's body and status: a refusal of the CLI's code gives its status and `{"ok": false,
    "error"}` (`stale: true` for a file changed since the page read it)."""
    try:
        return op(replace(project.repo, command=command), data)
    except ChantierError as e:
        refusal: dict[str, Any] = {"ok": False, "error": str(e)}
        if e.code == EXIT_CONFLICT:
            refusal["stale"] = True
        return refusal, STATUS.get(e.code, 500)
    except OSError as e:
        return {"ok": False, "error": f"not written: {e}"}, 500


WRITES: dict[str, tuple[Op, str]] = {
    "backlog.new": (_new, "board backlog/new"),
    "backlog.move": (_move, "board backlog/move"),
    "backlog.labels": (_labels, "board backlog/labels"),
    "backlog.group": (_group, "board backlog/group"),
    "backlog.ungroup": (_ungroup, "board backlog/ungroup"),
    "backlog.file": (_file, "board backlog/file"),
    "backlog.next_batch": (_next_batch, "board backlog/next-batch"),
    "journal.rescan": (_rescan, "board journal/rescan"),
}
