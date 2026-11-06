"""The rails: what the CLI refuses whatever an agent decides, and the facts it keeps straight.

Nothing here decides what a batch does next; the Foreman does, from `chantier status`. A rail is
a refusal (a take past the budget or the slots, a round past the limit, an irreversible action
without the user's word), and a fact is a record two runs must agree on (an archive on merge).
"""
from __future__ import annotations

import re

from .lifecycle import archive_cr
from .state import (EXIT_BUDGET, EXIT_PRECONDITION, EXIT_USAGE, LIVE, Batch, ChantierError, Repo, now,
                    round_limit)

ENDED = {"merged", "cancelled"}
MAX_GRANTED_FIXES = 3


def check_no_open_batch(repo: Repo) -> None:
    """One batch at a time, whatever its state until `close`: new work joins it by `order add`."""
    folders = repo.batch_folders()
    if folders:
        raise ChantierError(f"{folders[0].name} is open (a landed batch stays until `close`): "
                            "`order add` joins new work to it", EXIT_PRECONDITION)


def live(b: Batch) -> list[dict]:
    return [c for c in b.data["crs"] if c["status"] in LIVE]


def over_budget(b: Batch) -> bool:
    budget = b.data.get("budget_usd")
    return bool(budget) and b.data.get("spent_usd", 0) >= budget


def others_merged(b: Batch, c: dict) -> bool:
    return all(x["status"] in ENDED for x in b.data["crs"] if x is not c)


def all_merged(b: Batch) -> bool:
    return all(c["status"] in ENDED for c in b.data["crs"])


def check_budget(b: Batch) -> None:
    """No Driver of any kind starts past the budget; the ones already live, and their workers,
    go on."""
    if over_budget(b):
        raise ChantierError(f"budget spent: ${b.data.get('spent_usd', 0):.2f} of "
                            f"${b.data['budget_usd']}; only the user raises it (`order budget`)",
                            EXIT_BUDGET)


def pending_fixes(b: Batch, c: dict) -> list[str]:
    """The fix CRs of a release that have not ended: the release waits for them."""
    return [x["id"] for x in b.data["crs"] if x.get("fix_for") == c["id"]
            and x["status"] not in ENDED]


def check_take(b: Batch, c: dict, note: str | None) -> None:
    """A Driver starts only in a free slot, within the budget. It takes a queued CR, resumes a
    working one, or takes a ready or blocked one when the Foreman says why (`--note`): an answer,
    a change, a merged fix, a rebase, a red check."""
    if c["status"] in {"ready", "blocked"} and not note:
        raise ChantierError(f"{c['id']} is {c['status']}: a Driver takes it back only with "
                            "`--note` saying why (an answer, a change, a rebase, a red check)")
    if c["status"] not in {"queued", "working", "ready", "blocked"}:
        raise ChantierError(f"{c['id']} is {c['status']}: nothing for a Driver to do")
    check_budget(b)
    if c["status"] != "working" and len(live(b)) >= b.data["slots"]:
        raise ChantierError(f"no free slot: {len(live(b))} of {b.data['slots']} live "
                            f"({', '.join(x['id'] for x in live(b)) or 'slots 0'})")
    if c.get("kind") == "release" and not others_merged(b, c):
        raise ChantierError(f"{c['id']} releases what is merged: it starts once every other CR "
                            "is merged or cancelled")


def check_round(b: Batch, c: dict) -> int:
    """A round is counted before its Coder starts; past the limit, only the user grants more."""
    limit = round_limit(b.data, c)
    if c.get("round", 0) >= limit:
        raise ChantierError(f"{c['id']}: round limit {limit} reached; hand back blocked, only the "
                            "user grants more (`order rounds`)", EXIT_BUDGET)
    return limit


def archive_merged(b: Batch, c: dict) -> list[str]:
    """The PR is merged: the folder goes to the archives. Returns what the Foreman should hear."""
    archive_cr(b, c)
    b.touch(c, status="merged")
    lines = [f"merged {c['id']}: archived to {c['path']}"]
    if all_merged(b):
        lines.append("every CR is merged or cancelled: `chantier land`")
    return lines


def release_merged(b: Batch, c: dict) -> None:
    """The release PR is merged: the procedure goes on with a new Driver, and the next attempt
    opens a PR of its own."""
    c.setdefault("notes", []).append(f"merged: {c.get('pr')}")
    b.touch(c, status="queued", pr=None, head=None)


def release_go(b: Batch, c: dict, action: str) -> tuple[str, str]:
    """Spend what allows one irreversible action: `go` and why, `budget`, `fix` (a fix of this
    release is not merged), or `ask`. A `go` is for that action, in that Driver: the log keeps
    it, the CR does not."""
    grant = b.data["release"]
    if over_budget(b):
        b.log("release-go", c["id"], action=action, result="budget")
        return "budget", ""
    fixes = pending_fixes(b, c)
    if fixes:
        b.log("release-go", c["id"], action=action, result="fix", fixes=fixes)
        return "fix", " ".join(fixes)
    if c.get("approvals"):
        why = f"the user approved: {c['approvals'].pop(0)}"
    elif grant.get("autonomous", 0) > grant.get("published", 0):
        why = (f"the user allowed {grant['autonomous']} releases without asking; "
               f"{grant.get('published', 0)} published")
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
    result = ("budget" if over_budget(b) else
              "go" if b.data["release"].get("fixes") else "ask")
    b.log("release-go", c["id"], action=action, result=result)
    return result, "the user granted the release's fixes"


def check_granted_fix(b: Batch, c: dict) -> None:
    """The Foreman starts a fix of release `c` only under the user's grant, within the budget,
    and up to MAX_GRANTED_FIXES; past that, a fix is the user's go."""
    if not b.data["release"].get("fixes"):
        raise ChantierError("no grant for the release's fixes: the user's go comes as `order add "
                            "--fix-for`")
    check_budget(b)
    if sum(x.get("fix_for") == c["id"] for x in b.data["crs"]) >= MAX_GRANTED_FIXES:
        raise ChantierError(f"{MAX_GRANTED_FIXES} fixes under the grant: another one is the "
                            "user's go", EXIT_BUDGET)


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
        raise ChantierError("a release grant needs a batch budget: `budget=<usd>` (or `open "
                            "--budget`)", EXIT_USAGE)


def record_ask(b: Batch, text: str) -> str:
    """What the Chief of Staff must hear stays in the state until it has read it, whatever
    becomes of the message. Returns the ask's id."""
    asks = b.data.setdefault("asks", [])
    aid = f"A-{len(asks) + 1}"
    asks.append({"id": aid, "text": text, "sent": now(), "read": None})
    b.log("ask", None, ask=aid, text=text)
    return aid
