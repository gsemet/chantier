"""The drawing of `chantier live`: one function from the models (one per board) and a size to a Rich
renderable, and the loop that redraws it once a second, so the lease times count down between
events, and reads the keys. Rich and `blessed` load here, when `live` runs.

A header (the board or boards, the transport, the link's state, the server's time with its UTC
offset and the four counts), a left column (projects, agents; not drawn under 100 columns), the
flow in the centre (newest at the bottom) and, on the right, Ready (the PRs to review or to merge)
above the tasks. Boxes are rounded; the Flow, Ready and Tasks are tables with a header row. Text is
only cut with `…`, never wrapped; no colour carries a meaning alone (each state has its word)."""

from __future__ import annotations

import contextlib
import sys
import threading
import time
from collections.abc import Callable
from typing import Any

from chantier.clients.tui.model import (
    LATE,
    Model,
    merged,
)
from chantier.clients.tui.parts import (
    COUNT_COLOURS,
    LEFT_W,
    RIGHT_W,
    STATE_COLOURS,
    coloured,
    cr_cell,
    dim,
    grid,
    models_of,
    panel,
    table,
    watched,
)
from chantier.clients.tui.ready import ready, ready_rows
from chantier.clients.tui.times import lease_left, since
from chantier.clients.tui.view import HELP, View

NARROW = 100  # under this many columns, no left column
PROJECT_W, WHO_W, CR_W = 10, 10, 9
TIME_W, STATE_W = 14, 7
FOOTER_H, BORDERS, HEADER_ROW = 1, 2, 1
REDRAW_S = 1.0
KEYS_FOOTER = "? keys  / filter  t time  q quit"
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
}


def header_height(models: list[Model]) -> int:
    """2 lines with one board, `2 + n` with `n` boards (one line each)."""
    return 2 if len(models) == 1 else 2 + len(models)


def body_height(models: list[Model], height: int) -> int:
    """The body's height, the boxes' borders included."""
    return max(height - header_height(models) - FOOTER_H, 0)


def body_rows(models: list[Model], height: int) -> int:
    """The lines of the Flow's table under its header row."""
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


def _project_lines(models: list[Model]) -> int:
    return 2 * len(watched(models))


def projects_table(models: list[Model]) -> Any:
    t = grid(None)
    for m, p in watched(models):
        line = (m.states.get(p) or {}).get("batch")
        b = line if isinstance(line, dict) else None
        board_line = next((x for x in m.projects() if x["id"] == p), {})
        where = f"{b['id']} {b.get('state')} {b.get('mode')}" if b else "no batch"
        ready = m.ready_count(p)
        found = f"inbox {board_line.get('inbox', 0)} backlog {board_line.get('backlog', 0)}"
        if ready is not None:
            found += f" ready {ready}"
        t.add_row(f"{m.named(p)}  {where}")
        t.add_row(f"  {found}")
    return t


def agent_lines(models: list[Model]) -> list[str]:
    """The Agents box's lines: each project's sessions (with its name when several are watched)."""
    several = len(watched(models)) > 1
    found = [(m.named(project), text) for m in models for project, text in m.agents()]
    return [f"{project} {text}" if several else text for project, text in found]


def agents_table(models: list[Model]) -> Any:
    from rich.text import Text

    t = grid(None)
    lines = agent_lines(models)
    for line in lines:
        late = line.endswith(LATE)
        text = Text(line[: -len(LATE)] if late else line, no_wrap=True, overflow="ellipsis")
        if late:
            text.append(LATE, style=f"bold {STATE_COLOURS['blocked']}")
        t.add_row(text)
    if not lines:
        t.add_row("none")
    return t


def flow(models: Model | list[Model], rows: int, view: View | None = None) -> Any:
    """The window of the lines the view gives (the last lines that fit while it follows live,
    newest at the bottom): time (or time since), project (when several), who, text."""
    models, view = models_of(models), view or View()
    several = len(watched(models)) > 1
    project_w = PROJECT_W + (2 if len(models) > 1 else 0)
    time_head = ("Ago" if view.ago else "Time", TIME_W)
    if several:
        t = table(time_head, ("Project", project_w), ("Who", WHO_W), ("Event", None))
    else:
        t = table(time_head, ("Who", WHO_W), ("Event", None))
    kept = [x for x in merged(models) if x.holds(view.text)]
    shown, title = view.window(kept, rows)
    first = models[0]
    for line in shown:
        project = f"{line.board}/{line.project}" if line.board else line.project
        when = since(line.t, first.now()) if view.ago else first.stamp(line.t)
        cells = [dim(when), project, dim(line.who), line.text]
        t.add_row(*(cells if several else [cells[0], *cells[2:]]))
    return panel(t, title)


def _working(t: Any, cr: str, r: dict[str, Any], now: Any) -> None:
    t.add_row(coloured("working", "working"), f"{cr}  {r.get('title') or ''}")
    left_ = lease_left(r.get("lease"), now)  # first: a cut never hides it
    detail = [f"lease {left_}" if left_ else ""]
    detail += [f"round {r.get('round')}/{r.get('round_limit')}", str(r.get("phase") or "")]
    t.add_row("", "  ".join(x for x in detail if x))


def _row_holds(text: str, m: Model, project: str, r: dict[str, Any]) -> bool:
    if not text:
        return True
    found = (m.label, project, m.named(project), r.get("cr"), r.get("title"), r.get("phase"))
    return any(text.casefold() in str(x or "").casefold() for x in found)


def tasks_height(models: list[Model]) -> int:
    """The lines Tasks' table needs under its header row, no filter."""
    rows = [r for m in models for _, r in m.rows()]
    working = sum(1 for r in rows if r.get("state") == "working")
    blocked = sum(1 for r in rows if r.get("state") == "blocked")
    return 2 * working + blocked or 1


def tasks(models: Model | list[Model], view: View | None = None) -> Any:
    """The working CRs with their lease time left, then the blocked ones with their reason; only
    those the filter keeps. The CRs to review are in Ready."""
    models, view = models_of(models), view or View()
    t = table(("State", STATE_W), ("Task", None))
    every = [(m, p, r) for m in models for p, r in m.rows()]
    rows = [(m, p, r) for m, p, r in every if _row_holds(view.text, m, p, r)]
    drawn = 0
    for m, _, r in rows:
        if r.get("state") == "working":
            _working(t, cr_cell(m, r), r, m.now())
            drawn += 1
    blocked = [(m, r) for m, _, r in rows if r.get("state") == "blocked"]
    for m, r in blocked:
        t.add_row(
            coloured("blocked", "blocked"),
            f"{cr_cell(m, r)}  {r.get('title') or ''}",
        )
        t.add_row("", str(r.get("blocked") or "blocked"))
    if not every:
        t.add_row("", "no running batch")
    elif view.text and not (drawn or blocked):
        t.add_row("", f"no task matches {view.text}")
    return panel(t, "Tasks")


# Ready


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
    return Text(text, no_wrap=True, overflow="ellipsis")


def _help_panel() -> Any:
    t = grid(14, None)
    for key, effect in HELP:
        t.add_row(key, effect)
    t.add_row("", "")
    t.add_row("", "any key closes this help")
    return panel(t, "Keys")


def _boxed(lines: int) -> int:
    """A box's height for this many lines under its borders."""
    return lines + BORDERS


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
    if view.help:
        root["body"].update(_help_panel())
        return root
    total = body_height(models, height)
    half = total // 2
    rows = body_rows(models, height)
    right = Layout(size=RIGHT_W)
    right.split_column(
        Layout(
            ready(models, view),
            size=min(_boxed(HEADER_ROW + max(len(ready_rows(models, view)), 1)), half),
        ),
        Layout(tasks(models, view)),
    )
    columns = [Layout(flow(models, rows, view)), right]
    if width >= NARROW:
        column = Layout(size=LEFT_W)
        column.split_column(
            Layout(
                panel(projects_table(models), "Projects"),
                size=min(_boxed(_project_lines(models)), half),
            ),
            Layout(panel(agents_table(models), "Agents")),
        )
        columns.insert(0, column)
    root["body"].split_row(*columns)
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
    return text if len(text) == 1 and text.isprintable() else ""


def run(  # noqa: PLR0913, PLR0917 - the arguments the loop is given
    models: list[Model],
    view: View,
    lock: threading.Lock,
    alive: Callable[[], bool],
    term: Any = None,
    console: Any = None,
) -> None:
    """Redraw the screen once a second until `alive` is false, `q` or Ctrl-C (an interrupt the
    caller handles); a key redraws at once. The terminal (`cbreak`, then Rich's alternate screen)
    is given back on every way out. With no `term` and a stdin that is not a terminal there are no
    keys and the loop sleeps; `term` is a `blessed.Terminal` or a stand-in with `cbreak()` and
    `inkey(timeout)`."""
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
            name = key_name(term.inkey(timeout=max(0.0, next_at - time.monotonic())))
            if name and view.press(name, body_rows(models, console.height)):
                return
            now = time.monotonic()
            if name or now >= next_at:
                live.update(frame(), refresh=True)
                if now >= next_at:
                    next_at = now + REDRAW_S

    keyed = term.cbreak() if term is not None else contextlib.nullcontext()
    with keyed, Live(frame(), console=console, screen=True, auto_refresh=False) as live:
        loop(live)
