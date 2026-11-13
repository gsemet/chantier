"""`chantier rules` and `chantier playbook`."""

from __future__ import annotations

import re
from pathlib import Path

from chantier.commands.registry import BATCH, Subparsers, add_command
from chantier.core.batch import read_batch, resolve_batch
from chantier.core.errors import EXIT_PRECONDITION, ChantierError
from chantier.lifecycle.convert import open_repo
from chantier.playbook.config import FILE
from chantier.playbook.lines import escalate_line, playbook_lines
from chantier.plugin_files import (
    INSTRUCTIONS,
    detect_host,
    plugin_roles,
    project_instructions,
    read_playbook,
    surface_instructions,
)

MD_LINK = re.compile(r"\]\(([^)\s#]+\.md)(?:#[^)]*)?\)|^\[[^\]]+\]:\s*(\S+\.md)\s*$", re.M)


def linked(path: Path, root: Path, seen: list[Path], depth: int) -> None:
    text = path.read_text(encoding="utf-8", errors="replace")
    for m in MD_LINK.finditer(text):
        target = m.group(1) or m.group(2)
        if target.startswith(("http://", "https://", "/")) or ".." in target.split("/"):
            continue
        for raw in (path.parent / target, root / target):
            try:
                candidate = raw.resolve()
            except OSError:
                continue
            if candidate.is_file() and candidate.is_relative_to(root) and candidate not in seen:
                seen.append(candidate)
                if depth > 1:
                    linked(candidate, root, seen, depth - 1)
                break


def playbook(args) -> tuple[list[str], int]:
    """The project's playbook: which agent and model each role of the plugin runs. Without
    `--batch` it reads `chantier.yaml` now, for the host; with it, the playbook the batch opened
    with (a batch with none recorded runs the plugin's agents and models)."""
    repo = open_repo()
    if args.batch:
        d = read_batch(repo, resolve_batch(repo, args.batch))
        made, host = d.get("playbook"), d["host"]
        label = d.get("id") or args.batch
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
    if not args.batch:  # the Spec-writer's first line, to copy as printed
        lines.append(
            "spec-writer prompt, first line: chantier spec-writer for the Chief of Staff, "
            f"in the project {repo.root.as_posix()}."
        )
    lines.append(escalate_line(host))
    return lines, 0


def rules(args) -> list[str]:
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
    return ["project:", *listed(found, repo.root), "surface:", *listed(outer, repo.surface)]


def register(sub: Subparsers) -> None:
    """Declare this module's commands."""
    add_command(sub, "rules", rules, "the project's instruction file and the files it links", BATCH)

    s = add_command(
        sub,
        "playbook",
        playbook,
        "the agent and model each role runs, from chantier.yaml (or, with --batch, as the batch "
        "opened); "
        "exit 2 if the file is invalid",
        BATCH,
    )
    s.add_argument(
        "--host",
        choices=["claude", "copilot"],
        help="the host to resolve for (default: the detected host); ignored with --batch",
    )
