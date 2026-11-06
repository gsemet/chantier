"""The rails: what the CLI refuses whatever an agent decides, and the facts it keeps straight.

Nothing here decides what a batch does next; the Foreman does, from `chantier status`. A rail is
a refusal (a take past the budget or the slots, a round past the limit, an irreversible action
without the user's word), and a fact is a record two runs must agree on (an archive on merge).
"""
from __future__ import annotations

import re

from . import costs
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


QUIET_SECONDS = 300  # a session record written more recently than this: something still runs


def running(repo: Repo, d: dict) -> list[str]:
    """What shows a batch still runs, from its record and from its sessions' files; empty when
    nothing does. A long tool call writes nothing, so the recorded state is the first proof and
    the files only the second. The Foreman's session tree is all the CLI knows: a Driver run
    from another session of the user's is not in it. The Chief of Staff's own session is not
    counted: it is the one that closes."""
    causes = [f"{c['id']} is {c['status']}, not merged or cancelled"
              for c in d["crs"] if c["status"] not in ENDED]
    causes += [f"order {o['id']} ({o['kind']}) is open" for o in d.get("orders", [])
               if not o["done"]]
    if d.get("stack_agent"):
        causes.append(f"stack agent {d['stack_agent']} is recorded")
    sessions = [s for s in (d.get("foreman_transcripts") or [d.get("foreman_transcript")]) if s]
    for label, age in costs.idle_seconds(repo.root, d["host"], sessions):
        if age is None:
            causes.append(f"{label}: not measured")
        elif age < QUIET_SECONDS:
            causes.append(f"{label} was written {age:.0f} s ago (under {QUIET_SECONDS // 60} min)")
    return causes


def check_idle(repo: Repo, d: dict) -> None:
    causes = running(repo, d)
    if causes:
        raise ChantierError(f"cannot close {d['id']}, something still runs: " + "; ".join(causes)
                            + ". Nothing was deleted.", EXIT_PRECONDITION)


def live(b: Batch) -> list[dict]:
    return [c for c in b.data["crs"] if c["status"] in LIVE]


def qa_open(b: Batch) -> list[dict]:
    """The QA orders not done: each is a QA driver, and holds a slot from the order on."""
    return [o for o in b.data.get("orders", []) if o["kind"] == "qa" and not o["done"]]


def held(b: Batch) -> list[str]:
    """What holds a slot: a CR in `working` and an open QA order, never a ready or blocked CR."""
    return [x["id"] + " working" for x in live(b)] + [f"{o['id']} qa" for o in qa_open(b)]


def check_slot(b: Batch, what: str) -> None:
    if len(held(b)) >= b.data["slots"]:
        raise ChantierError(f"no free slot for {what}: {len(held(b))} of {b.data['slots']} held "
                            f"({', '.join(held(b)) or 'slots 0'})")


WORD = "the user's confirmation (`order confirm`)"


def is_release(c: dict) -> bool:
    return c.get("kind") == "release"


def alone(crs: list[dict], c: dict) -> bool:
    """A release alone in its batch: no other CR but fixes was ever in it, whatever its state."""
    return not any(x["id"] != c["id"] and x.get("kind") != "fix" for x in crs)


def waits_for(crs: list[dict], c: dict) -> list[str]:
    """The CRs of `after` not yet met. For a CR, met is ready or merged (a cancelled one stays
    unmet); for a release, merged or cancelled, since it ships what is merged."""
    found = {x["id"]: x for x in crs}
    met = ENDED if is_release(c) else {"ready", "merged"}
    return [f"{i} {found[i]['status']}" for i in c.get("after", [])
            if i in found and found[i]["status"] not in met]


def needs_word(crs: list[dict], c: dict) -> bool:
    """A release that shares its batch starts only on the user's confirmation."""
    return is_release(c) and not alone(crs, c) and not c.get("confirmed")


def waits_all(crs: list[dict], c: dict) -> list[str]:
    """What a queued CR waits for, as `status` shows it: its `after`, then, once that is met,
    a release's confirmation."""
    found = waits_for(crs, c)
    if not found and needs_word(crs, c):
        return [WORD]
    return found


def unmet(b: Batch, c: dict) -> list[str]:
    return waits_for(b.data["crs"], c)


def over_budget(b: Batch) -> bool:
    budget = b.data.get("budget_usd")
    return bool(budget) and b.data.get("spent_usd", 0) >= budget


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
    if c["status"] != "working":
        check_slot(b, c["id"])
    if c["status"] == "queued" and unmet(b, c):
        ends = "merged or cancelled" if is_release(c) else "ready or merged"
        raise ChantierError(f"{c['id']} waits for {', '.join(unmet(b, c))}: it starts once each "
                            f"is {ends}")
    if is_release(c):
        fixes = pending_fixes(b, c)
        if fixes:
            raise ChantierError(f"{c['id']} waits for {', '.join(fixes)}: a fix of the release "
                                "must be merged or cancelled first")
        if needs_word(b.data["crs"], c):
            raise ChantierError(f"{c['id']} needs {WORD}: the Chief of Staff grills the version "
                                "with the user once the others have ended, then gives it")


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
