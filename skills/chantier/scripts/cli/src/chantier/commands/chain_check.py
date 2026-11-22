"""The chain check of an ordered batch: a CR the record places on another CR's branch must hold
that CR's recorded head (`stack_chain.chain_below`). Read-only: nothing is fetched or recorded."""

from __future__ import annotations

from pathlib import Path

from chantier.commands.crs import short_head
from chantier.core.errors import EXIT_PRECONDITION, ChantierError
from chantier.core.git import git, is_ancestor
from chantier.core.records import BatchRecord, CrEntry
from chantier.core.repo import Repo
from chantier.hub import journal
from chantier.stack_chain import chain_below
from chantier.stacks import chain


def landed_of(repo: Repo, d: BatchRecord) -> frozenset[str]:
    """The CRs of the batch the forge hub saw merged, as `take` reads them."""
    return journal.seen_merged(journal.read(repo.store, repo.changes)[0], d)


def _below_head(
    d: BatchRecord, c: CrEntry, repo: Repo, landed: frozenset[str]
) -> tuple[CrEntry, str] | None:
    """The CR below `c` in an ordered batch and its recorded head, None when `c` is not checked
    or the CR below was never shipped (no head to hold)."""
    below = chain_below(d, c, repo, landed)
    return (below, below.head) if below is not None and below.head else None


def refuse_off_chain(repo: Repo, d: BatchRecord, c: CrEntry, wt: Path, head: str) -> None:
    """`ship`: refuse, recording nothing, a CR placed on another CR's branch (the release on the
    top CR) whose head does not hold that CR's recorded head. The first message says rebase; the
    second, when the head already holds the remote tip of the branch below and that tip is past
    the recorded head, says that CR ships first. Reads only; the remote ref is read as the clone
    has it."""
    if d.mode not in {"stack", "series"}:
        return
    found = _below_head(d, c, repo, landed_of(repo, d))
    if found is None:
        return
    below, rec = found
    held = is_ancestor(rec, head, cwd=wt)
    if held:
        return
    rec7 = short_head(rec)
    if held is None:
        raise ChantierError(
            f"{c.id}: git cannot read {below.id}'s head {rec7}: fetch, then ship again; "
            "nothing recorded",
            EXIT_PRECONDITION,
        )
    tip = f"{repo.config['remote']}/{below.branch}"
    if is_ancestor(tip, head, cwd=wt) and is_ancestor(tip, rec, cwd=wt) is False:
        tip7 = short_head(git("rev-parse", "--verify", "--quiet", tip, cwd=wt, check=False))
        raise ChantierError(
            f"{c.id}: {below.id}'s branch moved since its last ship ({rec7} -> {tip7}): it ships "
            "first, then ship again; nothing recorded",
            EXIT_PRECONDITION,
        )
    raise ChantierError(
        f"{c.id}: branch not based on {below.id}'s head {rec7}: rebase onto {below.branch}, "
        "push, ship again; nothing recorded",
        EXIT_PRECONDITION,
    )


def check_chain(repo: Repo, d: BatchRecord, crs: list[CrEntry]) -> None:
    """`stack --out-of-draft`: bottom up over the named CRs, refuse the first whose recorded head
    does not hold its CR below's recorded head; its fix starts with putting back to draft the
    PRs of it and of every named CR above it."""
    landed = landed_of(repo, d)
    ids = [x.id for x in chain(d)]
    ordered = sorted(crs, key=lambda x: ids.index(x.id) if x.id in ids else len(ids))
    cwd = repo.clone if repo.external else repo.root
    for i, c in enumerate(ordered):
        found = _below_head(d, c, repo, landed)
        if found is None or not c.head:
            continue
        below, rec = found
        held = is_ancestor(rec, c.head, cwd=cwd)
        if held:
            continue
        rec7 = short_head(rec)
        if held is None:
            raise ChantierError(
                f"{c.id}: git cannot read {below.id}'s head {rec7}: fetch, then stack "
                "--out-of-draft again; nothing recorded",
                EXIT_PRECONDITION,
            )
        back = ", ".join(x.id for x in ordered[i:])
        raise ChantierError(
            f"{c.id}: branch not based on {below.id}'s head {rec7}: put {back}' PRs back to "
            f"draft, rebase onto {below.branch}, push, ship, then stack --out-of-draft again; "
            "nothing recorded",
            EXIT_PRECONDITION,
        )
