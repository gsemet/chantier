"""`chantier rules` and `chantier playbook`."""

from __future__ import annotations

import argparse
import re
from collections.abc import Iterator
from pathlib import Path

from chantier.core.batch import read_batch, resolve_batch
from chantier.core.errors import EXIT_PRECONDITION, ChantierError
from chantier.core.repo import Repo
from chantier.lifecycle.stages import specifying_markers
from chantier.playbook.lines import (
    escalate_line,
    events_line,
    limits_line,
    long_gate_lines,
    playbook_lines,
    timing_lines,
    timing_warnings,
)
from chantier.playbook.long_gate import load_long_gate
from chantier.plugin_files import (
    INSTRUCTIONS,
    chief_prompt_lines,
    detect_host,
    plugin_roles,
    project_instructions,
    read_escalation,
    read_limits,
    read_playbook,
    read_timing,
    read_wake_rules,
    recorded_escalation,
    recorded_timing,
    surface_instructions,
    user_files,
)

MD_LINK = re.compile(r"\]\(([^)\s#]+\.md)(?:#[^)]*)?\)|^\[[^\]]+\]:\s*(\S+\.md)\s*$", re.M)


def _candidates(path: Path, root: Path, target: str, seen: list[Path]) -> Iterator[Path]:
    """The files a link may name, the first one that is in the project and not seen yet."""
    for raw in (path.parent / target, root / target):
        try:
            candidate = raw.resolve()
        except OSError:
            continue
        if candidate.is_file() and candidate.is_relative_to(root) and candidate not in seen:
            yield candidate


def linked(path: Path, root: Path, seen: list[Path], depth: int) -> None:
    text = path.read_text(encoding="utf-8", errors="replace")
    for m in MD_LINK.finditer(text):
        target = m.group(1) or m.group(2)
        if target.startswith(("http://", "https://", "/")) or ".." in target.split("/"):
            continue
        found = next((c for c in _candidates(path, root, target, seen) if c), None)
        if found:
            seen.append(found)
            if depth > 1:
                linked(found, root, seen, depth - 1)


def playbook(args: argparse.Namespace) -> tuple[list[str], int]:
    """The project's playbook: which agent and model each role of the plugin runs. Without
    `--batch` it reads `chantier.yaml` now, for the host; with it, the playbook the batch opened
    with (a batch with none recorded runs the plugin's agents and models)."""
    repo = Repo.find()
    if args.batch:
        d = read_batch(repo, resolve_batch(repo, args.batch))
        made, host, timing = d.playbook, d.host, recorded_timing(d)
        escalation = recorded_escalation(d)
        label = d.id or args.batch
        limits, last = read_limits(repo)  # live, never frozen with the batch
    else:
        host = detect_host(args.host)
        made, problems = read_playbook(repo, host)
        timing, more = read_timing(repo, host)
        escalation, extra = read_escalation(repo, host)
        limits, last = read_limits(repo)
        problems += [p for p in dict.fromkeys([*more, *extra, *last]) if p not in problems]
        label = None
        if problems:
            return [
                f"playbook: the configuration ({', '.join(user_files(repo)) or 'no user file'}) "
                f"is not valid ({len(problems)} problems)",
                *problems,
            ], EXIT_PRECONDITION
    lines = playbook_lines(made, host, plugin_roles(host), label, escalation)
    gate = load_long_gate(repo)  # live, like the limits: the commands are never frozen
    lines += (
        long_gate_lines(gate.commands, gate.ignored)
        if not gate.problems
        else [f"long gate: not readable: {gate.problems[0]}"]
    )
    lines += timing_lines(timing, host) + timing_warnings(timing, host)
    lines.append(
        limits_line(limits, specifying_markers(repo))
        if not args.batch or not last
        else f"limits: not readable: {last[0]}"
    )
    wake = read_wake_rules(repo)
    lines.append(
        events_line(wake)
        if not wake["events_problems"]
        else f"events: not readable: {wake['events_problems'][0]}"
    )
    # first lines to copy as printed: the Chief of Staff's all, the Foreman's (in a batch) only
    # those of the agents whose description says the Foreman starts them
    started_by = "Foreman" if args.batch else None
    lines += chief_prompt_lines(host, repo.root.as_posix(), started_by, made, escalation)
    lines.append(escalate_line(escalation))
    return lines, 0


def rules(args: argparse.Namespace) -> list[str]:
    """The project's rules: its instruction file and the local Markdown files it links, two
    levels deep. Every role reads them before its own card; they rank above it."""
    repo = Repo.find()
    found, outer = project_instructions(repo), surface_instructions(repo)
    if not found and not outer:
        raise ChantierError(f"no {', '.join(INSTRUCTIONS)} in {repo.session_root}: ask your parent")

    def listed(first: Path | None, root: Path) -> list[str]:
        if not first:
            return []
        seen = [first.resolve()]
        linked(first.resolve(), root.resolve(), seen, 2)
        return [
            f"{p.as_posix()} ({sum(1 for _ in p.open(encoding='utf-8', errors='replace'))} lines)"
            for p in seen
        ]

    if not repo.external:
        return listed(found, repo.root)
    return ["project:", *listed(found, repo.root), "surface:", *listed(outer, repo.surface_root)]
