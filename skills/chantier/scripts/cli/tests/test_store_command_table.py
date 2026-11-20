"""The command table of the plan's store (spec CR-402 5.4), one row per command: every published
write of the command goes through `repo.store`, after a `check_publish` that named its paths,
made before the first write, when nothing had changed. A spy wraps `Repo.store`
(`store_spy.py`) and records every call."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from conftest import Chantier, Surface
from store_spy import (
    MAIN,
    WRITES,
    Spy,
    build_states,
    enter_state,
    fingerprint,
    install_spy,
    under,
    unguarded,
)

from chantier.board import autosync_tool, routes
from chantier.board import key as keys
from chantier.board.context import Context, Request
from chantier.board.projects import Projects
from chantier.board.seats import Seats
from chantier.core import batch as batch_module
from chantier.core.errors import ChantierError
from chantier.core.repo import Repo

OK = 200


@pytest.fixture
def spies(monkeypatch: pytest.MonkeyPatch) -> dict[int, Spy]:
    return install_spy(monkeypatch)


@pytest.fixture(scope="session")
def states(surface_template: Path, tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    return build_states(surface_template, tmp_path_factory)


@pytest.fixture
def world(
    states: dict[str, Path],
    repo: Path,
    tmp_path: Path,
    chantier: Chantier,
    monkeypatch: pytest.MonkeyPatch,
) -> Callable[[str], Surface]:
    """A copy of one state, the session running in it."""
    return lambda state: enter_state(states[state], tmp_path, monkeypatch)


# --- the rows ------------------------------------------------------------------------------------


@dataclass
class Row:
    name: str
    state: str
    argv: list[str]  # the CLI's command, or the board's `METHOD route`, then the body below
    command: str  # the command name a refusal quotes
    setup: tuple[tuple[str, ...], ...] = ()  # CLI commands run before the spy, same state
    body: dict[str, Any] | None = None


A, B = "1-inbox/alpha", "1-inbox/beta"
TERRA = "gpt-6.1-terra"
PEND = "4-batch/1-pending/"
RELEASE = ("order", "add", "--note", "1-inbox/delta", "--release")
SET = ("summary", "set", PEND + "101-alpha", "--title", "T", "--summary", "S")
MERGE = [("order", "merged", f"CR-{n}", "--epoch", "0") for n in (101, 102, 103)]
# fmt: off
ROWS = [
    Row("file", "backlog", ["file", "A new idea"], "file"),
    Row("init", "bare", ["init"], "init"),
    Row("triage", "backlog", ["triage", "1-inbox/idea-a", "--ready"], "triage"),
    Row("abandon", "backlog", ["abandon", "1-inbox/idea-a"], "abandon"),
    Row("restore", "backlog", ["restore", "{trash}"], "restore"),
    Row("open one", "backlog", ["open", A, *MAIN], "open"),
    Row("open several", "backlog", ["open", A, B, "1-inbox/gamma", *MAIN], "open"),
    Row("take", "batch", ["take", "CR-101", "--epoch", "0"], "take"),
    Row("round", "batch", ["round", "CR-101"], "round", (("take", "CR-101", "--epoch", "0"),)),
    Row("order qa", "batch", ["order", "qa", "--note", "check it"], "order qa"),
    Row("order add", "batch", ["order", "add", "--note", "1-inbox/delta"], "order add"),
    Row(
        "order add release", "batch", list(RELEASE), "order add",
    ),
    Row(
        "order add fix", "batch",
        ["order", "add", "--fix-for", "CR-104", "--note", PEND + "104-delta/fix.md"],
        "order add",
        (RELEASE, ("@write", PEND + "104-delta/fix.md")),
    ),
    Row("order merged", "batch", ["order", "merged", "CR-101", "--epoch", "0"], "order merged"),
    Row("order drop", "batch", ["order", "drop", "CR-102", "--note", "P2"], "order drop"),
    Row(
        "cancel", "batch", ["cancel", "CR-102", "--epoch", "0"], "cancel",
        (("take", "CR-102", "--epoch", "0"), ("order", "drop", "CR-102", "--note", "P2")),
    ),
    Row(
        "handback", "batch", ["handback", "CR-104", "ready", "v1.0.0"], "handback",
        (RELEASE, *MERGE, ("take", "CR-104", "--epoch", "0")),
    ),
    Row(
        "close", "batch", ["close", "--yes"], "close",
        tuple(MERGE),
    ),
    Row(
        "summary set", "batch",
        ["summary", "set", PEND + "101-alpha", "--title", "T", "--summary", "S"], "summary set",
    ),
    Row(
        "summary label", "batch", ["summary", "label", PEND + "101-alpha", "--add", "x"],
        "summary label", (SET,),
    ),
    Row(
        "summary group", "batch", ["summary", "group", PEND + "101-alpha", "--name", "g"],
        "summary group", (SET,),
    ),
    Row("board new", "backlog", ["POST backlog/new"], "board backlog/new", body={"text": "x"}),
    Row(
        "board move", "backlog", ["POST backlog/move"], "board backlog/move",
        body={"items": ["alpha"], "to": "3-ready"},
    ),
    Row(
        "board labels", "backlog", ["POST backlog/labels"], "board backlog/labels",
        (("summary", "set", A, "--title", "T", "--summary", "S"),),
        {"items": ["alpha"], "add": "x"},
    ),
    Row(
        "board group", "backlog", ["POST backlog/group"], "board backlog/group",
        (("summary", "set", A, "--title", "T", "--summary", "S"),),
        {"items": ["alpha"], "name": "g"},
    ),
    Row("board edit", "backlog", ["PUT backlog/file"], "board backlog/file", body={}),
    Row(
        "board next batch", "backlog", ["POST backlog/next-batch"], "board backlog/next-batch",
        (("triage", "1-inbox/beta", "--ready"),),
    ),
    Row("board config", "backlog", ["PUT config"], "board config", body={}),
]
# fmt: on


def _board(surface: Surface, monkeypatch: pytest.MonkeyPatch) -> Callable[..., tuple[int, Any]]:
    """The board's routes, called in-process with the key and the headers a page sends."""
    monkeypatch.setattr(autosync_tool, "spawn_join", lambda *a, **k: pytest.fail("autosync"))
    found = Repo.find(project="demo", readonly=True)
    projects = Projects(found, found.surface, [])
    secret = keys.load_or_create(found)
    ctx = Context(projects, keys.KeyFile(keys.key_path(found)), Seats(projects), "t", lambda: None)

    def call(method: str, route: str, body: object = None) -> tuple[int, Any]:
        head = {keys.HEADER: secret, "content-type": "application/json", "host": "board"}
        raw = b"" if body is None else json.dumps(body).encode()
        path = f"/api/projects/{projects.home_id}/{route}"
        reply = routes.handle(ctx, Request(method, path, {}, head, raw))
        return reply.status, json.loads(reply.body)

    return call


def _prepare(row: Row, surface: Surface, chantier: Chantier) -> list[str]:
    for step in row.setup:
        if step[0] == "@write":
            (surface.project / "changes" / step[1]).write_text("# fix\n\nFix.\n", encoding="utf-8")
        else:
            code, out, err = chantier(*step)
            assert code == 0, (step, out, err)
    argv = list(row.argv)
    if "{trash}" in argv:
        trash = surface.project / "changes" / "6-trash"
        argv[argv.index("{trash}")] = (
            next(trash.iterdir()).relative_to(surface.project / "changes").as_posix()
        )
    return argv


def _execute(
    row: Row, argv: list[str], surface: Surface, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> int:
    """Run the row's command; returns its exit code (board: 0 for 200, else the status)."""
    if row.name == "close":  # no Foreman transcript in a test: nothing to price
        monkeypatch.setattr("chantier.commands.closing.final_rows", lambda *a: [])
    if row.command.startswith("board"):
        call = _board(surface, monkeypatch)
        method, route = argv[0].split()
        body = row.body
        if row.name == "board edit":
            item = surface.project / "changes" / "1-inbox" / "alpha" / "03-change-spec.md"
            text = "# alpha\n\nEdited.\n"
            body = {
                "item": "alpha",
                "path": "03-change-spec.md",
                "text": text,
                "base_sha256": hashlib.sha256(item.read_bytes()).hexdigest(),
            }
        if row.name == "board config":
            view = call("GET", "config")[1]
            body = {
                "changes": [{"host": "copilot", "role": "coder", "key": "model", "value": TERRA}],
                "base_sha256": view["sha256"],
                "dry_run": False,
            }
        status, answer = call(method, route, body)
        assert status == OK, answer
        return 0
    code, out, err = chantier(*argv)
    assert code == 0, (argv, out, err)
    return code


def _covered(path: str, checked: list[str]) -> bool:
    return any(under(path, c) for c in checked)


def _published(spy: Spy, project: Path, before: dict[str, bytes | None]) -> set[str]:
    """The published paths of the planning folder (as store paths) that changed since `before`."""
    after = fingerprint(project)
    changed = {p for p in {*before, *after} if before.get(p) != after.get(p)}
    return {
        p.removeprefix("changes/")
        for p in changed
        if p.startswith("changes/")
        and p != "changes/.gitignore"  # through the store, never checked
        and spy.real.published(p.removeprefix("changes/"))
    }


@pytest.mark.parametrize("row", ROWS, ids=[r.name for r in ROWS])
def test_every_published_write_of_a_command_is_checked_first_through_the_store(
    row: Row,
    world: Callable[[str], Surface],
    chantier: Chantier,
    spies: dict[int, Spy],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    surface = world(row.state)
    argv = _prepare(row, surface, chantier)
    before = fingerprint(surface.project)
    spies.clear()  # only the command's own calls
    assert _execute(row, argv, surface, chantier, monkeypatch) == 0
    (spy,) = (s for s in spies.values() if s.calls)
    calls = [c for c in spy.calls if c[0] != "ensure_gitignore"]
    names = [c[0] for c in calls]
    # a check ran, before every write, and at a time when nothing had changed
    assert "check_publish" in names, names
    first_write = next((i for i, n in enumerate(names) if n in WRITES), len(names))
    assert "check_publish" in names[:first_write], names
    assert unguarded(spy.prints[0]) == unguarded(before), "written before the first check"
    # every check names the command, and the paths of each write; nothing else is written
    checks = [c for c in calls if c[0] == "check_publish"]
    assert {c[2]["command"] for c in checks} == {row.command}
    checked = [p for c in calls[:first_write] if c[0] == "check_publish" for p in c[1]]
    for name, rels, _ in calls[first_write:]:  # every write is named by a check made up front
        if name in WRITES and name != "write_config":
            for rel in rels:
                assert not spy.real.published(rel) or _covered(rel, checked), (name, rel, checked)
    if row.name == "board config":
        assert any(c[2]["config"] for c in checks)
        assert "write_config" in names
    changed = _published(spy, surface.project, before)
    written = {rel for name, rels, _ in calls if name in WRITES for rel in rels}
    assert all(_covered(p, sorted(written)) or _under_any(p, written) for p in changed), (
        changed - written
    )


def _under_any(path: str, written: set[str]) -> bool:
    """A path changed by a recorded write: the write's own, or under a moved or made folder."""
    return any(under(path, w) for w in written)


def test_a_refused_command_puts_every_move_back_through_the_store(
    world: Callable[[str], Surface],
    chantier: Chantier,
    spies: dict[int, Spy],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An `open` that fails after its moves: each move is undone, through `move`; the planning
    folder is as it was."""
    surface = world("backlog")
    before = fingerprint(surface.project)

    def refuse(*_a: object) -> None:
        raise ChantierError("refused after the moves")

    monkeypatch.setattr(batch_module, "reserve_record", refuse)
    spies.clear()
    assert chantier("open", A, B, *MAIN)[0] != 0
    (spy,) = (s for s in spies.values() if s.calls)
    moves = [rels for name, rels, _ in spy.calls if name == "move"]
    forth, back = moves[:2], moves[2:]
    assert [(d, s) for s, d in forth][::-1] == back
    checked = [p for name, rels, _ in spy.calls if name == "check_publish" for p in rels]
    assert all(_covered(p, checked) for pair in forth for p in pair)
    assert not _published(spy, surface.project, before)


def test_the_gitignore_is_written_through_the_store_and_never_checked(
    world: Callable[[str], Surface],
    chantier: Chantier,
    spies: dict[int, Spy],
) -> None:
    surface = world("bare")
    spies.clear()
    assert chantier("init")[0] == 0
    (spy,) = (s for s in spies.values() if s.calls)
    assert any(name == "ensure_gitignore" for name, _, _ in spy.calls)
    assert (surface.project / "changes" / ".gitignore").is_file()
    assert not [
        p
        for name, rels, _ in spy.calls
        if name == "check_publish"
        for p in rels
        if ".gitignore" in p
    ]
