"""`order merged` in a stack batch names the restack the stack owes, as one printed line."""

from __future__ import annotations

from pathlib import Path

import pytest
from batch_helpers import open_batch, record, write_record
from conftest import Chantier

PR = "https://github.com/acme/demo/pull/"


def batch(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch, mode: str, **kw: object
) -> list[str]:
    """Three CRs handed back with PRs, in order; `kw` sets fields on the batch record."""
    ids = open_batch(repo, chantier, monkeypatch, "A", "B", "C", args=("--mode", mode))
    data = record(repo)
    for i, c in enumerate(data["crs"], 1):
        c.update({"status": "ready", "order": i, "pr": f"{PR}{i}"})
    data.update(kw)
    write_record(repo, data)
    return ids


def merged(chantier: Chantier, cr: str) -> list[str]:
    code, out, err = chantier("order", "merged", cr, "--epoch", 1)
    assert code == 0, err
    return [ln for ln in out if "restack owed" in ln]


def test_the_bottom_cr_merged_names_the_two_above_in_order_and_who_restacks(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    a, b, c = batch(repo, chantier, monkeypatch, "stack")
    (line,) = merged(chantier, a)
    assert line == (
        f"restack owed: {b}, {c} stood on {a}'s branch; the stack driver restacks them in one "
        "pass: one `take stack --epoch <n>` once every CR this merge merged is recorded"
    )


def test_a_recorded_stack_driver_gets_the_note_form(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    a, b, c = batch(repo, chantier, monkeypatch, "stack", stack_agent="local_stack_1")
    out = chantier("order", "merged", a, "--epoch", 1)[1]
    assert out[0] == f"merged {a}: moved to 3-done"  # right after it
    assert out[1] == (
        f"restack owed: {b}, {c} stood on {a}'s branch; the stack driver local_stack_1 restacks "
        f"them in one pass: send it the note `merged: {a}`"
    )


@pytest.mark.parametrize("case", ["parallel", "series", "fix", "last", "no PR above"])
def test_no_line_when_nothing_is_owed(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch, case: str
) -> None:
    mode = case if case in {"parallel", "series"} else "stack"
    a, _b, c = batch(repo, chantier, monkeypatch, mode)
    data = record(repo)
    if case == "fix":
        data["crs"][0]["kind"] = "fix"
    if case == "last":
        data["crs"][0]["status"] = data["crs"][1]["status"] = "merged"
    if case == "no PR above":
        data["crs"][1]["pr"] = data["crs"][2]["pr"] = None
    write_record(repo, data)
    assert merged(chantier, c if case == "last" else a) == []
