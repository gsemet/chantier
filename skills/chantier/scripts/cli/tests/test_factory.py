"""Factory mode: a CR made ready with `triage --ready` joins the open factory batch on its own;
`order factory` switches it; a release joining turns it off; `status` and the files say it."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from batch_helpers import (
    changes,
    events,
    host,
    open_batch,
    open_factory,
    prepared,
    record,
    write_record,
)
from conftest import Chantier

from chantier.board.state import project_line, project_state
from chantier.core.errors import EXIT_PRECONDITION, EXIT_USAGE
from chantier.core.repo import Repo
from chantier.lifecycle.backlog import move_item


def inbox_cr(repo: Path, chantier: Chantier, title: str, bare: bool = False) -> Path:
    """A CR of the inbox, with its specification, or with only its request when `bare`."""
    if not bare:
        return prepared(repo, chantier, title)
    return repo / chantier("file", title)[1][0].removeprefix("filed ").split(";")[0]


def orders(repo: Path) -> list[dict[str, Any]]:
    return list(record(repo)["orders"])


def added(repo: Path) -> int:
    return len([e for e in events(repo) if e["kind"] == "add"])


@pytest.mark.parametrize(
    ("state", "bare"),
    [("running", False), ("paused", False), ("paused", True), ("plain", False), ("none", False)],
)
def test_triage_ready_joins_a_factory_batch_on_its_own(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch, state: str, bare: bool
) -> None:
    host(monkeypatch)
    if state == "running":
        open_factory(repo, chantier, monkeypatch, "--factory", str(prepared(repo, chantier, "S")))
    elif state == "paused":
        open_factory(repo, chantier, monkeypatch)
    elif state == "plain":
        open_batch(repo, chantier, monkeypatch, "Plain")
    before = len(record(repo)["crs"]) if state != "none" else 0
    folder = inbox_cr(repo, chantier, "Joiner", bare)
    code, out, err = chantier("triage", str(folder), "--ready")
    assert code == 0, err
    waits = changes(repo) / "3-ready" / folder.name
    assert out[0].startswith("triaged ")
    if state in ("none", "plain"):  # no factory: the CR waits in 3-ready, nothing is recorded
        assert len(out) == 1 and waits.is_dir()
        assert state == "none" or orders(repo) == []
        return
    batch = record(repo)
    assert not waits.exists() and len(batch["crs"]) == before + 1
    new = batch["crs"][-1]["id"]
    assert batch["crs"][-1]["status"] == "queued"
    assert [o["kind"] for o in batch["orders"]] == ["add"]
    order = [e for e in events(repo) if e["kind"] == "order"][-1]
    assert order["origin"] == "triage --ready" and order["order_kind"] == "add"
    assert out[1].startswith("[chief-of-staff→foreman] order O-1: add ")
    assert any(x.startswith(f"added {new}, queued") for x in out)
    assert out[-1].startswith(f"factory {batch['id']}: {new} joined on its own")
    assert any("stays paused" in x for x in out) == (state == "paused")


@pytest.mark.parametrize("cause", ["slug", "release"])
def test_a_refused_join_leaves_the_cr_in_3_ready(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch, cause: str
) -> None:
    open_factory(repo, chantier, monkeypatch)
    if cause == "release":
        release = prepared(repo, chantier, "Release")
        assert chantier("order", "add", "--note", str(release), "--release")[0] == 0
        crs = [{**c, "status": "working"} for c in record(repo)["crs"]]
        write_record(repo, {**record(repo), "crs": crs, "factory": True})
    folder = prepared(repo, chantier, "Refused")
    if cause == "slug":
        (folder / "depends.json").write_text('{"after": ["nope"]}', encoding="utf-8")
    kept = (len(orders(repo)), added(repo))
    code, out, err = chantier("triage", str(folder), "--ready")
    assert code == EXIT_PRECONDITION and out[0].startswith("triaged ")
    assert "not joined batch-01" in err and "order add --note" in err
    assert (changes(repo) / "3-ready" / folder.name).is_dir()
    assert (len(orders(repo)), added(repo)) == kept


def test_only_triage_ready_joins_and_in_a_stack_each_joins_on_top(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    open_factory(repo, chantier, monkeypatch, "--mode", "stack")
    first, second, third = (prepared(repo, chantier, t) for t in ("One", "Two", "Three"))
    out = chantier("triage", str(first), "--priority", "P2")[1]
    assert chantier("triage", str(second), "--inbox")[0] == EXIT_PRECONDITION  # already there
    ready = move_item(Repo.find(), str(third), "3-ready")  # the board's move joins nothing
    assert out[0].startswith("triaged ") and ready[0].startswith("triaged ")
    assert record(repo)["crs"] == [] and orders(repo) == []
    for folder in (changes(repo) / "2-backlog" / "P2" / first.name, second):
        assert chantier("triage", str(folder), "--ready")[0] == 0
    assert [c["order"] for c in record(repo)["crs"]] == [1, 2]  # the second joined above


def test_order_factory_switches_the_batch_and_its_brief(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    batch = open_factory(repo, chantier, monkeypatch)
    brief = changes(repo) / "4-batch" / "brief.md"
    code, out, err = chantier("order", "factory", "off", "--note", "stop it")
    assert code == 0, err
    assert record(repo)["factory"] is False and "Factory: off." in brief.read_text("utf-8")
    assert any(x.startswith(f"no CR ever joined {batch}: next: offer the close") for x in out)
    assert any(x.endswith("no retro") for x in out)
    done = orders(repo)[-1]
    assert done["kind"] == "factory" and done["cr"] == "-" and done["done"] and done["applied"]
    assert [e["kind"] for e in events(repo)].count("factory") == 1
    for words in (("off", "--note", "again"), ("maybe", "--note", "x")):
        code, _, err = chantier("order", "factory", *words)
        assert code in (EXIT_PRECONDITION, EXIT_USAGE) and err.startswith("error")
    waiting = inbox_cr(repo, chantier, "Waiting")
    assert chantier("triage", str(waiting), "--ready")[0] == 0  # off: it joins nothing
    code, out, err = chantier("order", "factory", "on", "--note", "again")
    assert code == 0 and record(repo)["factory"] is True, err
    assert "Factory: on." in brief.read_text("utf-8")
    assert any(x.startswith("3-ready holds 1 CRs not joined") and waiting.name in x for x in out)
    assert chantier("order", "factory", "on", "--note", "twice")[0] == EXIT_PRECONDITION
    assert chantier("order", "factory", "on")[0] == EXIT_USAGE
    assert chantier("order", "add", "--note", str(changes(repo) / "3-ready" / waiting.name))[0] == 0
    assert (
        chantier("order", "drop", record(repo)["crs"][0]["id"], "--note", "trash")[0] == 0
    )  # every CR ended: the batch pauses
    code, out, _ = chantier("order", "factory", "off", "--note", "done")
    assert code == 0 and any("next: the retro (with its critic)" in x for x in out)


def test_a_release_joining_turns_the_factory_off(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    open_factory(repo, chantier, monkeypatch)
    release = prepared(repo, chantier, "Release")
    code, out, err = chantier("order", "add", "--note", str(release), "--release")
    assert code == 0, err
    cr = record(repo)["crs"][0]["id"]
    assert record(repo)["factory"] is False
    assert any(x.startswith(f"factory off: the release CR {cr} joined") for x in out)
    assert "Factory: off." in (changes(repo) / "4-batch" / "brief.md").read_text("utf-8")
    code, _, err = chantier("order", "factory", "on", "--note", "again")
    assert code == EXIT_PRECONDITION and "a release CR is in batch-01" in err


@pytest.mark.parametrize("on", [True, False])
def test_status_says_a_factory_and_the_ready_cr_not_joined(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch, on: bool
) -> None:
    batch = open_factory(repo, chantier, monkeypatch)
    if not on:
        assert chantier("order", "factory", "off", "--note", "no")[0] == 0
    waiting = inbox_cr(repo, chantier, "Waiting")
    move_item(Repo.find(), str(waiting), "3-ready")  # the board's move: nothing joins
    status = chantier("status")[1]
    line = next(x for x in status if x.startswith(batch))
    assert (" factory: on " in line) == on
    held = [x for x in status if x.startswith("factory: 3-ready holds 1 CRs not joined")]
    assert bool(held) == on
    if held:
        assert waiting.name in held[0] and "a release CR excepted" in held[0]
    view = json.loads((changes(repo) / "4-batch" / "STATUS.json").read_text("utf-8"))
    assert view["factory"] is on
    header = (changes(repo) / "4-batch" / "STATUS.md").read_text("utf-8").splitlines()[2]
    assert (" · factory: on · " in header) == on


@pytest.mark.parametrize("on", [True, False])
def test_the_board_state_carries_the_factory(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch, on: bool
) -> None:
    open_factory(repo, chantier, monkeypatch)
    if not on:
        assert chantier("order", "factory", "off", "--note", "no")[0] == 0
    state = project_state("proj", Repo.find(), False, None)
    assert state["batch"]["factory"] is on
    assert project_line("proj", state)["batch"]["factory"] is on
