"""A PR's real base and draft state: what the forge holds, read once, for `ship` (every CR),
and the base alone for `take`, `round` and `handoff` (a stacked CR). It reuses `forge-stack`'s calls
(`pr_parts`, `gh`, `glab`): no copy."""

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


def pr_state(link: str) -> tuple[str, bool]:
    """The base branch and the draft state of the PR or MR at `link`, from the forge (one read,
    no retry). The forge is read from the shape of the link. A failed read, or a draft field
    that is not a boolean, raises."""
    host, owner, name, number = pr_parts(link)
    if GITLAB_LINK.match(link):
        mr = glab(f"projects/{quote(owner, safe='')}/merge_requests/{number}", host)
        base, draft = str(mr["target_branch"]), mr["draft"]
    else:
        pull = gh(["-X", "GET", f"repos/{owner}/{name}/pulls/{number}"], host)
        base, draft = str(pull["base"]["ref"]), pull["draft"]
    if not isinstance(draft, bool):
        raise TypeError("draft is not a boolean")
    return base, draft


def read_state(link: str) -> tuple[str | None, bool | None, str]:
    """`(branch, draft, "")` read from the forge, or `(None, None, the unread text)` when the
    read failed: `base ? (not read from <link>: <the forge's text, one line>)`."""
    try:
        base, draft = pr_state(link)
        return base, draft, ""
    except (ChantierError, KeyError, TypeError) as e:
        why = " ".join(str(e).split()) or type(e).__name__
        return None, None, UNREAD.format(link=link, why=why)


def read_base(link: str) -> tuple[str | None, str]:
    """`(branch, "")` read from the forge, or `(None, the unread text)` when the read failed."""
    base, _, shown = read_state(link)
    return base, shown


def stacked_read(d: BatchRecord, c: CrEntry) -> tuple[str | None, str] | None:
    """`read_base` for a stacked CR with a PR recorded; None for any other CR (no forge call)."""
    if not c.pr or not is_stacked(d, c):
        return None
    return read_base(c.pr)
