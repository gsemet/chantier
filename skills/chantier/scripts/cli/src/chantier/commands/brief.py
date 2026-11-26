"""`chantier brief`: one role's whole start brief, written in the repository's git folder, and the
short prompt that points at it. It reads the record, the planning folder and, for a Driver's
`Team:` line, the review steps of the project's `chantier` section: it records nothing, renews
no lease and appends no journal line. The roles it knows are data, read from
`roles.yaml` (`roles_data`); the facts come from the builders `take`, `take stack`, `order qa` and
`handoff` use."""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass, field
from pathlib import Path

from chantier.board.projects import project_name
from chantier.commands.crs import batch_cr
from chantier.commands.driver import _cr_driver_block, stack_block
from chantier.commands.facts import cr_facts, unit_facts, worker_writes
from chantier.commands.orders import qa_block, qa_default_branch
from chantier.core import leases
from chantier.core.batch import read_batch, resolve_batch
from chantier.core.errors import EXIT_PRECONDITION, ChantierError
from chantier.core.files import write_file
from chantier.core.ids import normalize_cr
from chantier.core.records import BatchRecord, read_events
from chantier.core.repo import Repo
from chantier.driver_prompt import (
    DriverBlock,
    DriverRow,
    driver_prompt_lines,
    driver_row,
    needs_line,
)
from chantier.host_rows import HostRow, load_rows, row_lines
from chantier.lifecycle.stages import cr_directory
from chantier.playbook.lines import team_lines, timing_lines
from chantier.plugin_files import (
    chief_prompt_lines,
    cli_command,
    detect_host,
    project_instructions,
    read_escalation,
    read_playbook,
    recorded_timing,
    review_steps,
    skill_dir,
)
from chantier.role_wrappers import first_line_template, role_contract_lines
from chantier.roles_data import Role, load_roles
from chantier.stack_shape import shape_line
from chantier.status.views import shown_title

CLOSING = "`$CHANTIER next` says what is due; `$CHANTIER help <topic>` when a line names one."
STEERING_ROLES = ("foreman", "chief-of-staff")
DRIVERS = ("cr-driver", "release-driver", "stack-driver", "qa-driver")
ORDER, STACK, FOLDER, NONE = "order", "stack", "folder", "none"
FOLDERS = ("1-inbox", "2-backlog/P1", "2-backlog/P2", "2-backlog/P3", "2-backlog/P4", "3-ready")


@dataclass
class Facts:
    """A brief's facts and what its short prompt draws from them: the first line's fills, the
    `writes:` value and the `worktree:` line, when the role and the unit have them."""

    lines: list[str]
    fill: dict[str, str] = field(default_factory=dict)
    writes: str | None = None
    worktree: str | None = None


def _refuse(text: str) -> ChantierError:
    return ChantierError(f"brief: {text}", EXIT_PRECONDITION)


def _role(name: str) -> Role:
    table = {r.name: r for r in load_roles()}
    if name not in table:
        raise _refuse(f"unknown role '{name}'; roles: {', '.join(table)}")
    return table[name]


def _check_words(role: Role, args: argparse.Namespace) -> None:
    """The refusals that need no state: a unit, a lease or an epoch the role does not take."""
    unit = args.unit
    if args.epoch is not None and role.name not in STEERING_ROLES:
        raise _refuse(f"--epoch is for {' and '.join(STEERING_ROLES)} only, not {role.name}")
    if unit and role.unit == NONE:
        raise _refuse(f"{role.name} has no unit: give none (got '{unit}')")
    if role.name not in DRIVERS:
        if args.lease is not None:
            raise _refuse(f"--lease is for a Driver's unit only, not {role.name}")
    elif args.lease is not None and not unit:
        raise _refuse(f"--lease needs the {role.name}'s unit")
    elif unit and args.lease is None:
        raise _refuse(f"{role.name} {unit} needs --lease <n>, the Driver's lease on its unit")


def _named_batch(repo: Repo, args: argparse.Namespace) -> str | None:
    """The batch `--batch` or `CHANTIER_BATCH` names, else the only open or paused one, else
    none: a brief with no batch is a role-only brief."""
    if args.batch or os.environ.get("CHANTIER_BATCH"):
        return resolve_batch(repo, args.batch, paused=True)
    if repo.open_batches() or repo.paused_batches():
        return resolve_batch(repo, None, paused=True)
    return None


def _check_lease(d: BatchRecord, unit: str, lease: int) -> None:
    held = leases.lease_of(d, unit)
    if held is None or held.n != lease or held.ended:
        raise _refuse(f"lease {lease} is not {unit}'s live lease")


def _take_note(repo: Repo, batch: str, cr: str | None, lease: int) -> str:
    """The note of the `take` that started the unit's lease (`cr` None: the stack's)."""
    for e in reversed(read_events(repo.store, repo.batch_dir(batch))):
        if e.kind == "take" and e.cr == cr and e.lease == lease:
            return str(e.note or "")
    return ""


def _cli(repo: Repo, batch: str | None) -> str:
    return f"CLI ($CHANTIER): {cli_command(repo)} <command>" + (
        f" --batch {batch}" if batch else ""
    )


def _base(repo: Repo, batch: str | None) -> list[str]:
    return [_cli(repo, batch), f"Repository: {repo.root.as_posix()}"]


def _cr_roles(
    repo: Repo, role: Role, args: argparse.Namespace, host: str | None
) -> tuple[Facts, str, str, BatchRecord]:
    """A CR's Driver or worker: `(facts, batch, host, record)`."""
    try:
        batch, d, c = batch_cr(repo, args.unit, args.batch)
    except ChantierError as e:
        raise _refuse(str(e)) from e
    host = d.host or host or detect_host()
    folder = cr_directory(repo, c)
    if role.name in DRIVERS:
        row = driver_row(host, "take <cr>", c.kind)
        if row.role != role.name:
            raise _refuse(f"{c.id} is a {c.kind} CR: its Driver is the {row.role}, not {role.name}")
        lease = leases.lease_of(d, c.id)
        _check_lease(d, c.id, args.lease)
        assert lease is not None
        facts = cr_facts(repo, batch, d, c)
        block = _cr_driver_block(repo, batch, c, facts)
        block.team, block.reviews = team_lines(d.playbook), review_steps(repo, host)
        block.lease, block.number = leases.driver_line(c.id, lease), lease.n
        block.note = _take_note(repo, batch, c.id, lease.n)
        return _driver_facts(row, d, block, facts[0]), batch, host, d
    head = unit_facts(repo, batch, d, c)
    writes = worker_writes(c, folder)
    lines = [*head, *role_contract_lines(host, role.name, d), writes]
    title = shown_title(repo.store, c.title, folder)
    fill = {"<cr>": c.id, "<title>": title, "<batch>": batch, "<root>": repo.root.as_posix()}
    found = Facts(lines, fill, writes.removeprefix("writes: "), _worktree(head))
    return found, batch, host, d


def _worktree(lines: list[str]) -> str | None:
    return next((ln for ln in lines if ln.startswith("worktree: ")), None)


def _driver_facts(
    row: DriverRow, d: BatchRecord, block: DriverBlock, head: str | None = None
) -> Facts:
    """A Driver's facts: `head`, when the unit has one, then its prompt's lines."""
    lines = [*([head] if head else []), *driver_prompt_lines(row, d, block)]
    return Facts(lines, block.fill, block.writes if row.writes else None, _worktree(block.middle))


def _stack_driver(
    repo: Repo, role: Role, args: argparse.Namespace
) -> tuple[Facts, str, str, BatchRecord]:
    batch = resolve_batch(repo, args.batch, paused=True)
    d = read_batch(repo, batch)
    if d.mode != "stack":
        raise _refuse(f"batch {batch} is not a stack: it has no stack driver")
    _check_lease(d, "stack", args.lease)
    row = driver_row(d.host, "take stack")
    note = _take_note(repo, batch, None, args.lease)
    block, _ = stack_block(repo, batch, d, args.lease, note)
    return _driver_facts(row, d, block), batch, d.host, d


def _qa_driver(
    repo: Repo, role: Role, args: argparse.Namespace
) -> tuple[Facts, str, str, BatchRecord]:
    batch = resolve_batch(repo, args.batch, paused=True)
    d = read_batch(repo, batch)
    order = next((o for o in d.orders if o.id == args.unit), None)
    if order is None or order.kind != "qa" or order.done:
        raise _refuse(f"{args.unit} is not an open QA order of {batch}")
    _check_lease(d, order.id, args.lease)
    row = driver_row(d.host, "order qa")
    branch = qa_default_branch(repo)
    block = qa_block(repo, batch, (order.id, order.cr), branch, args.lease, order.note)
    return _driver_facts(row, d, block), batch, d.host, d


def _folder(repo: Repo, unit: str) -> Path:
    """The CR folder a spec role reads: absolute, or relative to the planning folder or the
    working folder, or a bare name found in the inbox, the backlog or `3-ready`."""
    changes = repo.changes.resolve()
    given = Path(unit)
    options = [given] if given.is_absolute() else [changes / given, Path.cwd() / given]
    options += [changes / place / unit for place in FOLDERS]
    for p in options:
        if p.is_dir():
            found = p.resolve()
            if found.parent in {(changes / place).resolve() for place in FOLDERS}:
                return found
    raise _refuse(
        f"{unit} is not a CR folder of {', '.join(FOLDERS[:2])}..P4 or {FOLDERS[-1]}: "
        "a spec role works on an item of the inbox, the backlog or `3-ready`"
    )


def _spec_role(repo: Repo, args: argparse.Namespace) -> tuple[Facts, Path]:
    folder = _folder(repo, args.unit)
    spec = folder / "03-change-spec.md"
    lines = [
        *_base(repo, None),
        f"CR folder: {folder.as_posix()}",
        *([f"Specification: {spec.as_posix()}"] if spec.is_file() else []),
    ]
    return Facts(lines, {"<root>": repo.root.as_posix()}), folder


def _foreman_lines(repo: Repo, batch: str, d: BatchRecord, epoch: int | None) -> list[str]:
    return [
        _cli(repo, batch),
        f"Repository: {repo.root.as_posix()}",
        f"batch: {batch}",
        f"epoch: {epoch if epoch is not None else d.foreman_epoch}",
        *shape_line(d),
        *team_lines(d.playbook),
        *timing_lines(recorded_timing(d), d.host),
        *(ln.strip() for ln in needs_line(d.playbook, "foreman")),
    ]


def _chief_lines(repo: Repo, host: str) -> list[str]:
    resolved, _ = read_playbook(repo, host)
    escalated, _ = read_escalation(repo, host)
    found = project_instructions(repo)
    return [
        *_base(repo, None),
        f"planning folder: {repo.changes.as_posix()}",
        f"project instructions: {found.as_posix() if found else 'none'}",
        f"host: {host}",
        *chief_prompt_lines(host, repo.root.as_posix(), None, resolved, escalated),
    ]


def _facts(
    repo: Repo, role: Role, args: argparse.Namespace
) -> tuple[Facts, str | None, str, Path | None]:
    """`(facts, batch, host, folder)` for the role and its unit; a role-only brief when no unit
    is given."""
    unit = args.unit
    if role.unit == FOLDER and unit:
        found, folder = _spec_role(repo, args)
        batch = _named_batch(repo, args)
        host = read_batch(repo, batch).host if batch else detect_host()
        return found, batch, host, folder
    if unit and role.unit not in (NONE, FOLDER):
        if role.unit == STACK:
            found, batch, host, _ = _stack_driver(repo, role, args)
        elif role.unit == ORDER:
            found, batch, host, _ = _qa_driver(repo, role, args)
        else:
            args.unit = normalize_cr(unit)
            found, batch, host, _ = _cr_roles(repo, role, args, None)
        return found, batch, host, None
    batch = _named_batch(repo, args)
    d = read_batch(repo, batch) if batch else None
    host = (d.host if d else None) or detect_host()
    fill = {"<root>": repo.root.as_posix(), **({"<batch>": batch} if batch else {})}
    if unit is None and role.unit != NONE:
        return Facts(_base(repo, batch), fill), batch, host, None
    if role.name == "foreman" and d and batch:
        return Facts(_foreman_lines(repo, batch, d, args.epoch), fill), batch, host, None
    if role.name in ("chief-of-staff", "griller"):
        return Facts(_chief_lines(repo, host), fill), batch, host, None
    lines = [*_base(repo, batch), *([f"batch: {batch}"] if batch else [])]
    return Facts(lines, fill), batch, host, None


def _read_text(path: Path) -> str:
    """A file's text, its line ends LF (the working tree may hold CRLF)."""
    try:
        return path.read_bytes().decode("utf-8").replace("\r\n", "\n")
    except OSError as e:
        raise _refuse(f"cannot read {path.as_posix()}: {e.strerror or e}") from e


def _card_files(role: Role, cards: str | None) -> tuple[Path, Path]:
    """The card and the floor: the plugin's, or `--cards <folder>`'s."""
    if cards is None:
        refs = skill_dir() / "references"
        return (refs / role.card).resolve(), refs / "floor.md"
    folder = Path(cards).resolve()
    return folder / Path(role.card).name, folder / "floor.md"


def _rows(role: Role, host: str) -> list[str]:
    rows = load_rows(host)
    if role.rows is None:
        chosen = rows
    else:
        known = {r.capability for r in rows}
        for cap in role.rows:
            if cap not in known:
                raise _refuse(f"{role.name}'s row `{cap}` is not on the {host} host")
        chosen = [r for r in rows if r.capability in role.rows]
    if not chosen:
        return ["none"]
    return _row_text(chosen)


def _row_text(rows: list[HostRow]) -> list[str]:
    out: list[str] = []
    for i, r in enumerate(rows):
        if i:
            out.append("")
        out += row_lines(r)
    return out


def brief(args: argparse.Namespace) -> list[str]:
    role = _role(args.role)
    _check_words(role, args)
    repo = Repo.find(readonly=True)
    card, floor = _card_files(role, args.cards)
    card_text, floor_text = _read_text(card), _read_text(floor)
    facts, batch, host, folder = _facts(repo, role, args)
    parts = [
        card_text.rstrip("\n"),
        "=== floor\n" + floor_text.rstrip("\n"),
        "=== facts\n" + "\n".join(facts.lines),
        f"=== host rows: {host}\n" + "\n".join(_rows(role, host)),
        CLOSING,
    ]
    name = folder.name if folder else (args.unit or "none")
    path = (
        repo.git_dir
        / "chantier"
        / "briefs"
        / project_name(repo)
        / (batch or "none")
        / f"{name}-{role.name}.md"
    )
    write_file(path, "\n\n".join(parts) + "\n")
    return _short_prompt(role, host, facts, path)


def _short_prompt(role: Role, host: str, facts: Facts, path: Path) -> list[str]:
    wrapper = role.hosts[host].wrapper is not None
    template = first_line_template(host, role.name) if wrapper else None
    out: list[str] = []
    if template:
        first = template
        for key, value in facts.fill.items():
            first = first.replace(key, value)
        out.append(first)
    if role.writes != "none" and facts.writes:
        out.append(f"writes: {facts.writes}")
    if facts.worktree:
        out.append(facts.worktree)
    out.append(f"Read {path.as_posix()} whole, first.")
    return out
