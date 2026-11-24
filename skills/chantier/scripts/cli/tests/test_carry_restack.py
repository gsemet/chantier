"""A clean restack carries the pass and the verdict even when the gate recorded a base below the
CR below (the judged commits then hold that CR's own): in-process on a prepared repository."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from batch_helpers import record, write_record
from conftest import Chantier, sh
from test_carry_ship import (  # noqa: F401  (stack3 is a fixture)
    PR,
    events,
    judge,
    remote,
    ship_off,
    stack3,
)
from test_gate_carry import commit, git_at

World = tuple[Path, Chantier, list[dict[str, Any]]]


def _started_on_a(repo: Path, a: dict[str, Any], b: dict[str, Any]) -> tuple[str, str, str]:
    """B started on A's tip and is judged there, the gate having recorded main as its base:
    returns main, A's tip and the judged head."""
    wa, wb = Path(a["worktree"]), Path(b["worktree"])
    main = sh("git", "rev-parse", "HEAD", cwd=repo)
    a_tip = commit(wa, "a.txt", "a\n", "A")
    remote(repo, a["branch"], a_tip)
    git_at(wb, "rebase", "-q", a_tip)
    return main, a_tip, commit(wb, "b.txt", "b\n", "B")


@pytest.mark.parametrize("case", ["A moved on", "A merged by a rebase merge"])
def test_a_clean_restack_carries_when_the_judged_base_is_below_the_cr_below(
    stack3: World,  # noqa: F811
    case: str,
) -> None:
    repo, chantier, (a, b, _) = stack3
    wa, wb = Path(a["worktree"]), Path(b["worktree"])
    main, a_tip, judged = _started_on_a(repo, a, b)
    judge(repo, b, judged, main)
    if case == "A moved on":
        new_base = commit(wa, "a2.txt", "a2\n", "A again")
        remote(repo, a["branch"], new_base)
        git_at(wb, "rebase", "-q", new_base)
        onto = a["branch"]
    else:  # A's commit cherry-picked onto main: origin/main moved, A recorded merged
        git_at(wa, "branch", "mainline", main)
        git_at(wa, "switch", "-q", "mainline")
        git_at(wa, "cherry-pick", a_tip)
        new_base = sh("git", "rev-parse", "HEAD", cwd=wa)
        git_at(wa, "switch", "-q", a["branch"])
        remote(repo, "main", new_base)
        data = record(repo)
        data["crs"][0]["status"] = "merged"
        write_record(repo, data)
        git_at(wb, "rebase", "-q", "--onto", new_base, a_tip)
        onto = "main"
    carried, off = ship_off(chantier, b)
    assert not off, off
    (carry,) = events(repo, "carry")
    assert carry["base"] == new_base and carry["gate_from"] == carry["verdict_from"] == judged
    want = f"carried: long gate and verdict from {judged[:7]} (clean rebase onto "
    assert len(carried) == 1 and carried[0].startswith(want) and onto in carried[0], carried
    remote(repo, b["branch"], sh("git", "rev-parse", "HEAD", cwd=wb))  # pushed
    code, _, err = chantier("handback", b["id"], "ready", PR)
    assert code == 0, err
