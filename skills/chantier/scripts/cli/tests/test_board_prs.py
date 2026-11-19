"""The board's PRs page: its route (`GET /api/projects/<id>/prs`) on a prepared batch, the
judgement of a PR against the record, the forge read's query and its failures.

No test reaches a forge: the route's one seam, `forge_read.read`, is replaced, and the runner's
own failures are tried with `subprocess.run` replaced."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from batch_helpers import changes, open_batch, record, write_record
from conftest import Chantier

from chantier.board import fingerprint, forge_read, journal, prs, routes
from chantier.board.context import Context, Request
from chantier.board.key import KeyFile, key_path, load_or_create
from chantier.board.projects import Projects
from chantier.board.seats import Seats
from chantier.commands.forge_stack_gh import pr_parts
from chantier.commands.forge_stack_shared import NOT_ONE_REPOSITORY
from chantier.core import files
from chantier.core.errors import ChantierError
from chantier.core.repo import Repo

LINK = "https://github.com/acme/demo/pull/{}"
FIRST = 40
HTTP_OK, HTTP_NO_KEY = 200, 401
CRS, TWO_CALLS, THREE_CALLS, NEW_PR = 4, 2, 3, 99
OPEN: dict[str, Any] = {
    "state": "open",
    "conflicting": False,
    "checking": False,
    "checks": "green",
    "base": "main",
    "merged_at": None,
    "closed_at": None,
}


class Board:
    """A served project with four CRs whose PRs are 40 to 43, all ready in the record; the forge
    answers what `forge` holds (a PR number to the fields that differ from `OPEN`)."""

    def __init__(self, repo: Path, ids: list[str], monkeypatch: pytest.MonkeyPatch) -> None:
        self.repo, self.ids = repo, ids
        self.forge: dict[int, dict[str, Any]] = {}
        self.calls: list[list[str]] = []
        self.failure: Exception | None = None
        self.now = 0.0
        found = Repo.find(readonly=True)
        projects = Projects(found, None, [])
        self.key = load_or_create(found)
        self.id = projects.home_id
        self.ctx = Context(projects, KeyFile(key_path(found)), Seats(projects), "t", lambda: None)
        self.ctx.reads = prs.ForgeReads(now=lambda: self.now)
        monkeypatch.setattr(forge_read, "read", self.read)

    def read(self, links: list[str]) -> dict[int, dict[str, Any]]:
        self.calls.append(links)
        if self.failure:
            raise self.failure
        return {n: {**OPEN, **self.forge.get(n, {})} for n in (int(pr_parts(x)[3]) for x in links)}

    def get(self, key: bool = True) -> tuple[int, dict[str, Any]]:
        headers = {"x-chantier-board-key": self.key} if key else {}
        reply = routes.handle(self.ctx, Request("GET", f"/api/projects/{self.id}/prs", {}, headers))
        return reply.status, json.loads(reply.body or b"{}") if reply.status == HTTP_OK else {}

    def rows(self) -> dict[str, dict[str, Any]]:
        return {r["cr"]: r for r in self.get()[1]["rows"]}

    def edit(self, **batch: Any) -> None:
        data = record(self.repo)
        data.update(batch)
        write_record(self.repo, data)

    def planning(self) -> dict[str, bytes]:
        root = changes(self.repo)
        return {p.as_posix(): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


def served(repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch) -> Board:
    """The `board` fixture's body, for the other test files of the page."""
    ids = open_batch(repo, chantier, monkeypatch, "Alpha", "Beta", "Gamma", "Delta")
    data = record(repo)
    for i, c in enumerate(data["crs"]):
        c.update(pr=LINK.format(FIRST + i), pr_draft=False, pr_base="main", status="ready")
        c["branch"] = f"chantier/b/cr-{i}"
    write_record(repo, data)
    return Board(repo, ids, monkeypatch)


@pytest.fixture
def board(repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch) -> Board:
    return served(repo, chantier, monkeypatch)


def test_the_route_needs_the_key_and_with_no_batch_asks_no_forge(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert chantier("file", "Something")[0] == 0
    old = changes(repo) / "5-archives" / "batches"
    old.mkdir(parents=True, exist_ok=True)
    (old / "batch-7.json").write_text(json.dumps({"id": "batch-7"}), encoding="utf-8")
    board = Board(repo, [], monkeypatch)
    assert board.get(key=False)[0] == HTTP_NO_KEY
    status, body = board.get()
    assert (status, body["batch"], body["rows"]) == (HTTP_OK, None, [])
    assert (body["all_done"], body["error"], board.calls) == (False, None, [])


def test_the_four_crs_are_read_in_one_call_and_judged_against_the_record(board: Board) -> None:
    a, b, c, d = board.ids
    board.forge = {
        FIRST + 1: {"conflicting": True},
        FIRST + 2: {"checking": True, "checks": "running"},
        FIRST + 3: {"state": "merged", "base": "chantier/b/cr-0", "merged_at": "t"},
    }
    data = record(board.repo)
    data["crs"][3]["status"] = "working"  # the record does not hold the fourth as ready or merged
    write_record(board.repo, data)
    before = board.planning()
    status, body = board.get()
    rows = board.rows()
    assert status == HTTP_OK and len(board.calls) == 1 and len(board.calls[0]) == CRS
    assert [r["cr"] for r in body["rows"]] == board.ids
    assert [rows[x]["ready_now"] for x in (a, b, c, d)] == [True, False, False, False]
    assert (rows[b]["conflicting"], rows[b]["disagrees"]) == (
        True,
        "ready in the record, conflicting on the forge",
    )
    assert (rows[c]["checking"], rows[c]["disagrees"]) == (True, None)
    assert rows[d]["state"] == "merged" and rows[d]["merged_into"] == {
        "branch": "chantier/b/cr-0",
        "cr": a,
    }
    assert rows[d]["disagrees"] == prs.MERGED_NOT_RECORDED
    after = board.planning()  # a read writes nothing but the signal of the merge it sees
    assert {k: v for k, v in after.items() if not k.endswith("forge-journal.jsonl")} == before
    assert sum(k.endswith("forge-journal.jsonl") for k in after) == 1


def test_a_paused_batch_is_read_as_a_running_one(board: Board) -> None:
    board.edit(status="paused")
    body = board.get()[1]
    assert (body["paused"], len(body["rows"]), len(board.calls)) == (True, 4, 1)


def test_a_cr_not_ready_in_the_record_is_never_ready_now(board: Board) -> None:
    data = record(board.repo)
    data["crs"][0]["status"] = "working"
    write_record(board.repo, data)
    assert board.rows()[board.ids[0]]["ready_now"] is False


def test_two_reads_within_ten_seconds_are_one_forge_call_and_a_new_pr_reads_again(
    board: Board,
) -> None:
    board.get()
    board.now = 9.0
    board.get()
    assert len(board.calls) == 1
    board.now = 10.5
    board.get()
    assert len(board.calls) == TWO_CALLS
    data = record(board.repo)
    data["crs"][3]["pr"] = LINK.format(NEW_PR)
    write_record(board.repo, data)
    board.now = 11.0
    assert board.get()[1]["rows"][3]["number"] == NEW_PR and len(board.calls) == THREE_CALLS


@pytest.mark.parametrize(
    "failure",
    [
        ChantierError("gh: not found on PATH (the user's own `gh` login is needed)"),
        ChantierError("gh api graphql: HTTP 403: rate limited"),
        ChantierError(NOT_ONE_REPOSITORY),
    ],
)
def test_a_forge_failure_shows_its_text_and_keeps_the_last_good_read(
    board: Board, failure: Exception
) -> None:
    first = board.get()[1]
    board.failure, board.now = failure, 11.0
    body = board.get()[1]
    assert body["error"] == str(failure)
    assert body["rows"] == first["rows"] and body["read_at"] == first["read_at"]
    board.now = 22.0
    board.failure = None
    assert board.get()[1]["error"] is None


def test_a_failure_before_any_good_read_invents_no_row(board: Board) -> None:
    board.failure = ChantierError("gh: not found on PATH")
    body = board.get()[1]
    assert (body["rows"], body["read_at"], body["all_done"]) == ([], None, False)
    assert body["error"] == "gh: not found on PATH"


@pytest.mark.parametrize(
    ("states", "done"),
    [
        (["merged"] * 4, True),
        (["merged", "merged", "merged", "closed"], True),
        (["merged", "merged", "open", "closed"], False),
        (["draft", "merged", "merged", "merged"], False),
    ],
)
def test_all_done_is_every_pr_merged_or_closed(board: Board, states: list[str], done: bool) -> None:
    board.forge = {FIRST + i: {"state": s} for i, s in enumerate(states)}
    assert board.get()[1]["all_done"] is done


SEEN = "forge-journal.jsonl"
MERGED_AT = "2026-11-16T10:00:00Z"


def seen_lines(board: Board) -> list[dict[str, Any]]:
    path = changes(board.repo) / SEEN
    return [json.loads(x) for x in path.read_text("utf-8").splitlines()] if path.is_file() else []


def status_lines(chantier: Chantier, form: str, batch: str) -> list[str]:
    args = ("status",) if form == "direct" else ("status", "--refresh", "--batch", batch)
    code, out, err = chantier(*args, *(() if form == "direct" else ("--epoch", 1)))
    # a wake that cannot read the spend (no transcripts here) still prints the batch's lines
    assert code == 0 or form == "heartbeat", err
    return [x for x in out if x.startswith(("forge saw merged", SEEN))]


@pytest.mark.parametrize(("base", "into_cr"), [("main", None), ("chantier/b/cr-0", 0)])
def test_a_merge_the_record_lacks_is_signalled_once_and_a_cached_read_writes_nothing(
    board: Board, base: str, into_cr: int | None
) -> None:
    into = board.ids[into_cr] if into_cr is not None else None
    board.forge = {FIRST + 1: {"state": "merged", "base": base, "merged_at": MERGED_AT}}
    board.get()
    (first,) = seen_lines(board)
    assert {k: v for k, v in first.items() if k != "t"} == {
        "v": 1,
        "seq": 1,
        "kind": "merged",
        "source": "board",
        "audience": ["project"],
        "batch": record(board.repo)["id"],
        "cr": board.ids[1],
        "pr": LINK.format(FIRST + 1),
        "into": base,
        "into_cr": into,
        "merged_at": MERGED_AT,
    }
    (changes(board.repo) / SEEN).unlink()
    board.now = 5.0
    board.get()  # a cached read writes nothing, even where the line is missing
    assert seen_lines(board) == []
    board.now, board.failure = 20.0, None
    board.get()
    board.now = 40.0
    board.get()  # the same merge, read again: no second line
    assert [{k: v for k, v in x.items() if k != "t"} for x in seen_lines(board)] == [
        {k: v for k, v in first.items() if k != "t"}
    ]


CHAIN = 2
T1, T2, T3 = "2026-11-16T10:00:00Z", "2026-11-16T10:00:05Z", "2026-11-16T09:59:59Z"
INTO_0, INTO_1 = "chantier/b/cr-0", "chantier/b/cr-1"


def merged(base: str, at: str) -> dict[str, Any]:
    return {"state": "merged", "base": base, "merged_at": at}


# (the stacked CR, the forge's reads in turn, what each read adds for it: its lines' landed_with)
LANDING: list[Any] = [
    (1, [{40: merged("main", T2)}], [[0]]),  # the base landed later
    (1, [{40: merged("main", T1)}], [[0]]),  # at the same instant
    (1, [{40: merged("main", T3)}], [[None]]),  # the base merged before it: not landed
    (
        1,
        [{40: {}}, {40: merged("main", T2)}, {40: merged("main", T2)}],
        [[None], [None, 0], [None, 0]],
    ),
    (2, [{41: merged(INTO_0, T1), 40: merged("main", T2)}], [[0]]),  # a chain
]


@pytest.mark.parametrize(("stacked", "reads", "expected"), LANDING)
def test_a_stacked_merge_is_signalled_landed_with_its_base_once_the_base_landed(
    board: Board, stacked: int, reads: list[dict[int, Any]], expected: list[list[int | None]]
) -> None:
    board.forge = {
        FIRST + stacked: merged(INTO_0 if stacked == 1 else INTO_1, T3 if stacked == CHAIN else T1)
    }
    if stacked == CHAIN:
        board.edit(
            crs=[
                {**c, "status": "merged"} if i == 0 else c
                for i, c in enumerate(record(board.repo)["crs"])
            ]
        )
    for step, (more, want) in enumerate(zip(reads, expected, strict=True)):
        board.forge = {**board.forge, **more}
        board.now = step * 20.0
        board.get()
        mine = [x for x in seen_lines(board) if x["cr"] == board.ids[stacked]]
        got = [x.get("landed_with") for x in mine]
        assert got == [None if w is None else board.ids[w] for w in want]
        for x in mine:
            assert ("landed_at" in x) == bool(x.get("landed_with"))


@pytest.mark.parametrize("case", ["closed", "open", "recorded"])
def test_only_a_merge_the_record_lacks_is_signalled(board: Board, case: str) -> None:
    if case == "recorded":
        data = record(board.repo)
        data["crs"][0]["status"] = "merged"
        write_record(board.repo, data)
    board.forge = {FIRST: {"state": "merged" if case == "recorded" else case}}
    board.get()
    assert seen_lines(board) == []


@pytest.mark.parametrize("form", ["direct", "heartbeat"])
def test_status_prints_the_signal_until_the_merge_is_recorded(
    board: Board, chantier: Chantier, form: str
) -> None:
    cr = board.ids[0]
    batch = record(board.repo)["id"]
    board.forge = {FIRST: {"state": "merged", "merged_at": MERGED_AT}}
    board.get()
    assert status_lines(chantier, form, batch) == [
        f"forge saw merged: {cr} {LINK.format(FIRST)} into main at {MERGED_AT}; "
        f"for the Chief of Staff: order merged {cr}"
    ]
    assert chantier("order", "merged", cr, "--epoch", 1)[0] == 0
    assert status_lines(chantier, form, batch) == []


def test_status_names_what_it_cannot_read_and_prints_only_the_open_crs_of_its_batch(
    board: Board, chantier: Chantier
) -> None:
    a, b, c, d = board.ids
    batch = record(board.repo)["id"]
    data = record(board.repo)
    data["crs"][1]["status"] = "cancelled"
    write_record(board.repo, data)

    def entry(cr: str, **more: Any) -> str:
        found = {"kind": "merged", "batch": batch, "cr": cr, "pr": "P", "into": "main"}
        return json.dumps({**found, "into_cr": None, "merged_at": "t", **more})

    lines = [
        "not json",
        entry(a, batch="batch-old"),
        entry(b),
        entry(c, into="chantier/b/cr-0", into_cr=a),
        entry(c, into="chantier/b/cr-0", into_cr=a),
        entry(d, into="chantier/b/cr-0", into_cr=a),
        entry(d, into="chantier/b/cr-0", into_cr=a, landed_with=a, landed_at="u"),
    ]
    (changes(board.repo) / SEEN).write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert status_lines(chantier, "direct", batch) == [
        f"{SEEN}: line 1 unreadable",
        f"forge saw merged: {c} P into {a}'s branch at t; for the Chief of Staff: not landed, "
        f"tell the user, record nothing until {a} lands",
        f"forge saw merged: {d} P into {a}'s branch at t, landed with {a} at u; "
        f"for the Chief of Staff: order merged {d}",
    ]
    assert b not in "".join(status_lines(chantier, "direct", batch))


def test_the_signal_file_is_local_counted_by_no_one_and_moves_the_fingerprint(
    board: Board,
) -> None:
    repo = Repo.find(readonly=True)
    root = changes(board.repo)
    before = fingerprint.fingerprint(root)
    board.forge = {FIRST: {"state": "merged"}}
    board.get()
    assert (root / SEEN).is_file() and fingerprint.fingerprint(root) != before
    assert SEEN in files.IGNORED and SEEN in fingerprint.SINGLE
    journal.rescan(repo)
    assert (root / SEEN).is_file() and journal.since_rescan(root) == []
