"""`order mode --note parallel|series|stack`: any mode to any other, on a prepared record."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from batch_helpers import changes, open_batch, record, write_record
from conftest import Chantier

from chantier.core.errors import EXIT_USAGE

MODES = ("parallel", "series", "stack")


def events(repo: Path) -> Path:
    return changes(repo) / "4-batch" / "events.jsonl"


def prepare(
    repo: Path, ids: list[str], status: dict[str, str], ready_order: list[str] | None = None
) -> None:
    """Give the CRs a status, and `handback ready` events in the order named."""
    data = record(repo)
    for c in data["crs"]:
        c["status"] = status[c["id"]]
    write_record(repo, data)
    lines = [
        {
            "t": "2026-01-01T00:00:00Z",
            "actor": "driver",
            "kind": "handback",
            "cr": cr,
            "result": "ready",
        }
        for cr in ready_order or []
    ]
    with events(repo).open("a", encoding="utf-8") as f:
        f.writelines(json.dumps(e) + "\n" for e in lines)


def places(repo: Path) -> dict[str, int]:
    return {c["id"]: c["order"] for c in record(repo)["crs"]}


@pytest.mark.parametrize("mode", MODES)
def test_the_same_mode_and_an_unknown_one_are_refused_and_nothing_is_written(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    open_batch(repo, chantier, monkeypatch, "One", "Two", args=("--mode", mode))
    path = changes(repo) / "4-batch" / "batch.json"
    before = (path.read_bytes(), events(repo).read_bytes())
    code, _, err = chantier("order", "mode", "--note", mode)
    assert code != 0 and f"already a {mode}" in err
    code, _, err = chantier("order", "mode", "--note", "fast")
    assert code == EXIT_USAGE and "parallel|series|stack" in err
    assert (path.read_bytes(), events(repo).read_bytes()) == before


def test_to_a_stack_the_ready_cr_go_first_in_the_order_they_became_ready(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    a, b, c, d, e = open_batch(repo, chantier, monkeypatch, "A", "B", "C", "D", "E")
    status = {a: "queued", b: "ready", c: "ready", d: "working", e: "merged"}
    prepare(repo, [a, b, c, d, e], status, ready_order=[c, b])
    merged_place = places(repo)[e]
    code, out, err = chantier("order", "mode", "--note", "stack")
    assert code == 0, err
    got = places(repo)
    assert sorted(got, key=lambda k: got[k])[:4] == [c, b, a, d] and got[e] == merged_place
    assert f"order: {c} → {b} → {a} → {d}" in " ".join(out)
    mode = [json.loads(x) for x in events(repo).read_text("utf-8").splitlines()][-2:]
    event = next(x for x in mode if x["kind"] == "mode")
    assert event["mode"] == "stack" and event["previous"] == "parallel"
    assert not any(x.get("stacked") for x in record(repo)["crs"])


def test_a_chain_is_kept_when_the_switch_would_put_a_cr_below_its_dependency(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    a, b, c, d, e = open_batch(repo, chantier, monkeypatch, "A", "B", "C", "D", "E")
    status = {a: "queued", b: "ready", c: "ready", d: "working", e: "merged"}
    prepare(repo, [a, b, c, d, e], status, ready_order=[c, b])
    data = record(repo)
    data["crs"][0]["after"] = [d]
    write_record(repo, data)
    assert chantier("order", "mode", "--note", "series")[0] == 0
    got = places(repo)
    assert sorted(got, key=lambda k: got[k])[:4] == [c, b, d, a]


def test_leaving_a_stack_clears_every_place_in_it(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    open_batch(repo, chantier, monkeypatch, "A", "B", args=("--mode", "stack"))
    data = record(repo)
    for c in data["crs"]:
        c["stacked"] = True
    write_record(repo, data)
    code, out, err = chantier("order", "mode", "--note", "parallel")
    assert code == 0, err
    assert not any(c.get("stacked") for c in record(repo)["crs"])
    assert any("forge-stack unstack" in x for x in out) and record(repo)["mode"] == "parallel"
