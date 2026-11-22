"""The run-time proof of the plan's store reads (spec CR-452 section 6): while the board, `status`
and the hub read a prepared planning folder, no file of it is opened and no folder of it is listed
but through the store. An audit hook (`open`, `os.listdir`, `os.scandir`) records each such event
whose call stack holds no frame of `chantier/store/`; a write is not a read, and the reads that
stay direct are the table below, whose every entry must match an event. `exists`, `is_file`,
`is_dir` and `stat` raise no audit event: the structure test (`test_store_reads.py`) holds them."""

from __future__ import annotations

import json
import os
import shutil
import sys
import sysconfig
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from conftest import Chantier, Surface, live_writer
from forge_world import NEW_VERSION, OPEN, crs_of, write_batch

from chantier import connectors
from chantier.board.state import project_state
from chantier.commands.forge_stack_gh import pr_parts
from chantier.core.repo import Repo
from chantier.hub.cycle import Hub
from chantier.store import FolderStore

WRITE_MODE = set("wax+")

# (path suffix, module file, function) -> reason, of a read of the planning folder that stays
# direct: the event must also come from that innermost non-stdlib frame; each must match an event
# of the run, or the test fails (the table does not outlive the read it excuses)
EXEMPT: dict[tuple[str, str, str], str] = {
    (".long-gate.lock", "gate_slots.py", "lock_text"): (
        "a held OS lock file, read past its locked byte"
    ),
}

STDLIB = os.path.normcase(sysconfig.get_paths()["stdlib"])
Event = tuple[str, str, str, str, int]  # event, relative path, module file, function, line
events: list[Event] = []
armed: dict[str, Any] = {"on": False, "root": ""}


def stdlib_frame(name: str) -> bool:
    low = os.path.normcase(name)
    return name.startswith("<") or (low.startswith(STDLIB) and "site-packages" not in low)


def stack() -> tuple[bool, tuple[str, str, int]]:
    """Whether a frame of the plan store's package is on the stack, and the innermost frame outside
    the standard library (module file, function, line)."""
    frame: Any = sys._getframe(2)
    inner: tuple[str, str, int] | None = None
    in_store = False
    while frame is not None:
        name = frame.f_code.co_filename
        if "/chantier/store/" in name.replace("\\", "/"):
            in_store = True
        if inner is None and not stdlib_frame(name):
            inner = (Path(name).name, frame.f_code.co_name, frame.f_lineno)
        frame = frame.f_back
    return in_store, inner or ("?", "?", 0)


def writes(args: tuple[Any, ...]) -> bool:
    """Whether an `open` event is a write: its mode's letters, or its flags."""
    mode, flags = [*args, None, None][1:3]
    return bool(WRITE_MODE & set(str(mode))) or bool(
        isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_APPEND | os.O_CREAT)
    )


def audit(event: str, args: tuple[Any, ...]) -> None:
    if not armed["on"] or event not in ("open", "os.listdir", "os.scandir"):
        return
    target = args[0] if args else None
    if not isinstance(target, str | bytes | os.PathLike):
        return  # a file descriptor or no path
    path = os.fsdecode(target)
    if event == "open" and writes(args):
        return
    resolved = os.path.normcase(os.path.abspath(path))
    if not resolved.startswith(armed["root"]):
        return
    in_store, (module, func, line) = stack()
    if not in_store:
        rel = resolved[len(armed["root"]) :].lstrip("\\/").replace("\\", "/")
        events.append((event, rel, module, func, line))


sys.addaudithook(audit)


def is_exempt(found: Event) -> tuple[str, str, str] | None:
    _, rel, module, func, _ = found
    return next((k for k in EXEMPT if rel.endswith(k[0]) and (module, func) == (k[1], k[2])), None)


def describe(found: Event) -> str:
    event, rel, module, func, line = found
    return f"{rel}: {event} from {module}:{func}:{line}"


@pytest.fixture(scope="module")
def world(
    surface_template: Path, tmp_path_factory: pytest.TempPathFactory
) -> Iterator[tuple[Surface, Path]]:
    """One surface with a prepared planning folder, built once for the module."""
    root = tmp_path_factory.mktemp("store-runtime") / "surface"
    shutil.copytree(surface_template, root)
    live_writer(root.resolve() / ".git")
    root = root.resolve()
    project = root / "projects" / "demo"
    found = Surface(root, project, project / ".repo")
    changes = project / "changes"
    prepare(changes)
    write_batch(project, "running", crs_of("alpha", "working"))
    batch = changes / "4-batch"
    for stage in ("1-pending", "2-actives", "3-done"):
        order = batch / stage / f"{len(stage):03d}-order"
        (order / "work").mkdir(parents=True)
        (order / "01-intent.md").write_text(f"# {stage}\n\nAn intent.\n", encoding="utf-8")
        (order / "03-change-spec.md").write_text(f"# {stage}\n\nSee [x](01-intent.md).\n")
    (changes / ".long-gate.lock").write_bytes(b"locked\ncr-1 pid 1\n")
    (changes / ".lease-hold.CR-1.1.run").write_text(json.dumps({"pid": 1}), encoding="utf-8")
    (changes / ".batch-number").write_text("1\n", encoding="utf-8")
    records = changes / "5-archives" / "batches"
    records.mkdir(parents=True)
    (records / "batch-00.json").write_text(
        json.dumps({"id": "batch-00", "status": "done", "crs": []}), encoding="utf-8"
    )
    (changes / "forge-journal.jsonl").write_text("", encoding="utf-8")
    yield found, changes


def prepare(changes: Path) -> None:
    """CRs in the inbox, the backlog and the ready folder."""
    for folder in ("1-inbox", "2-backlog/P1", "2-backlog/P3", "3-ready"):
        cr = changes / folder / "example-cr"
        cr.mkdir(parents=True)
        (cr / "01-intent.md").write_text("# Example\n\nAn intent.\n", encoding="utf-8")
    ready = changes / "3-ready" / "example-cr"
    (ready / "03-change-spec.md").write_text("# Example\n\nA spec.\n", encoding="utf-8")


def board(found: Surface, monkeypatch: pytest.MonkeyPatch, chantier: Chantier) -> None:
    repo = Repo.find(found.root, str(found.project), readonly=True)
    state = project_state("demo", repo, True, None)
    assert state["batch"] is not None  # the prepared batch was read


def status(found: Surface, monkeypatch: pytest.MonkeyPatch, chantier: Chantier) -> None:
    monkeypatch.chdir(found.root)
    code, _, err = chantier("status")
    assert code == 0, err


def hub(found: Surface, monkeypatch: pytest.MonkeyPatch, chantier: Chantier) -> None:
    def read(links: list[str], facts: frozenset[str] = frozenset()) -> dict[int, dict[str, Any]]:
        return {int(pr_parts(x)[3]): dict(OPEN) for x in links}

    monkeypatch.setattr(connectors, "read", read)
    repo = Repo.find(found.root, str(found.project))
    Hub(repo, NEW_VERSION).cycle(0.0)


CASES: dict[str, Callable[[Surface, pytest.MonkeyPatch, Chantier], None]] = {
    "board": board,
    "status": status,
    "hub": hub,
}
seen: set[tuple[str, str, str]] = set()


def run_armed(found: Surface, changes: Path, case: str, *fixtures: Any) -> list[Event]:
    events.clear()
    armed["root"] = os.path.normcase(os.path.abspath(changes))
    armed["on"] = True
    try:
        CASES[case](found, *fixtures)
    finally:
        armed["on"] = False
    return list(events)


@pytest.mark.parametrize("case", list(CASES))
def test_no_read_of_the_planning_folder_but_through_the_store(
    world: tuple[Surface, Path],
    case: str,
    monkeypatch: pytest.MonkeyPatch,
    chantier: Chantier,
) -> None:
    found, changes = world
    monkeypatch.setenv("CHANTIER_SKILL_DIR", str(Path(__file__).resolve().parents[2]))
    found_events = run_armed(found, changes, case, monkeypatch, chantier)
    for item in found_events:
        hit = is_exempt(item)
        if hit:
            seen.add(hit)
    stray = [describe(e) for e in found_events if is_exempt(e) is None]
    message = f"{case}: read of the planning folder outside the store:\n" + "\n".join(stray)
    assert stray == [], message


def test_the_hook_sees_a_direct_read_and_not_a_store_read(world: tuple[Surface, Path]) -> None:
    """The prepared check: a direct `Path.read_text` of a planning-folder file is recorded, a
    `store.read_text` of the same file is not."""
    _, changes = world
    rel = "1-inbox/example-cr/01-intent.md"
    events.clear()
    armed["root"] = os.path.normcase(os.path.abspath(changes))
    armed["on"] = True
    try:
        FolderStore(changes).read_text(rel)
        through_store = list(events)
        (changes / rel).read_text(encoding="utf-8")
    finally:
        armed["on"] = False
    assert through_store == []
    assert [(e[0], e[1], e[2], e[3]) for e in events] == [
        (
            "open",
            rel,
            "test_store_runtime.py",
            "test_the_hook_sees_a_direct_read_and_not_a_store_read",
        )
    ]


def test_the_prepared_folder_is_read(world: tuple[Surface, Path]) -> None:
    """The proof is not empty: the folder holds a batch, its orders, and the CRs of each stage."""
    _, changes = world
    for rel in (
        "4-batch/batch.json",
        "4-batch/2-actives",
        "1-inbox/example-cr",
        "3-ready/example-cr/03-change-spec.md",
        "5-archives/batches/batch-00.json",
    ):
        assert (changes / rel).exists(), rel


def test_every_exemption_matches_a_read(world: tuple[Surface, Path]) -> None:
    """An entry of the table that no event of the three cases matched fails: the read it excused
    is gone, so the entry goes too."""
    assert set(EXEMPT) <= seen, f"unmatched exemption: {sorted(set(EXEMPT) - seen)}"
