"""A stacked CR's real base: the branch its PR targets on the forge, read once, for `take`,
`handoff` and `ship`. It reuses `forge-stack`'s calls (`pr_parts`, `gh`, `glab`): no copy."""

from __future__ import annotations

from urllib.parse import quote

from chantier.commands.forge_stack_gh import gh, pr_parts
from chantier.commands.forge_stack_gitlab import GITLAB_LINK, glab
from chantier.core.errors import ChantierError
from chantier.core.records import BatchRecord, CrEntry
from chantier.stacks import chain

UNREAD = "base ? (not read from {link}: {why})"


def is_stacked(d: BatchRecord, c: CrEntry) -> bool:
    """A CR of a batch in `stack` mode that is in its chain (not ended, not a fix)."""
    return d.mode == "stack" and any(x.id == c.id for x in chain(d))


def pr_base(link: str) -> str:
    """The base branch of the PR or MR at `link`, from the forge (one read, no retry). The forge
    is read from the shape of the link. A failed read raises `ChantierError`."""
    host, owner, name, number = pr_parts(link)
    if GITLAB_LINK.match(link):
        mr = glab(f"projects/{quote(owner, safe='')}/merge_requests/{number}", host)
        return str(mr["target_branch"])
    pull = gh(["-X", "GET", f"repos/{owner}/{name}/pulls/{number}"], host)
    return str(pull["base"]["ref"])


def read_base(link: str) -> tuple[str | None, str]:
    """`(branch, "")` read from the forge, or `(None, the unread text)` when the read failed:
    `base ? (not read from <link>: <the forge's text, one line>)`."""
    try:
        return pr_base(link), ""
    except (ChantierError, KeyError, TypeError) as e:
        why = " ".join(str(e).split()) or type(e).__name__
        return None, UNREAD.format(link=link, why=why)


def stacked_read(d: BatchRecord, c: CrEntry) -> tuple[str | None, str] | None:
    """`read_base` for a stacked CR with a PR recorded; None for any other CR (no forge call)."""
    if not c.pr or not is_stacked(d, c):
        return None
    return read_base(c.pr)
