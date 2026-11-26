"""A stack batch keeps its shape: the criterion `shape_blockers`, the guard of a per-CR
`ready-to-merge` ask, the flag `--outside-stack`, and the shape lines."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from batch_helpers import open_batch, record, write_record
from conftest import Chantier

from chantier.commands.help import load_topics
from chantier.core.errors import EXIT_PRECONDITION, EXIT_USAGE, ChantierError
from chantier.core.records import BatchRecord, CrEntry
from chantier.rails_release import check_shape
from chantier.stack_shape import shape_blockers, shape_line

PR = "https://github.com/o/r/pull/"
RULES = "shape: stack: read `$CHANTIER help stack` now and after each compaction"


def cr(n: int, **kw: Any) -> CrEntry:
    fields: dict[str, Any] = {"status": "ready", "pr": f"{PR}{n}", "order": n}
    return CrEntry(id=f"CR-{n}", **{**fields, **kw})


def batch(crs: list[CrEntry], **kw: Any) -> BatchRecord:
    return BatchRecord(**{"id": "batch-01", "mode": "stack", "crs": crs, **kw})


MERGED = {"status": "merged", "stacked": True}


@pytest.mark.parametrize(
    ("crs", "asking", "names"),
    [
        ([cr(1)], "CR-1", []),
        ([cr(1), cr(2, pr=None)], "CR-1", []),
        ([cr(1), cr(2)], "CR-1", ["CR-2"]),
        ([cr(1), cr(2)], None, ["CR-1", "CR-2"]),
        ([cr(1, stacked=True)], "CR-1", ["CR-1"]),
        ([cr(1, pr=None), cr(2, kind="release")], "CR-1", ["CR-2"]),
        ([cr(1, **MERGED), cr(2, **MERGED), cr(3)], "CR-3", []),
        ([cr(1, **MERGED), cr(3), cr(4)], "CR-3", ["CR-4"]),
        ([cr(1), cr(2, status="cancelled", stacked=True)], "CR-1", []),
        ([cr(1), cr(2, kind="fix")], "CR-1", []),
        ([cr(1), cr(2, held="O-1")], "CR-1", []),
        ([cr(1), cr(2, held="O-1", stacked=True)], "CR-1", []),
    ],
)
def test_the_blockers_of_a_per_cr_ask(
    crs: list[CrEntry], asking: str | None, names: list[str]
) -> None:
    assert [c.id for c in shape_blockers(batch(crs), asking)] == names


def refusal(blockers: str, nxt: str, cr_id: str = "CR-1") -> str:
    return (
        f"refused: batch-01 is a stack and {cr_id} is not alone (open: {blockers}): its readiness "
        f"goes up with the stack's (next: {nxt}; then the stack driver's hand-back and "
        '`asks "stack-ready-to-merge …"`); a CR not in the stack\'s chain asks alone; '
        f'`--outside-stack "O-<k>: <why>"` records this ask on an open order on {cr_id} that '
        "carries the user's word"
    )


WAIT = "parallel until 2 ready with a PR"
BEHIND = [cr(1, status="working", pr=PR + "1"), cr(2)]
REFUSED = [
    ([cr(1), cr(2)], "ready-to-merge CR-1 x", ("CR-2", "take stack")),
    ([cr(1), cr(2, kind="release")], "ready-to-merge CR-2 x", ("CR-1", WAIT)),
    ([cr(1, stacked=True), cr(2)], "ready-to-merge CR-2 x", ("CR-1 (stacked)", "take stack")),
    (BEHIND, "ready-to-merge CR-2 x", ("CR-1", WAIT)),
    ([cr(1, status="blocked"), cr(2)], "ready-to-merge CR-2 x", ("CR-1", WAIT)),
]
ACCEPTED = [
    ([cr(1), cr(2, kind="fix")], "ready-to-merge CR-2 x"),
    ([cr(1), cr(2, held="O-1")], "ready-to-merge CR-2 x"),
    ([cr(1, status="blocked", held="O-1"), cr(2)], "ready-to-merge CR-2 x"),
    ([cr(1), cr(2)], "pr-in-draft CR-1 x"),
    ([cr(1), cr(2)], "ready-locally CR-1"),
    ([cr(1), cr(2)], "stack-ready-to-merge https://x CR-1=https://y"),
    ([cr(1), cr(2)], "question CR-1 which?"),
    ([cr(1), cr(2, pr=None)], "ready-to-merge CR-1 x"),
    ([cr(1)], "ready-to-merge CR-1 x"),
    ([cr(1), cr(2), cr(3, kind="release", pr=None)], "ready-to-merge CR-9 x"),
]


@pytest.mark.parametrize(("crs", "text", "why"), REFUSED)
def test_the_guard_refuses_a_cr_that_is_not_alone(
    crs: list[CrEntry], text: str, why: tuple[str, str]
) -> None:
    cr_id = text.split()[1]
    with pytest.raises(ChantierError) as e:
        check_shape(batch(crs), text, None)
    assert (e.value.code, str(e.value)) == (EXIT_PRECONDITION, refusal(*why, cr_id=cr_id))


@pytest.mark.parametrize(("crs", "text"), ACCEPTED)
def test_the_guard_lets_the_other_asks_through(crs: list[CrEntry], text: str) -> None:
    assert check_shape(batch(crs), text, None) is None
    with pytest.raises(ChantierError) as e:  # nothing to force: the flag is a usage error
        check_shape(batch(crs), text, "O-1: the user's word")
    assert e.value.code == EXIT_USAGE and "only for a per-CR" in str(e.value)


@pytest.mark.parametrize("mode", ["parallel", "series"])
def test_only_a_stack_batch_is_guarded(mode: str) -> None:
    assert check_shape(batch([cr(1), cr(2)], mode=mode), "ready-to-merge CR-1 x", None) is None


def start_of(line: list[str]) -> str:
    assert line[1:] == [RULES]
    return line[0]


def shape(next_: str, driver: str, native: str, alone: str) -> str:
    return (
        f"shape stack: next {next_}; stack driver: {driver}; native stack: {native}; "
        f"alone asks: {alone}"
    )


@pytest.mark.parametrize(
    ("crs", "extra", "line"),
    [
        ([], {}, shape(WAIT, "none", "absent", "allowed")),
        ([cr(1, pr=None)], {}, shape(WAIT, "none", "absent", "allowed")),
        ([cr(1)], {}, shape(WAIT, "none", "absent", "allowed for CR-1 only")),
        ([cr(1), cr(2)], {}, shape("take stack", "none", "absent", "refused")),
        (
            [cr(1, **MERGED), cr(2, **MERGED), cr(3), cr(4)],
            {},
            shape("take stack", "none", "absent", "refused"),
        ),
        (
            [cr(1, stacked=True), cr(2, stacked=True)],
            {},
            shape(
                "take stack at the next ready CR or merge",
                "none",
                "present (CR-1, CR-2)",
                "refused",
            ),
        ),
        (
            [cr(1, stacked=True), cr(2)],
            {},
            shape("take stack", "none", "present (CR-1)", "refused"),
        ),
        (
            [cr(1), cr(2, kind="fix"), cr(3, held="O-1")],
            {},
            shape(WAIT, "none", "absent", "allowed for CR-1 only"),
        ),
        (
            [cr(1)],
            {"stack_agent": "agent-s"},
            shape("note to the stack driver", "agent-s", "absent", "allowed for CR-1 only"),
        ),
        (
            [cr(1, **MERGED), cr(2, stacked=True, status="working")],
            {},
            shape(
                "take stack at the next ready CR or merge",
                "none",
                "present (CR-2)",
                "refused",
            ),
        ),
    ],
)
def test_the_shape_line(crs: list[CrEntry], extra: dict[str, Any], line: str) -> None:
    assert start_of(shape_line(batch(crs, **extra))) == line


def test_the_shape_line_is_for_a_stack_and_names_a_topic_that_exists() -> None:
    assert shape_line(batch([])) == [shape(WAIT, "none", "absent", "allowed"), RULES]
    assert "stack" in load_topics()
    assert shape_line(batch([cr(1), cr(2)], mode="parallel")) == []
    assert shape_line(batch([cr(1), cr(2)], mode="series")) == []


def put(repo: Path, rows: list[dict[str, Any]]) -> None:
    data = record(repo)
    for c, fields in zip(data["crs"], rows, strict=True):
        c.update(fields)
    write_record(repo, data)


def test_the_flag_through_the_real_command(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    a, b, _ = open_batch(repo, chantier, monkeypatch, "A", "B", "C", args=("--mode", "stack"))
    ready = {"status": "ready", "stacked": False}
    put(repo, [{**ready, "pr": f"{PR}1"}, {**ready, "pr": f"{PR}2"}, {"status": "queued"}])
    word = "the user's word"
    for cr_id, note in (("-", word), (b, word), (a, "shape: through the stack"), (a, word)):
        assert chantier("order", "note", cr_id, "--note", note)[0] == 0
    assert chantier("order", "done", "O-4", "--epoch", 1)[0] == 0
    assert chantier("order", "note", a, "--note", word)[0] == 0  # O-5, open
    ask = f"ready-to-merge {a} {PR}1"
    code, out, err = chantier("asks", ask)
    assert (code, out) == (EXIT_PRECONDITION, []) and "is not alone (open: " in err
    assert record(repo)["asks"] == []
    for reason in ("", word, "O-99: x", "O-1: x", "O-2: x", "O-3: x", "O-4: x", "O-5:", "O-5"):
        code, out, err = chantier("asks", ask, "--outside-stack", reason)
        assert code == EXIT_USAGE and "--outside-stack needs a reason" in err, reason
    assert chantier("asks", f"pr-in-draft {a} x", "--outside-stack", "O-5: w")[0] == EXIT_USAGE
    code, out, err = chantier("asks", ask, "--outside-stack", f"O-5: {word}")
    assert code == 0, err
    assert out[0].endswith(f"{ask} outside the stack: O-5: {word}")
    log = (repo / ".agents" / "changes" / "4-batch" / "events.jsonl").read_text("utf-8")
    sent = [e for e in map(json.loads, log.splitlines()) if e.get("outside_stack")]
    assert [e["outside_stack"] for e in sent] == [f"O-5: {word}"]
    assert chantier("asks", f"pr-in-draft {a} x")[0] == 0
