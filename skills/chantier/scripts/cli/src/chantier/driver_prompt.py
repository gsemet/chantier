"""A Driver's prompt: the table "A Driver's prompt" of `concepts.md`, read by the CLI, and the
facts `brief` prints for the Driver the table names."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from chantier.core.errors import EXIT_PRECONDITION, ChantierError
from chantier.plugin_files import (
    _agent_files,
    contract_lines,
    recorded_escalation,
    skill_dir,
)
from chantier.roles_data import load_roles

if TYPE_CHECKING:
    from chantier.core.records import BatchRecord


DRIVER_TABLE_TITLE = "### A Driver's prompt"
BACKTICKED = re.compile(r"`([^`]+)`")


@dataclass(frozen=True)
class DriverRow:
    """A row of the "A Driver's prompt" table in `concepts.md`, with the role's card, as
    `roles.yaml` names it, its first line, read from its agent file on the batch's host, and its
    contract text."""

    role: str
    card: str
    writes: bool
    team: bool
    rewrites: str  # `own branch`, `batch branches` or `none`
    first: str
    text: str


@dataclass
class DriverBlock:
    """What a command gives for a Driver's prompt: the first line's `<…>` fills, the `CLI` value,
    the lines its command printed for the Driver, and, when the table gives the role those lines,
    the `writes:` value, the `team:` lines and the project's extra review steps. `note` says why
    the unit is with this Driver."""

    fill: dict[str, str]
    cli: str
    middle: list[str]
    writes: str | None = None
    team: list[str] = field(default_factory=list)
    reviews: list[str] = field(default_factory=list)  # `<name>: <what it checks>`, in order
    note: str = ""
    lease: str | None = None  # the `lease:` line, when the command started one
    number: int = 0  # the lease's number, set with `lease`
    remote: str = "origin"  # the project's remote, as P10 fills it


def driver_table() -> list[list[str]]:
    text = (skill_dir() / "references" / "concepts.md").read_text(encoding="utf-8")
    start = text.find(DRIVER_TABLE_TITLE)
    if start < 0:
        raise ChantierError(
            f'concepts.md has no "{DRIVER_TABLE_TITLE[4:]}" table: the plugin files are out '
            "of step",
            EXIT_PRECONDITION,
        )
    rows: list[list[str]] = []
    for line in text[start + len(DRIVER_TABLE_TITLE) :].splitlines():
        if line.startswith("#"):
            break
        if line.startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if cells[0] != "Driver" and not set(cells[0]) <= set("- "):
                rows.append(cells)
    return rows


def driver_row(host: str, started: str, kind: str | None = None) -> DriverRow:
    """The table's row for `started` (`take <cr>` with the CR's `kind`, `take stack` or
    `order qa`), checked against the role's agent file on the host. A missing row or agent file
    is an error that names it: the plugin's files are out of step, never a fallback. Call it
    before any state changes."""
    out_of_step = "the plugin's files are out of step"
    for cells in driver_table():
        ticks = BACKTICKED.findall(cells[1])
        if not ticks or ticks[0] != started or (started == "take <cr>" and kind not in ticks[1:]):
            continue
        role = cells[0].strip("`")
        pattern = re.compile(rf"Prompt starts with: `(chantier {re.escape(role)} for [^`]*)`")
        for p in _agent_files(host)[1]:
            text = p.read_text(encoding="utf-8")
            if (m := pattern.search(text)) and "Started by the steering session" in text:
                return DriverRow(
                    role,
                    next(r.card for r in load_roles() if r.name == role),
                    cells[3].strip("`").lower() != "none",
                    cells[4].strip("`").lower() != "none",
                    cells[5].strip("`").lower(),
                    m[1],
                    text,
                )
        raise ChantierError(
            f"no agent file for the {role} on the {host} host ({started}): {out_of_step}"
        )
    what = f"{started} of a CR of kind {kind}" if started == "take <cr>" else started
    raise ChantierError(f"no row of the Driver's prompt table for {what}: {out_of_step}")


def needs_line(resolved: dict[str, Any] | None, role: str) -> list[str]:
    rec = ((resolved or {}).get("roles") or {}).get(role) or {}
    parts = [f"{k} {', '.join(rec[k])}" for k in ("skills", "tools") if rec.get(k)]
    return [f"  Needs: {'; '.join(parts)}"] if parts else []


_WORKTREE_LINE = re.compile(r"^worktree: (.+) branch (\S+) base ([^\s;]+)")


def _rewrites_line(row: DriverRow, block: DriverBlock) -> list[str]:
    """The `Rewrites:` line the table's column asks for: the rebase and the push of a CR branch
    that the Driver may run, and their scope. A CR's Driver gets its path, branch and base from
    the `worktree:` line the command printed; the stack's driver, one branch per row above."""
    if row.rewrites == "none":
        return []
    flow = (
        "chantier's normal flow, pre-authorized by the playbook; never the default branch, "
        "a protected branch, another branch, a plain --force or a rebase --exec."
    )
    if row.rewrites == "batch branches":
        return [
            "Rewrites: for each CR branch of the stack listed above (chantier/*), git -C its "
            "row's worktree rebase its row's base, then $CHANTIER push with its row's CR "
            f"--lease {block.number} --unit stack, one command per branch, on that branch only: "
            f"{flow}"
        ]
    tree, branch, base = next(
        m.groups() for line in block.middle if (m := _WORKTREE_LINE.match(line))
    )
    return [
        f"Rewrites: git -C {tree} rebase {base}, then $CHANTIER push {block.fill['<cr>']} "
        f"--lease {block.number}, one command each, on your own CR branch only ({branch}): {flow}"
    ]


def _team_line(block: DriverBlock) -> str:
    """Who runs each worker: the `team:` lines, as printed, or the plugin's agents, then each
    extra review step, in the order the Driver runs them after the Inspector."""
    team = [t.removeprefix("team: ") for t in block.team] or ["the plugin's agents"]
    return "Team: " + "; ".join([*team, *(f"review step {r}" for r in block.reviews)])


RULES_LINE = (
    "the project's rules rank above them: run `$CHANTIER rules` first and read what "
    "touches your work."
)


def steering_who(d: BatchRecord) -> str:
    return "the Chief of Staff" if d.steering == "direct" else "the Foreman"


def start_lines(role: str, unit: str, lease: tuple[int, str], run: str, batch: str) -> list[str]:
    """What `take`, `take stack` and `order qa` print for a Driver's start: the `lease:` line of
    `lease`, its number and its line, then the `brief` command (`run`: how the CLI runs), whose
    output is the Driver's whole prompt."""
    number, line = lease
    return [
        line,
        f"brief: {run} brief {role} {unit} --lease {number} --batch {batch}",
        "next: run it and pass its output, unchanged, as the Driver's whole prompt",
    ]


def driver_prompt_lines(row: DriverRow, d: BatchRecord, block: DriverBlock) -> list[str]:
    """A Driver's prompt after its card, which its brief holds: the rules line, the contract
    lines (a role the playbook starts generic), `CLI`, the command's lines, `writes:` and
    `Team:` only where the table gives them, `Rewrites:`, `Steering:`, `Needs:` and, when there
    is one, `Note:`. The CLI reads roles only as data: the table is read."""
    return [
        RULES_LINE,
        *contract_lines(row.role, row.text, d.playbook, recorded_escalation(d)),
        f"CLI ($CHANTIER): {block.cli}",
        *block.middle,
        *([block.lease] if block.lease else []),
        *([f"writes: {block.writes}"] if row.writes and block.writes else []),
        *_rewrites_line(row, block),
        f"Steering: {steering_who(d)} (host means: the host rows below)",
        *([_team_line(block)] if row.team else []),
        *(line.strip() for line in needs_line(d.playbook, row.role)),
        *([f"Note: {block.note}"] if block.note else []),
    ]
