"""The limits' last matrix cells: the shipped file lacking a limit on the board's view, a board
save of 0 slots, and `open` on a repository with no planning surface."""

from __future__ import annotations

from pathlib import Path

import pytest
from batch_helpers import FROM_AGENTS_MD
from conftest import Chantier, Surface
from test_board_config import OK, _on_surface
from test_limits import SLOTS, _as_chief, _forge, _lacking, _limit, _open, _put

from chantier.core.errors import EXIT_PRECONDITION


@pytest.mark.parametrize("key", ["batch.slots", "specifying.parallel"])
def test_the_board_view_shows_the_problem_when_the_shipped_file_lacks_a_limit(
    surface: Surface, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, key: str
) -> None:
    monkeypatch.setenv("CHANTIER_PLUGIN_ROOT", str(_lacking(tmp_path, key)))
    view = _on_surface(monkeypatch)("GET")[1]
    assert any(f'the shipped defaults lack "{key}"' in p for p in view["problems"]), view[
        "problems"
    ]


def test_the_board_saves_zero_slots_and_journals_it_and_open_then_refuses(
    surface: Surface, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    _as_chief(monkeypatch)
    call = _on_surface(monkeypatch)
    code, answer = _put(call, [_limit("batch.slots", 0)])
    assert code == OK, answer
    assert "slots: 0" in (surface.project / "chantier.yaml").read_text("utf-8")
    (event,) = _forge(surface)
    assert (event["key"], event["old"], event["new"], event["by"]) == (
        "batch.slots",
        SLOTS,
        0,
        "board",
    )
    code, _, err = _open(chantier)
    assert code == EXIT_PRECONDITION and "batch.slots is 0 in" in err


def test_open_with_no_planning_surface_and_no_slots_takes_the_shipped_value(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    _as_chief(monkeypatch)
    code, out, err = chantier("open", *FROM_AGENTS_MD, "--mode", "stack")
    assert code == 0, err
    assert f", {SLOTS} slots, stack" in out[0]
