"""A Driver's prompt skeleton: the table "A Driver's prompt" of `concepts.md`, read by the CLI,
and the lines `take`, `take stack` and `order qa` print for the Driver the table names."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from chantier.core.errors import EXIT_PRECONDITION, ChantierError
from chantier.plugin_files import (
    _agent_files,
    contract_lines,
    recorded_escalation,
    skill_dir,
)

if TYPE_CHECKING:
    from chantier.core.records import BatchRecord


DRIVER_TABLE_TITLE = "### A Driver's prompt"
BACKTICKED = re.compile(r"`([^`]+)`")


@dataclass(frozen=True)
class DriverRow:
    """A row of the "A Driver's prompt" table in `concepts.md`, with the role's first line, read
    from its agent file on the batch's host, and its contract text."""

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
    the `writes:` value and the `Team:` lines (`None`: the placeholder)."""

    fill: dict[str, str]
    cli: str
    middle: list[str]
    writes: str | None = None
    team: list[str] | None = None
    note: str = ""
    lease: str | None = None  # the `lease:` line, when the command started one
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
                    cells[2].strip("`"),
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
    that the Driver may run, and their scope; the path, branch and base from the `worktree:` line
    the command printed, `<…>` when it printed none."""
    if row.rewrites == "none":
        return []
    tree, branch, base = "<worktree>", "<branch>", "<base>"
    cr = block.fill.get("<cr>", "<cr>")
    for line in block.middle:
        if m := _WORKTREE_LINE.match(line):
            tree, branch = m[1], m[2]
            base = m[3] if m[3] != "?" else base  # `base ?`: the read of the forge failed
    flow = (
        "chantier's normal flow, pre-authorized by the playbook; never the default branch, "
        "a protected branch, another branch, a plain --force or a rebase --exec."
    )
    if row.rewrites == "batch branches":
        return [
            f"  Rewrites: for each CR branch of the stack listed above (chantier/*), "
            f"git -C <worktree> rebase <base>, then $CHANTIER push <cr> --lease <n> --unit stack, "
            f"one command per branch, on that branch only: {flow}"
        ]
    return [
        f"  Rewrites: git -C {tree} rebase {base}, then $CHANTIER push {cr} --lease <n>, "
        f"one command each, on your own CR branch only ({branch}): {flow}"
    ]


def first_line(row: DriverRow, block: DriverBlock) -> str:
    """The role's first line, its `<…>` filled from the block."""
    first = row.first
    for key, value in block.fill.items():
        first = first.replace(key, value)
    return first


RULES_LINE = (
    "the project's rules rank above them: run `$CHANTIER rules` first and read what "
    "touches your work."
)


def steering_who(d: BatchRecord) -> str:
    return "the Chief of Staff" if d.steering == "direct" else "the Foreman"


def driver_body_lines(  # noqa: PLR0913 - the keywords say what each is
    row: DriverRow,
    d: BatchRecord,
    block: DriverBlock,
    *,
    steering: str | None = None,
    note: bool = True,
    indent: str = "  ",
) -> list[str]:
    """The lines of a Driver's prompt after its card lines: the contract lines (a role the
    playbook starts generic), `CLI`, the command's lines, `writes:` and `Team:` only where the
    table gives them, `Rewrites:`, `Steering:`, `Needs:` and `Note:`. Each is led by `indent`
    (the contract lines keep their own). `steering` replaces the text after `Steering: `; `note`
    False leaves the `Note:` line out."""
    team = [f"{indent}Team: <the team: lines, as printed, then the review steps>"]
    if block.team:
        printed = "; ".join(t.removeprefix("team: ") for t in block.team)
        team = [f"{indent}Team: {printed}; <review steps>"]
    if steering is None:
        steering = (
            f"{steering_who(d)} <the host's means, from its reference's row \"A Driver "
            'messages its steering session">'
        )
    rewrites = [f"{indent}{ln[2:]}" for ln in _rewrites_line(row, block)]
    return [
        *contract_lines(row.role, row.text, d.playbook, recorded_escalation(d)),
        f"{indent}CLI ($CHANTIER): {block.cli}",
        *(f"{indent}{line}" for line in block.middle),
        *([f"{indent}{block.lease}"] if block.lease else []),
        *([f"{indent}writes: {block.writes}"] if row.writes and block.writes else []),
        *rewrites,
        f"{indent}Steering: {steering}",
        *(team if row.team else []),
        *(f"{indent}{ln[2:]}" for ln in needs_line(d.playbook, row.role)),
        *([f"{indent}Note: {block.note or '<why this is with the Driver>'}"] if note else []),
    ]


def driver_prompt_lines(row: DriverRow, d: BatchRecord, block: DriverBlock) -> list[str]:
    """The whole prompt skeleton of a Driver, to copy: the heading, then the prompt's lines with
    two leading spaces, filled in where the CLI can and left as `<…>` otherwise. The opening
    lines, the card, the rules line, the contract lines (a role the playbook starts generic),
    `CLI`, the command's lines, `writes:` and `Team:` only where the table gives them,
    `Steering:`, `Needs:` and `Note:`. The CLI knows no role: the table is read."""
    refs = f"{skill_dir().as_posix()}/references"
    heading = (
        f"{row.role} prompt (copy it whole, without the two leading spaces, and fill each <…>; "
        "add no line and drop none):"
    )
    if not row.writes:
        heading = heading.replace(
            f"{row.role} prompt (",
            f"{row.role} prompt (no writes: line: this Driver gets none; ",
            1,
        )
    return [
        heading,
        f"  {first_line(row, block)}",
        f"  Read {refs}/startup-core.md, the host core, role core, and the short startup section "
        f"named by {refs}/startup-manifest.json; defer the rest until an action names it.",
        f"  Card: {refs}/{row.card}: its Startup core now, each other section when its step "
        "comes, as the card's opening says;",
        f"  {RULES_LINE}",
        *driver_body_lines(row, d, block),
    ]
