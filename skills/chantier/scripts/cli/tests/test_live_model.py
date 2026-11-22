"""The screen's data of `chantier live` and its drawing, fed with prepared events: no network, no
server."""

from __future__ import annotations

import contextlib
import io
import signal
import sys
import threading
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from chantier.clients.tui import screen
from chantier.clients.tui.link import Event, Idle, Linked
from chantier.clients.tui.model import FLOW, Line, Model, lease_left, merged
from chantier.clients.tui.view import HELP, View
from chantier.commands import live as live_command
from chantier.core.errors import EXIT_EXTERNAL, EXIT_USAGE, ChantierError

CAP = 2000

NOW = "2030-01-01T00:00:00Z"
WIDE, NARROW, HIGH = 140, 90, 20


def _lease(**over: Any) -> dict[str, Any]:
    facts = {"n": 1, "renewed": NOW, "expires": "2030-01-01T00:04:30Z", "ended": None}
    return {**facts, "gate": None, **over}


def _crs() -> list[dict[str, Any]]:
    row = {"phase": None, "round": 0, "round_limit": 3, "lease": None, "blocked": None}
    return [
        {**row, "cr": "CR-1", "title": "Working one", "state": "working", "phase": "coding",
         "round": 1, "lease": _lease()},
        {**row, "cr": "CR-2", "title": "Ready one", "state": "handed_back", "to_review": True,
         "handed_back_at": "2029-12-31T23:48:00Z"},
        {**row, "cr": "CR-3", "title": "Held one", "state": "blocked",
         "blocked": "waits for the user's answer"},
        {**row, "cr": "CR-4", "title": "Done one", "state": "merged"},
    ]  # fmt: skip


def _record(kind: str, t: str, **more: Any) -> dict[str, Any]:
    return {"t": t, "actor": "Foreman", "kind": kind, **more}


def _project(events: list[dict[str, Any]]) -> dict[str, Any]:
    batch = {"id": "batch-01", "state": "running", "mode": "batch", "crs": _crs()}
    return {**{"batch": {**batch, "stack_lease": None}}, "events": events}


def _fed(clock: list[float]) -> Model:
    m = Model(clock=lambda: clock[0])
    m.feed(Linked("ws", NOW))
    board = {"version": "0.15.0", "served": "/work/p", "projects": [{"id": "p", "inbox": 2}]}
    m.feed(Event("board", "board", board, NOW))
    first = [_record("took", "2029-12-31T23:50:00Z", cr="CR-1")]
    m.feed(Event("project:p", "project", _project(first), NOW))
    m.feed(Event("events:p", "events", {"lines": []}, NOW))
    return m


def test_the_model_counts_and_keeps_each_new_line_once() -> None:
    clock = [100.0]
    m = _fed(clock)
    assert m.counts() == {"working": 1, "ready": 1, "held": 1, "done": 1}
    assert m.missing() == [] and m.agents() == [("p", "Driver CR-1 coding")]
    earlier = [_record("took", "2029-12-31T23:50:00Z", cr="CR-1")]
    later = [*earlier, _record("handed_back", "2029-12-31T23:59:00Z", cr="CR-2", result="ok")]
    m.feed(Event("project:p", "project", _project(later), NOW))
    m.feed(Event("project:p", "project", _project(later), NOW))  # the same again: nothing new
    lines = [
        {"seq": 1, "t": "2029-12-31T23:59:30Z", "type": "board@1", "source": "board",
         "text": "board wrote (new): an idea"},
        {"seq": 2, "t": "2029-12-31T23:59:40Z", "type": "later@1", "source": "hub"},
    ]  # fmt: skip
    m.feed(Event("events:p", "events", {"lines": lines}, NOW))
    assert [x.text for x in m.flow] == [
        "took CR-1",
        "handed_back CR-2 ok",
        "board wrote (new): an idea",
        "later@1",  # no `text`: its type
    ]
    clock[0] += 30  # "now" is the server's plus the time elapsed here
    assert m.now() == datetime(2030, 1, 1, 0, 0, 30, tzinfo=UTC)


@pytest.mark.parametrize(
    ("over", "left"),
    [
        ({}, "04:30"),
        ({"expires": "2029-12-31T23:57:00Z", "gate": "gate"}, "gate"),
        ({"expires": "2029-12-31T23:57:00Z"}, "not confirmed 3 min"),
        ({"ended": "2029-12-31T23:59:00Z"}, None),
    ],
)
def test_the_time_left_of_a_lease_comes_from_its_facts_and_the_servers_now(
    over: dict[str, Any], left: str | None
) -> None:
    m = Model(clock=lambda: 0.0)
    m.feed(Linked("http", NOW))  # this machine's clock is not asked
    assert lease_left(_lease(**over), m.now()) == left
    assert lease_left(None, m.now()) is None


def _drawn(m: Model, width: int) -> str:
    out = io.StringIO()
    screen.plain(m, width, HIGH, out)
    return out.getvalue()


def test_the_screen_shows_the_counts_the_tasks_and_the_flow_and_drops_the_left_column() -> None:
    m = _fed([0.0])
    wide = _drawn(m, WIDE)
    assert "working 1  ready 1  held 1  done 1" in wide and "v0.15.0" in wide
    assert "lease 04:30" in wide and "round 1/3" in wide  # the working CR
    assert "12m  Ready one" in wide  # to review, with its age
    assert "waits for the user's answer" in wide  # blocked, with its reason
    assert "23:50:00" in wide and "took CR-1" in wide  # a flow line
    assert "Projects" in wide and "Driver CR-1 coding" in wide
    assert all(len(x) <= WIDE for x in wide.splitlines()) and "\x1b" not in wide
    narrow = _drawn(m, NARROW)
    assert "Projects" not in narrow and "lease 04:30" in narrow


# keys, scroll, filter, several boards


def _press(view: View, keys: list[str], page: int = 1) -> bool:
    return any([view.press(k, page) for k in keys])


def _journal(m: Model, lines: list[dict[str, Any]]) -> None:
    m.feed(Event("events:p", "events", {"lines": lines}, NOW))


def _lines(start: int, stop: int, minute: int = 30, prefix: str = "line") -> list[dict[str, Any]]:
    return [
        {"seq": i, "t": f"2029-12-31T23:{minute}:{i % 60:02d}Z", "source": "hub",
         "text": f"{prefix} {i:02d}"}
        for i in range(start, stop)
    ]  # fmt: skip


def _keyed(m: Model, view: View) -> str:
    out = io.StringIO()
    view.keys = True
    screen.plain(m, WIDE, HIGH, out, view)  # 15 rows of Flow
    return out.getvalue()


@pytest.mark.parametrize(
    ("keys", "arrive", "shown", "hidden"),
    [
        (["up"], 3, ["line 29", "Flow  paused, 3 new"], ["took CR-1", "late 01"]),
        (["pgup"], 0, ["line 02", "line 16", "paused, 0 new"], ["line 01", "line 17"]),
        (["home"], 3, ["line 01", "line 15", "paused, 3 new"], ["line 16", "late"]),
        (["home", "end"], 3, ["late 03", "took CR-1"], ["paused", "line 01"]),
        (["up", "down"], 3, ["late 03", "took CR-1"], ["paused"]),
        (["pgup", "pgdn", "pgdn"], 1, ["late 01"], ["paused"]),
        (["x", "\x00"], 0, ["took CR-1", "line 29"], ["paused"]),  # unbound keys
        (["/", "C", "R", "-", "2", "enter"], 0, ["filter: CR-2", "cr-2 note", "Ready one"],
         ["took CR-1", "Working one", "line 29"]),
        (["/", "x", "backspace", "enter"], 0, ["took CR-1", "Working one"], ["filter:"]),
        (["/", "c", "r", "enter", "esc"], 0, ["took CR-1", "Working one"], ["filter:"]),
        (["/", "z", "enter"], 0, ["no task matches z", "working 1"], ["took CR-1"]),
        (["/", "c"], 0, ["? keys  / filter  q quit  /c"], ["filter:"]),
        (["?"], 0, [*(k for k, _ in HELP), "any key closes"], ["took CR-1"]),
        (["?", "x"], 0, ["took CR-1", "Working one"], ["any key closes"]),
    ],
)  # fmt: skip
def test_keys_scroll_pause_filter_and_help_change_what_the_screen_prints(
    keys: list[str], arrive: int, shown: list[str], hidden: list[str]
) -> None:
    m = _fed([0.0])
    note = {"seq": 90, "t": "2029-12-31T23:31:00Z", "source": "hub", "text": "cr-2 note"}
    _journal(m, [*_lines(1, 30), note])  # 31 lines with the record's one
    view, wanted = View(), m.wanted()
    assert not _press(view, keys, page=15)
    _keyed(m, view)  # the keys are applied to the lines the screen holds
    _journal(m, _lines(1, arrive + 1, minute=55, prefix="late"))
    text = _keyed(m, view)
    for x in shown:
        assert x in text, (x, text)
    for x in hidden:
        assert x not in text, (x, text)
    assert "working 1  ready 1  held 1  done 1" in text  # the counts stay those of everything
    assert m.wanted() == wanted  # the filter is local: nothing more is asked of the server


@pytest.mark.parametrize(
    ("keys", "quit_"),
    [
        (["q"], True),
        (["ctrl-c"], True),
        (["x"], False),
        (["/", "q"], False),
        (["/", "ctrl-c"], True),
        (["?", "q"], False),
        (["?", "ctrl-c"], True),
        (["up", "esc"], False),
    ],
)
def test_q_and_ctrl_c_quit_and_a_key_in_the_filter_or_the_help_does_not(
    keys: list[str], quit_: bool
) -> None:
    assert _press(View(), keys) is quit_


def _board(label: str, start: datetime, n: int, offset: int) -> Model:
    m = Model(label=label, base=f"http://{label}/", clock=lambda: 0.0)
    m.feed(Linked("ws", NOW))
    m.feed(Event("board", "board", {"version": "1", "projects": [{"id": "p"}]}, NOW))
    lines = [
        {"seq": i, "t": (start + timedelta(seconds=2 * i + offset)).strftime("%Y-%m-%dT%H:%M:%SZ"),
         "source": "hub", "text": f"{label} {i}"}
        for i in range(n)
    ]  # fmt: skip
    m.feed(Event("events:p", "events", {"lines": lines}, NOW))
    return m


def test_each_board_keeps_2000_lines_and_home_shows_the_oldest_of_the_merged_view() -> None:
    start = datetime(2029, 1, 1, tzinfo=UTC)
    a, b = _board("a", start, FLOW + 100, 0), _board("b", start, FLOW + 100, 1)
    assert len(a.flow) == len(b.flow) == FLOW == CAP
    both = merged([a, b])
    assert len(both) == 2 * FLOW and [x.t for x in both] == sorted(x.t for x in both)
    view, rows = View(), 15
    view.press("home", rows)
    shown, title = view.window(both, rows)
    assert shown[0] is both[0] and shown[0].text == "a 100" and title == "Flow  paused, 0 new"
    a._add(Line("2030-01-01T00:00:00Z", "p", "hub", "a new", board="a"))  # drops "a 100"
    both = merged([a, b])
    shown, _ = view.window(both, rows)
    assert shown[0] is both[0] and shown[0].text == "b 100" and len(shown) == rows


def _key(ucs: str = "", code: int | None = None, name: str | None = None) -> Any:
    """A `blessed` keystroke built by hand, no terminal opened."""
    from blessed.keyboard import Keystroke

    return Keystroke(ucs, code=code, name=name)


@pytest.mark.parametrize(
    ("ucs", "code", "name", "mapped"),
    [
        ("\x1b[A", 259, "KEY_UP", "up"),
        ("\x1b[B", 258, "KEY_DOWN", "down"),
        ("\x1b[6~", 338, "KEY_PGDOWN", "pgdn"),
        ("\x1b[H", 262, "KEY_HOME", "home"),
        ("\x1b", 361, "KEY_ESCAPE", "esc"),
        ("\n", 343, "KEY_ENTER", "enter"),
        ("\x7f", 263, "KEY_BACKSPACE", "backspace"),
        ("/", None, None, "/"),
        ("q", None, None, "q"),
        ("\x03", None, None, "ctrl-c"),
        ("", None, None, ""),  # the timeout: no key
        ("\x1b[15~", 270, "KEY_F5", ""),  # unbound
    ],
)
def test_a_blessed_keystroke_maps_to_the_views_key_name(
    ucs: str, code: int | None, name: str | None, mapped: str
) -> None:
    assert screen.key_name(_key(ucs, code, name)) == mapped


def test_the_footer_says_which_keys_there_are() -> None:
    m = _fed([0.0])
    assert screen.footer(m).plain == "Ctrl-C to quit"
    keyed = View()
    keyed.keys = True
    assert screen.footer(m, keyed).plain == "? keys  / filter  q quit"


class Term:
    """A stand-in terminal: `cbreak()` recorded, `inkey` scripted."""

    def __init__(self, keys: list[Any]) -> None:
        self.log: list[str] = []
        self.keys = list(keys)

    @contextlib.contextmanager
    def cbreak(self) -> Iterator[None]:
        self.log.append("in")
        try:
            yield
        finally:
            self.log.append("out")

    def inkey(self, timeout: float) -> Any:
        if not self.keys:
            threading.Event().wait(0.05)
            return _key("")
        key = self.keys.pop(0)
        if isinstance(key, BaseException):
            raise key
        return key


class Stub:
    """A stand-in link: idle answers, or a refusal."""

    def __init__(self, refuse: bool = False) -> None:
        self.base, self.refuse = "http://127.0.0.1:9/", refuse

    def want(self, _wants: Any) -> None:
        pass

    def items(self) -> Iterator[Any]:
        if self.refuse:
            raise ChantierError("live: this board needs the link with its key", EXIT_EXTERNAL)
        while True:
            threading.Event().wait(0.05)
            yield Idle()


@pytest.mark.parametrize("case", ["q", "ctrl-c key", "interrupt", "refusal", "drawing"])
def test_watch_leaves_on_every_exit_and_gives_the_terminal_back(
    case: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    from rich.console import Console

    keys: dict[str, list[Any]] = {
        "q": [_key("q")],
        "ctrl-c key": [_key("\x03")],
        "interrupt": [KeyboardInterrupt()],
    }
    term = Term(keys.get(case, []))
    console = Console(file=io.StringIO(), force_terminal=True, width=100, height=20)
    if case == "drawing":

        def boom(*_a: Any, **_k: Any) -> None:
            raise RuntimeError("drawing broke")

        monkeypatch.setattr(screen, "render", boom)
    stubs: list[Any] = [Stub(case == "refusal")]
    models = [Model(base="http://127.0.0.1:9/")]
    if case == "refusal":
        with pytest.raises(ChantierError, match=r"with its key \(board http://127\.0\.0\.1:9/\)$"):
            live_command.watch(stubs, models, term=term, console=console)
    elif case == "drawing":
        with pytest.raises(RuntimeError, match="drawing broke"):
            live_command.watch(stubs, models, term=term, console=console)
    else:
        live_command.watch(stubs, models, term=term, console=console)
    assert term.log == ["in", "out"]
    if sys.platform != "win32":  # SIGTERM's own handler is put back
        assert signal.getsignal(signal.SIGTERM) in (signal.SIG_DFL, signal.SIG_IGN)


def test_once_refuses_an_unserved_only_before_the_reader_keeps_its_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The forced interleaving: every model is complete (the readers fed the last answer) before
    any reader's `--only` error is kept; `once` still ends with the `--only` sentence."""
    models = [Model(only=["nope"], base="http://a/"), Model(only=["nope"], base="http://b/")]

    def start(links: Any, models: list[Model], *_a: Any) -> tuple[list[Any], list[Any]]:
        for m in models:
            m.feed(Event("board", "board", {"projects": [{"id": "p"}]}, NOW))
        return [], []  # no error kept yet

    monkeypatch.setattr(live_command, "_start", start)
    with pytest.raises(ChantierError, match="--only nope: no board serves it") as e:
        stubs: list[Any] = [Stub(), Stub()]
        live_command.once(stubs, models)
    assert e.value.code == EXIT_USAGE
