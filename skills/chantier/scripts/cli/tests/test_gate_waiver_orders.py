"""`order waive`: the long gate waived, recorded per CR; what it refuses, what it records."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from batch_helpers import open_batch, prepared, record
from conftest import Chantier

from chantier.core.errors import EXIT_USAGE
from chantier.core.records import BatchRecord
from chantier.stacks import stack_top, validated_ids, validating_cr, waived_gate


def cr_of(repo: Path, cr: str) -> dict[str, Any]:
    return next(c for c in record(repo)["crs"] if c["id"] == cr)


def waiver_of(repo: Path, cr: str) -> dict[str, Any] | None:
    found: dict[str, Any] | None = cr_of(repo, cr).get("gate_waiver")
    return found


@pytest.fixture
def stack(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, Chantier, list[str]]:
    ids = open_batch(repo, chantier, monkeypatch, "One", "Two", "Three", args=("--mode", "stack"))
    return repo, chantier, ids


@pytest.mark.parametrize("mode", ["parallel", "series"])
def test_a_stack_waiver_is_refused_outside_stack_mode(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    ids = open_batch(repo, chantier, monkeypatch, "One", "Two", args=("--mode", mode))
    code, _, err = chantier("order", "waive", "stack", "--note", "the user said so")
    assert code != 0 and "not a stack" in err
    assert all(waiver_of(repo, i) is None for i in ids)


@pytest.mark.parametrize(
    ("extra", "words"),
    [
        ((), "--follow-up"),
        (("--follow-up", "no-such-folder"), "no-such-folder"),
    ],
)
def test_a_cr_waiver_needs_an_existing_backlog_folder(
    stack: tuple[Path, Chantier, list[str]], extra: tuple[str, ...], words: str
) -> None:
    repo, chantier, (one, _, _) = stack
    code, _, err = chantier("order", "waive", one, "--note", "the user said so", *extra)
    assert code != 0 and words in err
    assert waiver_of(repo, one) is None


def test_a_waiver_needs_a_note_and_follow_up_goes_with_waive_alone(
    stack: tuple[Path, Chantier, list[str]],
) -> None:
    repo, chantier, (one, _, _) = stack
    folder = prepared(repo, chantier, "Follow up").name
    assert chantier("order", "waive", one, "--follow-up", folder)[0] == EXIT_USAGE
    code, _, err = chantier("order", "note", "--note", "x", "--follow-up", folder)
    assert code == EXIT_USAGE and "--follow-up" in err
    assert chantier("order", "waive", "--note", "x")[0] == EXIT_USAGE


def test_a_cr_waiver_is_recorded_with_its_order_and_follow_up(
    stack: tuple[Path, Chantier, list[str]],
) -> None:
    repo, chantier, (one, two, _) = stack
    folder = prepared(repo, chantier, "Follow up").name
    code, out, err = chantier("order", "waive", one, "--note", "batch-17", "--follow-up", folder)
    assert code == 0, err
    assert f"follow-up {folder}" in "\n".join(out)
    assert waiver_of(repo, one) == {
        "order": "O-1",
        "scope": "cr",
        "note": "batch-17",
        "follow_up": folder,
    }
    assert waiver_of(repo, two) is None
    assert chantier("order", "waive", one, "--note", "-")[0] == 0
    assert waiver_of(repo, one) is None


def test_a_stack_waiver_covers_all_but_the_top_and_moves_up_with_a_new_cr(
    stack: tuple[Path, Chantier, list[str]],
) -> None:
    repo, chantier, (one, two, three) = stack
    assert chantier("order", "waive", "stack", "--note", "one gate on the top")[0] == 0
    for cr in (one, two, three):
        assert (waiver_of(repo, cr) or {}).get("order") == "O-1"
    _, shown, _ = chantier("handoff", one)
    assert any(
        ln.startswith(f"gate: waived (O-1, stack): run no long gate; validated by {three}")
        for ln in shown
    )
    _, top, _ = chantier("handoff", three)
    assert any(ln.startswith("gate: this CR's long gate validates the stack") for ln in top)
    new = prepared(repo, chantier, "Four")
    assert chantier("order", "add", "--note", str(new))[0] == 0
    four = record(repo)["crs"][-1]["id"]
    assert (waiver_of(repo, four) or {}).get("order") == "O-1"
    _, again, _ = chantier("handoff", three)
    assert any(f"validated by {four}" in ln for ln in again if ln.startswith("gate: waived"))
    assert any(ln.startswith("gate: this CR's") for ln in chantier("handoff", four)[1])


def test_withdrawing_a_stack_waiver_clears_every_cr(
    stack: tuple[Path, Chantier, list[str]],
) -> None:
    repo, chantier, ids = stack
    assert chantier("order", "waive", "stack", "--note", "one gate on the top")[0] == 0
    assert chantier("order", "waive", "stack", "--note", "-")[0] == 0
    assert all(waiver_of(repo, i) is None for i in ids)
    _, shown, _ = chantier("handoff", ids[0])
    assert not any(ln.startswith("gate:") for ln in shown)


def test_the_derived_top_is_never_covered(stack: tuple[Path, Chantier, list[str]]) -> None:
    repo, chantier, (one, two, three) = stack
    assert chantier("order", "waive", "stack", "--note", "one gate on the top")[0] == 0
    d = BatchRecord.model_validate(record(repo))
    by_id = {c.id: c for c in d.crs}
    top = stack_top(d)
    assert top is by_id[three] and waived_gate(d, top) is None
    assert waived_gate(d, by_id[one]) is not None
    assert (validating_cr(d, by_id[two]) or top).id == three
    assert validated_ids(d, top) == [one, two]


def test_a_cr_cannot_withdraw_a_waiver_of_the_stack_alone(
    stack: tuple[Path, Chantier, list[str]],
) -> None:
    repo, chantier, (one, _, _) = stack
    assert chantier("order", "waive", "stack", "--note", "one gate on the top")[0] == 0
    code, _, err = chantier("order", "waive", one, "--note", "-")
    assert code != 0 and "order waive stack --note -" in err
    assert (waiver_of(repo, one) or {}).get("order") == "O-1"
