"""`chantier conflicts <cr> --epoch N`: the Foreman's early conflict check of a parallel batch.

The CR against each other CR that is ready with a PR on the default branch, by `git merge-tree
--write-tree` only (it writes objects, no ref, branch, index or worktree file): one note on the
CR per conflicting pair, and the one ask printed for the steering session to send. It records no
ask, switches no mode, starts no rebase, reads no forge."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from chantier.core import git
from chantier.core.batch import check_epoch, find_cr_batch, require_epoch
from chantier.core.errors import EXIT_PRECONDITION, ChantierError
from chantier.core.records import CrEntry
from chantier.core.repo import Repo
from chantier.lifecycle.filing import slugify
from chantier.lifecycle.session import RenderedBatch
from chantier.lifecycle.stages import cr_slug

MERGE_TREE_WRITE = (2, 38, 0)
NOTE_PATHS = 5


def _refuse_old_git(cr: str, epoch: int) -> None:
    text = git.version_text()
    found = git.parse_version(text)
    if found is None:
        raise ChantierError(
            f"conflicts: cannot read git's version (git --version: {text or 'not found'}): "
            "git 2.38 or later is needed",
            EXIT_PRECONDITION,
        )
    if found < MERGE_TREE_WRITE:
        raise ChantierError(
            f"conflicts: git {'.'.join(map(str, found))} is older than 2.38, which git "
            f"merge-tree --write-tree needs: update git, then run conflicts {cr} --epoch "
            f"{epoch} again",
            EXIT_PRECONDITION,
        )


def _name(c: CrEntry) -> str:
    """`CR-<n> <slug>`: how the ask names a CR to the user."""
    slug = cr_slug(Path(c.path).name) if c.path else slugify(c.title)
    return f"{c.id} {slug}".rstrip()


def _chained(c: CrEntry, o: CrEntry) -> bool:
    return (
        o.id in c.after
        or c.id in o.after
        or c.start_on == o.branch
        or o.start_on == c.branch
        or c.pr_base == o.branch
        or o.pr_base == c.branch
    )


def _noted(c: CrEntry, o: CrEntry) -> bool:
    for holder, other in ((c, o), (o, c)):
        for n in holder.notes:
            head = f"early conflict: with {other.id}"
            if n.startswith(head) and n[len(head) : len(head) + 1] in (":", " "):
                return True
    return False


def _read(root: Path, one: CrEntry, other: CrEntry) -> tuple[list[str] | None, str]:
    """(the conflicting paths, "") on exit 1; ([], "") when clean; (None, why) when not run."""
    code, out, err = git.run(
        "merge-tree",
        "--write-tree",
        "--name-only",
        "--no-messages",
        one.branch,
        other.branch,
        cwd=root,
    )
    if code == 0:
        return [], ""
    lines = out.splitlines()
    # a missing ref also exits 1, with no tree id on the first line of its output
    if code == 1 and lines and re.fullmatch(r"[0-9a-f]{40,64}", lines[0].strip()):
        return list(dict.fromkeys(ln for ln in lines[1:] if ln.strip())), ""
    why = next((ln for text in (err, out) for ln in text.splitlines() if ln.strip()), "")
    return None, why.strip() or f"git exited {code}"


def _shown(paths: list[str]) -> str:
    more = len(paths) - NOTE_PATHS
    return ", ".join(paths[:NOTE_PATHS]) + (f" and {more} more" if more > 0 else "")


def _check(
    repo: Repo, b: RenderedBatch, c: CrEntry, others: list[CrEntry]
) -> tuple[list[str], dict[str, int], list[CrEntry], list[str]]:
    """Run the pairs and note them: (the lines, the tally, the conflicting CRs, their paths)."""
    lines: list[str] = []
    tally = {"conflict": 0, "clean": 0, "skipped": 0, "not run": 0}
    hit: list[CrEntry] = []
    paths: list[str] = []
    for o in others:
        pair = f"{c.id} x {o.id}"
        if skip := "chained" if _chained(c, o) else "already noted" if _noted(c, o) else "":
            lines.append(f"{pair}: skipped: {skip}")
            tally["skipped"] += 1
            continue
        found, why = _read(repo.root, c, o)
        if found is None:
            text = f"early conflict check: not run against {o.id}: {why}"
            lines.append(f"{pair}: not run: {why}; noted")
            tally["not run"] += 1
        elif not found:
            lines.append(f"{pair}: clean")
            tally["clean"] += 1
            continue
        else:
            text = f"early conflict: with {o.id}: {_shown(found)}"
            lines.append(f"{pair}: conflict in {_shown(found)}; noted")
            tally["conflict"] += 1
            hit.append(o)
            paths += found
        c.append("notes", text)
        b.touch(c)
        b.log("note", c.id, note=text)
    return lines, tally, hit, paths


def conflicts(args: argparse.Namespace) -> list[str]:
    repo = Repo.find()
    cr = args.cr
    require_epoch(args.epoch, "conflicts <cr> --epoch <n>")
    _refuse_old_git(cr, args.epoch)
    with RenderedBatch(repo, find_cr_batch(repo, cr, args.batch), actor="foreman") as b:
        check_epoch(b, args.epoch)
        mode = b.record.mode or "parallel"
        if mode != "parallel":
            return [
                f"conflicts: not run: {b.id} is a {mode} batch, where the PRs sit on one "
                "another; a conflict there is the stack driver's anomaly"
            ]
        c = b.cr(cr)
        if c.status != "ready" or not c.pr:
            raise ChantierError(
                f"conflicts: {c.id} is {c.status}{'' if c.pr else ' with no PR'}: the check "
                "runs at its ready hand-back with a PR; run conflicts "
                f"{c.id} --epoch {args.epoch} once it is handed back ready",
                EXIT_PRECONDITION,
            )
        default = repo.config["default_branch"]
        others = [
            o
            for o in b.record.crs
            if o.id != c.id and o.status == "ready" and o.pr and o.pr_base in (None, default)
        ]
        if not others:
            return [f"conflicts: {c.id}: no other ready PR on {default} to check against"]
        lines, tally, hit, paths = _check(repo, b, c, others)
        out = [
            f"conflicts: {c.id} against {len(others)} ready PR(s): {tally['conflict']} in "
            f"conflict, {tally['clean']} clean, {tally['skipped']} skipped (already noted or "
            f"chained), {tally['not run']} not run",
            *lines,
        ]
        if hit:
            ask = (
                f"conflict {_name(c)} with {', '.join(_name(o) for o in hit)}: "
                f"{', '.join(dict.fromkeys(paths))}; switch to a stack?"
            )
            out.append(f'next: asks "{ask}"')
        return out
