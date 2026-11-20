"""`chantier open`: the batch's frame, its CRs and their dependencies."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from chantier.commands.closing import record_born_paused
from chantier.commands.crs import grant_line
from chantier.commands.factory import not_joined_line, not_joined_text
from chantier.commands.joining import check_joins, join_cr
from chantier.commands.opening_record import (
    instruction_files,
    new_record,
    open_settings,
    release_grant,
)
from chantier.core.batch import Batch
from chantier.core.errors import EXIT_PRECONDITION, EXIT_USAGE, ChantierError
from chantier.core.files import read_text
from chantier.core.records import CrEntry, ReleaseGrant
from chantier.core.repo import Repo
from chantier.hub.autostart import not_running_line
from chantier.lifecycle.filing import shown, slugify
from chantier.lifecycle.session import RenderedBatch
from chantier.lifecycle.stages import (
    changes_lock,
    cr_directory,
    cr_slug,
    prepared_cr,
    stage_layout,
)
from chantier.playbook.lines import ci_lines, ci_source, timing_text
from chantier.plugin_files import (
    detect_host,
    own_transcript,
    read_escalation,
    read_limits,
    read_playbook,
    read_timing,
)
from chantier.rails import ENDED, alone, check_no_open_batch, is_release


def read_depends(folder: Path) -> list[str]:
    """The slugs of `depends.json`'s `after`; no file, no dependency."""
    path = folder / "depends.json"
    if not path.is_file():
        return []
    try:
        data = json.loads(read_text(path))
    except (OSError, ValueError) as e:
        raise ChantierError(
            f'{path}: not valid UTF-8 JSON ({e}); expected {{"after": ["<slug>", …]}}'
        ) from e
    after = data.get("after", []) if isinstance(data, dict) else None
    if not isinstance(after, list) or not all(isinstance(s, str) and s.strip() for s in after):
        raise ChantierError(
            f'{path}: expected {{"after": ["<slug>", …]}}, slugs being folder '
            "names without their number"
        )
    return after


def archived_merged(repo: Repo, slug: str) -> bool:
    paths = stage_layout(repo)
    folders = [
        f
        for stage in (paths["archives"], paths["done"])
        if stage.is_dir()
        for f in sorted(stage.iterdir())
    ]
    for folder in folders:
        if folder.is_dir() and folder.name != "batches" and cr_slug(folder.name) == slug:
            try:
                state = json.loads(read_text(folder / "STATUS.json")).get("state")
            except (OSError, ValueError):
                state = "merged"  # an archive holds only merged CRs
            if state == "merged":
                return True
    return False


def declare_dependencies(b: Batch, added: list[CrEntry]) -> None:
    """Record the `after` of each CR just added, as CR ids, once all of them are in the batch.
    A slug archived as merged is met and not recorded; the rest is refused, naming the slug."""
    for c in added:
        ids = list(
            dict.fromkeys(
                dep
                for slug in read_depends(cr_directory(b.repo, c))
                if (dep := _dependency(b, c, slug))
            )
        )
        if ids:
            c.after = ids
            b.log("depends", c.id, after=ids)
    check_cycles(b)


def _dependency(b: Batch, c: CrEntry, slug: str) -> str | None:
    """The id of the CR a `depends.json` slug names; None when it is met (archived as merged)."""
    key = slugify(slug)
    dep = next((x for x in b.record.crs if cr_slug(Path(x.path or "").name) == key), None)
    if dep is None:
        if archived_merged(b.repo, key):
            return None
        raise ChantierError(
            f"{c.id}: depends.json names {slug!r}, which is in "
            "neither the batch nor the archives as merged"
        )
    if is_release(dep) and dep.id != c.id:
        raise ChantierError(
            f"{c.id}: depends.json names {slug!r}, the batch's release "
            f"CR {dep.id}, which waits for every other CR: a cycle. "
            "Remove it from depends.json"
        )
    return None if dep.status == "merged" else dep.id  # archived: met, so not recorded


def check_series_order(b: Batch) -> None:
    """A series runs in the order given: a CR cannot come before one it depends on."""
    place = {x.id: x.order for x in b.record.crs}
    for c in b.record.crs:
        if c.kind in {"release", "fix"}:
            continue
        for dep in c.after:
            if place.get(dep, 0) > c.order:
                raise ChantierError(
                    f"{c.id} depends on {dep}: it cannot come before it in the series"
                )


def _release_tag(b: Batch, c: CrEntry) -> str:
    if alone(b.record.crs, c):
        return " (release, alone in its batch: it starts when taken)"
    return (
        " (release: starts once every other CR is handed back ready (stack, series) or merged "
        "(parallel); its PR is the user's to merge)"
    )


def release_waits_for_all(b: Batch) -> None:
    """The release CR's `after` holds every other CR of the batch that has not ended, fix CRs
    excepted (`pending_fixes` rules those); the CLI keeps the list, and an entry that ends stays
    as history."""
    for rel in b.record.crs:
        if not is_release(rel) or rel.status in ENDED:
            continue
        after = list(rel.after)
        after += [
            x.id
            for x in b.record.crs
            if x.id != rel.id and x.kind != "fix" and x.status not in ENDED and x.id not in after
        ]
        if after:
            rel.after = after
        else:
            rel.unset("after")
    check_cycles(b)


def check_cycles(b: Batch) -> None:
    graph = {x.id: x.after for x in b.record.crs}
    done: set[str] = set()

    def visit(node: str, path: list[str]) -> None:
        if node in path:
            cycle = [*path[path.index(node) :], node]
            raise ChantierError(f"dependency cycle: {' → '.join(cycle)}")
        if node in done:
            return
        for nxt in graph.get(node, []):
            visit(nxt, [*path, node])
        done.add(node)

    for node in graph:
        visit(node, [])


def _cr_line(b: Batch, c: CrEntry) -> str:
    tag = _release_tag(b, c) if c.kind == "release" else ""
    after = f" (after {', '.join(c.after)})" if c.after and c.kind != "release" else ""
    return f"  - {c.id}: {c.title} ({c.path}){tag}{after}\n"


def _brief_text(b: Batch, args: argparse.Namespace, host: str, release: ReleaseGrant | None) -> str:
    repo = b.repo
    data = b.record
    instructions = f"- Project instructions: {instruction_files(repo.root)}"
    if repo.external:
        instructions += f"; the surface's: {instruction_files(repo.surface_root)}"
    return (
        f"# {b.id}\n\n- Mode: {data.mode}. Slots: {args.slots}. "
        f"Budget: {args.budget or 'none'}. Host: {host}. "
        f"Steering: {data.steering}. Factory: {'on' if data.factory else 'off'}.\n"
        + (
            "- CRs, in order: none yet (born paused; each CR made ready with "
            "`triage --ready` joins on its own)\n"
            if not data.crs
            else "- CRs, in order:\n" + "".join(_cr_line(b, c) for c in data.crs)
        )
        + (f"- Release grant: {grant_line(release)}\n" if release else "")
        + instructions
        + ".\n"
        + f"- Timing: {timing_text(data.timing, host)}\n"
        "- Team (who runs which role):\n"
        + (
            f"- CI beside the long gate: on ({ci_source(data.playbook)}).\n"
            if ci_lines(data.playbook)
            else ""
        )
        + "- Autonomous decisions:\n- Questions to bring back:\n"
    )


def _open_crs(b: Batch, args: argparse.Namespace, release: ReleaseGrant | None) -> dict[str, str]:
    """Add each CR; the join lines of those that came back, by id."""
    told: dict[str, str] = {}
    check_joins(b.repo, args.items)  # every move, before the first
    for i, item in enumerate(args.items, 1):
        c, line = join_cr(b, item, kind="release" if i == args.release else "change")
        if line:
            told[c.id] = line
        if release and c.kind == "release":
            release.cr = c.id
    declare_dependencies(b, list(b.record.crs))
    release_waits_for_all(b)
    if args.mode == "series":
        check_series_order(b)
    return told


def _short(p: Path | str) -> str:
    return str(p).replace("\\", "/").split("changes/")[-1]


def _read_configuration(repo: Repo, host: str) -> tuple[Any, Any, Any, Any]:
    """The playbook, the timing and the escalation to freeze in the record, and the limits;
    all the problems found, each once, stop the opening."""
    team, problems = read_playbook(repo, host)
    timing, more = read_timing(repo, host)
    escalation, extra = read_escalation(repo, host)
    limits, last = read_limits(repo)
    more = [*more, *(p for p in [*extra, *last] if p not in problems and p not in more)]
    if problems or more:
        raise ChantierError("\n".join([*problems, *more]), EXIT_PRECONDITION)
    return team, timing, escalation, limits


def _slots_from(args: argparse.Namespace, limits: dict[str, Any]) -> str:
    """`batch.slots` set on `args` when no `--slots`; the label of the layer that set it."""
    if args.slots is not None:
        return ""
    entry = limits.get("batch.slots") or {}
    if entry.get("value") is None:
        raise ChantierError(
            "open: no batch.slots: no plugin defaults file and no chantier.yaml sets it; "
            "give --slots <n>"
        )
    if entry["value"] == 0:
        raise ChantierError(
            f"open: batch.slots is 0 in {entry['src']}: give --slots <n> or set it on the board"
        )
    args.slots = entry["value"]
    return "" if entry["layer"] == "defaults" else f" [{entry['layer']}]"


def _empty_lines(
    repo: Repo, b: Batch, args: argparse.Namespace, shape: tuple[str, Any, Path, str]
) -> list[str]:
    """The output of an `open` with no CR: the batch is born paused, and what comes next."""
    host, data, brief, where = shape
    return [
        f"opened {b.id} on {host}: no CR, paused, {args.slots} slots{where}, "
        f"{data.mode}, steering {data.steering}, factory",
        f"next: complete the brief {shown(repo, brief)}, then start the Foreman (direct mode: "
        f"steer it yourself); {FACTORY_NEXT}",
        *_ready_lines(repo, b),
    ]


FACTORY_NEXT = "each CR made ready with `triage <folder> --ready` joins it on its own (factory)"


def _ready_lines(repo: Repo, b: Batch) -> list[str]:
    """A factory batch: the CRs `3-ready` already holds, which the factory's go covers."""
    left = not_joined_line(repo) if b.record.factory else None
    return [not_joined_text(left, b.id)] if left else []


def _direct_needs_a_chief(args: argparse.Namespace, chief: str | None) -> None:
    if args.direct and not chief:
        raise ChantierError(
            "--direct needs the Chief of Staff's own session id "
            "(CLAUDE_CODE_SESSION_ID or COPILOT_AGENT_SESSION_ID): none is known, "
            "so a Foreman's claim could not be told from the Chief of Staff's",
            EXIT_PRECONDITION,
        )


def _freeze_rules(data: Any, team: Any, escalation: Any, timing: Any) -> None:
    """A running batch keeps the playbook, escalation and timing it opened with."""
    if team:  # the prices are read live at each pricing, not frozen with the roles
        data.playbook = {k: v for k, v in team.items() if k not in ("prices", "price_layers")}
    data.escalation = escalation
    data.timing = timing


def open_batch(args: argparse.Namespace) -> list[str]:
    repo = Repo.find()
    host = detect_host()
    team, timing, escalation, limits = _read_configuration(repo, host)  # before any folder moves
    where = _slots_from(args, limits)
    settings = open_settings(repo, args)
    repo.config.update(settings)
    paths = stage_layout(repo)
    release = release_grant(args)
    chief = own_transcript(host)
    _direct_needs_a_chief(args, chief)
    selected = [prepared_cr(repo, item, paths).directory for item in args.items]
    if len(set(selected)) != len(selected):
        raise ChantierError("the same CR was selected more than once", EXIT_USAGE)
    data = new_record(args, host, settings, release, chief)
    _freeze_rules(data, team, escalation, timing)
    with changes_lock(repo):
        check_no_open_batch(repo)
        with RenderedBatch(repo, None, actor="chief-of-staff", create=data) as b:
            brief = b.dir / "brief.md"
            told = _open_crs(b, args, release)
            brief.write_text(_brief_text(b, args, host, release), encoding="utf-8")
            b.log(
                "open",
                None,
                crs=[c.id for c in b.record.crs],
                **({"factory": True} if b.record.factory else {}),
            )
            if not b.record.crs:
                record_born_paused(b)
    if not args.items:
        return _empty_lines(repo, b, args, (host, data, brief, where))
    lines = [
        f"opened {b.id} on {host}: {len(args.items)} CRs, {args.slots} slots{where}, "
        f"{data.mode}, steering {data.steering}" + (", factory" if data.factory else "")
    ]
    # the next step comes before the CR list: past ten lines it is the list that is cut
    lines.append(
        f"next: complete the brief {shown(repo, brief)}, then "
        + ("steer it yourself" if args.direct else "start the Foreman")
        + (f"; {FACTORY_NEXT}" if data.factory else "")
    )
    lines += _ready_lines(repo, b)
    for c, src in zip(b.record.crs, selected, strict=False):
        lines.append(f"{c.id} {c.title[:40]}: {_short(src)} -> {_short(c.path or '')}")
        lines += [told[c.id]] if c.id in told else []
    return lines + not_running_line(repo)
