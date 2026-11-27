"""The Projects, Agents and Tasks boxes of `chantier live`, each scrolled by the view's offset."""

from __future__ import annotations

from typing import Any

from chantier.clients.tui.model import LATE, Model
from chantier.clients.tui.parts import (
    STATE_COLOURS,
    coloured,
    cr_cell,
    grid,
    models_of,
    panel,
    table,
    watched,
)
from chantier.clients.tui.times import lease_left
from chantier.clients.tui.view import View

STATE_W = 7


def project_lines(models: list[Model]) -> int:
    return 2 * len(watched(models))


def projects_table(models: list[Model], view: View | None = None, rows: int | None = None) -> Any:
    view = view or View()
    lines = []
    for m, p in watched(models):
        line = (m.states.get(p) or {}).get("batch")
        b = line if isinstance(line, dict) else None
        board_line = next((x for x in m.projects() if x["id"] == p), {})
        where = f"{b['id']} {b.get('state')} {b.get('mode')}" if b else "no batch"
        ready = m.ready_count(p)
        found = f"inbox {board_line.get('inbox', 0)} backlog {board_line.get('backlog', 0)}"
        if ready is not None:
            found += f" ready {ready}"
        lines += [f"{m.named(p)}  {where}", f"  {found}"]
    t = grid(None)
    for line in view.page("projects", lines, rows):
        t.add_row(line)
    return t


def agent_lines(models: list[Model]) -> list[str]:
    """The Agents box's lines: each project's sessions (with its name when several are watched)."""
    several = len(watched(models)) > 1
    found = [(m.named(project), text) for m in models for project, text in m.agents()]
    return [f"{project} {text}" if several else text for project, text in found]


def agents_table(models: list[Model], view: View | None = None, rows: int | None = None) -> Any:
    from rich.text import Text

    t = grid(None)
    lines = (view or View()).page("agents", agent_lines(models) or ["none"], rows)
    for line in lines:
        late = line.endswith(LATE)
        text = Text(line[: -len(LATE)] if late else line, no_wrap=True, overflow="ellipsis")
        if late:
            text.append(LATE, style=f"bold {STATE_COLOURS['blocked']}")
        t.add_row(text)
    return t


def _working(cr: str, r: dict[str, Any], now: Any) -> list[tuple[Any, str]]:
    left_ = lease_left(r.get("lease"), now)  # first: a cut never hides it
    detail = [f"lease {left_}" if left_ else ""]
    detail += [f"round {r.get('round')}/{r.get('round_limit')}", str(r.get("phase") or "")]
    return [
        (coloured("working", "working"), f"{cr}  {r.get('title') or ''}"),
        ("", "  ".join(x for x in detail if x)),
    ]


def _row_holds(text: str, m: Model, project: str, r: dict[str, Any]) -> bool:
    if not text:
        return True
    found = (m.label, project, m.named(project), r.get("cr"), r.get("title"), r.get("phase"))
    return any(text.casefold() in str(x or "").casefold() for x in found)


def tasks(models: Model | list[Model], view: View | None = None, rows: int | None = None) -> Any:
    """The working CRs with their lease time left, then the blocked ones with their reason; only
    those the filter keeps, `rows` lines of them from the view's offset (all when None). The CRs
    to review are in Ready."""
    models, view = models_of(models), view or View()
    t = table(("State", STATE_W), ("Task", None))
    every = [(m, p, r) for m in models for p, r in m.rows()]
    kept = [(m, p, r) for m, p, r in every if _row_holds(view.text, m, p, r)]
    lines: list[tuple[Any, str]] = []
    for m, _, r in kept:
        if r.get("state") == "working":
            lines += _working(cr_cell(m, r), r, m.now())
    for m, _, r in kept:
        if r.get("state") == "blocked":
            lines.append(
                (coloured("blocked", "blocked"), f"{cr_cell(m, r)}  {r.get('title') or ''}")
            )
            lines.append(("", str(r.get("blocked") or "blocked")))
    if not every:
        lines.append(("", "no running batch"))
    elif view.text and not lines:
        lines.append(("", f"no task matches {view.text}"))
    for cells in view.page("tasks", lines, rows):
        t.add_row(*cells)
    return panel(t, view.title("tasks", "Tasks"))
