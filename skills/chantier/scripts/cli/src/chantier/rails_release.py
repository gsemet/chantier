"""The refusals of a release and of the grant: what lets an irreversible action go."""

from __future__ import annotations

import re

from chantier.core.batch import Batch
from chantier.core.clock import now
from chantier.core.errors import EXIT_BUDGET, EXIT_USAGE, ChantierError
from chantier.lifecycle.stages import done_cr
from chantier.rails import ENDED, all_merged, check_budget, over_budget, pending_fixes

MAX_GRANTED_FIXES = 3


def merge_done(b: Batch, c: dict) -> list[str]:
    """The PR is merged: the folder goes to `3-done`, where it stays until `close` archives it.
    Returns what the Foreman should hear."""
    done_cr(b, c)
    b.touch(c, status="merged")
    lines = [f"merged {c['id']}: moved to 3-done"]
    if all_merged(b):
        lines.append("every CR is merged or cancelled: `chantier pause`")
    return lines


def release_merged(b: Batch, c: dict) -> None:
    """The release PR is merged: that merge is the go for the rest of the procedure (the field
    `merged_pr`), which goes on with a new Driver; the next attempt opens a PR of its own."""
    c.setdefault("notes", []).append(f"merged: {c.get('pr')}")
    b.touch(c, status="queued", pr=None, head=None, merged_pr=c.get("pr") or "the release PR")


def release_go(b: Batch, c: dict, action: str) -> tuple[str, str]:
    """Spend what allows one irreversible action: `go` and why, `budget`, `fix` (a fix of this
    release is not merged), `merge` (the other CRs of the batch are not all merged or cancelled,
    which nothing lifts, or the release PR is recorded and not merged, which only the grant
    lifts: the steering session's merge), or `ask`. After the merge, the release PR's merge (or
    the user's word to run a procedure with no release PR) is the go; a `go` is for that
    action, in that Driver: the log keeps it, the CR does not."""
    grant = b.data["release"]
    granted = grant.get("autonomous", 0) > grant.get("published", 0)
    if over_budget(b):
        b.log("release-go", c["id"], action=action, result="budget")
        return "budget", ""
    fixes = pending_fixes(b.data["crs"], c)
    if fixes:
        b.log("release-go", c["id"], action=action, result="fix", fixes=fixes)
        return "fix", " ".join(fixes)
    open_ = [
        x["id"]
        for x in b.data["crs"]
        if x["id"] != c["id"] and x.get("kind") != "fix" and x["status"] not in ENDED
    ]
    if open_:
        b.log("release-go", c["id"], action=action, result="merge", open=open_)
        return (
            "merge",
            f"{' '.join(open_)} not merged: every irreversible step waits for their merge",
        )
    if c.get("pr") and not granted:
        b.log("release-go", c["id"], action=action, result="merge", pr=c["pr"])
        return "merge", f"the release PR {c['pr']} is the user's to merge"
    if c.get("merged_pr"):
        why = f"the release PR {c['merged_pr']} was merged"
    elif c.get("procedure"):
        why = f"the user's word to run the release procedure: {c['procedure']}"
    elif c.get("approvals"):
        why = f"the user approved: {c['approvals'].pop(0)}"
    elif granted:
        why = (
            f"the user allowed {grant['autonomous']} releases without asking; "
            f"{grant.get('published', 0)} published"
        )
    else:
        b.log("release-go", c["id"], action=action, result="ask")
        return "ask", ""
    b.touch(c)
    b.log("release-go", c["id"], action=action, result="go", why=why)
    return "go", why


def fix_go(b: Batch, c: dict, action: str) -> tuple[str, str]:
    """The Foreman merges a ready fix of the release under the user's grant, within the budget:
    `go`, `budget`, or `ask` (the user merges it)."""
    if c["status"] != "ready":
        raise ChantierError(f"{c['id']} is {c['status']}: only a ready fix merges")
    result = "budget" if over_budget(b) else "go" if b.data["release"].get("fixes") else "ask"
    b.log("release-go", c["id"], action=action, result=result)
    return result, "the user granted the release's fixes"


def check_granted_fix(b: Batch, c: dict) -> None:
    """The Foreman starts a fix of release `c` only under the user's grant, within the budget,
    and up to MAX_GRANTED_FIXES; past that, a fix is the user's go."""
    if not b.data["release"].get("fixes"):
        raise ChantierError(
            "no grant for the release's fixes: the user's go comes as `order add --fix-for`"
        )
    check_budget(b)
    if sum(x.get("fix_for") == c["id"] for x in b.data["crs"]) >= MAX_GRANTED_FIXES:
        raise ChantierError(
            f"{MAX_GRANTED_FIXES} fixes under the grant: another one is the user's go", EXIT_BUDGET
        )


GRANT = "releases=<n> fixes=<on|off> budget=<usd>"


def parse_grant(text: str) -> dict:
    """What the user allows without asking: a number of releases, the release's fixes started
    and merged by the Foreman, and the budget they run within. Any of the three."""
    grant = {}
    for word in text.split():
        key, _, value = word.partition("=")
        if key == "releases" and value.isdigit():
            grant["autonomous"] = int(value)
        elif key == "fixes" and value in ("on", "off"):
            grant["fixes"] = value == "on"
        elif key == "budget" and re.fullmatch(r"\d+(\.\d+)?", value) and float(value) > 0:
            grant["budget_usd"] = float(value)
        else:
            raise ChantierError(f"grant: `{GRANT}`, any of them; not {word!r}", EXIT_USAGE)
    if not grant:
        raise ChantierError(f"grant: `{GRANT}`, any of them", EXIT_USAGE)
    return grant


def check_grant(release: dict, budget: float | None) -> None:
    """Autonomy is always bounded by a budget."""
    if (release.get("autonomous") or release.get("fixes")) and not budget:
        raise ChantierError(
            "a release grant needs a batch budget: `budget=<usd>` (or `open --budget`)", EXIT_USAGE
        )


def record_ask(b: Batch, text: str) -> str:
    """What the Chief of Staff must hear stays in the state until it has read it, whatever
    becomes of the message. Returns the ask's id."""
    asks = b.data.setdefault("asks", [])
    aid = f"A-{len(asks) + 1}"
    asks.append({"id": aid, "text": text, "sent": now(), "read": None})
    b.log("ask", None, ask=aid, text=text)
    return aid
