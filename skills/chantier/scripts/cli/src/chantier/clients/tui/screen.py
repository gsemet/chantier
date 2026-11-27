"""The drawing of `chantier live`: one function from the models (one per board) and a size to a Rich
renderable, and the loop that redraws it once a second, so the lease times count down between
events, and reads the keys and the mouse. Rich and `blessed` load here, when `live` runs.

A header (the board or boards, the transport, the link's state, the server's time with its UTC
offset and the four counts), a left column (projects, agents), the flow in the centre (newest
first, the live end at the top) and, on the right, Ready (the PRs to review or to merge) above the
tasks. Boxes are rounded; the Flow, Ready and Tasks are tables with a header row. One panel is
active (its title starts with `▸`, so it reads without colour): Tab moves it, the scroll keys move
it only, `m` maximizes it over the whole body. The Flow's `Ago` column is as wide as the widest
time drawn (3 to 8 columns) and right-aligned. Text is only cut with `…`, never wrapped; no colour
carries a meaning alone (each state has its word).

The widths of the left and right columns and of the Flow's `Project` and `Who`, and how a narrow
screen closes them up, are `widths.py`'s. The `Time` column's width counts in both modes, so `t`
never hides the left column.

The mouse is turned on just after the first screen, when the terminal handles it, and off before
the screen is given back: a drag of a border between two columns sizes the left or the right one,
the width kept in `live.json`, and the wheel scrolls the active panel (`mouse.py`). While it is on,
the footer and the help say what it does."""

from __future__ import annotations

import contextlib
import sys
import threading
import time
from collections.abc import Callable
from typing import Any

from chantier.clients.tui import mouse
from chantier.clients.tui.boxes import agents_table, project_lines, projects_table, tasks
from chantier.clients.tui.model import Model, merged
from chantier.clients.tui.parts import (
    COUNT_COLOURS,
    STATE_COLOURS,
    dim,
    grid,
    models_of,
    panel,
    table,
    watched,
)
from chantier.clients.tui.ready import ready, ready_rows
from chantier.clients.tui.times import since
from chantier.clients.tui.view import HELP, MOUSE_FOOTER, MOUSE_HELP, View
from chantier.clients.tui.widths import TIME_W, Widths, column_widths

CR_W = 9
AGO_MIN, AGO_MAX = 3, 8  # the Flow's `Ago` column: as wide as its widest text, within these
FOOTER_H, BORDERS, HEADER_ROW = 1, 2, 1
REDRAW_S = 1.0
KEYS_FOOTER = "? keys  / filter  Tab panel  m max  t time  q quit"
NO_KEYS_FOOTER = "Ctrl-C to quit"
KEY_NAMES = {
    "KEY_UP": "up",
    "KEY_DOWN": "down",
    "KEY_PGUP": "pgup",
    "KEY_PGDOWN": "pgdn",
    "KEY_HOME": "home",
    "KEY_END": "end",
    "KEY_ENTER": "enter",
    "KEY_ESCAPE": "esc",
    "KEY_BACKSPACE": "backspace",
    "KEY_TAB": "tab",
    "KEY_BTAB": "btab",
}


def header_height(models: list[Model]) -> int:
    """2 lines with one board, `2 + n` with `n` boards (one line each)."""
    return 2 if len(models) == 1 else 2 + len(models)


def body_height(models: list[Model], height: int) -> int:
    """The body's height, the boxes' borders included."""
    return max(height - header_height(models) - FOOTER_H, 0)


def body_rows(models: list[Model], height: int) -> int:
    """The lines of the Flow's table under its header row (a maximized table's too)."""
    return max(body_height(models, height) - BORDERS - HEADER_ROW, 0)


def counts(models: list[Model]) -> dict[str, int]:
    """The four counts, summed over the boards."""
    out: dict[str, int] = {}
    for m in models:
        for k, v in m.counts().items():
            out[k] = out.get(k, 0) + v
    return out


def header(models: Model | list[Model]) -> Any:
    from rich.text import Text

    models = models_of(models)
    clock = models[0].clock_text()
    lines = []
    if len(models) == 1:
        m = models[0]
        board = m.board or {}
        version = board.get("version")
        first = ["chantier live", str(board.get("served") or ""), f"v{version}" if version else ""]
        first += [m.transport or "", m.link_word(), clock]
        lines.append("  ".join(x for x in first if x))
    else:
        lines.append(f"chantier live  {len(models)} boards  {clock}")
        for m in models:
            board = m.board or {}
            version = board.get("version")
            state = " ".join(x for x in (m.transport or "", m.link_word()) if x)
            line = [
                m.label,
                m.base,
                str(board.get("served") or ""),
                f"v{version}" if version else "",
            ]
            lines.append("  ".join(x for x in [*line, state] if x))
    text = Text("\n".join(lines), no_wrap=True, overflow="ellipsis")
    text.append("\n")
    for i, (k, v) in enumerate(counts(models).items()):
        if i:
            text.append("  ")
        text.append(f"{k} {v}", style=f"bold {STATE_COLOURS[COUNT_COLOURS[k]]}")
    return text


def flow(models: Model | list[Model], rows: int, view: View | None, widths: Widths) -> Any:
    """The window of the lines the view gives (the newest first; the newest lines while it
    follows live): time (or time since, as wide as its widest text and right-aligned), project
    (when several), who, text. `Project` and `Who` are as wide as `widths` says (`column_widths`:
    `Who` closes up first, then `Project`); the text takes the rest."""
    models, view = models_of(models), view or View()
    several = len(watched(models)) > 1
    kept = [x for x in merged(models) if x.holds(view.text)]
    shown, title = view.window(kept, rows)
    first = models[0]
    whens = [since(x.t, first.now()) if view.ago else first.stamp(x.t) for x in shown]
    if view.ago:
        widest = max((len(x) for x in whens), default=0)
        time_head = ("Ago", min(max(widest, AGO_MIN), AGO_MAX))
    else:
        time_head = ("Time", TIME_W)
    right = ("Ago",) if view.ago else ()
    who = ("Who", widths.who)
    if several:
        t = table(time_head, ("Project", widths.project), who, ("Event", None), right=right)
    else:
        t = table(time_head, who, ("Event", None), right=right)
    for line, when in zip(shown, whens, strict=True):
        project = f"{line.board}/{line.project}" if line.board else line.project
        cells = [dim(when), project, dim(line.who), line.text]
        t.add_row(*(cells if several else [cells[0], *cells[2:]]))
    return panel(t, view.title("flow", title))


def tasks_height(models: list[Model]) -> int:
    """The lines Tasks' table needs under its header row, no filter."""
    rows = [r for m in models for _, r in m.rows()]
    working = sum(1 for r in rows if r.get("state") == "working")
    blocked = sum(1 for r in rows if r.get("state") == "blocked")
    return 2 * working + blocked or 1


def footer(models: Model | list[Model], view: View | None = None) -> Any:
    from rich.text import Text

    models, view = models_of(models), view or View()
    text = KEYS_FOOTER if view.keys else NO_KEYS_FOOTER
    if view.typing is not None:
        text += f"  /{view.typing}"
    elif view.text:
        text += f"  filter: {view.text}"
    more = [m.named(p) for m in models for p in m.not_watched()]
    if more:
        text += f"   {len(more)} more projects not watched: {', '.join(more)}"
    if view.tracking:  # last, so that a narrow footer cuts them first
        text += f"   {MOUSE_FOOTER}"
    return Text(text, no_wrap=True, overflow="ellipsis")


def _help_panel(view: View) -> Any:
    t = grid(14, None)
    for key, effect in HELP + (MOUSE_HELP if view.tracking else ()):
        t.add_row(key, effect)
    t.add_row("", "")
    t.add_row("", "any key closes this help")
    return panel(t, "Keys")


def _boxed(lines: int) -> int:
    """A box's height for this many lines under its borders."""
    return lines + BORDERS


def _plan(
    models: list[Model], width: int, height: int, view: View
) -> tuple[list[str], dict[str, int], int, int]:
    """The panels drawn at this width, the lines each shows, and the two heights the layout gives
    (Ready's box, Projects' box)."""
    drawn = ["projects", "agents"] if column_widths(models, width, view).left else []
    drawn += ["flow", "ready", "tasks"]
    total = body_height(models, height)
    half = total // 2
    ready_h = min(_boxed(HEADER_ROW + max(len(ready_rows(models, view)), 1)), half)
    projects_h = min(_boxed(project_lines(models)), half)
    rows = body_rows(models, height)
    if view.maximized:
        lines = {p: rows for p in ("flow", "ready", "tasks")}
        lines |= {p: rows + HEADER_ROW for p in ("projects", "agents")}
    else:
        lines = {
            "flow": rows,
            "ready": ready_h - BORDERS - HEADER_ROW,
            "tasks": total - ready_h - BORDERS - HEADER_ROW,
            "projects": projects_h - BORDERS,
            "agents": total - projects_h - BORDERS,
        }
    return drawn, {k: max(v, 0) for k, v in lines.items()}, ready_h, projects_h


def _maximized(models: list[Model], width: int, rows: dict[str, int], view: View) -> Any:
    """The active panel alone, over the whole body."""
    if view.active == "flow":
        widths = column_widths(models, width, view, maximized=True)
        return flow(models, rows["flow"], view, widths)
    if view.active == "ready":
        return ready(models, view, width, rows["ready"])
    if view.active == "tasks":
        return tasks(models, view, rows["tasks"])
    if view.active == "projects":
        body = projects_table(models, view, rows["projects"])
        return panel(body, view.title("projects", "Projects"))
    return panel(agents_table(models, view, rows["agents"]), view.title("agents", "Agents"))


def render(
    models: Model | list[Model],
    width: int,
    height: int,
    view: View | None = None,
) -> Any:
    """The whole screen at this size."""
    from rich.layout import Layout

    models, view = models_of(models), view or View()
    root = Layout()
    root.split_column(
        Layout(header(models), size=header_height(models)),
        Layout(name="body"),
        Layout(footer(models, view), size=FOOTER_H),
    )
    drawn, rows, ready_h, projects_h = _plan(models, width, height, view)
    view.settle(drawn)
    if view.help:
        root["body"].update(_help_panel(view))
        return root
    if view.maximized:
        root["body"].update(_maximized(models, width, rows, view))
        view.moves.clear()
        return root
    widths = column_widths(models, width, view)
    right = Layout(size=widths.right)
    right.split_column(
        Layout(ready(models, view, widths.right, rows["ready"]), size=ready_h),
        Layout(tasks(models, view, rows["tasks"])),
    )
    columns = [Layout(flow(models, rows["flow"], view, widths)), right]
    if widths.left:
        column = Layout(size=widths.left)
        column.split_column(
            Layout(
                panel(
                    projects_table(models, view, rows["projects"]),
                    view.title("projects", "Projects"),
                ),
                size=projects_h,
            ),
            Layout(
                panel(agents_table(models, view, rows["agents"]), view.title("agents", "Agents"))
            ),
        )
        columns.insert(0, column)
    root["body"].split_row(*columns)
    view.moves.clear()
    return root


def plain(
    models: Model | list[Model],
    width: int,
    height: int,
    file: Any,
    view: View | None = None,
) -> None:
    """The screen printed once as plain text (no colour, no link, no control code), for
    `--once`."""
    from rich.console import Console

    console = Console(
        file=file,
        width=width,
        height=height,
        color_system=None,
        force_terminal=False,
        force_interactive=False,
        no_color=True,
        highlight=False,
        emoji=False,
        legacy_windows=False,
    )
    with console.capture() as captured:
        console.print(render(models, width, height, view))
    file.write("".join(x.rstrip() + "\n" for x in captured.get().splitlines()))


def key_name(key: Any) -> str:
    """The name `View.press` takes for a `blessed` keystroke; empty for no key or an unbound one."""
    if key.is_sequence:
        return KEY_NAMES.get(key.name or "", "")
    text = str(key)
    if text == "\x03":
        return "ctrl-c"
    if text == "\t":
        return "tab"
    return text if len(text) == 1 and text.isprintable() else ""


def _event(models: list[Model], view: View, key: Any, size: tuple[int, int]) -> tuple[bool, bool]:
    """One keystroke, a key or a mouse event, on a screen of this size (columns, lines): whether
    the screen should quit, and whether what is drawn changes."""
    if name := key_name(key):
        return view.press(name), True
    width, height = size
    body = range(header_height(models), height - FOOTER_H)
    return False, mouse.handle(models, view, key, width, body)


def run(  # noqa: PLR0913, PLR0917 - the arguments the loop is given
    models: list[Model],
    view: View,
    lock: threading.Lock,
    alive: Callable[[], bool],
    term: Any = None,
    console: Any = None,
) -> None:
    """Redraw once a second until `alive` is false, `q` or Ctrl-C (an interrupt the caller
    handles); a key, or a mouse event that changes the screen, redraws at once. Every way out gives
    the terminal back. With no `term` and no terminal on stdin there are no keys; `term` is a
    `blessed.Terminal` or a stand-in (`cbreak`, `inkey`, `does_mouse`, `mouse_enabled`)."""
    from rich.console import Console
    from rich.live import Live

    if term is None and sys.stdin.isatty():
        from blessed import Terminal

        term = Terminal()
    console = console or Console()
    view.keys = term is not None

    def frame() -> Any:
        with lock:
            return render(models, console.width, console.height, view)

    def loop(live: Any) -> None:
        next_at = time.monotonic() + REDRAW_S
        while alive():
            if term is None:
                time.sleep(REDRAW_S)
                live.update(frame(), refresh=True)
                continue
            key = term.inkey(timeout=max(0.0, next_at - time.monotonic()))
            with lock:
                quits, changed = _event(models, view, key, console.size)
            if quits:
                return
            now = time.monotonic()
            if changed or now >= next_at:
                live.update(frame(), refresh=True)
                if now >= next_at:
                    next_at = now + REDRAW_S

    with (
        term.cbreak() if term is not None else contextlib.nullcontext(),
        Live(frame(), console=console, screen=True, auto_refresh=False) as live,
        mouse.tracked(term, view),  # only now: the first screen is drawn
    ):
        loop(live)
