"""What the keys of `chantier live` change: a plain object fed with key names, with no Rich, no
terminal library and no network in it.

Key names: `up`, `down`, `pgup`, `pgdn`, `home`, `end`, `tab`, `btab`, `enter`, `esc`,
`backspace`, `ctrl-c`, or one printable character. `press` says whether to quit.

One panel is active (`projects`, `agents`, `flow`, `ready` or `tasks`; the Flow at the start): Tab
and Shift-Tab move it among the panels the last drawing drew, the scroll keys move it only, and
`m` maximizes it. A scroll is kept as a move and applied at the next drawing, against the lines the
panel then holds. Ready, Tasks, Projects and Agents each keep an offset from their first line,
clamped to their last full page. The Flow is newest first: its window stays on the lines it shows
while new lines arrive (the Flow is paused, and counts them) until it is back at the live end, the
top."""

from __future__ import annotations

from typing import Any

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


class View:
    """The active panel, each panel's scroll (the Flow's with the lines that came while paused),
    the maximized state, the filter and the help."""

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

    def press(self, name: str, page: int | None = None) -> bool:
        """Give one key; true when the screen should quit. A `page` of None is the active
        panel's visible rows at the drawing."""
        if name == "ctrl-c":
            return True
        if self.help:
            self.help = False
        elif self.typing is not None:
            self._type(name)
        else:
            return self._command(name, page)
        return False

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
