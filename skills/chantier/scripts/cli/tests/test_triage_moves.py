"""`triage` moves an item between the inbox, the backlog and 3-ready; it refuses a non-move."""

from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from batch_helpers import FROM_AGENTS_MD, changes, host, prepared
from conftest import Chantier

from chantier.commands.help import load_topics
from chantier.core import files as core_files
from chantier.core.errors import EXIT_EXTERNAL, EXIT_PRECONDITION
from chantier.roles_data import load_roles

SPEC = "03-change-spec.md"


def moved(repo: Path, out: list[str]) -> Path:
    return repo / out[0].removeprefix("triaged ").split(";", 1)[0].rsplit(" (", 1)[0]


def test_triage_moves_between_the_folders_and_refuses_what_is_not_a_move(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    host(monkeypatch)
    tree = changes(repo)
    spec = prepared(repo, chantier, "Tree with spec")
    bare = repo / chantier("file", "Tree without spec")[1][0].removeprefix("filed ").split(";")[0]
    ready_spec = moved(repo, chantier("triage", str(spec), "--ready")[1])
    ready_bare = moved(repo, chantier("triage", str(bare), "--ready")[1])
    assert ready_spec.parent == ready_bare.parent == tree / "3-ready"  # with a spec or without
    assert (ready_spec / SPEC).is_file() and not (ready_bare / SPEC).exists()
    assert not spec.exists() and not bare.exists()
    with pytest.raises(SystemExit):  # a target is required
        chantier("triage", str(ready_spec))
    assert ready_spec.is_dir()
    code, _, _ = chantier("triage", str(ready_spec), "--ready")
    assert code == EXIT_PRECONDITION and ready_spec.is_dir()  # already in 3-ready
    back = moved(repo, chantier("triage", str(ready_spec), "--priority", "P2")[1])
    assert back.parent == tree / "2-backlog" / "P2" and not ready_spec.exists()
    chantier("triage", str(back), "--ready")
    inboxed = moved(repo, chantier("triage", str(tree / "3-ready" / back.name), "--inbox")[1])
    assert inboxed.parent == tree / "1-inbox" and not back.exists()
    code, _, err = chantier("triage", str(inboxed), "--inbox")
    assert code == EXIT_PRECONDITION and "already in 1-inbox" in err and inboxed.is_dir()
    with pytest.raises(SystemExit):  # two targets move nothing
        chantier("triage", str(inboxed), "--inbox", "--ready")
    assert inboxed.is_dir()
    chantier("triage", str(inboxed), "--ready")
    backlog_bare = prepared(repo, chantier, "Tree backlog bare")
    (backlog_bare / SPEC).unlink()
    code, _, _ = chantier("open", str(backlog_bare), *FROM_AGENTS_MD)
    assert code == EXIT_PRECONDITION and backlog_bare.is_dir()
    assert not (tree / "4-batch" / "batch.json").exists()
    assert chantier("abandon", str(backlog_bare))[0] == 0


HOLDS = 3
SHIPPED_WAIT_S = 10.0
LONGEST_PAUSE_S = 0.5
REFERENCES = Path(__file__).resolve().parents[3] / "references"


@pytest.fixture
def world(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    """A fake clock for the helper (no real wait), its Windows check forced on, and a folder
    rename that raises `w.error` for the first `w.fails` calls (every call when None)."""
    w = SimpleNamespace(now=0.0, pauses=[], attempts=0, fails=None, windows=True)
    w.error = PermissionError(13, "The process cannot access the file", None, 32)
    real = Path.rename

    def sleep(seconds: float) -> None:
        w.pauses.append(seconds)
        w.now += seconds

    def rename(self: Path, target: Path) -> Path:
        w.attempts += 1
        if w.fails is None or w.attempts <= w.fails:
            raise w.error
        return real(self, target)

    monkeypatch.setattr(core_files, "time", SimpleNamespace(monotonic=lambda: w.now, sleep=sleep))
    monkeypatch.setattr(core_files, "on_windows", lambda: w.windows)
    monkeypatch.setattr(Path, "rename", rename)
    return w


def test_a_brief_hold_is_waited_out(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch, world: SimpleNamespace
) -> None:
    host(monkeypatch)
    item = prepared(repo, chantier, "Brief hold")
    world.fails = HOLDS
    code, _, err = chantier("triage", str(item), "--ready")
    assert code == 0, err
    assert world.attempts == HOLDS + 1 and len(world.pauses) == HOLDS  # three holds, then it moved
    assert not item.exists() and (changes(repo) / "3-ready" / item.name).is_dir()


@pytest.mark.parametrize("command", ["triage", "abandon"])
def test_a_lasting_hold_is_refused_with_its_cause(
    repo: Path,
    chantier: Chantier,
    monkeypatch: pytest.MonkeyPatch,
    world: SimpleNamespace,
    command: str,
) -> None:
    host(monkeypatch)
    assert core_files.HELD_WAIT_S == SHIPPED_WAIT_S  # board-lock-Q1
    item = prepared(repo, chantier, "Lasting hold")
    before = (item / SPEC).read_text("utf-8")
    code, _, err = chantier(command, str(item), *(["--ready"] if command == "triage" else []))
    assert code == EXIT_EXTERNAL
    wait = f"{core_files.HELD_WAIT_S:.3f}".rstrip("0").rstrip(".")
    assert f"refused for {wait} s, the folder is likely held; nothing moved" in err
    # the OS error stays at the end (its str() differs by platform: winerror shows on Windows only)
    assert "the board need not stop" in err and f"({world.error})" in err
    assert world.now >= core_files.HELD_WAIT_S and max(world.pauses) <= LONGEST_PAUSE_S
    assert (item / SPEC).read_text("utf-8") == before and item.parent.name == "1-inbox"
    ready = changes(repo) / "3-ready"
    assert not ready.exists() or not any(ready.iterdir())


@pytest.mark.parametrize(
    "error",
    [
        (FileNotFoundError(2, "No such file"), True),
        (PermissionError(13, "Permission denied"), False),
    ],
)
def test_any_other_error_is_one_attempt_with_todays_text(
    repo: Path,
    chantier: Chantier,
    monkeypatch: pytest.MonkeyPatch,
    world: SimpleNamespace,
    error: tuple[OSError, bool],
) -> None:
    host(monkeypatch)
    item = prepared(repo, chantier, "Other error")
    world.error, world.windows = error
    code, _, err = chantier("triage", str(item), "--ready")
    assert code == EXIT_EXTERNAL and world.attempts == 1 and not world.pauses
    assert "cannot move CR folder" in err and "refused for" not in err
    assert item.is_dir()


def test_every_role_is_told_to_keep_its_shell_out_of_cr_folders() -> None:
    topics = load_topics()
    told = {*topics["worker-shell"].roles, *topics["session-shell"].roles}
    untold = {r.name for r in load_roles()} - told
    assert untold == {"board-griller"}  # it runs its four chantier commands alone
    for name in ("session-shell-p2.md", "worker-shell.md"):
        assert "into a CR folder" in (REFERENCES / "topics" / name).read_text("utf-8"), name


windows_only = pytest.mark.skipif(
    sys.platform != "win32", reason="a folder is held by a handle only on Windows"
)


@windows_only
def test_w1_a_file_open_for_a_moment_is_waited_out(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    host(monkeypatch)
    monkeypatch.setattr(core_files, "HELD_WAIT_S", 1.0)
    item = prepared(repo, chantier, "Open file")
    opened = threading.Event()

    def hold() -> None:
        with open(item / SPEC, encoding="utf-8"):
            opened.set()
            time.sleep(0.3)

    thread = threading.Thread(target=hold)
    thread.start()
    assert opened.wait(5)
    code, _, err = chantier("triage", str(item), "--ready")
    thread.join()
    assert code == 0, err
    assert not item.exists() and (changes(repo) / "3-ready" / item.name).is_dir()


@windows_only
def test_w2_a_shell_inside_the_folder_refuses_then_lets_go(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    host(monkeypatch)
    monkeypatch.setattr(core_files, "HELD_WAIT_S", 1.0)
    item = prepared(repo, chantier, "Held by a process")
    # the child takes its working directory while it starts, after `Popen` returns: wait for its
    # word that it runs before moving the folder, or the move can come first and succeed
    child = subprocess.Popen(
        [sys.executable, "-c", "import time; print('up', flush=True); time.sleep(60)"],
        cwd=item,
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        assert child.stdout is not None and child.stdout.readline().strip() == "up"
        code, _, err = chantier("triage", str(item), "--ready")
        assert code == EXIT_EXTERNAL and "refused for 1 s, the folder is likely held" in err
        assert item.is_dir() and not (changes(repo) / "3-ready" / item.name).exists()
    finally:
        child.kill()
        child.wait()
        if child.stdout:
            child.stdout.close()
    code, _, err = chantier("triage", str(item), "--ready")
    assert code == 0, err


def arrivals_told(repo: Path) -> list[dict[str, object]]:
    file = changes(repo) / "forge-journal.jsonl"
    lines = file.read_text(encoding="utf-8").splitlines() if file.is_file() else []
    return [x for x in map(json.loads, lines) if x["type"] == "arrived@1"]


@pytest.mark.parametrize(
    ("session", "told"),
    [
        (
            "uuid-other",
            [
                ("1-inbox/an-idea", None),
                ("2-backlog/P2/an-idea", "1-inbox/an-idea"),
                ("1-inbox/an-idea", "3-ready/an-idea"),
            ],
        ),
        ("uuid-seat", []),
    ],
)
def test_file_and_triage_tell_an_arrival_unless_the_run_is_the_seats_own_session(
    repo: Path,
    chantier: Chantier,
    monkeypatch: pytest.MonkeyPatch,
    session: str,
    told: list[tuple[str, str | None]],
) -> None:
    host(monkeypatch)
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "uuid-seat")
    assert chantier("seat", "take", "s1")[0] == 0
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", session)
    tree = changes(repo)
    idea = repo / chantier("file", "An idea")[1][0].removeprefix("filed ").split(";")[0]
    p2 = moved(repo, chantier("triage", str(idea), "--priority", "P2")[1])
    ready = moved(repo, chantier("triage", str(p2), "--ready")[1])  # no line: not an arrival
    back = moved(repo, chantier("triage", str(ready), "--inbox")[1])  # back from 3-ready
    trash = tree / "6-trash"
    assert chantier("abandon", str(back))[0] == 0  # no line
    (gone,) = trash.iterdir()
    assert chantier("restore", str(gone))[0] == 0  # a restore: no line
    found = arrivals_told(repo)
    assert [(x["folder"], x["before"]) for x in found] == told
    assert all(x["via"] == "session" and x["source"] == "cli" for x in found)
    assert all(x["upstream"] is None for x in found)
