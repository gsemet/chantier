"""`order hold` of a working CR in a stack, through the real commands: what stands out of the
stack, the forge's stack without it, leaving the stack, the release and the drop."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from batch_helpers import changes, open_batch, record, write_record
from conftest import Chantier
from test_stack_hold import PR, FakeForge

from chantier.core.batch import read_batch, resolve_batch
from chantier.core.records import BatchRecord
from chantier.core.repo import Repo
from chantier.rails import apart_owner, out_of_order
from chantier.stack_words import ready_word
from chantier.stacks import chain, next_merge, start_base, top_cr


def batch_now() -> tuple[Repo, BatchRecord]:
    r = Repo.find()
    return r, read_batch(r, resolve_batch(r, None))


def dependent_stack(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch, forge: FakeForge | None = None
) -> list[str]:
    """CR one ready at the bottom; two working (its PR open); three ready, after two; four ready,
    started on two. Two is then held."""
    ids = open_batch(repo, chantier, monkeypatch, "A", "B", "C", "D", args=("--mode", "stack"))
    data = record(repo)
    rows: list[dict[str, Any]] = data["crs"]
    for i, c in enumerate(rows, 1):
        c.update(
            status="ready",
            pr=f"{PR}{i}",
            pr_draft=False,
            branch=f"b/{i}",
            stacked=True,
            order=i,
            pr_base=("main", "b/1", "b/2", "b/2")[i - 1],
        )
    rows[1]["status"] = "working"
    rows[2]["after"] = [ids[1]]
    rows[3]["start_on"] = "b/2"
    write_record(repo, data)
    if forge is not None:
        monkeypatch.setattr("chantier.commands.forge_stack.gh", forge)
        monkeypatch.setattr("chantier.commands.forge_stack_gh.gh", forge)
    assert chantier("order", "hold", ids[1])[0] == 0
    return ids


def test_a_held_working_cr_and_its_dependent_stand_out_of_the_stack(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    a, b, c, e = dependent_stack(repo, chantier, monkeypatch)
    r, d = batch_now()
    held, dep, other = d.crs[1], d.crs[2], d.crs[3]
    assert held.stacked is False and held.start_on is None
    assert other.start_on is None  # it only started on the held CR's branch
    assert [x.id for x in chain(d)] == [a, e]
    top, merge = top_cr(d), next_merge(d)
    assert top is not None and top.id == e and merge is not None and merge.id == a
    assert out_of_order(d.crs, dep, d.mode) and apart_owner(d.crs, dep, d.mode) is held
    assert start_base(d, dep, r) == "b/2"  # its base is the held CR's branch
    assert ready_word(d, dep, r) == "PR in draft"
    path = changes(repo) / "4-batch" / "batch.json"
    before = path.read_bytes()
    for args, words in [
        (("stack", c), f"{c} waits with held {b} (order O-1): it stays out of the stack until {b}"),
        (("stack", "--out-of-draft", c), f"{c} waits with held {b} (order O-1)"),
        (("stack", b), f"{b} is held out of the stack (order O-1)"),
    ]:
        code, _, err = chantier(*args)
        assert code != 0 and words in err
    assert path.read_bytes() == before


def test_forge_stack_leaves_the_held_pr_and_its_dependents_out_of_the_stack(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    forge = FakeForge({1: "main", 2: "b/1", 3: "b/2", 4: "b/2"}, [1, 2, 3, 4])
    _, b, c, _ = dependent_stack(repo, chantier, monkeypatch, forge)
    code, out, err = chantier("forge-stack", "rebuild")
    assert code == 0, err
    text = "\n".join(out)
    assert f"#3 of {c}, waits with held {b} (order O-1): left out" in text
    assert "#2 base b/1 -> main (held out of the stack)" in text
    assert "foreign" not in text and "#3 base" not in text  # not retargeted, never foreign
    assert forge.bases == {1: "main", 2: "main", 3: "b/2", 4: "b/1"}
    assert forge.stacks[-1]["prs"] == [1, 4]
    forge.stacks[-1]["prs"] = [1, 3, 4]  # the dependent's PR back in the stack
    code, out, _ = chantier("forge-stack", "show")
    assert code != 0 and (
        f"check 2: #3 of {c} waits with held {b} (order O-1): left out of the stack and still in "
        "stack #355" in "\n".join(out)
    )


def test_leaving_a_stack_lets_the_ready_hold_go_and_keeps_the_live_one(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    a, b, c = open_batch(repo, chantier, monkeypatch, "A", "B", "C", args=("--mode", "stack"))
    data = record(repo)
    for i, x in enumerate(data["crs"], 1):
        x.update(status="ready", pr=f"{PR}{i}", pr_draft=False, stacked=True, order=i)
    data["crs"][2]["status"] = "working"
    write_record(repo, data)
    assert chantier("order", "hold", b)[0] == 0  # held from ready
    assert chantier("order", "hold", c)[0] == 0  # held from live
    code, out, err = chantier("order", "mode", "--note", "parallel")
    assert code == 0, err
    assert f"{b}: no longer held (the batch leaves the stack)" in out
    assert f"{c}: still held (order O-2): it was live; only `order unhold {c}` releases it" in out
    rows = record(repo)["crs"]
    assert "held" not in rows[1] and rows[1]["status"] == "ready"
    assert rows[2]["held"] == "O-2" and rows[2]["status"] == "blocked"
    assert rows[2]["blocked_reason"] == "held: order O-2"
    open_ = [x["order"] for x in rows if x["status"] not in {"merged", "cancelled"}]
    assert len(set(open_)) == len(open_) and a


def test_no_release_starts_over_a_held_ready_cr_but_a_working_one_resumes(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    a, b, rel = open_batch(repo, chantier, monkeypatch, "A", "B", "R", args=("--mode", "stack"))
    data = record(repo)
    for i, x in enumerate(data["crs"][:2], 1):
        x.update(status="ready", pr=f"{PR}{i}", pr_draft=False, stacked=True, order=i)
    data["crs"][2].update(kind="release", order=3)
    write_record(repo, data)
    assert chantier("order", "hold", b)[0] == 0
    path = changes(repo) / "4-batch" / "batch.json"
    before = path.read_bytes()
    code, _, err = chantier("take", rel, "--epoch", 1)
    assert code != 0 and f"{rel} waits for {b} held (order O-1)" in err
    assert f"`order unhold {b}` or `order drop {b}` lets it start" in err
    assert path.read_bytes() == before and a
    data = record(repo)
    data["crs"][2]["status"] = "working"  # a release already taken keeps its slot
    write_record(repo, data)
    code, _, err = chantier("take", rel, "--note", "resume: stuck", "--epoch", 1)
    assert code == 0, err


def view(repo: Path, cr_id: str) -> dict[str, Any]:
    path = next(c["path"] for c in record(repo)["crs"] if c["id"] == cr_id)
    shown: dict[str, Any] = json.loads(
        (changes(repo) / path / "STATUS.json").read_text(encoding="utf-8")
    )
    return shown


def test_status_and_the_views_read_held_then_unheld(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    a, b = open_batch(repo, chantier, monkeypatch, "A", "B", args=("--mode", "parallel"))
    data = record(repo)
    data["crs"][0]["status"] = "working"
    data["crs"][1].update(status="working", after=[a])
    write_record(repo, data)
    assert chantier("order", "hold", a)[0] == 0
    _code, out, _ = chantier("status")
    assert (
        f"held: {a} (order O-1), was working, out of the slots: only the user's "
        f"`order unhold {a}` brings it back; waiting with it: {b}" in out
    )
    shown = view(repo, a)
    assert (shown["step"], shown["phase"], shown["severity"]) == ("Held", "held (order O-1)", "red")
    assert shown["now"] == "Held by the user (order O-1): out of the slots."
    assert shown["next"] == "The user's `order unhold`, through the Chief of Staff."
    assert chantier("order", "unhold", a)[0] == 0
    shown = view(repo, a)
    assert (shown["step"], shown["phase"], shown["severity"]) == ("Unheld", "to take back", "red")
    assert shown["now"] == "Unheld (order O-2): back on top, to take back."
    assert shown["next"] == "A Driver takes it back, before any queued CR."
    _code, out, _ = chantier("status")
    assert not any(x.startswith("held:") for x in out)
    row = next(x for x in out if x.startswith(f"{a} "))
    assert "blocked: unheld: order O-2" in row
