"""The spend of a batch: prices, unpriced calls and the window."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from chantier.core.errors import EXIT_PRECONDITION, ChantierError
from chantier.core.records import chief_sessions
from chantier.core.repo import Repo
from chantier.plugin_files import read_playbook
from chantier.rails import usd_text

TO_DATE = "To date: it grows if the batch runs again; `close` prices the final cost"


def price_table(repo: Repo, host: str) -> dict[str, Any] | None:
    """The project's prices (`prices:` of `chantier.yaml`), read at each pricing and not frozen
    at `open`, so a price added mid-batch prices the next refresh. Not used on Copilot, whose
    records carry the price. A file that is not valid refuses, never silently ignored."""
    if host == "copilot":
        return None
    resolved, problems = read_playbook(repo, host)
    if problems:
        raise ChantierError(
            "chantier.yaml is not valid, the prices cannot be read:\n"
            + "\n".join(problems)
            + "\nrun `$CHANTIER playbook`",
            EXIT_PRECONDITION,
        )
    return (resolved or {}).get("prices") or None


def unpriced_of(r: dict[str, Any]) -> dict[str, Any]:
    return r.get("unpriced") or {}


def add_unpriced(into: dict[str, Any], un: dict[str, Any]) -> dict[str, Any]:
    for model, n in un.items():
        into[model] = into.get(model, 0) + n
    return into


def sum_unpriced(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Calls of a model with no price, by model, summed over rows."""
    out: dict[str, int] = {}
    for r in rows:
        add_unpriced(out, unpriced_of(r))
    return out


def minus(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    return {m: n - b.get(m, 0) for m, n in a.items() if n - b.get(m, 0) > 0}


def spend(usd: float, calls: int, un: dict[str, Any], places: int = 2) -> str:
    """A priced amount, a floor (`at least`) when calls are not priced; no priced call at all
    is `not priced`, never $0.00."""
    return "not priced" if un and not calls else usd_text(usd, un, places)


def hints(models: Iterable[str]) -> list[str]:
    return [
        f"{m} has no price: add it under prices: in chantier.yaml (exact id: {m})" for m in models
    ]


def steering_window(d: dict[str, Any], uuid: str) -> tuple[str, str]:
    """The part of a steering transcript that belongs to the batch's steering: a Foreman's from
    the batch's opening (its startup is the batch's), the Chief of Staff's from its claim; each
    ends where the next claim begins. A batch with no recorded claims has no end."""
    claims = d.get("foreman_claims") or []
    names = [c["transcript"] for c in claims]
    if uuid not in names:
        return d.get("created", ""), ""
    i = names.index(uuid)
    since = claims[i]["since"] if uuid in chief_sessions(d) else d.get("created", "")
    return since, claims[i + 1]["since"] if i + 1 < len(claims) else ""
