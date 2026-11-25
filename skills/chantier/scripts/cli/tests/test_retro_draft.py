"""`chantier retro draft`: the retro's draft points from prepared events, each with the three
fields left for the author; the window of the current pause; the cost lines; nothing written
without `--write`; `--write` appends after the author's text once. No git, no network, no
transcript."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from batch_helpers import changes
from conftest import Chantier

from chantier.commands import retro as retro_command
from chantier.commands.retro_draft import END_LINE, FIELDS, OPEN_LINE, draft_points
from chantier.core.errors import EXIT_PRECONDITION, ChantierError
from chantier.core.records import EventRecord

H1, H2 = "abc1234" + "0" * 33, "def5678" + "0" * 33
LONG = "x" * 170


def ev(kind: str, cr: str | None = "CR-1", **kw: Any) -> EventRecord:
    return EventRecord(t="2026-11-15T10:00:00Z", actor="driver", kind=kind, cr=cr, **kw)


def take(note: str | None = None, cr: str = "CR-1") -> EventRecord:
    return ev("take", cr, restart=True, note=note)


def gate(result: str, head: str) -> EventRecord:
    return ev("gate", result=result, head=head, name="scenario", command="just scenario")


def costs(*usd: float) -> dict[str, float]:
    return {f"CR-{n}": v for n, v in enumerate(usd, start=1)}


def crs_seen(n: int) -> list[EventRecord]:
    return [ev("note", f"CR-{i}", note="hi") for i in range(1, n + 1)]


# (id, the events, the cost map, the problem texts whole)
CASES: list[Any] = [
    (
        "asks",
        [ev("ask", ask="A-1", text="merge?"), ev("ask", None, ask="A-2", text=LONG)],
        None,
        [
            "ask A-1 to the user on CR-1: merge? (events 1)",
            f"ask A-2 to the user: {'x' * 160}… (events 2)",
        ],
    ),
    (
        "refusals and a block",
        [
            ev("note", note="refused: git push -> denied"),
            ev("note", "CR-2", note="refused: git push -> denied"),
            ev("handback", "CR-3", result="blocked", note="refused rm -rf"),
            ev("handback", "CR-4", result="blocked", note="no spec"),
        ],
        None,
        [
            "refused on CR-1, CR-2: git push -> denied (2 times) (events 1, 2)",
            "refused on CR-3: rm -rf (1 time) (events 3)",
            "CR-4 handed back blocked: no spec (events 4)",
        ],
    ),
    (
        "Driver restarts",
        [take("first"), ev("take"), take("second")],
        None,
        ["CR-1: 2 Driver restarts (last note: second) (events 1, 3)"],
    ),
    (
        "red gates",
        [gate("fail", H1), gate("fail", H2), gate("pass", H2), gate("stopped", H2)],
        None,
        ["CR-1: long gate `scenario` failed 2 times at abc1234, def5678 (events 1, 2)"],
    ),
    (
        "cost outlier",
        crs_seen(4),
        costs(1.0, 1.0, 6.0, 2.0),
        ["CR-3: $6.00, 4.0 times the median $1.50 of the window's 4 CRs (events 3)"],
    ),
    ("cost of 2 CRs", crs_seen(2), costs(1.0, 9.0), []),
    ("cost with no outlier", crs_seen(3), costs(1.0, 1.5, 1.9), []),
    ("nothing", [ev("note", note="fine")], None, []),
]


@pytest.mark.parametrize(
    ("events", "spent", "texts"), [c[1:] for c in CASES], ids=[c[0] for c in CASES]
)
def test_points_are_drafted_whole_from_the_events(
    events: list[EventRecord], spent: dict[str, float] | None, texts: list[str]
) -> None:
    points = draft_points(list(enumerate(events, start=1)), spent)
    assert [p.problem() for p in points] == texts


# the command, on a prepared record


def put(events: list[dict[str, Any]], repo: Path, status: str = "paused") -> Path:
    folder = changes(repo) / "4-batch"
    folder.mkdir(parents=True, exist_ok=True)
    rows = [
        {"id": f"CR-{n}", "order": n, "path": f"4-batch/2-actives/{n}-s", "status": "working"}
        for n in (1, 2, 3)
    ]
    data = {"id": "batch-01", "status": status, "slots": 4, "foreman_epoch": 1, "crs": rows}
    (folder / "batch.json").write_text(json.dumps(data), encoding="utf-8")
    lines = [{"t": "2026-11-15T10:00:00Z", "actor": "driver", **e} for e in events]
    (folder / "events.jsonl").write_text(
        "".join(json.dumps(e) + "\n" for e in lines), encoding="utf-8"
    )
    return folder


PAUSE = {"kind": "pause", "trigger": "x"}
FAIL = {"kind": "gate", "cr": "CR-1", "result": "fail", "head": H1, "name": "scenario"}
STORY = [FAIL, PAUSE, {**FAIL, "cr": "CR-2"}, PAUSE, {**FAIL, "cr": "CR-3"}, PAUSE]


def run(chantier: Chantier, *args: object) -> tuple[int, list[str], str]:
    return chantier.bare("retro", "draft", "--batch", "batch-01", *args)  # type: ignore[attr-defined, no-any-return]


@pytest.fixture
def no_cost(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*_: object) -> list[dict[str, Any]]:
        raise ChantierError("no Foreman transcript recorded: the Foreman runs x")

    monkeypatch.setattr(retro_command, "batch_rows", refuse)


@pytest.mark.usefixtures("no_cost")
@pytest.mark.parametrize(
    ("status", "since", "want"),
    [
        ("paused", (), ("events 5..6, CRs CR-3", "CR-3")),
        ("running", (), ("events 7..7, CRs none", None)),
        ("paused", ("--since", 0), ("events 1..6, CRs CR-1, CR-2, CR-3", "CR-1")),
    ],
)
def test_the_window_is_the_current_pause_unless_since_says(
    repo: Path,
    chantier: Chantier,
    status: str,
    since: tuple[object, ...],
    want: tuple[str, str | None],
) -> None:
    first, crs = want
    put([*STORY, *([{"kind": "reopen"}] if status == "running" else [])], repo, status)
    code, out, err = run(chantier, "--epoch", 1, *since)
    assert code == 0, err
    assert out[0].startswith(f"retro draft: batch-01, {first} (")
    assert out[1] == "cost: not read (no Foreman transcript recorded: the Foreman runs x)"
    assert out[2] == OPEN_LINE and END_LINE in out
    assert out[-1].startswith("next: judge each point")
    if crs:
        point = next(x for x in out if x.startswith("- [<tag>] "))
        assert f"{crs}: long gate `scenario` failed" in point
        i = out.index(point)
        assert tuple(out[i + 1 : i + 4]) == FIELDS
    else:
        assert (
            "- no ask, refusal, block, Driver restart, red gate or cost outlier in events 7..7"
            in out
        )


@pytest.mark.parametrize("since", [-1, 7])
def test_a_bad_since_is_refused(repo: Path, chantier: Chantier, since: int) -> None:
    put(STORY, repo)
    code, _, err = run(chantier, "--epoch", 1, "--since", since)
    assert code == 1
    assert "retro draft --since 0" in err


def test_the_cost_lines(repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch) -> None:
    put([{"kind": "note", "cr": f"CR-{n}", "note": "x"} for n in (1, 2, 3)], repo)
    rows = [
        {"agent": f"a{n}", "calls": 1, "usd": usd, "description": f"CR-{n} work"}
        for n, usd in ((1, 1.0), (2, 1.0), (3, 5.0))
    ]
    monkeypatch.setattr(retro_command, "batch_rows", lambda *_: rows)
    out = run(chantier, "--epoch", 1)[1]
    assert not any(x.startswith("cost:") for x in out)
    assert any("CR-3: $5.00, 5.0 times the median $1.00 of the window's 3 CRs" in x for x in out)
    priced = [*rows, {"agent": "b", "calls": 2, "usd": 0.0, "unpriced": {"m-x": 2}}]
    monkeypatch.setattr(retro_command, "batch_rows", lambda *_: priced)
    out = run(chantier, "--epoch", 1)[1]
    assert out[1] == "cost: not all priced (2 calls of m-x not priced); no outlier judged"
    assert not any("times the median" in x for x in out)


def planning(repo: Path) -> dict[str, bytes]:
    root = changes(repo)
    return {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file() and not p.name.startswith(".")
    }


@pytest.mark.parametrize("retro", [None, b"## Mine\n"])
def test_without_write_nothing_is_written(
    repo: Path, chantier: Chantier, no_cost: None, retro: bytes | None
) -> None:
    folder = put(STORY, repo)
    if retro is not None:
        (folder / "retro.md").write_bytes(retro)
    before = planning(repo)
    assert run(chantier, "--epoch", 1)[0] == 0
    assert planning(repo) == before


@pytest.mark.parametrize(
    ("author", "sep"),
    [(None, b""), (b"", b""), (b"## Mine\n\n- a\n\n", b""), (b"## Mine\n\n- a", b"\n\n")],
    ids=["missing", "empty", "blank line", "no final newline"],
)
def test_write_appends_after_the_authors_text_once(
    repo: Path, chantier: Chantier, no_cost: None, author: bytes | None, sep: bytes
) -> None:
    folder = put(STORY, repo)
    path = folder / "retro.md"
    if author is not None:
        path.write_bytes(author)
    before = {k: v for k, v in planning(repo).items() if k != "4-batch/retro.md"}
    code, out, err = run(chantier, "--write", "--epoch", 1)
    assert code == 0, err
    original = author or b""
    assert (
        out[-1]
        == f"written: 4-batch/retro.md (1 points appended after {len(original)} bytes of your text)"
    )
    data = path.read_bytes()
    rest = data[len(original) + len(sep) :]
    assert data.startswith(original + sep) and rest.startswith(OPEN_LINE.encode())
    assert data.count(OPEN_LINE.encode()) == 1 and END_LINE.encode() in rest
    lines = rest.decode().splitlines()
    assert lines[3].startswith("- [<tag>] CR-3: long gate") and tuple(lines[4:7]) == FIELDS
    assert {k: v for k, v in planning(repo).items() if k != "4-batch/retro.md"} == before
    code, _, err = run(chantier, "--write", "--epoch", 1)
    assert code == EXIT_PRECONDITION and "retro draft --epoch 1" in err
    assert path.read_bytes() == data


def test_a_draft_section_with_author_text_after_it_is_left_whole(
    repo: Path, chantier: Chantier, no_cost: None
) -> None:
    path = put(STORY, repo) / "retro.md"
    path.write_bytes(f"{OPEN_LINE}\n- [x] judged\n{END_LINE}\n\n## After\n".encode())
    data = path.read_bytes()
    assert run(chantier, "--write", "--epoch", 1)[0] == EXIT_PRECONDITION
    assert path.read_bytes() == data


@pytest.mark.parametrize(("epoch", "code"), [((), 2), (("--epoch", 2), 3)])
def test_a_missing_or_stale_epoch_is_refused(
    repo: Path, chantier: Chantier, epoch: tuple[object, ...], code: int
) -> None:
    folder = put(STORY, repo)
    assert run(chantier, "--write", *epoch)[0] == code
    assert not (folder / "retro.md").exists()
