"""`chantier rules` and `chantier playbook`."""

from __future__ import annotations

import argparse
import re
from collections.abc import Iterator
from pathlib import Path

from chantier.core.batch import read_batch, resolve_batch
from chantier.core.errors import EXIT_PRECONDITION, ChantierError
from chantier.lifecycle.convert import open_repo
from chantier.playbook.config import FILE
from chantier.playbook.lines import escalate_line, playbook_lines
from chantier.plugin_files import (
    INSTRUCTIONS,
    chief_prompt_lines,
    detect_host,
    plugin_roles,
    project_instructions,
    read_playbook,
    surface_instructions,
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
    repo = open_repo()
    if args.batch:
        d = read_batch(repo, resolve_batch(repo, args.batch))
        made, host = d.playbook, d.host
        label = d.id or args.batch
    else:
        host = detect_host(args.host)
        made, problems = read_playbook(repo, host)
        label = None
        if problems:
            return [
                f"playbook: {FILE} is not valid ({len(problems)} problems)",
                *problems,
            ], EXIT_PRECONDITION
    lines = playbook_lines(made, host, plugin_roles(host), label)
    if not args.batch:  # the Chief of Staff's subagents' first lines, to copy as printed
        lines += chief_prompt_lines(host, repo.root.as_posix())
    lines.append(escalate_line(host))
    return lines, 0


def rules(args: argparse.Namespace) -> list[str]:
    """The project's rules: its instruction file and the local Markdown files it links, two
    levels deep. Every role reads them before its own card; they rank above it."""
    repo = open_repo()
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
