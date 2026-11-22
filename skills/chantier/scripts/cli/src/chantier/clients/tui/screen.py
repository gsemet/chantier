"""The drawing of `chantier live`: one function from the models (one per board) and a size to a Rich
renderable, and the loop that redraws it once a second, so the lease times count down between
events, and reads the keys. Rich and `blessed` load here, when `live` runs.

A header (the board or boards, the transport, the link's state, the server's time and the four
counts), a left column (projects, agents; not drawn under 100 columns), the flow in the centre
(newest at the bottom) and the tasks on the right. Text is only cut with `…`, never wrapped; no
colour carries a meaning alone (each state has its word)."""

from __future__ import annotations

import contextlib
import sys
import threading
import time
from collections.abc import Callable
from typing import Any

from chantier.clients.tui.model import Model, age, hms, lease_left, merged
from chantier.clients.tui.view import HELP, View

NARROW = 100  # under this many columns, no left column
LEFT_W, RIGHT_W = 28, 44
PROJECT_W, WHO_W, CR_W = 10, 10, 9
FOOTER_H, BORDERS = 1, 2
REDRAW_S = 1.0
KEYS_FOOTER = "? keys  / filter  q quit"
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


def _grid(*widths: int | None) -> Any:
    """A table of text columns, each cut with `…`; a None width takes the rest."""
    from rich.table import Table

    t = Table.grid(padding=(0, 1), expand=True)
    for w in widths:
        if w is None:
            t.add_column(ratio=1, no_wrap=True, overflow="ellipsis")
        else:
            t.add_column(width=w, no_wrap=True, overflow="ellipsis")
    return t


def _panel(body: Any, title: str) -> Any:
    from rich import box
    from rich.panel import Panel

    return Panel(body, box.SQUARE, title=title, title_align="left", padding=(0, 1))


def _models(models: Model | list[Model]) -> list[Model]:
    return [models] if isinstance(models, Model) else models


def header_height(models: list[Model]) -> int:
    """2 lines with one board, `2 + n` with `n` boards (one line each)."""
    return 2 if len(models) == 1 else 2 + len(models)


def body_rows(models: list[Model], height: int) -> int:
    return max(height - header_height(models) - FOOTER_H - BORDERS, 0)


def _watched(models: list[Model]) -> list[tuple[Model, str]]:
    return [(m, p) for m in models for p in m.watched()]


def counts(models: list[Model]) -> dict[str, int]:
    """The four counts, summed over the boards."""
    out: dict[str, int] = {}
    for m in models:
        for k, v in m.counts().items():
            out[k] = out.get(k, 0) + v
    return out


def header(models: Model | list[Model]) -> Any:
    from rich.text import Text

    models = _models(models)
    clock = f"{models[0].now().strftime('%H:%M:%S')} UTC"
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
    second = "  ".join(f"{k} {v}" for k, v in counts(models).items())
    text = Text("\n".join(lines), no_wrap=True, overflow="ellipsis")
    text.append("\n" + second, style="bold")
    return text


def projects_table(models: list[Model]) -> Any:
    t = _grid(None)
    for m, p in _watched(models):
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


def agents_table(models: list[Model]) -> Any:
    t = _grid(None)
    several = len(_watched(models)) > 1
    found = [(m.named(project), text) for m in models for project, text in m.agents()]
    for project, text in found:
        t.add_row(f"{project} {text}" if several else text)
    if not found:
        t.add_row("none")
    return t


def left(models: list[Model]) -> Any:
    from rich.console import Group
    from rich.text import Text

    return _panel(
        Group(projects_table(models), Text(""), Text("Agents", style="bold"), agents_table(models)),
        "Projects",
    )


def flow(models: Model | list[Model], rows: int, view: View | None = None) -> Any:
    """The window of the lines the view gives (the last lines that fit while it follows live,
    newest at the bottom): time, project (when several), who, text."""
    models, view = _models(models), view or View()
    several = len(_watched(models)) > 1
    project_w = PROJECT_W + (2 if len(models) > 1 else 0)
    t = _grid(8, project_w, WHO_W, None) if several else _grid(8, WHO_W, None)
    kept = [x for x in merged(models) if x.holds(view.text)]
    shown, title = view.window(kept, rows)
    for line in shown:
        project = f"{line.board}/{line.project}" if line.board else line.project
        cells = [hms(line.t), project, line.who, line.text]
        t.add_row(*(cells if several else [cells[0], *cells[2:]]))
    return _panel(t, title)


def _working(t: Any, cr: str, r: dict[str, Any], now: Any) -> None:
    t.add_row(cr, str(r.get("title") or ""))
    left_ = lease_left(r.get("lease"), now)  # first: a cut never hides it
    detail = [f"lease {left_}" if left_ else ""]
    detail += [f"round {r.get('round')}/{r.get('round_limit')}", str(r.get("phase") or "")]
    t.add_row("", "  ".join(x for x in detail if x))


def _row_holds(text: str, m: Model, project: str, r: dict[str, Any]) -> bool:
    if not text:
        return True
    found = (m.label, project, m.named(project), r.get("cr"), r.get("title"), r.get("phase"))
    return any(text.casefold() in str(x or "").casefold() for x in found)


def tasks(models: Model | list[Model], view: View | None = None) -> Any:
    """The working CRs with their lease time left, then the CRs to review with their age, then
    the blocked ones with their reason; only those the filter keeps."""
    from rich.text import Text

    models, view = _models(models), view or View()
    t = _grid(CR_W + (2 if len(models) > 1 else 0), None)
    every = [(m, p, r) for m in models for p, r in m.rows()]
    rows = [(m, p, r) for m, p, r in every if _row_holds(view.text, m, p, r)]

    def cell(m: Model, r: dict[str, Any]) -> str:
        return f"{m.label} {r.get('cr')}" if m.label else str(r.get("cr"))

    drawn = 0
    for m, _, r in rows:
        if r.get("state") == "working":
            _working(t, cell(m, r), r, m.now())
            drawn += 1
    review = [(m, r) for m, _, r in rows if r.get("to_review")]
    if review:
        t.add_row(Text("to review", style="bold"), "")
    for m, r in review:
        t.add_row(cell(m, r), f"{age(r.get('handed_back_at'), m.now())}  {r.get('title') or ''}")
    blocked = [(m, r) for m, _, r in rows if r.get("state") == "blocked"]
    if blocked:
        t.add_row(Text("blocked", style="bold"), "")
    for m, r in blocked:
        t.add_row(cell(m, r), str(r.get("blocked") or "blocked"))
    if not every:
        t.add_row("", "no running batch")
    elif view.text and not (drawn or review or blocked):
        t.add_row("", f"no task matches {view.text}")
    return _panel(t, "Tasks")


def footer(models: Model | list[Model], view: View | None = None) -> Any:
    from rich.text import Text

    models, view = _models(models), view or View()
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
    t = _grid(14, None)
    for key, effect in HELP:
        t.add_row(key, effect)
    t.add_row("", "")
    t.add_row("", "any key closes this help")
    return _panel(t, "Keys")


def render(
    models: Model | list[Model],
    width: int,
    height: int,
    view: View | None = None,
) -> Any:
    """The whole screen at this size."""
    from rich.layout import Layout

    models, view = _models(models), view or View()
    root = Layout()
    root.split_column(
        Layout(header(models), size=header_height(models)),
        Layout(name="body"),
        Layout(footer(models, view), size=FOOTER_H),
    )
    if view.help:
        root["body"].update(_help_panel())
        return root
    rows = body_rows(models, height)
    columns = [Layout(flow(models, rows, view)), Layout(tasks(models, view), size=RIGHT_W)]
    if width >= NARROW:
        columns.insert(0, Layout(left(models), size=LEFT_W))
    root["body"].split_row(*columns)
    return root


def plain(
    models: Model | list[Model],
    width: int,
    height: int,
    file: Any,
    view: View | None = None,
) -> None:
    """The screen printed once as plain text (no control code), for `--once`."""
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
