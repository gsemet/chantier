"""What `forge-stack` reads the same on both forges: check 4 against each CR's status, the
mergeable part and its commit, the `to come:` line. `mark` is `#` (GitHub PRs) or `!` (GitLab
MRs), `noun` is `PR` or `MR`."""

from __future__ import annotations

from typing import Any

Where = tuple[str, str, str]


def left(come: list[dict[str, Any]]) -> dict[int, str]:
    """The PRs of the batch's stack left out of the rows (a CR above one with no PR)."""
    return {c["number"]: c["cr"] for c in come if c["number"] is not None}


def come_line(rows: list[dict[str, Any]], come: list[dict[str, Any]], merge: int) -> list[str]:
    """`to come:` the drafts' CRs, then those with no PR, bottom first; nothing when complete."""
    todo = [*rows[merge:], *come]
    return ["to come: " + ", ".join(f"{c['cr']} {c['word']}" for c in todo)] if todo else []


def draft_checks(
    prs: list[dict[str, Any]], rows: list[dict[str, Any]], mark: str = "#", noun: str = "PR"
) -> list[str]:
    """Check 4, each PR's draft state read against its CR's status and against the draft state
    the CLI recorded, bottom first. A draft on top of a CR that is not ready is no failure."""
    cr = {r["number"]: r for r in rows}
    lines = []
    still = []
    below_ready = True  # every CR under this PR is ready
    for i, p in enumerate(prs):
        n, draft = p["number"], bool(p.get("draft"))
        status = cr[n]["status"] if n in cr else ""
        kept = cr[n].get("recorded") if n in cr else None
        if kept is not None and kept != draft:
            said = ("draft", "out of draft")
            lines.append(
                f"check 4: recorded {said[not kept]} {mark}{n}, the forge says {said[not draft]}"
            )
        if draft and any(not q.get("draft") for q in prs[i + 1 :]):
            lines.append(f"check 4: a draft under a ready {noun} {mark}{n}")
        elif draft and below_ready and status == "ready":
            still.append(f"{mark}{n}")
        elif not draft and n in cr and status != "ready":
            lines.append(f"check 4: not a draft {mark}{n} ({cr[n]['cr']} {cr[n]['word']})")
        below_ready = below_ready and status == "ready"
    return ([f"check 4: still a draft {' '.join(still)}"] if still else []) + lines


def mergeable(rows: list[dict[str, Any]], drafts: set[int]) -> int:
    """How many CRs from the bottom are ready with a PR that is not a draft."""
    merge = 0
    while (
        merge < len(rows)
        and rows[merge]["status"] == "ready"
        and rows[merge]["number"] not in drafts
    ):
        merge += 1
    return merge


def ready_tail(
    rows: list[dict[str, Any]],
    come: list[dict[str, Any]],
    drafts: set[int],
    release: dict[str, Any] | None,
    mark: str = "#",
) -> tuple[str, list[str]]:
    """The end of the success line (the mergeable part, the drafts on top, the release) and the
    `to come:` lines."""
    noun = "MR" if mark == "!" else "PR"
    merge = mergeable(rows, drafts)
    top = rows[merge - 1] if merge else None
    if top is None:
        part = "no part mergeable yet"
    elif merge == len(rows) and not come:
        part = f"stack complete, mergeable below {top['head']} ({mark}{top['number']})"
    else:
        part = (
            f"partial stack mergeable below {top['head']} ({mark}{top['number']}, {merge} {noun}s)"
        )
    if rows[merge:]:
        part += ", drafts on top " + " ".join(f"{mark}{r['number']}" for r in rows[merge:])
    if release:
        part += ", the release on top"
    return part, come_line(rows, come, merge)
