"""The rails: what the CLI refuses whatever an agent decides, and the facts it keeps straight.

Nothing here decides what a batch does next; the Foreman does, from `chantier status`. A rail is
a refusal (a take past the budget or the slots, a round past the limit, an irreversible action
without the user's word), and a fact is a record two runs must agree on (an archive on merge).
"""
from __future__ import annotations

import re

from . import costs
from .lifecycle import done_cr
from .state import (EXIT_BUDGET, EXIT_PRECONDITION, EXIT_USAGE, LIVE, Batch, ChantierError, Repo, chief_sessions,
                    now, round_limit)

ENDED = {"merged", "cancelled"}
MAX_GRANTED_FIXES = 3


def check_no_open_batch(repo: Repo) -> None:
    """One batch at a time, running or paused until `close`: new work joins it by `order add`."""
    ids = repo.batch_ids()
    if ids:
        raise ChantierError(f"{ids[0]} is not closed (a paused batch stays until `close`): "
                            "`order add` joins new work to it", EXIT_PRECONDITION)


QUIET_SECONDS = 300  # a session record written more recently than this: something still runs


def running(repo: Repo, d: dict) -> list[str]:
    """What shows a batch still runs, from its record and from its sessions' files; empty when
    nothing does. A long tool call writes nothing, so the recorded state is the first proof and
    the files only the second. The Foreman's session tree is all the CLI knows: a Driver run
    from another session of the user's is not in it. The Chief of Staff's own session is not
    counted: it is the one that closes, and on a direct batch it is also the steering session,
    so its own file is skipped and its subagents (the Drivers) are checked."""
    causes = [f"{c['id']} is {c['status']}, not merged or cancelled"
              for c in d["crs"] if c["status"] not in ENDED]
    causes += [f"order {o['id']} ({o['kind']}) is open" for o in d.get("orders", [])
               if not o["done"]]
    if d.get("stack_agent"):
        causes.append(f"stack agent {d['stack_agent']} is recorded")
    sessions = [s for s in (d.get("foreman_transcripts") or [d.get("foreman_transcript")]) if s]
    for label, age in costs.idle_seconds(repo.session_root, d["host"], sessions, chief_sessions(d)):
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


def slot_free(b) -> bool:
    """A slot is free by the rule `take` applies. `b` is a Batch or anything with a `.data`."""
    return len(held(b)) < b.data["slots"]


def check_slot(b: Batch, what: str) -> None:
    if not slot_free(b):
        raise ChantierError(f"no free slot for {what}: {len(held(b))} of {b.data['slots']} held "
                            f"({', '.join(held(b)) or 'slots 0'})")


def is_release(c: dict) -> bool:
    return c.get("kind") == "release"


def alone(crs: list[dict], c: dict) -> bool:
    """A release alone in its batch: no other CR but fixes was ever in it, whatever its state."""
    return not any(x["id"] != c["id"] and x.get("kind") != "fix" for x in crs)


def series_predecessor(crs: list[dict], c: dict) -> dict | None:
    """In a series, the nearest CR before `c` in the order that is neither a release nor a fix
    CR and not cancelled; a merged one counts, it is met."""
    if c.get("kind") in {"release", "fix"}:
        return None
    before = [x for x in crs if x["order"] < c["order"] and x.get("kind") not in {"release", "fix"}
              and x["status"] != "cancelled"]
    return max(before, key=lambda x: x["order"], default=None)


def waits_for(crs: list[dict], c: dict, mode: str = "parallel") -> list[str]:
    """The CRs not yet met: those of `after`, then, in a series, the predecessor. For a CR, met
    is ready or merged (a cancelled one stays unmet); for a release, ready, merged or cancelled
    in an ordered batch (stack or series: it is prepared on top of the others), merged or
    cancelled in a parallel one (no branch holds all the work until the others are merged)."""
    found = {x["id"]: x for x in crs}
    if is_release(c):
        met = ENDED | {"ready"} if mode in {"stack", "series"} else ENDED
    else:
        met = {"ready", "merged"}
    ids = list(c.get("after", []))
    pred = series_predecessor(crs, c) if mode == "series" else None
    if pred and pred["id"] not in ids:
        ids.append(pred["id"])
    return [f"{i} {found[i]['status']}" for i in ids
            if i in found and found[i]["status"] not in met]


def waits_all(crs: list[dict], c: dict, mode: str = "parallel") -> list[str]:
    """What a queued CR waits for, as `status` shows it: its `after`, then a release's fixes
    not ended."""
    status = {x["id"]: x["status"] for x in crs}
    return waits_for(crs, c, mode) + [f"{i} {status[i]}" for i in pending_fixes(crs, c)]


def unmet(b: Batch, c: dict) -> list[str]:
    return waits_for(b.data["crs"], c, b.data["mode"])


def over_budget(b: Batch) -> bool:
    budget = b.data.get("budget_usd")
    return bool(budget) and (b.data.get("spent_usd") or 0) >= budget  # the priced part; no spend seen yet: 0


def spent_text(data: dict) -> str:
    """The spend as shown to a reader: `unknown` until a priced refresh, never a false $0.00, and
    `at least` while calls of a model with no price are left out of it."""
    spent = data.get("spent_usd")
    if spent is None:
        return "unknown"
    return f"{'at least ' if data.get('unpriced') else ''}${spent:.2f}"


def usd_text(amount: float, unpriced: dict | None, places: int = 2) -> str:
    """A priced amount; `at least` while calls of a model with no price are left out of it."""
    return f"{'at least ' if unpriced else ''}${amount:.{places}f}"


def not_priced(unpriced: dict) -> str:
    """`3 calls of <model> not priced`, one `N calls of <model>` per model."""
    return ", ".join(f"{n} calls of {m}" for m, n in unpriced.items()) + " not priced"


def all_merged(b: Batch) -> bool:
    return all(c["status"] in ENDED for c in b.data["crs"])


def check_budget(b: Batch) -> None:
    """No Driver of any kind starts, and no Driver starts a new round, past the budget; the spend
    is the last recorded one. The gate, the verdict, the ship, the notes and the hand-back stay
    open, and so do the workers of a round already started."""
    if over_budget(b):
        raise ChantierError(f"budget spent: {spent_text(b.data)} of "
                            f"${b.data['budget_usd']}; only the user raises it (`order budget`)",
                            EXIT_BUDGET)


def pending_fixes(crs: list[dict], c: dict) -> list[str]:
    """The fix CRs of a release that have not ended: the release waits for them."""
    return [x["id"] for x in crs if x.get("fix_for") == c["id"]
            and x["status"] not in ENDED]


def check_take(b: Batch, c: dict, note: str | None) -> None:
    """A Driver starts only in a free slot, within the budget, on a CR with no agent recorded. It
    takes a queued CR, resumes a working one (`--note`: a restart keeps the slot and counts no
    round), or takes a ready or blocked one when the Foreman says why (`--note`): an answer,
    a change, a merged fix, a rebase, a red check."""
    if c["status"] not in {"queued", "working", "ready", "blocked"}:
        raise ChantierError(f"{c['id']} is {c['status']}: nothing for a Driver to do")
    if c["status"] in {"ready", "blocked"} and not note:
        raise ChantierError(f"{c['id']} is {c['status']}: a Driver takes it back only with "
                            "`--note` saying why (an answer, a change, a rebase, a red check)")
    if c["status"] == "working" and not note:
        raise ChantierError(f"{c['id']} is working: a new Driver resumes it only with `--note` "
                            "saying why (resume: <cause>)")
    if c.get("agent"):  # one Driver per CR: the recorded one must have ended first
        raise ChantierError(f"{c['id']} still has an agent recorded ({c['agent']}): "
                            f"`agents set {c['id']} -` first, once it ended")
    check_budget(b)
    if c["status"] != "working":
        check_slot(b, c["id"])
    # a release taken back (ready, blocked) waits again for the stack under it, e.g. after a
    # change of content
    if unmet(b, c) and (c["status"] == "queued" or
                        (is_release(c) and c["status"] in {"ready", "blocked"})):
        ordered = b.data["mode"] in {"stack", "series"}
        ends = ("ready or merged" if ordered else "merged or cancelled") if is_release(c) \
            else "ready or merged"
        raise ChantierError(f"{c['id']} waits for {', '.join(unmet(b, c))}: it starts once each "
                            f"is {ends}")
    if is_release(c):
        fixes = pending_fixes(b.data["crs"], c)
        if fixes:
            raise ChantierError(f"{c['id']} waits for {', '.join(fixes)}: a fix of the release "
                                "must be merged or cancelled first")


def check_round(b: Batch, c: dict) -> int:
    """A round is counted before its Coder starts; past the budget, or past the limit, only the
    user grants more. The budget is checked first: when both are spent, more rounds alone would
    not let the Driver go on."""
    check_budget(b)
    limit = round_limit(b.data, c)
    if c.get("round", 0) >= limit:
        raise ChantierError(f"{c['id']}: round limit {limit} reached; hand back blocked, only the "
                            "user grants more (`order rounds`)", EXIT_BUDGET)
    return limit


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
    open_ = [x["id"] for x in b.data["crs"] if x["id"] != c["id"] and x.get("kind") != "fix"
             and x["status"] not in ENDED]
    if open_:
        b.log("release-go", c["id"], action=action, result="merge", open=open_)
        return "merge", f"{' '.join(open_)} not merged: every irreversible step waits for their merge"
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
