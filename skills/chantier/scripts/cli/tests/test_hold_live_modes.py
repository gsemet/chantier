"""`order hold` of a working CR through the real commands (`take`, `agents set`, `handback`,
`order`), in each batch mode: the lease, the slot, the refusals and the way back."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from batch_helpers import changes, open_batch, record
from conftest import Chantier

from chantier.core.batch import read_batch, resolve_batch
from chantier.core.repo import Repo
from chantier.rails import held, slot_free

PR = "https://github.com/o/r/pull/1"
HELD = "{cr} is held (order O-1): only the user's `order unhold {cr}`"


def crs(repo: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = record(repo)["crs"]
    return rows


@pytest.mark.parametrize("mode", ["parallel", "series", "stack"])
def test_a_working_cr_held_in_every_mode_loses_its_lease_and_slot_then_comes_back(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    args = ("--mode", mode, "--slots", 1)
    a, b, _ = open_batch(repo, chantier, monkeypatch, "A", "B", "C", args=args)
    assert chantier("take", a, "--epoch", 1)[0] == 0
    lease = chantier.leases[a]  # type: ignore[attr-defined]
    assert chantier("agents", "set", a, "agent-x", "--epoch", 1)[0] == 0
    code, _, err = chantier("take", b, "--epoch", 1)
    assert code != 0 and "no free slot" in err  # the one slot is A's
    assert chantier("order", "hold", a)[0] == 0
    row = crs(repo)[0]
    assert row["status"] == "blocked" and row["blocked_reason"] == "held: order O-1"
    r = Repo.find()
    assert held(d := read_batch(r, resolve_batch(r, None))) == [] and slot_free(d)
    code, _, err = chantier.bare(  # type: ignore[attr-defined]
        "note", a, "more", "--lease", lease
    )
    assert code != 0 and "claim lost" in err  # the old Driver's next leased command
    ready = ("handback", a, "ready", PR, "--no-gate", "x")
    for argv, words in [
        (ready, HELD.format(cr=a)),  # the agent is still recorded: the held refusal
        (("handback", a, "blocked", "why"), f"{a} is blocked: no Driver holds it"),
    ]:
        code, _, err = chantier(*argv)
        assert code != 0 and words in err
    assert chantier("agents", "set", a, "-", "--epoch", 1)[0] == 0
    before = (changes(repo) / "4-batch" / "batch.json").read_bytes()
    code, _, err = chantier(*ready)  # no agent recorded: `live_cr`'s own text
    assert code != 0 and f"{a} is blocked: no Driver holds it" in err
    code, _, err = chantier("take", a, "--note", "again", "--epoch", 1)
    assert code != 0 and f"{HELD.format(cr=a)} releases it" in err
    assert (changes(repo) / "4-batch" / "batch.json").read_bytes() == before
    assert chantier("order", "done", "O-1", "--epoch", 1)[0] == 0
    assert chantier("take", b, "--epoch", 1)[0] == 0  # a queued CR takes the freed slot
    spent = crs(repo)[0].get("round", 0)
    assert chantier("order", "unhold", a)[0] == 0
    back = crs(repo)[0]
    assert back["blocked_reason"] == "unheld: order O-2" and "held" not in back
    started = [x["order"] for x in crs(repo) if x["id"] != a and x["status"] != "queued"]
    assert back["order"] > max(started)
    if mode != "series":  # a series puts it below the queued CRs
        assert back["order"] > max(x["order"] for x in crs(repo) if x["id"] != a)
    code, _, err = chantier("take", a, "--note", "unhold: O-2", "--epoch", 1)
    assert code != 0 and "no free slot" in err  # B holds the slot now
    assert chantier("handback", b, "blocked", "stop")[0] == 0
    code, _, err = chantier("take", a, "--note", "unhold: O-2", "--epoch", 1)
    assert code == 0, err
    again = crs(repo)[0]
    assert again["status"] == "working" and again.get("round", 0) == spent
