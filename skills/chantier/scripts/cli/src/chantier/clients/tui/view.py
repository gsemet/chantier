"""What the keys and the mouse of `chantier live` change: a plain object fed with key names, with no
Rich, no terminal library and no network in it.

Key names: `up`, `down`, `pgup`, `pgdn`, `home`, `end`, `tab`, `btab`, `enter`, `esc`,
`backspace`, `ctrl-c`, or one printable character. `press` says whether to quit.

The view keeps the widths of the two side columns, read from `live.json` at the start. While mouse
tracking is on (turned on just after the first screen), the footer and the help say what the mouse
does: a drag of a border between two columns (`mouse.py`) sizes a side column, and the wheel is the
`up` and `down` keys. A key press drops a drag under way (its release may never come), so none
lasts under the help or a maximized panel.

One panel is active (`projects`, `agents`, `flow`, `ready` or `tasks`; the Flow at the start): Tab
and Shift-Tab move it among the panels the last drawing drew, the scroll keys move it only, and
`m` maximizes it. A scroll is kept as a move and applied at the next drawing, against the lines the
panel then holds. Ready, Tasks, Projects and Agents each keep an offset from their first line,
clamped to their last full page. The Flow is newest first: its window stays on the lines it shows
while new lines arrive (the Flow is paused, and counts them) until it is back at the live end, the
top."""

from __future__ import annotations

from pathlib import Path
from typing import Any, NamedTuple

from chantier.clients.tui.parts import LEFT_W, RIGHT_W

PANELS = ("projects", "agents", "flow", "ready", "tasks")
MARK = "▸ "  # the active panel's title starts with it: no colour carries it alone
MAXIMIZE = "m"

HELP = (
    ("Tab, Shift-Tab", "the next / previous panel (the active one has a ▸)"),
    ("Up / Down", "the active panel one line up / down (the Flow: newer / older)"),
    ("PgUp / PgDn", "the active panel one page up / down (the Flow: newer / older)"),
    ("Home", "the first line of the active panel (the Flow: the newest, follows live)"),
    ("End", "the last line of the active panel (the Flow: the oldest kept)"),
    ("m", "maximize the active panel; again restores the layout"),
    ("t", "the Flow's time: date and time / time since the event"),
    ("/", "type a filter (Enter applies it, Esc cancels)"),
    ("?", "show these keys"),
    ("Esc", "clear the filter; leave this help"),
    ("q, Ctrl-C", "quit"),
)
MOVES = {"up", "down", "pgup", "pgdn", "home", "end"}
# the words added while mouse tracking is on: the footer's, and the help's rows
MOUSE_FOOTER = "drag a border: resize  Shift-drag: select  Ctrl-click: open a PR"
MOUSE_HELP = (
    ("Drag a border", "resize the left or the right column (kept for the next start)"),
    ("Wheel", "the active panel one line up / down"),
    ("Shift-drag", "select text (Ctrl-click opens a PR link in Ready)"),
)


class Drag(NamedTuple):
    """A drag of a border under way: the side column it sizes (`left` or `right`), the pointer's
    column at the press, and the two side widths drawn then and now."""

    side: str
    x: int
    start: tuple[int, int]
    now: tuple[int, int]


class View:
    """The active panel, each panel's scroll (the Flow's with the lines that came while paused),
    the maximized state, the filter, the help, the side columns' widths and the mouse."""

    def __init__(self) -> None:
        self.keys = False  # a keyboard is attached: the footer names the keys
        self.text = ""  # the filter applied
        self.typing: str | None = None  # the filter being typed, None when not typing
        self.help = False
        self.ago = False  # the Flow's time column: the time since each event, not the clock
        self.active = "flow"
        self.maximized = False
        self.drawn: list[str] = list(PANELS)  # the panels the last drawing drew, in reading order
        self.new = 0  # lines arrived since the Flow left the live end
        self.anchor: Any = None  # the newest line shown while scrolled back, None at the live end
        self.gap = 0  # lines newer than the anchor when it was set
        self.offsets: dict[str, int] = {}  # the first line shown of each panel but the Flow
        self.moves: list[tuple[str, int | None, str]] = []  # (key, page or None, panel)
        self.left, self.right = LEFT_W, RIGHT_W  # the side columns' kept widths
        self.file: Path | None = None  # `live.json`, written on a drag's release; None: no write
        self.tracking = False  # mouse tracking is on
        self.drag: Drag | None = None

    def press(self, name: str, page: int | None = None) -> bool:
        """Give one key; true when the screen should quit. A key drops a drag under way, nothing
        kept: a terminal that never delivers the release would leave the widths frozen. A `page`
        of None is the active panel's visible rows at the drawing."""
        self.drag = None
        if name == "ctrl-c":
            return True
        if self.help:
            self.help = False
        elif self.typing is not None:
            self._type(name)
        else:
            return self._command(name, page)
        return False

    def wheel(self, name: str) -> bool:
        """One line of the wheel, as the `up` or `down` key moves the active panel; nothing, and
        false, under the help or while a filter is typed. It is no key: a drag goes on."""
        if self.help or self.typing is not None:
            return False
        self._command(name, None)
        return True

    def _command(self, name: str, page: int | None) -> bool:
        if name == "q":
            return True
        if name == "/":
            self.typing = ""
        elif name == "?":
            self.help = True
        elif name == "t":
            self.ago = not self.ago
        elif name == MAXIMIZE:
            self.maximized = not self.maximized
        elif name in ("tab", "btab"):
            self._step(1 if name == "tab" else -1)
        elif name == "esc":
            self._filter("")
        elif name in MOVES:
            self.moves.append((name, page, self.active))
        return False

    def _step(self, by: int) -> None:
        panels = self.drawn or list(PANELS)
        at = panels.index(self.active) if self.active in panels else panels.index("flow")
        self.active = panels[(at + by) % len(panels)]

    def settle(self, drawn: list[str]) -> None:
        """The panels this drawing draws: a hidden active panel gives way to the Flow."""
        self.drawn = drawn
        if self.active not in drawn:
            self.active = "flow"
            self.moves = [x for x in self.moves if x[2] in drawn]

    def title(self, panel: str, text: str) -> str:
        """A panel's title, marked when it is the active one."""
        return f"{MARK}{text}" if self.active == panel else text

    def _type(self, name: str) -> None:
        if name == "esc":
            self.typing = None
            self._filter("")
        elif name == "enter":
            text, self.typing = self.typing or "", None
            self._filter(text)
        elif name == "backspace":
            self.typing = (self.typing or "")[:-1]
        elif len(name) == 1:
            self.typing = (self.typing or "") + name

    def _filter(self, text: str) -> None:
        if text != self.text:
            self.text = text
            self.moves.clear()
            self.offsets.clear()
            self.anchor, self.gap, self.new = None, 0, 0  # a new text shows the start of each

    def _take(self, panel: str) -> list[tuple[str, int | None]]:
        mine = [(name, page) for name, page, who in self.moves if who == panel]
        self.moves = [x for x in self.moves if x[2] != panel]
        return mine

    def page(self, panel: str, items: list[Any], rows: int | None) -> list[Any]:
        """The `rows` items of a panel but the Flow, from its offset (moved by its pending keys,
        clamped to its last full page); all of them when `rows` is None."""
        if rows is None:
            return items
        rows = max(rows, 0)
        top = max(len(items) - rows, 0)
        at = self.offsets.get(panel, 0)
        for name, page in self._take(panel):
            step = page or max(rows, 1)
            at = {
                "up": at - 1,
                "down": at + 1,
                "pgup": at - step,
                "pgdn": at + step,
                "home": 0,
                "end": top,
            }[name]
            at = max(0, min(at, top))
        at = max(0, min(at, top))
        self.offsets[panel] = at
        return items[at : at + rows]

    def window(self, lines: list[Any], rows: int) -> tuple[list[Any], str]:
        """The `rows` lines to draw out of `lines` (oldest first), newest first, and the Flow's
        title (not marked)."""
        n = len(lines)
        mine = self._take("flow")
        if n == 0 or rows <= 0:
            self.anchor, self.gap, self.new = None, 0, 0
            return [], "Flow"
        last = n - 1
        if self.anchor is None:
            at = last
        else:
            found = next((i for i in range(last, -1, -1) if lines[i] is self.anchor), None)
            if found is None:  # it fell out of its board's lines: the oldest kept
                at = min(rows, n) - 1
            else:
                at = found
                self.new += max(0, (last - at) - self.gap)
        oldest = min(rows, n) - 1
        for name, page in mine:
            step = page or rows
            at = {
                "up": at + 1,
                "down": at - 1,
                "pgup": at + step,
                "pgdn": at - step,
                "home": last,
                "end": oldest,
            }[name]
            at = max(oldest, min(at, last))
        at = max(oldest, min(at, last))
        if at == last:
            self.anchor, self.gap, self.new = None, 0, 0
            return lines[max(0, n - rows) :][::-1], "Flow"
        self.anchor, self.gap = lines[at], last - at
        return lines[max(0, at + 1 - rows) : at + 1][::-1], f"Flow  paused, {self.new} new"
