"""`chantier access`: what the rules say now for a session, read-only. In-process, on prepared
states: an in-project batch (CR one taken at T0, its lease live until 00:10) and, for the writer,
a planning surface. Every answer exits 0 and changes nothing: bytes and mtimes are the same."""

from __future__ import annotations

import json
import os
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import pytest
from batch_helpers import DEAD, changes, name_server, record, write_record
from conftest import Chantier, Surface
from store_spy import _environment, enter_state
from test_store_command_table import states  # noqa: F401 - the surface states (a fixture)

from chantier.cli import main
from chantier.core import clock
from chantier.core.errors import EXIT_USAGE
from chantier.hub import state

T0 = "2030-01-01T00:00:00Z"  # CR one's lease 1 expires at 00:10:00
ME = "uuid-me"
WITH_EPOCH_LINE, TWO_LINES = 3, 2
Ask = Callable[..., list[str]]
Change = Callable[[dict[str, Any]], None]
START = "start the surface server ($CHANTIER board --seat <session id>)"


@pytest.fixture(scope="session")
def batch_template(repo_template: Path, tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The plain repository with a batch of three CRs (two slots), CR one taken at T0."""
    root = tmp_path_factory.mktemp("access-batch") / "proj"
    shutil.copytree(repo_template, root)
    with pytest.MonkeyPatch.context() as mp:
        _environment(mp, root.parent)
        mp.chdir(root)
        mp.setattr("chantier.core.repo.PROJECT", None)
        mp.setattr(clock, "_fixed", [])
        clock.fix(T0)
        names = ("alpha", "beta", "gamma")
        for name in names:
            assert main(["file", name]) == 0
            spec = changes(root) / "1-inbox" / name / "03-change-spec.md"
            spec.write_text(f"# {name}\n\nDo it.\n", encoding="utf-8")
        folders = [str(changes(root) / "1-inbox" / n) for n in names]
        assert main(["open", *folders, "--default-branch", "main", "--slots", "2"]) == 0
        mp.setenv("CHANTIER_BATCH", record(root)["id"])
        assert main(["foreman", "set", "local_foreman_t", "--epoch", "1"]) == 0
        assert main(["take", "CR-101", "--epoch", "1"]) == 0
    return root


@pytest.fixture
def world(repo: Path, batch_template: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    shutil.copytree(batch_template, repo, ignore=shutil.ignore_patterns(".git"), dirs_exist_ok=True)
    monkeypatch.setenv("CHANTIER_HOST", "claude")
    monkeypatch.setenv("CLAUDE_CODE_ENTRYPOINT", "claude-desktop")
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", ME)
    monkeypatch.setattr(clock, "_fixed", [])
    clock.fix(T0)
    return repo


def _prints(*folders: Path) -> dict[str, tuple[int, bytes | None]]:
    found: dict[str, tuple[int, bytes | None]] = {}
    for folder in folders:
        for p in sorted(folder.rglob("*")) if folder.exists() else []:
            found[str(p)] = (p.stat().st_mtime_ns, p.read_bytes() if p.is_file() else None)
    return found


def _asker(chantier: Chantier, planning: Path, git_dir: Path) -> Ask:
    """`access` as typed: exit 0, and the planning folder and the git folder's `chantier/` the
    same afterwards, bytes and modification times."""

    def ask(*args: object) -> list[str]:
        before = _prints(planning, git_dir / "chantier")
        code, out, err = chantier("access", *args)
        assert code == 0, (out, err)
        assert _prints(planning, git_dir / "chantier") == before
        return out

    return ask


@pytest.fixture
def ask(world: Path, chantier: Chantier) -> Ask:
    return _asker(chantier, changes(world), world / ".git")


def edit(repo: Path, change: Change) -> None:
    data = record(repo)
    change(data)
    write_record(repo, data)


def _cr(data: dict[str, Any], n: int = 0) -> dict[str, Any]:
    cr: dict[str, Any] = data["crs"][n]
    return cr


# --- the session line ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("seat", "where", "expected"),
    [
        ({"session": "chief", "transcript": ME}, "", f"session {ME}: holds the seat of proj"),
        (
            {"session": "chief", "transcript": "cop-1"},
            "copilot",
            "session cop-1: holds the seat of proj",
        ),
        (
            {"session": "chief", "transcript": "o", "link": "https://x/1"},
            "",
            f"session {ME}: the seat is chief (https://x/1)",
        ),
        (
            {"session": "chief", "transcript": "o"},
            "",
            f"session {ME}: the seat is chief (unknown)",
        ),
        (None, "", f"session {ME}: no seat recorded"),
        (
            {"session": "chief", "transcript": ME},
            "bare",
            "session none: the seat is chief (unknown)",
        ),
    ],
)
def test_the_session_line_says_who_holds_the_seat(  # noqa: PLR0913, PLR0917 - one per row
    world: Path,
    ask: Ask,
    monkeypatch: pytest.MonkeyPatch,
    seat: dict[str, str] | None,
    where: str,
    expected: str,
) -> None:
    seat_file = changes(world) / "seat.json"
    seat_file.unlink(missing_ok=True)
    if seat is not None:
        seat_file.write_text(json.dumps(seat), encoding="utf-8")
    if where == "copilot":  # Copilot: its own session variable is the transcript
        monkeypatch.setenv("CHANTIER_HOST", "copilot")
        monkeypatch.setenv("COPILOT_AGENT_SESSION_ID", "cop-1")
    if where == "bare":  # a bare terminal: no host, no session id
        for var in ("CHANTIER_HOST", "CLAUDE_CODE_ENTRYPOINT", "CLAUDE_CODE_SESSION_ID"):
            monkeypatch.delenv(var)
    assert ask("write")[0] == expected


# --- write ---------------------------------------------------------------------------------------


def test_write_in_project_commits_nothing(ask: Ask) -> None:
    assert ask("write") == [
        f"session {ME}: no seat recorded",
        "write: allowed: in-project planning folder, under the lifecycle lock; chantier "
        "commits nothing",
    ]


@pytest.fixture
def plan(
    states: dict[str, Path],  # noqa: F811
    repo: Path,
    tmp_path: Path,
    chantier: Chantier,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[Surface, Ask]:
    surface = enter_state(states["batch"], tmp_path, monkeypatch)
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", ME)
    return surface, _asker(chantier, surface.project / "changes", surface.root / ".git")


def _writer(surface: Surface, entry: dict[str, Any] | None) -> None:
    def put(data: dict[str, Any]) -> None:
        data.pop(state.WRITER, None)
        if entry is not None:
            data[state.WRITER] = {"pid": os.getpid(), "started": clock.now(), **entry}

    state.modify(surface.root / ".git", put)


@pytest.mark.parametrize(
    ("entry", "tail"),
    [
        ({"state": "synced"}, ""),
        ({"state": "syncing"}, ""),
        ({"state": "pending", "pending": 2, "ahead": 0}, "; not pushed yet: 2 paths"),
        ({"state": "offline", "ahead": 3}, "; not pushed yet: 3 commits"),
        ({"state": "blocked", "reason": "no-upstream"}, "; not pushed yet: no-upstream"),
        ({"state": "conflict", "ahead": 1}, "; not pushed yet: 1 commits"),
    ],
)
def test_write_on_a_surface_with_a_writer_says_how_far_it_has_pushed(
    plan: tuple[Surface, Ask], entry: dict[str, Any], tail: str
) -> None:
    surface, ask = plan
    _writer(surface, entry)
    assert ask("write")[1] == (
        f"write: allowed: the surface's writer runs (pid {os.getpid()}, {entry['state']}); "
        f"it commits and pushes within 5 min{tail}"
    )


def test_write_on_a_surface_with_no_writer_is_refused_and_names_an_older_board(
    plan: tuple[Surface, Ask],
) -> None:
    surface, ask = plan
    _writer(surface, None)
    assert ask("write")[1] == f"write: refused: the surface's writer is not running; {START}"
    name_server(surface.root / ".git", version="0.0.1")
    line = ask("write")[1]
    assert f"chantier board 0.0.1 (PID {os.getpid()}) serves this surface with no writer" in line
    assert "; stop it (" in line and line.endswith(f"), then {START}")
    _writer(surface, {"state": "stopped", "text": "the thread died"})
    assert "writer is stopped: the thread died" in ask("write")[1]


def test_on_a_surface_claim_with_no_writer_is_refused_and_push_names_the_writer(
    plan: tuple[Surface, Ask],
) -> None:
    surface, ask = plan
    cr = json.loads((surface.project / "changes/4-batch/batch.json").read_text("utf-8"))["crs"][0]
    assert ask("claim", cr["id"])[1].startswith(f"claim: allowed: {cr['id']} is queued;")
    _writer(surface, None)
    out = ask("claim", cr["id"])
    assert out[1].startswith(
        "claim: refused: the surface's writer is not running: nothing written;"
    )
    assert ask("push", cr["id"])[1:] == [
        f"push: refused: {cr['id']} is queued",
        "push surface: only the writer pushes the surface; never by hand",
    ]


def _slots(n: int) -> Change:
    return lambda d: d.update(slots=n)


def _budget(budget: float, spent: float | None, unpriced: bool = False) -> Change:
    return lambda d: d.update(
        budget_usd=budget, spent_usd=spent, unpriced={"m": 1} if unpriced else {}
    )


def _set(n: int, **fields: Any) -> Change:
    return lambda d: _cr(d, n).update(fields)


def _ended(d: dict[str, Any]) -> None:
    _cr(d)["lease"]["ended"] = T0


def _no_lease(d: dict[str, Any]) -> None:
    _cr(d)["lease"] = None


def _unchanged(d: dict[str, Any]) -> None:
    del d


BASE = "; 1 of 2 slots held; dependencies ready; budget left "
LAST = " (last recorded spend)"
NOTE = f"none set{LAST}; take needs --note saying why (CR-101 is working)"
FINE = [
    ("none-set", _unchanged, "CR-102", f"claim: allowed: CR-102 is queued{BASE}none set{LAST}"),
    ("left", _budget(10, 2.5), "CR-102", f"claim: allowed: CR-102 is queued{BASE}$7.50{LAST}"),
    (
        "unpriced",
        _budget(10, 2.5, True),
        "CR-102",
        f"claim: allowed: CR-102 is queued{BASE}at least $7.50{LAST}",
    ),
    (
        "unknown",
        _budget(10, None),
        "CR-102",
        f"claim: allowed: CR-102 is queued{BASE}budget $10.00, spend unknown{LAST}",
    ),
    ("ended-lease", _ended, "CR-101", f"claim: allowed: CR-101 is working{BASE}{NOTE}"),
    ("no-lease", _no_lease, "CR-101", f"claim: allowed: CR-101 is working{BASE}{NOTE}"),
]


@pytest.mark.parametrize(("change", "cr", "line"), [x[1:] for x in FINE], ids=[x[0] for x in FINE])
def test_claim_is_allowed_with_its_facts(
    world: Path, ask: Ask, change: Change, cr: str, line: str
) -> None:
    edit(world, change)
    assert ask("claim", cr, "--epoch", 1)[1:] == [line]


# (id, the change, minutes after T0, the CR, what the refusal says)
REFUSED = [
    ("live-lease", _unchanged, 5, "CR-101", "CR-101 is held: lease 1 live until 00:10:00"),
    ("lease-not-confirmed", _unchanged, 11, "CR-101", "CR-101: lease 1 not confirmed since 00:10"),
    ("no-slot", _slots(1), 0, "CR-102", "no free slot for CR-102"),
    ("dependency", _set(1, after=["CR-103"]), 0, "CR-102", "CR-102 waits for CR-103"),
    ("budget", _budget(1, 2), 0, "CR-102", "budget spent"),
    ("agent", _set(1, agent="a-driver"), 0, "CR-102", "CR-102 still has an agent recorded"),
    ("merged", _set(1, status="merged"), 0, "CR-102", "CR-102 is merged: nothing for a Driver"),
]


@pytest.mark.parametrize(
    ("change", "minutes", "cr", "says"), [x[1:] for x in REFUSED], ids=[x[0] for x in REFUSED]
)
def test_claim_quotes_the_refusal_take_prints(  # noqa: PLR0913, PLR0917 - one prepared state per row
    world: Path,
    ask: Ask,
    chantier: Chantier,
    change: Change,
    minutes: int,
    cr: str,
    says: str,
) -> None:
    edit(world, change)
    clock.fix(clock.after(minutes * 60, T0))
    line = ask("claim", cr, "--epoch", 1)[1]
    text = line.removeprefix("claim: refused: ")
    assert line.startswith("claim: refused: ") and says in text and "take: " not in text
    code, _, err = cast(Any, chantier).bare(
        "take", cr, "--note", "why", "--epoch", 1
    )  # one check function
    assert code != 0 and err.strip() == f"error: {text}"


def test_claim_says_what_the_epoch_needs_and_a_dead_hold_record_stays(
    world: Path, ask: Ask
) -> None:
    needs = "claim: needs the steering session's --epoch (Foreman n°1)"
    assert len(ask("claim", "CR-102", "--epoch", 1)) == WITH_EPOCH_LINE - 1  # the current one
    assert ask("claim", "CR-102")[2] == needs and ask("claim", "CR-102", "--epoch", 7)[2] == needs
    hold = changes(world) / ".lease-hold.CR-101.1.run"
    hold.write_text(json.dumps({"unit": "CR-101", "lease": 1, "pid": DEAD}), encoding="utf-8")
    clock.fix(clock.after(11 * 60, T0))
    assert "not confirmed since 00:10" in ask("claim", "CR-101", "--epoch", 1)[1]
    assert hold.exists()  # a dead record holds nothing, and `access` removes none


def _branch(world: Path) -> str:
    return str(_cr(record(world))["branch"])


@pytest.mark.parametrize(
    ("change", "minutes", "lease", "says"),
    [
        (_unchanged, 5, 1, "push: allowed: lease 1 of CR-101 is live; push {b} without force; "),
        (_unchanged, 5, None, "push: refused: no --lease given (lease 1 is current)"),
        (_unchanged, 5, 2, "push: refused: claim lost (lease 1 is current)"),
        (_ended, 5, 1, "push: refused: claim lost (lease 1 is current), ended at 00:00"),
        (
            _unchanged,
            11,
            1,
            "push: allowed: lease 1 of CR-101 not confirmed since 00:10, not taken again; renew "
            "it first (lease CR-101 renew --lease 1), then push {b} without force; ",
        ),
        (_set(0, status="ready"), 5, 1, "push: refused: CR-101 is ready"),
        (_no_lease, 5, None, "push: allowed: CR-101 is working; no lease in this batch; push {b} "),
    ],
    ids=["live", "no-lease-given", "stale", "ended", "not-confirmed", "ready", "batch-no-lease"],
)
def test_push_follows_the_lease(  # noqa: PLR0913, PLR0917 - one prepared state per row
    world: Path, ask: Ask, change: Change, minutes: int, lease: int | None, says: str
) -> None:
    edit(world, change)
    clock.fix(clock.after(minutes * 60, T0))
    args = ("push", "CR-101", *(("--lease", lease) if lease else ()))
    out = ask(*args)
    assert len(out) == TWO_LINES and out[1].startswith(says.format(b=_branch(world)))
    if "allowed" in out[1]:
        assert out[1].endswith("a rewrite uses --force-with-lease (driver.md)")


def test_a_cr_the_batch_does_not_hold_is_refused_with_exit_zero(world: Path, ask: Ask) -> None:
    assert ask("push", "99")[1] == "push: refused: no batch holds CR-99"
    batch = record(world)["id"]
    assert ask("claim", "CR-99", "--batch", batch)[1] == (
        f"claim: refused: unknown CR CR-99 in batch {batch}"
    )
    assert [x[:6] for x in ask("CR-102", "--epoch", 1)[1:]] == ["write:", "claim:", "push: "]


def test_claim_and_push_need_a_cr_and_write_does_not(world: Path, chantier: Chantier) -> None:
    for action in ("claim", "push"):
        code, out, err = chantier("access", action)
        assert (
            code == EXIT_USAGE
            and not out
            and err.strip() == (f"error: access {action} <cr>: name the CR")
        )
    assert chantier("access", "write")[0] == 0
