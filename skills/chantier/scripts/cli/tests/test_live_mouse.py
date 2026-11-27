"""The live view's mouse (a stand-in terminal's events), which sizes the side columns, and
`live.json`, which keeps their widths. No network and no terminal."""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import re
import threading
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from live_world import HIGH, fed
from test_live_model import Term

from chantier.clients.tui import mouse, screen, widths
from chantier.clients.tui.model import Model
from chantier.clients.tui.view import HELP, MOUSE_HELP, View
from chantier.commands import live as live_command
from chantier.core.errors import EXIT_PRECONDITION, ChantierError

WIDE_OPEN = 200  # a terminal on which the default widths all fit
LEFT, MIDDLE, RIGHT = 0, 1, 2  # the SGR mouse buttons
MOVE, NO_BUTTON, UP, DOWN, SHIFT = 32, 35, 64, 65, 4
BODY, ROW = range(2, HIGH - 1), 5  # one board: two header lines, one footer line


def _event(button: int, x: int, y: int = ROW, released: bool = False) -> Any:
    """A mouse event as `blessed` reads it from an SGR report."""
    from blessed.keyboard import resolve_sequence

    report = f"\x1b[<{button};{x + 1};{y + 1}{'m' if released else 'M'}"
    return resolve_sequence(report, {}, {}, set(), dec_mode_cache={1006: 1})


def _typed(text: str) -> Any:
    from blessed.keyboard import Keystroke

    return Keystroke(text)


def _drag(x: int, to: int) -> list[Any]:
    return [_event(LEFT, x), _event(MOVE, to), _event(LEFT, to, released=True)]


def _give(m: Model, view: View, width: int, events: list[Any]) -> list[bool]:
    return [mouse.handle([m], view, e, width, BODY) for e in events]


def _plain(m: Model, view: View, width: int) -> list[str]:
    out = io.StringIO()
    screen.plain(m, width, HIGH, out, view)
    return out.getvalue().splitlines()


def _sides(m: Model, view: View, width: int) -> tuple[int, int, int]:
    """As drawn: the left column's width, the right one's and the Flow's `Who`."""
    lines = _plain(m, view, width)
    at = next(i for i, x in enumerate(lines) if "Ready" in x and "╭" in x)
    flow, ready = (re.search(rf"╭─ (▸ )?{x}", lines[at]) for x in ("Flow", "Ready"))
    assert flow and ready
    head = lines[at + 1][flow.start() : ready.start()]
    who = head.index("Event") - head.index("Who") - 1
    return flow.start(), width - ready.start(), who


def _kept(left: int, right: int) -> View:
    view = View()
    view.left, view.right = left, right
    return view


class Mouse(Term):
    """A stand-in terminal with a mouse: its calls recorded, and what was on the screen at each."""

    def __init__(self, keys: list[Any], handles: bool = True) -> None:
        super().__init__(keys)
        self.handles, self.out = handles, io.StringIO()
        self.asked: list[dict[str, Any]] = []
        self.first = ""  # what was written before the first mouse question
        self.written: list[int] = []  # the screen's length at each `inkey`

    def does_mouse(self, **asked: Any) -> bool:
        self.log.append("does_mouse")
        self.asked.append(asked)
        self.first = self.out.getvalue()
        return self.handles

    @contextlib.contextmanager
    def mouse_enabled(self, **asked: Any) -> Iterator[None]:
        self.log.append("on")
        self.asked.append(asked)
        try:
            yield
        finally:
            self.log.append("off")

    def inkey(self, timeout: float) -> Any:
        self.written.append(len(self.out.getvalue()))
        return super().inkey(timeout)


def _run(term: Mouse, view: View, width: int = WIDE_OPEN) -> None:
    from rich.console import Console

    console = Console(
        file=term.out,
        force_terminal=True,
        color_system=None,
        legacy_windows=False,  # else the width is one less on Windows
        width=width,
        height=HIGH,
    )
    screen.run([fed([0.0])], view, threading.Lock(), lambda: True, term, console)


@pytest.mark.parametrize("handles", [True, False])
def test_the_first_screen_comes_before_the_mouse_and_early_keys_are_kept(handles: bool) -> None:
    term = Mouse([_typed("?"), _typed("x"), _typed("\t"), _typed("q")], handles)
    view = View()
    _run(term, view)
    asked = {"clicks": True, "report_drag": True, "timeout": 1.0}
    assert term.asked == [asked] * (2 if handles else 1)
    assert term.log == ["in", "does_mouse", *(["on", "off"] if handles else []), "out"]
    assert screen.KEYS_FOOTER in term.first and "drag a border" not in term.first
    assert view.tracking is handles and view.active == "ready" and not view.help
    later = term.out.getvalue()[len(term.first) :]
    assert ("drag a border" in later) is handles
    assert ("Shift-drag" in later) is handles


@pytest.mark.parametrize("tracking", [True, False])
def test_the_help_and_a_narrow_footer_with_the_mouse_words(tracking: bool) -> None:
    m, view = fed([0.0]), View()
    view.keys, view.tracking = True, tracking
    view.press("?")
    text = "\n".join(_plain(m, view, WIDE_OPEN))
    assert all(key in text for key, _ in HELP) and "any key closes" in text
    assert all((key in text) is tracking for key, _ in MOUSE_HELP)
    view.press("x")
    for keys, shown in ((["/", "a", "b"], "/ab"), (["enter"], "filter: ab")):
        for key in keys:
            view.press(key)
        footer = _plain(m, view, 90)[-1]
        assert shown in footer and "Ctrl-click" not in footer
        assert ("drag a" in footer) is tracking


@pytest.mark.parametrize(
    ("x", "by", "want"),
    [  # either panel border of each of the two pairs, on a 200 wide screen
        (41, 6, (48, 44)),
        (42, -6, (36, 44)),
        (155, -6, (42, 50)),
        (156, 6, (42, 38)),
    ],
)
def test_a_drag_of_a_border_sizes_its_column_and_writes_once_on_release(
    x: int,
    by: int,
    want: tuple[int, int],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    saved: list[tuple[int, int]] = []

    def save(where: Path, left: int, right: int) -> None:
        saved.append((left, right))
        widths.save(where, left, right)

    monkeypatch.setattr(mouse, "save", save)
    monkeypatch.setattr(screen, "REDRAW_S", 600.0)  # only the events redraw
    nothing = [
        _event(UP, 100),
        *_drag(100, 110),  # a click elsewhere
        _event(RIGHT, x),  # the other buttons, on the border
        _event(MIDDLE, x),
        _event(LEFT, x, y=0),  # in the header's rows
        _event(LEFT, x, released=True),  # no drag started
        *_drag(x, x),  # pressed and released where it is
        _typed("t"),
        _event(NO_BUTTON, x + 3),
    ]
    events = [*nothing, *_drag(x, x + by), _typed("q")]
    term, view = Mouse(events), View()
    view.file = tmp_path / "new" / widths.FILE
    _run(term, view)
    assert (view.left, view.right) == want and saved == [want]
    text = view.file.read_text(encoding="utf-8")
    assert json.loads(text) == {"left": want[0], "right": want[1]}
    assert [p.name for p in view.file.parent.iterdir()] == [widths.FILE]
    assert _sides(fed([0.0]), view, WIDE_OPEN)[:2] == want
    redrawn = [b > a for a, b in zip(term.written, term.written[1:], strict=False)]
    assert not redrawn[len(nothing) - 1] and redrawn[len(nothing) + 1]  # bare motion; the drag


@pytest.mark.parametrize(
    ("width", "kept", "x", "to", "during", "after"),
    [  # `during`: drawn while dragging; `after`: kept at the release
        (140, (42, 44), 40, 0, (20, 44), (20, 44)),  # the left minimum
        (140, (42, 44), 40, 139, (46, 44), (46, 44)),  # the central column's
        (140, (42, 44), 96, 139, (41, 30), (42, 30)),  # the right minimum
        (140, (42, 44), 96, 0, (41, 49), (42, 49)),
        # drawn narrower than kept: the other column stays as drawn, and its kept width is kept
        (130, (42, 60), 30, 25, (26, 44), (26, 60)),
        (130, (42, 60), 31, 129, (36, 44), (36, 60)),
        (130, (42, 60), 86, 90, (31, 40), (42, 40)),
        # the central column already under its minimum: the column narrows, never widens
        (90, (42, 44), 46, 0, (0, 44), (42, 44)),
        (90, (42, 44), 46, 50, (0, 40), (42, 40)),
    ],
)
def test_a_drag_stops_at_the_minimums_and_keeps_the_other_column(  # noqa: PLR0913, PLR0917
    width: int,
    kept: tuple[int, int],
    x: int,
    to: int,
    during: tuple[int, int],
    after: tuple[int, int],
    tmp_path: Path,
) -> None:
    m, view = fed([0.0]), _kept(*kept)
    view.file = tmp_path / widths.FILE
    press, move, release = _drag(x, to)
    _give(m, view, width, [press, move])
    assert _sides(m, view, width)[:2] == during
    _give(m, view, width, [release])
    assert view.drag is None and (view.left, view.right) == after
    assert view.file.exists() is (after != kept)
    if after != kept:
        assert widths.load(view.file) == after


@pytest.mark.parametrize("key", ["?", "m"])
def test_no_drag_under_the_help_or_a_maximized_panel(key: str, tmp_path: Path) -> None:
    m, view = fed([0.0]), View()
    view.file = tmp_path / widths.FILE
    press, move, release = _drag(41, 30)
    _give(m, view, WIDE_OPEN, [press, move])
    view.press(key)  # during a drag: it is dropped
    assert view.drag is None
    assert not any(_give(m, view, WIDE_OPEN, [release, press, move, release]))
    assert (view.left, view.right) == (42, 44) and not view.file.exists()


def test_a_key_drops_a_drag_whose_release_never_came_and_nothing_is_written(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    saved: list[tuple[int, int]] = []
    monkeypatch.setattr(mouse, "save", lambda _file, *both: saved.append(both))
    # a key the view takes and one with no use here drop it; a wait that ran out and the wheel,
    # no keys, leave it to the release
    lost, (press, move, release) = _drag(41, 25), _drag(41, 30)
    dropped = [e for key in ("t", "\x01") for e in (*lost[:2], _typed(key), lost[2])]
    kept = [press, move, _typed(""), _event(UP, 100), release]
    view = View()
    view.file = tmp_path / widths.FILE
    _run(Mouse([*dropped, *kept, _typed("q")]), view)
    assert saved == [(31, 44)] == [(view.left, view.right)]


@pytest.mark.parametrize(
    ("buttons", "keys"),
    [([DOWN, DOWN, UP], ["down", "down", "up"]), ([DOWN | SHIFT], [])],
)
def test_the_wheel_is_up_and_down_but_not_under_the_help_or_a_filter(
    buttons: list[int], keys: list[str]
) -> None:
    m, wheeled, keyed = fed([0.0]), View(), View()
    for view in (wheeled, keyed):
        view.active = "agents"
    _give(m, wheeled, WIDE_OPEN, [_event(b, 100) for b in buttons])
    for key in keys:
        keyed.press(key)
    assert wheeled.moves == keyed.moves and len(wheeled.moves) == len(keys)
    for key in ("?", "/"):
        view = View()
        view.press(key)
        assert not any(_give(m, view, WIDE_OPEN, [_event(b, 100) for b in buttons]))
        assert view.moves == [] and view.help is (key == "?")


def _args(once: bool) -> argparse.Namespace:
    return argparse.Namespace(once=once, url=[], only=[], transport="auto")


class _Terminal(io.StringIO):
    def isatty(self) -> bool:
        return True


@pytest.mark.parametrize(
    ("content", "want"),
    [
        (None, (42, 44)),
        ('{"left": 20, "right": 30}', (20, 30)),
        ('﻿{"left": 900}', (900, 44)),
        ('{"right": 31}', (42, 31)),
        ("not json", "Expecting value"),
        ("[42, 44]", "not an object"),
        ('{"left": "42"}', "`left` is not an integer"),
        ('{"right": 44.0}', "`right` is not an integer"),
        ('{"left": true}', "`left` is not an integer"),
        ('{"left": 19}', "`left` is under 20"),
        ('{"right": 29}', "`right` is under 30"),
        ('{"left": 42, "flow": 1}', "unknown key 'flow'"),
        (b"\xff", "codec"),
    ],
)
def test_live_reads_live_json_before_it_connects_or_refuses(
    content: str | bytes | None,
    want: tuple[int, int] | str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CHANTIER_CONFIG_HOME", str(tmp_path))
    file = tmp_path / widths.FILE
    if content is not None:
        file.write_bytes(content if isinstance(content, bytes) else content.encode())
    asked: list[bool] = []
    views: list[View] = []

    def boards(_args: argparse.Namespace) -> tuple[list[tuple[str, str]], bool]:
        asked.append(True)
        return [("http://127.0.0.1:9/", "k")], False

    monkeypatch.setattr("sys.stdout", _Terminal())
    monkeypatch.setattr(live_command, "_boards", boards)
    monkeypatch.setattr(live_command, "watch", lambda _l, _m, view: views.append(view))
    if isinstance(want, str):
        with pytest.raises(ChantierError) as refused:
            live_command.live(_args(once=False))
        said = str(refused.value)
        assert refused.value.code == EXIT_PRECONDITION and not asked
        assert said.startswith(f"live: {file}: ") and said.endswith(": fix or delete it")
        assert want in said and "\n" not in said
    else:
        live_command.live(_args(once=False))
        assert [(v.left, v.right, v.file) for v in views] == [(*want, file)]


@pytest.mark.parametrize("content", [None, '{"left": 20, "right": 90}', "not json"])
def test_once_draws_the_defaults_and_leaves_live_json_alone(
    content: str | None,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("CHANTIER_CONFIG_HOME", str(tmp_path))
    file = tmp_path / widths.FILE
    if content is not None:
        file.write_text(content, encoding="utf-8")
    monkeypatch.setattr(live_command, "_boards", lambda _a: ([("http://x/", "k")], False))

    def answered(_links: Any, models: list[Model], *_a: Any) -> tuple[list[Any], list[Any]]:
        models[0] = fed([0.0])  # the board's answers
        return [], []

    monkeypatch.setattr(live_command, "_start", answered)
    monkeypatch.setattr(live_command, "_width", lambda: WIDE_OPEN)
    monkeypatch.setattr(live_command, "ONCE_S", 0.0)
    live_command.live(_args(once=True))
    top = next(x for x in capsys.readouterr().out.splitlines() if "╭─ ▸ Flow" in x)
    assert (top.index("╭─ ▸ Flow"), WIDE_OPEN - top.index("╭─ Ready")) == (42, 44)
    assert (file.read_text(encoding="utf-8") if file.exists() else None) == content


@pytest.mark.parametrize("case", ["interrupt", "write fails"])
def test_the_mouse_is_off_again_on_every_way_out(case: str, tmp_path: Path) -> None:
    (tmp_path / "taken").write_text("a file where the folder should be", encoding="utf-8")
    view = View()
    view.file = tmp_path / "taken" / widths.FILE
    events = [KeyboardInterrupt()] if case == "interrupt" else _drag(41, 30)
    term = Mouse(list(events))
    expected: type[BaseException] = KeyboardInterrupt if case == "interrupt" else ChantierError
    with pytest.raises(expected) as left:
        _run(term, view)
    assert term.log == ["in", "does_mouse", "on", "off", "out"]
    if case == "write fails":
        said = str(left.value)
        assert said.startswith(f"live: {view.file}: not written: ") and "\n" not in said
