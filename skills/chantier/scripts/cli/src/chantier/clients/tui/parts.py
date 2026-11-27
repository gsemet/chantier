"""The Rich pieces `chantier live` draws with: the board's state colours, the tables, the boxes."""

from __future__ import annotations

from typing import Any

from chantier.clients.tui.model import Model

LEFT_W, RIGHT_W = 42, 44  # the side columns' widths until a drag sizes them

# the board's state colours: the `--state-<name>` values of `clients/web/css/tokens.css`
STATE_COLOURS = {
    "working": "#4a76d9",
    "ready": "#2f9e6b",
    "blocked": "#d14b5e",
    "draft": "#a77b4f",
    "waits": "#d08a1f",
    "queued": "#a3a7af",
    "merged": "#2a7a55",
    "local": "#8b6bd8",
}
COUNT_COLOURS = {"working": "working", "ready": "ready", "held": "blocked", "done": "merged"}


def grid(*widths: int | None) -> Any:
    """A table of text columns with no header, each cut with `…`; a None width takes the rest."""
    from rich.table import Table

    t = Table.grid(padding=(0, 1), expand=True)
    for w in widths:
        if w is None:
            t.add_column(ratio=1, no_wrap=True, overflow="ellipsis")
        else:
            t.add_column(width=w, no_wrap=True, overflow="ellipsis")
    return t


def table(*columns: tuple[str, int | None], fit: bool = False, right: tuple[str, ...] = ()) -> Any:
    """A table with a bold header row; each cell is cut with `…`; a None width takes the rest.
    With `fit`, a width is the most the column takes: it is as wide as its cells. The columns named
    in `right` are right-aligned."""
    from rich.table import Table

    t = Table(
        box=None,
        show_edge=False,
        padding=(0, 1),
        collapse_padding=True,
        pad_edge=False,
        expand=True,
        show_header=True,
        header_style="bold",
    )
    for name, w in columns:
        side: Any = "right" if name in right else "left"
        if w is None:
            t.add_column(name, ratio=1, no_wrap=True, overflow="ellipsis", justify=side)
        elif fit:
            t.add_column(name, max_width=w, no_wrap=True, overflow="ellipsis", justify=side)
        else:
            t.add_column(name, width=w, no_wrap=True, overflow="ellipsis", justify=side)
    return t


def panel(body: Any, title: str) -> Any:
    from rich import box
    from rich.panel import Panel

    return Panel(body, box.ROUNDED, title=title, title_align="left", padding=(0, 1))


def coloured(text: str, state: str) -> Any:
    from rich.text import Text

    return Text(text, style=STATE_COLOURS[state], no_wrap=True, overflow="ellipsis")


def dim(text: str) -> Any:
    from rich.text import Text

    return Text(text, style="dim", no_wrap=True, overflow="ellipsis")


def models_of(models: Model | list[Model]) -> list[Model]:
    return [models] if isinstance(models, Model) else models


def watched(models: list[Model]) -> list[tuple[Model, str]]:
    return [(m, p) for m in models for p in m.watched()]


def cr_cell(m: Model, r: dict[str, Any]) -> str:
    return f"{m.label} {r.get('cr')}" if m.label else str(r.get("cr"))
