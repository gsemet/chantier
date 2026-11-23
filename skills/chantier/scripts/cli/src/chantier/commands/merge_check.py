"""`ship`'s refusal of a head that holds a merge commit among the CR's own commits."""

from __future__ import annotations

from pathlib import Path

from chantier.commands.carry import head_base
from chantier.commands.crs import short_head
from chantier.core.errors import EXIT_PRECONDITION, ChantierError
from chantier.core.git import git
from chantier.core.records import BatchRecord, CrEntry
from chantier.core.repo import Repo


def refuse_merge_commit(repo: Repo, d: BatchRecord, c: CrEntry, wt: Path, head: str) -> None:
    """Refuse a head that holds a merge commit among the CR's own commits: those above the base
    it sits on (`head_base`), else above the remote default branch. A git failure is a refusal
    too, never read as "no merge commit"."""
    base = head_base(repo, d, c, wt, head)
    remote = repo.config["remote"]
    name = f"{remote}/{base.branch}" if base else f"{remote}/{repo.config['default_branch']}"
    lower = base.sha if base else name
    short = short_head(head)
    try:
        merges = git("rev-list", "--merges", f"{lower}..{head}", cwd=wt).split()
    except ChantierError as e:
        first = str(e).splitlines()[0].split(": ", 1)[-1] if str(e) else ""
        raise ChantierError(
            f"{c.id}: cannot check {short} for a merge commit: git could not read "
            f"{name}..{short}: {first}; fetch and ship again",
            EXIT_PRECONDITION,
        ) from e
    if merges:
        raise ChantierError(
            f"{c.id}: {short} holds a merge commit ({short_head(merges[0])}) above {name}: "
            "chantier's PRs hold none; rebase onto "
            f"{base.branch if base else repo.config['default_branch']} "
            f"(git -C {wt} rebase {name}), push with --force-with-lease, and ship again",
            EXIT_PRECONDITION,
        )
