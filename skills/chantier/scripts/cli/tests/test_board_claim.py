"""One serving process per planning surface: `serve` claims the surface (`hub.lock`, held for the
process's life) before it looks at what runs. A start that loses joins the winner's board or
refuses; a running server that finds another live process recorded stops itself."""

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Any

import pytest
from batch_helpers import prepared
from conftest import Chantier
from test_board_running import _answer, _prepare_board

from chantier import __version__, procs
from chantier.board import claim, command
from chantier.board.projects import open_projects
from chantier.core.errors import EXIT_EXTERNAL
from chantier.hub import lock, state

PORT = 4321


def _winner_arrives(git_dir: Path, served: str, after_s: float) -> threading.Timer:
    """The start that won the claim records its board, a little after the loser began to wait."""
    timer = threading.Timer(
        after_s, lambda: state.write_server(git_dir, "127.0.0.1", PORT, __version__, served)
    )
    timer.start()
    return timer


def test_a_start_that_loses_the_claim_joins_the_board_that_won_it(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, bound = _prepare_board(repo, chantier, monkeypatch, (True, None, None))
    projects = open_projects()
    served, git_dir = projects.served.as_posix(), projects.home.git_dir
    answer = _answer(served, __version__)
    monkeypatch.setattr(command, "probe", lambda *_a, **_k: answer)
    monkeypatch.setattr(claim, "probe", lambda *_a, **_k: answer)
    monkeypatch.setattr(claim, "STEP_S", 0.05)
    winner = lock.HubLock(git_dir)
    assert winner.acquire()  # another process serves, or starts to
    timer = _winner_arrives(git_dir, served, 0.3)
    try:
        code, out, err = chantier("serve", "--port", "0")
    finally:
        timer.join()
        winner.release()
    assert code == 0, err
    assert out[0].startswith("board already running at http://127.0.0.1:") and not bound


def test_a_start_that_loses_the_claim_and_sees_no_board_refuses_at_the_bound(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, bound = _prepare_board(repo, chantier, monkeypatch, (False, None, None))
    monkeypatch.setattr(claim, "WAIT_S", 0.2)
    monkeypatch.setattr(claim, "STEP_S", 0.05)
    winner = lock.HubLock(open_projects().home.git_dir)
    assert winner.acquire()
    try:
        code, out, err = chantier("serve", "--port", "0")
    finally:
        winner.release()
    assert code == EXIT_EXTERNAL and out == [] and not bound
    assert f"board not started: {claim.HELD}" in err


def test_the_start_that_wins_serves_with_the_claim_held_and_lets_it_go_at_its_end(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    _prepare_board(repo, chantier, monkeypatch, (False, None, None))
    seen: list[tuple[bool, bool]] = []
    git_dir = open_projects().home.git_dir

    def serve(ctx: Any, sock: Any, files: Any, args: Any) -> None:
        other = lock.HubLock(git_dir)
        seen.append((ctx.claim.held, other.acquire()))  # held here, by this start, not free
        files.stop()
        sock.close()

    monkeypatch.setattr(command, "_run", serve)
    code, _, err = chantier("serve", "--port", "0")
    assert code == 0, err
    assert seen == [(True, False)]
    free = lock.HubLock(git_dir)
    assert free.acquire()
    free.release()


@pytest.mark.parametrize("recorded", ["other", "self", "dead"])
def test_a_server_that_is_not_the_recorded_one_stops_and_leaves_the_entry_alone(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch, recorded: str
) -> None:
    prepared(repo, chantier, "Board one")
    projects = open_projects()
    git_dir, served = projects.home.git_dir, projects.served.as_posix()
    state.write_server(git_dir, "127.0.0.1", PORT, __version__, served)
    path = state.path(git_dir)
    if recorded == "other":
        state.modify(git_dir, lambda d: d[state.SERVER].__setitem__("pid", os.getpid() + 1))
    monkeypatch.setattr(procs, "alive_since", lambda *_a, **_k: recorded != "dead")
    before = path.read_bytes()
    stops: list[int] = []
    claim.stray_check(git_dir, lambda: stops.append(1))()
    assert stops == ([1] if recorded == "other" else [])
    assert path.read_bytes() == before
