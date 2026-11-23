"""The Ready box of `chantier live`: the PRs to review or to merge, in merge order."""

from __future__ import annotations

import re
from typing import Any

from chantier.clients.tui.model import Model
from chantier.clients.tui.parts import (
    RIGHT_W,
    coloured,
    cr_cell,
    dim,
    models_of,
    panel,
    table,
    watched,
)
from chantier.clients.tui.times import age, ready_word
from chantier.clients.tui.view import View

PR_W, READY_CR_W, READY_STATE_W, AGE_W = 6, 7, 20, 5


def _pr_number(pr: dict[str, Any] | None, r: dict[str, Any]) -> tuple[str, str]:
    """The PR cell's text (`#<n>` for a PR, `!<n>` for an MR) and its link ('' when none)."""
    url = str((pr or {}).get("pr") or r.get("pr") or "")
    number = (pr or {}).get("number")
    if number is None:
        found = re.search(r"(\d+)/?$", url.partition("#")[0].partition("?")[0])
        number = found[1] if found else None
    if number is None:
        return "-", ""
    sign = "!" if "/merge_requests/" in url else "#"
    linked = url if url.startswith(("http://", "https://")) else ""
    return f"{sign}{number}", linked


def _ready_holds(text: str, m: Model, project: str, r: dict[str, Any], number: str) -> bool:
    if not text:
        return True
    found = (m.label, project, m.named(project), r.get("cr"), r.get("title"), number)
    return any(text.casefold() in str(x or "").casefold() for x in found)


def ready_rows(
    models: list[Model], view: View | None = None
) -> list[tuple[Model, str, dict[str, Any], dict[str, Any] | None]]:
    """The Ready rows the filter keeps: (model, project, CR row, PR row), by board then merge
    order."""
    text = view.text if view else ""
    out = []
    for m in models:
        for p, r in m.review():
            pr = m.pr_of(p, str(r.get("cr")))
            if _ready_holds(text, m, p, r, _pr_number(pr, r)[0]):
                out.append((m, p, r, pr))
    return out


def ready_height(models: list[Model]) -> int:
    """The lines Ready's table needs under its header row, no filter."""
    return max(sum(len(m.review()) for m in models), 1)


def ready(models: Model | list[Model], view: View | None = None) -> Any:
    """The CRs to review or to merge with their PR, state, age and title, in merge order."""
    from rich.console import Group
    from rich.style import Style
    from rich.text import Text

    models, view = models_of(models), view or View()
    several = len(watched(models)) > 1
    t = table(
        ("PR", PR_W),
        ("CR", READY_CR_W + (2 if len(models) > 1 else 0)),
        ("State", READY_STATE_W),
        ("Age", AGE_W),
        ("Title", None),
        fit=True,
    )
    rows = ready_rows(models, view)
    for m, p, r, pr in rows:
        number, url = _pr_number(pr, r)
        cell = Text(number, no_wrap=True, overflow="ellipsis")
        if url:
            cell.stylize(Style(link=url))
        word, colour = ready_word(pr)
        cr = cr_cell(m, r)
        t.add_row(
            cell,
            f"{p} {cr}" if several and not m.label else cr,
            coloured(word, colour),
            dim(age(r.get("handed_back_at"), m.now())),
            str(r.get("title") or ""),
        )
    body: Any = t
    if not rows:
        if not any(m.has_batch() for m in models):
            empty = "no batch"
        elif view.text and any(m.review() for m in models):
            empty = f"no PR matches {view.text}"
        else:
            empty = "no PR ready"
        body = Group(t, Text(empty, no_wrap=True, overflow="ellipsis"))
    error = next((m.prs_error() for m in models if m.prs_error()), "")
    title = f"Ready  forge: {error}"[: RIGHT_W - 4] if error else "Ready"
    return panel(body, title)
