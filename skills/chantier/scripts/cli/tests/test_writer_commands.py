"""The commands that show the surface's writer (spec CR-404 C.9, C.10): `sync`, `sync now`,
`status`, `seat`, preflight's P13 and the board's `writer` route; read from a prepared entry."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import pytest
from api_client import call_op
from batch_helpers import FROM_AGENTS_MD, host
from conftest import Chantier, Surface

from chantier.board import key as keys
from chantier.board.context import Context
from chantier.board.projects import Projects
from chantier.board.seats import Seats
from chantier.core import clock
from chantier.core.errors import EXIT_PRECONDITION
from chantier.core.repo import Repo
from chantier.hub import journal, lock, state

AT = "2026-11-20T10:30:00Z"
HHMM = clock.local_hhmm(AT)
HTTP_OK, HTTP_NO_KEY, HTTP_NOT_FOUND, HTTP_CONFLICT = 200, 401, 404, 409
IN_PROJECT = "sync: in-project planning folder: chantier commits nothing"


def put(surface: Surface, kind: str | None, **more: Any) -> None:
    """The `writer` entry of this test's process, in this state; none removes it."""
    git_dir = surface.root / ".git"
    if kind is None:
        state.modify(git_dir, lambda data: data.pop(state.WRITER, None))
        return
    entry = {
        "pid": os.getpid(),
        "started": clock.now(),
        "state": kind,
        "ahead": 2,
        "pending": 3,
        **more,
    }
    state.modify(git_dir, lambda data: data.__setitem__(state.WRITER, entry))


def test_sync_prints_the_state_line_and_each_conflicted_file(
    surface: Surface, chantier: Chantier
) -> None:
    put(surface, "synced", last_push={"at": AT})
    assert chantier("sync")[1] == [f"writer: synced, pushed {HHMM}"]
    put(surface, "conflict", conflict={"files": ["projects/demo/a.md", "projects/demo/b.md"]})
    out = chantier("sync")[1]
    assert out[0].startswith("writer: conflict with the remote on projects/demo/a.md")
    assert out[1:] == ["conflict: projects/demo/a.md", "conflict: projects/demo/b.md"]


def test_sync_in_a_project_folder_says_chantier_commits_nothing(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(repo)
    assert chantier("sync") == (0, [IN_PROJECT], "")
    assert chantier("sync", "now") == (0, [IN_PROJECT], "")


def test_sync_now_with_no_writer_is_refused_and_asks_for_nothing(
    surface: Surface, chantier: Chantier
) -> None:
    put(surface, None)
    code, out, err = chantier("sync", "now")
    assert code == EXIT_PRECONDITION and out == []
    assert "sync now: the surface's writer is not running: nothing written" in err
    assert not lock.wake_path(surface.root / ".git").exists()


def test_sync_now_wakes_the_writer_and_waits_for_the_next_cycle_end(
    surface: Surface, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    put(surface, "pending", last_cycle="2000-01-01T00:00:00Z")
    waits: list[float] = []

    def cycle_ends(seconds: float) -> None:
        waits.append(seconds)
        assert lock.wake_path(surface.root / ".git").is_file()  # touched before the wait
        put(surface, "synced", last_cycle=clock.now(), last_push={"at": AT})

    monkeypatch.setattr(time, "sleep", cycle_ends)
    code, out, _ = chantier("sync", "now")
    assert (code, out) == (0, [f"writer: synced, pushed {HHMM}"]) and len(waits) == 1


def test_sync_now_gives_up_after_ten_seconds_and_prints_the_state(
    surface: Surface, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    put(surface, "pending", last_cycle="2000-01-01T00:00:00Z")
    ticks = iter(range(0, 1000, 4))
    monkeypatch.setattr(time, "monotonic", lambda: float(next(ticks)))
    monkeypatch.setattr(time, "sleep", lambda _s: None)
    code, out, _ = chantier("sync", "now")
    assert code == 0 and out[0].startswith("writer: pending, 3 paths changed since")


def test_seat_carries_the_writer_line_in_a_surface_only(
    surface: Surface, chantier: Chantier, repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CHANTIER_HOST", "claude")
    put(surface, "synced")
    line = "writer: synced, never pushed"
    assert chantier("seat")[1] == ["seat none", line]
    assert chantier("seat", "take", "s1")[1][-1] == line
    assert chantier("seat")[1][-1] == line
    put(surface, None)
    assert chantier("seat")[1][-1].startswith("writer: not running")
    monkeypatch.chdir(repo)
    assert chantier("seat")[1] == ["seat none"]


def test_seat_take_tells_an_untold_arrival_once_and_does_not_wait_on_the_lock(
    surface: Surface, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CHANTIER_HOST", "claude")
    assert chantier("file", "Arrives before the seat")[0] == 0  # no seat: an `arrived@1` line
    code, out, _ = chantier("seat", "take", "s1")
    assert code == 0
    assert any("another session wrote" in x for x in out)
    assert not any("another session wrote" in x for x in chantier("seat", "get")[1])


def test_status_has_the_writer_line_and_tells_an_episode_only_while_it_lasts(
    surface: Surface, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    host(monkeypatch)
    assert chantier("open", *FROM_AGENTS_MD, "--mode", "stack")[0] == 0
    folder = surface.project / "changes"
    folder.mkdir(exist_ok=True)
    line = {
        "v": 2, "seq": 1, "t": AT, "source": "writer", "audience": ["demo"],
        "type": "sync-conflict@1", "upstream": "a" * 40, "local": "b" * 40,
        "files": ["projects/demo/a.md"], "projects": ["demo"],
    }  # fmt: skip
    (folder / journal.FILE).write_text(json.dumps(line) + "\n", encoding="utf-8")
    put(surface, "conflict", conflict={"files": ["projects/demo/a.md"]})
    shown = chantier("status")[1]
    assert shown[1].startswith("writer: conflict")  # right after the batch line
    assert any(x.startswith("writer: conflict with the remote") for x in shown)
    assert any("writer saw a conflict with the remote on projects/demo/a.md" in x for x in shown)
    put(surface, "synced")
    shown = chantier("status")[1]
    assert "writer: synced, never pushed" in shown
    assert not any("writer saw a conflict" in x for x in shown)


@pytest.mark.parametrize(
    ("kind", "good"),
    [
        ("synced", True), ("pending", True), ("syncing", True),
        ("offline", False), ("blocked", False), ("conflict", False), (None, False),
    ],
)  # fmt: skip
def test_p13_is_the_writer_check_and_never_fails_the_report(
    surface: Surface, chantier: Chantier, kind: str | None, good: bool
) -> None:
    put(surface, kind, reason="staged", text="x.md")
    out = chantier("preflight", "--direct")[1]
    p13 = [x for x in out if x.startswith("P13")]
    assert len(p13) == 1
    assert p13[0].startswith("P13 ok   the surface's writer runs: ") == good
    assert good or p13[0].startswith("P13 warn writer: ")


def test_p13_warns_on_a_surface_rule_that_names_the_old_tool_or_a_hand_push(
    surface: Surface, chantier: Chantier
) -> None:
    put(surface, "synced")
    rules = surface.root / "AGENTS.md"

    def p13() -> list[str]:
        return [x for x in chantier("preflight", "--direct")[1] if x.startswith("P13")]

    rules.write_text("Commit, `git pull --rebase`, `git push`.\n", encoding="utf-8")
    assert p13()[1:] == [
        "P13 warn the surface's rules name a hand pull or push: chantier's writer pushes every "
        "commit of the surface while it runs, nobody pulls or pushes it by hand; remove it from "
        "the surface's AGENTS.md"
    ]
    rules.write_text("See .agents/guidelines/autosync.guidelines.md.\n", encoding="utf-8")
    assert p13()[1:] == [
        "P13 warn the surface's rules name its autosync tool: chantier's writer replaces it; "
        "remove the mention from the surface's AGENTS.md"
    ]
    rules.write_text("Nothing about it.\n", encoding="utf-8")
    assert len(p13()) == 1


def test_the_board_serves_the_writer_entry_and_its_sync_op_wakes_it(
    surface: Surface, monkeypatch: pytest.MonkeyPatch
) -> None:
    found = Repo.find(project="demo", readonly=True)
    projects = Projects(found, found.surface, [])
    secret = keys.load_or_create(found)
    ctx = Context(
        projects, keys.KeyFile(keys.key_path(found)), Seats(projects), "t", lambda: None, None
    )

    def call(op: str, key: bool = True) -> tuple[int, Any]:
        return call_op(ctx, secret if key else None, op)

    put(surface, "pending")
    status, body = call("board.get")
    assert status == HTTP_OK and body["writer"]["state"] == "pending" and "autosync" not in body
    assert call("writer.sync", key=False)[0] == HTTP_NO_KEY
    assert not lock.wake_path(surface.root / ".git").exists()
    status, body = call("writer.sync")
    assert status == HTTP_OK and body["writer"]["state"] == "pending"
    assert lock.wake_path(surface.root / ".git").is_file()
    put(surface, None)
    assert call("board.get")[1]["writer"] == {"state": "off"}
    status, body = call("writer.sync")
    assert status == HTTP_CONFLICT and "the surface's writer is not running" in body["error"]
    assert call("autosync")[0] == HTTP_NOT_FOUND
