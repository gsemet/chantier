"""The drawing of `chantier live`: one function from the model and a size to a Rich renderable, and
the loop that redraws it once a second, so the lease times count down between events. Rich loads
here, when `live` runs.

A header (the board, the transport, the link's state, the server's time and the four counts), a
left column (projects, agents; not drawn under 100 columns), the flow in the centre (newest at the
bottom) and the tasks on the right. Text is only cut with `…`, never wrapped; no colour carries a
meaning alone (each state has its word)."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from typing import Any

from chantier.clients.tui.model import Model, age, hms, lease_left

NARROW = 100  # under this many columns, no left column
LEFT_W, RIGHT_W = 28, 44
PROJECT_W, WHO_W, CR_W = 10, 10, 9
HEADER_H, FOOTER_H, BORDERS = 2, 1, 2
REDRAW_S = 1.0


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


def header(m: Model) -> Any:
    from rich.text import Text

    board = m.board or {}
    served = str(board.get("served") or "")
    version = board.get("version")
    first = ["chantier live", served, f"v{version}" if version else "", m.transport or ""]
    first += [m.link_word(), f"{m.now().strftime('%H:%M:%S')} UTC"]
    counts = m.counts()
    second = "  ".join(f"{k} {v}" for k, v in counts.items())
    text = Text("  ".join(x for x in first if x), no_wrap=True, overflow="ellipsis")
    text.append("\n" + second, style="bold")
    return text


def projects_table(m: Model) -> Any:
    t = _grid(None)
    for p in m.watched():
        line = (m.states.get(p) or {}).get("batch")
        b = line if isinstance(line, dict) else None
        board_line = next((x for x in m.projects() if x["id"] == p), {})
        where = f"{b['id']} {b.get('state')} {b.get('mode')}" if b else "no batch"
        ready = m.ready_count(p)
        counts = f"inbox {board_line.get('inbox', 0)} backlog {board_line.get('backlog', 0)}"
        if ready is not None:
            counts += f" ready {ready}"
        t.add_row(f"{p}  {where}")
        t.add_row(f"  {counts}")
    return t


def agents_table(m: Model) -> Any:
    t = _grid(None)
    several = len(m.watched()) > 1
    for project, text in m.agents():
        t.add_row(f"{project} {text}" if several else text)
    if not m.agents():
        t.add_row("none")
    return t


def left(m: Model) -> Any:
    from rich.console import Group
    from rich.text import Text

    return _panel(
        Group(projects_table(m), Text(""), Text("Agents", style="bold"), agents_table(m)),
        "Projects",
    )


def flow(m: Model, rows: int) -> Any:
    """The last lines that fit, newest at the bottom: time, project (when several), who, text."""
    several = len(m.watched()) > 1
    t = _grid(8, PROJECT_W, WHO_W, None) if several else _grid(8, WHO_W, None)
    for line in m.flow[-rows:] if rows > 0 else []:
        cells = [hms(line.t), line.project, line.who, line.text]
        t.add_row(*(cells if several else [cells[0], *cells[2:]]))
    return _panel(t, "Flow")


def _working(t: Any, r: dict[str, Any], now: Any) -> None:
    t.add_row(str(r.get("cr")), str(r.get("title") or ""))
    left_ = lease_left(r.get("lease"), now)  # first: a cut never hides it
    detail = [f"lease {left_}" if left_ else ""]
    detail += [f"round {r.get('round')}/{r.get('round_limit')}", str(r.get("phase") or "")]
    t.add_row("", "  ".join(x for x in detail if x))


def tasks(m: Model) -> Any:
    """The working CRs with their lease time left, then the CRs to review with their age, then
    the blocked ones with their reason."""
    from rich.text import Text

    now = m.now()
    t = _grid(CR_W, None)
    rows = [r for _, r in m.rows()]
    for r in rows:
        if r.get("state") == "working":
            _working(t, r, now)
    review = [r for r in rows if r.get("to_review")]
    if review:
        t.add_row(Text("to review", style="bold"), "")
    for r in review:
        t.add_row(str(r.get("cr")), f"{age(r.get('handed_back_at'), now)}  {r.get('title') or ''}")
    blocked = [r for r in rows if r.get("state") == "blocked"]
    if blocked:
        t.add_row(Text("blocked", style="bold"), "")
    for r in blocked:
        t.add_row(str(r.get("cr")), str(r.get("blocked") or "blocked"))
    if not rows:
        t.add_row("", "no running batch")
    return _panel(t, "Tasks")


def footer(m: Model) -> Any:
    from rich.text import Text

    text = "Ctrl-C to quit"
    more = m.not_watched()
    if more:
        text += f"   {len(more)} more projects not watched: {', '.join(more)}"
    return Text(text, no_wrap=True, overflow="ellipsis")


def render(m: Model, width: int, height: int) -> Any:
    """The whole screen at this size."""
    from rich.layout import Layout

    body_rows = max(height - HEADER_H - FOOTER_H - BORDERS, 0)
    root = Layout()
    root.split_column(
        Layout(header(m), size=HEADER_H),
        Layout(name="body"),
        Layout(footer(m), size=FOOTER_H),
    )
    columns = [Layout(flow(m, body_rows)), Layout(tasks(m), size=RIGHT_W)]
    if width >= NARROW:
        columns.insert(0, Layout(left(m), size=LEFT_W))
    root["body"].split_row(*columns)
    return root


def plain(m: Model, width: int, height: int, file: Any) -> None:
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
        console.print(render(m, width, height))
    file.write("".join(x.rstrip() + "\n" for x in captured.get().splitlines()))


def run(m: Model, lock: threading.Lock, alive: Callable[[], bool]) -> None:
    """Redraw the screen once a second until `alive` is false or Ctrl-C (which the caller
    handles); the terminal is restored on the way out."""
    from rich.console import Console
    from rich.live import Live

    console = Console()

    def frame() -> Any:
        with lock:
            return render(m, console.width, console.height)

    with Live(frame(), console=console, screen=True, auto_refresh=False) as live:
        while alive():
            time.sleep(REDRAW_S)
            live.update(frame(), refresh=True)
