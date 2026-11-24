"""The line that tells the Chief of Staff to start its watcher, the lock that says whether one
runs, and the cut that keeps the line last."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from batch_helpers import FROM_AGENTS_MD, host, open_batch, prepared, record, write_record
from conftest import Chantier
from watch_fakes import served

from chantier import __version__, cli
from chantier.core.repo import Repo
from chantier.hub import autostart, journal, lock, state
from chantier.hub.watch import Watch
from chantier.plugin_files import cli_command

ME, OTHER = "s-me", "s-other"
VAR = "CLAUDE_CODE_SESSION_ID"
LINE = "watch: not running: for the Chief of Staff, start in the background: "


def test_watchers_lists_the_held_locks_of_one_project(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    found = Repo.find()
    folder = found.git_dir / "chantier"
    assert lock.watchers(found.git_dir, "p") == [] and not folder.exists()  # no file created
    monkeypatch.setenv("CHANTIER_HOST", "claude")
    monkeypatch.setenv(VAR, ME)
    w = Watch(found, 0, board=served(found))
    w.project = "p"
    w.own = lock.WatcherLock(found.git_dir, "p", w.session)
    w.start()
    other = lock.WatcherLock(found.git_dir, "q", ME)
    assert other.acquire() and w.session == ME
    assert lock.watchers(found.git_dir, "p") == [ME]  # a held lock of another project is not listed
    assert lock.watchers(found.git_dir, "q") == [ME]
    other.release()
    w.close()
    assert lock.watchers(found.git_dir, "p") == []
    assert (folder / "watch-p" / f"{ME}.lock").is_file()  # left in place


def test_a_watcher_that_lost_its_lock_to_a_probe_takes_it_at_its_next_poll(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    found = Repo.find()
    monkeypatch.setenv("CHANTIER_HOST", "claude")
    monkeypatch.setenv(VAR, ME)
    probe = lock.WatcherLock(found.git_dir, Watch(found, 0).project, ME)
    assert probe.acquire()
    w = Watch(found, 0, board=served(found))
    w.start()
    assert not w.own.held
    probe.release()
    w.poll(0.0)
    assert w.own.held
    w.close()


@pytest.mark.parametrize(("raw", "key"), [("a-1", "a-1"), ("a/../b", "ab"), ("", "none")])
def test_the_session_key_keeps_letters_digits_and_dashes(
    monkeypatch: pytest.MonkeyPatch, raw: str, key: str
) -> None:
    monkeypatch.setenv("CHANTIER_HOST", "claude")
    monkeypatch.setenv(VAR, raw)
    assert autostart.session_key() == key


Setup = Callable[[Path, Chantier, pytest.MonkeyPatch], Callable[[], list[str]]]


def _open(repo: Path, chantier: Chantier, mp: pytest.MonkeyPatch) -> Callable[[], list[str]]:
    folder = prepared(repo, chantier, "Alpha")
    return lambda: chantier("open", str(folder), *FROM_AGENTS_MD)[1]


def _paused(repo: Path, chantier: Chantier, mp: pytest.MonkeyPatch) -> None:
    data = record(repo)
    data["status"] = "paused"
    write_record(repo, data)


def _take(repo: Path, chantier: Chantier, mp: pytest.MonkeyPatch) -> Callable[[], list[str]]:
    cr = open_batch(repo, chantier, mp, "Alpha")[0]
    _paused(repo, chantier, mp)
    return lambda: chantier("take", cr, "--epoch", 1)[1]


def _order_qa(repo: Path, chantier: Chantier, mp: pytest.MonkeyPatch) -> Callable[[], list[str]]:
    folder = prepared(repo, chantier, "Alpha")
    assert chantier("open", str(folder), "--direct", *FROM_AGENTS_MD)[0] == 0
    mp.setenv("CHANTIER_BATCH", record(repo)["id"])
    _paused(repo, chantier, mp)

    def run() -> list[str]:
        code, out, err = chantier("order", "qa", "--note", "test it")
        assert code == 0, err
        return out

    return run


def _transcript(repo: Path, chantier: Chantier, mp: pytest.MonkeyPatch) -> Callable[[], list[str]]:
    open_batch(repo, chantier, mp, "Alpha", seat=False)
    assert chantier("foreman", "set", "s-foreman", "--epoch", 1)[0] == 0
    assert chantier("foreman", "transcript", "uuid-foreman", "--epoch", 1)[0] == 0
    assert chantier("foreman", "set", ME, "--epoch", 2)[0] == 0
    return lambda: chantier("foreman", "transcript", ME, "--epoch", 2)[1]


def _status(repo: Path, chantier: Chantier, mp: pytest.MonkeyPatch) -> Callable[[], list[str]]:
    open_batch(repo, chantier, mp, "Alpha")
    return lambda: chantier("status")[1]


def _status_paused(
    repo: Path, chantier: Chantier, mp: pytest.MonkeyPatch
) -> Callable[[], list[str]]:
    open_batch(repo, chantier, mp, "Alpha")
    _paused(repo, chantier, mp)
    return lambda: chantier("status")[1]


def _seat_take(repo: Path, chantier: Chantier, mp: pytest.MonkeyPatch) -> Callable[[], list[str]]:
    return lambda: chantier("seat", "take", "s-chief")[1]


def _seat_get(repo: Path, chantier: Chantier, mp: pytest.MonkeyPatch) -> Callable[[], list[str]]:
    assert chantier("seat", "take", "s-chief")[0] == 0
    return lambda: chantier("seat", "get")[1]


SETUPS: dict[str, Setup] = {
    "open": _open,
    "take": _take,
    "order-qa": _order_qa,
    "transcript": _transcript,
    "status": _status,
    "status-paused": _status_paused,
    "seat-take": _seat_take,
    "seat-get": _seat_get,
}


@pytest.mark.parametrize("who", ["none", "mine", "other"])
@pytest.mark.parametrize("command", SETUPS)
def test_the_outputs_end_with_the_line_when_no_watcher_of_this_session_runs(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch, command: str, who: str
) -> None:
    host(monkeypatch)
    monkeypatch.setenv(VAR, ME)
    run = SETUPS[command](repo, chantier, monkeypatch)
    found = Repo.find()
    journal.append(
        found,
        [
            journal.red_event("b", "CR-1", "P", "c" * 40),
            journal.red_event("b", "CR-1", "P", "d" * 40),
        ],
        "hub",
    )
    watchers: list[Watch] = []
    if who != "none":
        monkeypatch.setenv(VAR, ME if who == "mine" else OTHER)
        w = Watch(found, 0, board=served(found))
        w.start()
        state.write_hub(found.git_dir, state.hub_record(__version__))  # the hub observes it
        watchers.append(w)
        monkeypatch.setenv(VAR, ME)
    out = run()
    for w in watchers:
        w.close()
    pull = f"{cli_command(found)} watch --once --after 2"
    no = "; after the user's no, at each user message: "
    last = f"{LINE}{cli_command(found)} watch --after 2 --stream{no}{pull}"  # host: claude
    if who == "mine":
        assert not any(x.startswith("watch: not running") for x in out)
    else:
        assert out[-1] == last and "--batch" not in last
        assert sum(x.startswith("watch: not running") for x in out) == 1
    if command.startswith("status"):
        mine = f"watch: this session's watcher runs; pull path: {pull}"
        assert (mine in out) == (who == "mine")
        theirs = (
            f"watch: session {OTHER} runs a watcher too; its end wakes that session, not this one"
        )
        assert (theirs in out) == (who == "other")


@pytest.mark.parametrize(("name", "stream"), [("claude", True), ("copilot", False), (None, False)])
def test_the_watcher_command_streams_on_claude_code_only(
    repo: Path, monkeypatch: pytest.MonkeyPatch, name: str | None, stream: bool
) -> None:
    if name is not None:
        monkeypatch.setenv("CHANTIER_HOST", name)
    found = Repo.find()
    plain = f"{cli_command(found)} watch --after 4"
    assert autostart.watch_command(found, 4) == plain + (" --stream" if stream else "")
    (line,) = autostart.not_running_line(found)
    assert f"start in the background: {autostart.watch_command(found, 0)};" in line
    assert line.endswith(autostart.pull_command(found, 0)) and "--once --after 0" in line


def test_some_outputs_print_no_line(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    host(monkeypatch)
    monkeypatch.setenv(VAR, ME)
    cr = open_batch(repo, chantier, monkeypatch, "Alpha")[0]
    nothing = "watch: not running"
    assert not any(x.startswith(nothing) for x in chantier("take", cr, "--epoch", 1)[1])
    extra = prepared(repo, chantier, "Beta")
    _paused(repo, chantier, monkeypatch)
    code, out, err = chantier("order", "add", "--note", str(extra))
    assert code == 0, err
    assert not any(x.startswith(nothing) for x in out)


def test_the_seat_of_another_session_gets_no_line_and_a_status_names_a_board_of_another_version(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    host(monkeypatch)
    monkeypatch.setenv(VAR, ME)
    assert chantier("seat", "take", "s-chief")[0] == 0
    monkeypatch.setenv(VAR, OTHER)
    code, out, _ = chantier("seat", "get")
    assert code == 0 and not any(x.startswith("watch:") for x in out)
    open_batch(repo, chantier, monkeypatch, "Alpha")
    found = Repo.find()
    for version, shown in (("0.0.1", True), (__version__, False)):
        state.write_server(found.git_dir, "127.0.0.1", 1, version, "x")
        out = chantier("status")[1]
        assert any(x.startswith("board: chantier 0.0.1 serves this surface") for x in out) == shown
        assert not any("board wrote" in x for x in out)


TWELVE = [f"line {i}" for i in range(12)]


@pytest.mark.parametrize("trigger", [True, False])
def test_the_ten_line_cut_keeps_the_watcher_line_last(trigger: bool) -> None:
    lines = [*TWELVE[:-1], LINE + "x"] if trigger else TWELVE
    got = cli.cut(lines)
    assert len(got) == cli.MAX_LINES
    if trigger:
        assert got[-2] == "… 3 more lines"
        assert got[-1] == LINE + "x" and got[:8] == lines[:8]
    else:
        assert got[-1] == "… 3 more lines" and got[:9] == lines[:9]


def _set_source(git_dir: Path, source: str | None) -> None:
    def put(data: dict[str, Any]) -> None:
        data[state.SERVER].pop("source", None)
        if source is not None:
            data[state.SERVER]["source"] = source

    state.modify(git_dir, put)


FOREIGN = (
    f"board runs another build of chantier {__version__} (/uv/cache/chantier), not this checkout's"
)
UNKNOWN = (
    f"board runs a build of chantier {__version__} older than this notice "
    "(source unknown), not this checkout's"
)
BUILDS = [  # (source of the entry, is_dev_checkout, is_chantier_project, the line said)
    ("this", True, True, None),
    ("/uv/cache/chantier", True, True, FOREIGN),
    (None, True, True, UNKNOWN),
    ("/uv/cache/chantier", False, True, None),
    ("/uv/cache/chantier", True, False, None),
    (None, False, False, None),
]  # fmt: skip


@pytest.mark.parametrize("case", BUILDS)
def test_a_status_names_a_board_of_another_build_only_in_the_dev_mode_of_chantier(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch, case: tuple[Any, ...]
) -> None:
    source, dev, mine, said = case
    host(monkeypatch)
    monkeypatch.setenv(VAR, ME)
    open_batch(repo, chantier, monkeypatch, "Alpha")
    found = Repo.find()
    monkeypatch.setattr("chantier.hub.lines.is_dev_checkout", lambda: dev)
    monkeypatch.setattr("chantier.hub.lines.is_chantier_project", lambda _repo: mine)
    state.write_server(found.git_dir, "127.0.0.1", 1, __version__, "x")
    assert state.read(found.git_dir)[state.SERVER]["source"] == state.build_source()
    assert state.hub_record(__version__)["source"] == state.build_source()
    _set_source(found.git_dir, state.build_source() if source == "this" else source)
    out = chantier("status")[1]
    assert [x for x in out if x.startswith("board runs")] == ([said] if said else [])
    assert not any("restart" in x or "stop" in x.lower() for x in out if x.startswith("board"))
    state.write_server(found.git_dir, "127.0.0.1", 1, "0.0.1", "x")
    out = chantier("status")[1]
    assert not any(x.startswith("board runs") for x in out)
    assert any(x.startswith("board: chantier 0.0.1 serves this surface") for x in out)
