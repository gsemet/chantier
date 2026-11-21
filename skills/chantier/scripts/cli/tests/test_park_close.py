"""`close`, the batch's end and the release while a CR is parked, held or blocked: each CR's way
back, on a batch the CLI's own commands built."""

from __future__ import annotations

from pathlib import Path

import pytest
from batch_helpers import open_batch, record, write_record
from conftest import Chantier
from test_park import WAITS

PR = "https://example.com/pr/"
BACK = {
    "open": "is parked (w1 answer since ",
    "cleared": "is parked, its wait cleared: `take ",
    "held": "is held (order O-1): the user's `order unhold ",
    "infra": "is blocked (infra: down): take it back (`take ",
}


def left_batch(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch, way: str, extra: str
) -> list[str]:
    """CR one ready, CR two left in the given way, then what waits for it: nothing, a release, or
    two queued CRs (the second `after` the first)."""
    titles = {"none": (), "release": ("R",), "dependents": ("C", "D")}[extra]
    ids = open_batch(repo, chantier, monkeypatch, "A", "B", *titles, args=("--mode", "parallel"))
    data = record(repo)
    data["crs"][0].update(status="ready", pr=f"{PR}1", pr_draft=False, branch="b/1")
    data["crs"][1].update(status="working", branch="b/2")
    if way == "held":
        data["crs"][1].update(status="ready", held="O-1", pr=f"{PR}2", pr_draft=True)
    if way == "infra":
        data["crs"][1].update(status="blocked", blocked_reason="infra: down")
    if extra == "release":
        data["crs"][2].update(kind="release", after=[ids[0], ids[1]])
    if extra == "dependents":
        data["crs"][2]["after"], data["crs"][3]["after"] = [ids[1]], [ids[2]]
    write_record(repo, data)
    if way in {"open", "cleared"}:
        assert chantier("park", ids[1], *WAITS, "--epoch", 1)[0] == 0
    if way == "cleared":
        assert chantier("wait", ids[1], "clear", "w1", "--epoch", 1)[0] == 0
    return ids


@pytest.mark.parametrize(
    ("way", "extra"),
    [
        ("open", "none"),
        ("cleared", "none"),
        ("held", "none"),
        ("infra", "none"),
        ("open", "release"),
        ("open", "dependents"),
    ],
)
def test_close_and_the_batchs_end_name_each_crs_own_way_back(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch, way: str, extra: str
) -> None:
    ids = left_batch(repo, chantier, monkeypatch, way, extra)
    code, out, err = chantier("order", "merged", ids[0], "--note", "merged")
    assert code == 0, err
    text = "\n".join(out)
    assert f"every other CR is merged or cancelled; {ids[1]} {BACK[way]}" in text
    assert "the batch stays open until it comes back or the user sends it out" in text
    assert record(repo)["status"] != "paused"
    queued = ids[2:]
    line = "{q} is queued, waiting for {b} parked: it starts once each is back"
    for q in queued:
        assert line.format(q=q, b=ids[1]) in text
    code, _, err = chantier("close")
    assert code != 0 and f"cannot close batch-01: {ids[1]} {BACK[way]}" in err
    assert "Nothing was deleted." in err and "or send it out (`order drop <cr>" in err
    for q in queued:
        assert line.format(q=q, b=ids[1]) in err
    code, _, err = chantier("order", "drop", ids[1], "--note", "P2")
    assert code == 0, err
    for q in queued:  # the queued ones left with it
        assert chantier("order", "drop", q, "--note", "trash")[0] == 0
    assert record(repo)["status"] == "paused"
    code, _, err = chantier("close")  # no longer refused for the parked CR
    assert "or send it out" not in err and "is parked" not in err


@pytest.mark.parametrize(
    ("mode", "ends"),
    [("stack", "handed back ready or merged"), ("parallel", "merged or cancelled")],
)
def test_take_of_the_release_is_refused_while_a_cr_is_parked(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch, mode: str, ends: str
) -> None:
    a, b, rel = open_batch(repo, chantier, monkeypatch, "A", "B", "R", args=("--mode", mode))
    data = record(repo)
    data["crs"][0].update(status="ready", pr=f"{PR}1", pr_draft=False, branch="b/1", order=1)
    data["crs"][1].update(status="working", branch="b/2", order=2)
    data["crs"][2].update(kind="release", status="queued", after=[a, b], order=3)
    write_record(repo, data)
    assert chantier("park", b, *WAITS, "--epoch", 1)[0] == 0
    code, _, err = chantier("take", rel, "--epoch", 1)
    assert code != 0
    assert f"{rel} waits for " in err and f"{b} parked: it starts once each is {ends}" in err
