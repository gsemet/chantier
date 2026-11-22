"""What the keys of `chantier live` change: a plain object fed with key names, with no Rich, no
terminal library and no network in it.

Key names: `up`, `down`, `pgup`, `pgdn`, `home`, `end`, `enter`, `esc`, `backspace`, `ctrl-c`,
or one printable character. `press` says whether to quit. A scroll is kept as a move and applied by
`window` at the next drawing, against the lines the screen then holds: the window stays on the
lines it shows while new lines arrive (the Flow is paused, and counts them) until it is back at the
live end."""

from __future__ import annotations

from typing import Any

HELP = (
    ("Up / Down", "the Flow one line older / newer"),
    ("PgUp / PgDn", "the Flow one page older / newer"),
    ("Home", "the oldest kept line of the Flow"),
    ("End", "back to the live end (follows again)"),
    ("/", "type a filter (Enter applies it, Esc cancels)"),
    ("?", "show these keys"),
    ("Esc", "clear the filter; leave this help"),
    ("q, Ctrl-C", "quit"),
)
MOVES = {"up", "down", "pgup", "pgdn", "home", "end"}


class View:
    """The Flow's scroll, the lines that came while paused, the filter and the help."""

    def __init__(self) -> None:
        self.keys = False  # a keyboard is attached: the footer names the keys
        self.text = ""  # the filter applied
        self.typing: str | None = None  # the filter being typed, None when not typing
        self.help = False
        self.new = 0  # lines arrived since the Flow left the live end
        self.anchor: Any = None  # the newest line shown while scrolled back, None at the live end
        self.gap = 0  # lines newer than the anchor when it was set
        self.moves: list[tuple[str, int]] = []

    def press(self, name: str, page: int = 1) -> bool:
        """Give one key; true when the screen should quit."""
        if name == "ctrl-c":
            return True
        if self.help:
            self.help = False
        elif self.typing is not None:
            self._type(name)
        elif name == "q":
            return True
        elif name == "/":
            self.typing = ""
        elif name == "?":
            self.help = True
        elif name == "esc":
            self._filter("")
        elif name in MOVES:
            self.moves.append((name, max(page, 1)))
        return False

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
            self.anchor, self.gap, self.new = None, 0, 0  # a new text shows the live end

    def window(self, lines: list[Any], rows: int) -> tuple[list[Any], str]:
        """The `rows` lines to draw out of `lines` (oldest first) and the Flow's title."""
        n = len(lines)
        if n == 0 or rows <= 0:
            self.anchor, self.gap, self.new, self.moves = None, 0, 0, []
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
        for name, page in self.moves:
            at = {
                "up": at - 1,
                "down": at + 1,
                "pgup": at - page,
                "pgdn": at + page,
                "home": oldest,
                "end": last,
            }[name]
            at = max(oldest, min(at, last))
        self.moves = []
        at = max(oldest, min(at, last))
        if at == last:
            self.anchor, self.gap, self.new = None, 0, 0
            return lines[max(0, n - rows) :], "Flow"
        self.anchor, self.gap = lines[at], last - at
        return lines[max(0, at + 1 - rows) : at + 1], f"Flow  paused, {self.new} new"
