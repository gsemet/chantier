"""The API's ops: each of today's routes as `<area>.<verb>`, with checked arguments and a
`Result` (an HTTP status, the route's JSON answer as `data`). The handlers read and write through
the same functions the routes do (`reads`, `write_api`, `config_api`, `writer_api`)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from http import HTTPStatus
from typing import Any

from pydantic import BaseModel, ValidationError

from chantier.board import config_api, files, journal, prs, reads, write_api, writer_api
from chantier.board.api import protocol
from chantier.board.context import Context
from chantier.board.projects import Project
from chantier.board.reply import Reply
from chantier.core import clock
from chantier.core.errors import ChantierError
from chantier.core.files import inside, rel_in
from chantier.playbook import edit

NOT_FOUND = "not found"
BINARY = "binary: read it over HTTP"


@dataclass
class Result:
    status: int
    data: dict[str, Any] | None = None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return HTTPStatus.OK <= self.status < HTTPStatus.MULTIPLE_CHOICES


Handler = Callable[[Context, Any], Result]


def fail(status: int, error: str) -> Result:
    return Result(status, None, error)


def _of(status: int, data: dict[str, Any]) -> Result:
    """A route's JSON answer as a result: a refusal's `error` is the frame's."""
    failed = status >= HTTPStatus.BAD_REQUEST and "error" in data
    return Result(status, data, str(data["error"]) if failed else None)


def _project(ctx: Context, a: Any) -> Project | None:
    return reads.found(ctx, a.project)


def _on_project(read: Callable[[Context, Project, Any], Result]) -> Handler:
    def run(ctx: Context, a: Any) -> Result:
        project = _project(ctx, a)
        return fail(404, NOT_FOUND) if project is None else read(ctx, project, a)

    return run


def _board(ctx: Context, a: Any) -> Result:
    return Result(200, reads.board_data(ctx))


def _state(ctx: Context, project: Project, a: Any) -> Result:
    data, rev = reads.state_data(ctx, project)
    return Result(200, {"changed": False, "rev": rev} if a.rev == rev else data)


def _tree(ctx: Context, project: Project, a: Any) -> Result:
    found = files.tree(project.repo.store, project.repo.changes.resolve(), a.path)
    if isinstance(found, Reply):
        return fail(404, NOT_FOUND)
    return Result(200, {"path": a.path, "files": found, "now": clock.now()})


def _file(ctx: Context, project: Project, a: Any) -> Result:
    root = project.repo.changes.resolve()
    target = inside(root, a.path)
    store = project.repo.store
    if target is None or not store.is_file(rel_in(store.root, target)):
        return fail(404, NOT_FOUND)
    if files.kind_of(target.name) != "text":
        return fail(415, BINARY)
    reply = files.read(store, root, a.path)
    data = {
        "text": reply.body.decode("utf-8"),
        "cut": "X-Chantier-Cut" in reply.headers,
        "sha256": reply.headers.get(files.SHA_HEADER),
    }
    return Result(200, data)


def _costs(ctx: Context, project: Project, a: Any) -> Result:
    return Result(200, reads.costs_data(ctx, project))


def _recompute(ctx: Context, project: Project, a: Any) -> Result:
    ctx.live(project).start()
    return Result(202, {"computing": True, "now": clock.now()})


def _prs(ctx: Context, project: Project, a: Any) -> Result:
    data, _ = reads.state_of(ctx, project, ask=False)
    return Result(200, prs.answer(ctx.reads, project.id, data, project.repo, a.batch))


def _seat(ctx: Context, a: Any) -> Result:
    if not ctx.seats.add(a.project or ctx.projects.home_id, a.session):
        return fail(404, NOT_FOUND)
    return Result(200, {"seats": ctx.seats.count(), "now": clock.now()})


def _journal(ctx: Context, project: Project, a: Any) -> Result:
    return Result(200, journal_data(project))


def journal_data(project: Project) -> dict[str, Any]:
    """The board's own journal since the last rescan."""
    entries = journal.since_rescan(project.repo.store, project.repo.changes)
    return {"entries": entries, "count": len(entries), "now": clock.now()}


def _config(ctx: Context, project: Project, a: Any) -> Result:
    return Result(200, edit.config_view(project.repo))


def _writes(op: write_api.Op, command: str) -> Handler:
    def run(ctx: Context, a: Any) -> Result:
        project = _project(ctx, a)
        if project is None:
            return fail(404, NOT_FOUND)
        data = a.model_dump(exclude_unset=True, exclude_none=True, exclude={"project"})
        body, status = write_api.execute(project, op, command, data)
        return _of(status, body)

    return run


def _sync(ctx: Context, a: Any) -> Result:
    body, status = writer_api.sync_data(ctx)
    return _of(status, body)


HANDLERS: dict[str, Handler] = {
    "board.get": _board,
    "project.state": _on_project(_state),
    "project.tree": _on_project(_tree),
    "project.file": _on_project(_file),
    "costs.get": _on_project(_costs),
    "costs.recompute": _on_project(_recompute),
    "prs.get": _on_project(_prs),
    "seats.register": _seat,
    "journal.get": _on_project(_journal),
    "config.get": _on_project(_config),
    "config.put": _writes(*config_api.WRITE),
    "writer.sync": _sync,
    **{name: _writes(op, command) for name, (op, command) in write_api.WRITES.items()},
}


def problem(e: ValidationError) -> str:
    first = e.errors()[0]
    where = ".".join(str(x) for x in first["loc"])
    return f"{where!r}: {first['msg']}" if where else str(first["msg"])


def checked(model: type[BaseModel], args: Any) -> BaseModel | str:
    """The arguments as their model, or the text of the first thing wrong with them."""
    if not isinstance(args, dict):
        return "the arguments are a JSON object"
    try:
        return model.model_validate(args)
    except ValidationError as e:
        return problem(e)


def call(ctx: Context, name: str, args: Any) -> Result:
    """One op: 404 for an unknown one, 400 naming the argument that is missing, extra or
    mistyped, 500 when the record could not be read."""
    model, handler = protocol.OP_ARGS.get(name), HANDLERS.get(name)
    if model is None or handler is None:
        return fail(404, f"unknown op {name!r}")
    a = checked(model, args)
    if isinstance(a, str):
        return fail(400, a)
    try:
        return handler(ctx, a)
    except (OSError, ValueError, KeyError, ChantierError):
        return fail(500, reads.UNREADABLE)
