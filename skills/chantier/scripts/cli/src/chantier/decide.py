"""The Foreman's decision table: one event in, the actions to take out.

Every function mutates the locked batch and returns action lines, in the order the Foreman must
do them. An action line is a verb and its arguments:

    spawn cr-driver <cr> [<note>]   start the CR's Driver in the background (`chantier spawn`)
    spawn release-driver <cr> [<note>]   the same for the release CR
    spawn qa-driver <cr>            start the CR's QA driver
    spawn stack-driver stack        start the stack driver; `message stack restack` when it is live
    cancel <cr>                     stop the CR's Driver, then `chantier cancel <cr>`
    merge <cr>                      `chantier merge <cr>`: what the user allowed: a fix under the
                                    grant, the release PR after a `go`
    message <cr> <text>             message the CR's Driver
    ask-chief-of-staff <kind> <text>   one message to the Chief of Staff
    land                            `chantier land`
    ok <what>                       nothing to send, `status` shows it: an order is done, or ready
                                    CRs went back to rebase
    none                            nothing to do

A release CR waits until every other CR of its batch is merged or cancelled: it releases what is
merged. A fix CR (`order fix`) is one the release found; the release starts again once it merges.
"""
from __future__ import annotations

import re
import subprocess

from .lifecycle import archive_cr, trash_cr
from .state import LIVE, Batch, ChantierError, EXIT_EXTERNAL, EXIT_USAGE, git, now

DRIVER_EVENTS = {"hand-back-ready", "hand-back-blocked", "anomaly", "qa-done", "driver-lost",
                 "driver-done"}
MAX_RESUMES = 2
ORDER_EVENTS = {"order-add", "order-drop", "order-first", "order-change", "order-merged",
                "order-pause", "order-resume", "order-fix", "order-approve", "order-grant"}
MERGE_METHODS = ("rebase", "squash", "merge")
BATCH_EVENTS = {"start", "tick"}
EVENTS = DRIVER_EVENTS | ORDER_EVENTS | BATCH_EVENTS


def _live(b: Batch) -> list[dict]:
    return [c for c in b.data["crs"] if c["status"] in LIVE]


def _queued(b: Batch) -> list[dict]:
    return sorted((c for c in b.data["crs"] if c["status"] == "queued"), key=lambda c: c["order"])


def _over_budget(b: Batch) -> bool:
    budget = b.data.get("budget_usd")
    return bool(budget) and b.data.get("spent_usd", 0) >= budget


def driver_role(c: dict) -> str:
    return "release-driver" if c.get("kind") == "release" else "cr-driver"


def _others_merged(b: Batch, c: dict) -> bool:
    return all(x["status"] in {"merged", "cancelled", "landed"} for x in b.data["crs"] if x is not c)


def fill_slots(b: Batch) -> list[str]:
    """Spawn queued CRs while slots are free, the batch is not paused and budget remains."""
    out: list[str] = []
    if b.data.get("paused"):
        return out
    for c in _queued(b):
        if c.get("kind") == "release" and not _others_merged(b, c):
            continue
        if len(_live(b)) >= b.data["slots"]:
            break
        if _over_budget(b):
            if not b.data.get("budget_asked"):
                b.data["budget_asked"] = True
                out.append(f"ask-chief-of-staff budget {b.data.get('spent_usd', 0):.2f}/{b.data['budget_usd']}")
            break
        b.touch(c, status="working")
        b.log("spawn", c["id"])
        out.append(f"spawn {driver_role(c)} {c['id']}")
    return out


def _stack_ready(b: Batch) -> bool:
    active = [c for c in b.data["crs"] if c["status"] not in {"cancelled", "merged", "landed"}
              and c.get("kind") != "release"]
    return bool(active) and all(c["status"] in {"ready", "blocked"} for c in active)


def _all_merged(b: Batch) -> bool:
    return all(c["status"] in {"merged", "cancelled", "landed"} for c in b.data["crs"])


def _restack(b: Batch) -> str:
    """Message the live stack driver, or start one."""
    if b.data.get("stack_live"):
        return "message stack restack"
    b.data["stack_live"] = True
    return "spawn stack-driver stack"


def _links(b: Batch, crs: list[dict]) -> str:
    return " ".join(f"{c['id']}={c.get('pr') or 'no-pr'}" for c in crs)


def decide(b: Batch, cr_id: str, kind: str, note: str = "", order: str | None = None) -> list[str]:
    if kind not in EVENTS:
        raise ChantierError(f"unknown event kind {kind!r}; one of: {', '.join(sorted(EVENTS))}",
                       EXIT_USAGE)
    if b.data.get("status") == "landed":
        return ["none landed"]
    if kind in ORDER_EVENTS and order:
        o = next((x for x in b.data.get("orders", []) if x["id"] == order), None)
        if o is None:
            raise ChantierError(f"unknown order {order}", EXIT_USAGE)
        if o.get("done"):
            return [f"ok {order} already done"]  # a burst read twice stays idempotent
        o["done"] = now()
    b.log("event", None if cr_id == "-" else cr_id, event=kind, note=note, order=order)
    handler = globals()["_on_" + kind.replace("-", "_")]
    actions = handler(b, cr_id, note) or ["none"]
    if order:
        actions = [a.replace("ok ", f"ok {order} ", 1) if a.startswith("ok ") else a
                   for a in actions]
    return actions


# ---- batch events -----------------------------------------------------------------------------

def _on_start(b: Batch, _cr: str, _note: str) -> list[str]:
    b.data["started"] = b.data.get("started") or now()
    return fill_slots(b)


def _on_tick(b: Batch, _cr: str, _note: str) -> list[str]:
    """The wake catches up on what a lost message left behind: an order whose line never came, a
    ready PR that stopped merging, a silent Driver."""
    stale = b.repo.config.get("stale_minutes", 90)
    out = []
    from .state import age_minutes
    for o in b.data.get("orders", []):
        if not o["done"]:
            out += [a for a in decide(b, o["cr"], f"order-{o['kind']}", o["note"], order=o["id"])
                    if a != "none"]
    out += _rebase_news(b)
    for c in _live(b):
        age = age_minutes(c.get("updated"))
        if age is not None and age > stale:
            out.append(f"message {c['id']} ping: reply with your state (silent {age:.0f} min)")
    return out + fill_slots(b)


# ---- Driver events ----------------------------------------------------------------------------

def _on_hand_back_ready(b: Batch, cr_id: str, note: str) -> list[str]:
    c = b.cr(cr_id)
    if c.get("kind") == "release":  # released: nothing is left to merge
        c["released"] = note.split()[0] if note else None
        archive_cr(b, c)
        b.touch(c, status="merged")
        return [f"ask-chief-of-staff released {cr_id} {c['released'] or '-'}"] \
            + (["land"] if _all_merged(b) else fill_slots(b))
    if note.startswith("http"):
        c["pr"] = note.split()[0]
    if c.get("kind") == "fix" and (b.data.get("release") or {}).get("auto_merge") \
            and not (c.get("qa") and not c.get("qa_done")):
        b.touch(c, status="ready")
        return [f"merge {cr_id}"] + fill_slots(b)
    out: list[str] = []
    if c.get("qa") and not c.get("qa_done"):
        b.touch(c, status="qa")
        out.append(f"spawn qa-driver {cr_id}")
        return out + fill_slots(b)
    b.touch(c, status="ready")
    out += fill_slots(b)
    if b.data["mode"] == "stack":
        if _stack_ready(b):
            ready = [x for x in b.data["crs"] if x["status"] == "ready"]
            out += [_restack(b), f"ask-chief-of-staff stack-ready {_links(b, ready)}"]
    elif not _conflicts(b, c, fetch=True):  # in conflict: its Driver's end sends it back
        out.append(f"ask-chief-of-staff ready {cr_id} {c.get('pr') or 'no-pr'}")
    return out


def _on_hand_back_blocked(b: Batch, cr_id: str, note: str) -> list[str]:
    c = b.cr(cr_id)
    if c.get("kind") == "release" and note.startswith("merge:"):  # the Foreman merges, once allowed
        method = note.removeprefix("merge:").strip()
        if method not in MERGE_METHODS:
            raise ChantierError(f"hand-back blocked merge: <{'|'.join(MERGE_METHODS)}>", EXIT_USAGE)
        b.touch(c, status="blocked", blocked_reason=note, merge_method=method)
        return _merge_release(b, c) + fill_slots(b)
    b.touch(c, status="blocked", blocked_reason=note)
    out = [f"ask-chief-of-staff blocked {cr_id} {note}".rstrip()] + fill_slots(b)
    if b.data["mode"] == "stack" and _stack_ready(b):
        ready = [x for x in b.data["crs"] if x["status"] == "ready"]
        if ready:
            out += [_restack(b), f"ask-chief-of-staff stack-ready {_links(b, ready)}"]
    return out


def _on_anomaly(b: Batch, cr_id: str, note: str) -> list[str]:
    c = b.cr(cr_id)
    limit = b.repo.config.get("max_rounds", 3)
    if c.get("round", 0) >= limit:
        b.touch(c, status="blocked", blocked_reason=f"round limit: {note}")
        return [f"ask-chief-of-staff blocked {cr_id} round limit ({limit}) reached: {note}"] + fill_slots(b)
    previous = c["status"]
    b.touch(c, status="working", qa_done=False)
    if previous == "working":
        return [f"message {cr_id} round {note}"]
    # The Driver ended with its hand-back: a new one resumes the CR with the finding.
    return [f"spawn {driver_role(c)} {cr_id} resume round: {note}"]


def _on_qa_done(b: Batch, cr_id: str, note: str) -> list[str]:
    """No finding: the CR is ready. Findings: a new round on them, then QA again."""
    c = b.cr(cr_id)
    words = note.split()
    if not words or not words[0].isdigit():
        raise ChantierError("qa-done needs the number of findings", EXIT_USAGE)
    c["qa_done"] = True
    if int(words[0]):
        return _on_anomaly(b, cr_id, f"QA found {words[0]} findings: {c.get('qa_findings') or '-'}")
    return _on_hand_back_ready(b, cr_id, c.get("pr") or "")


def _on_driver_lost(b: Batch, cr_id: str, _note: str) -> list[str]:
    c = b.cr(cr_id)
    if c["status"] not in LIVE:
        return []
    c["resumes"] = c.get("resumes", 0) + 1
    if c["resumes"] > MAX_RESUMES:
        b.touch(c, status="blocked", agent=None, blocked_reason="driver lost repeatedly")
        return [f"ask-chief-of-staff blocked {cr_id} its Driver ended {c['resumes']} times without a "
                "hand-back"] + fill_slots(b)
    b.touch(c, agent=None)
    return [f"spawn {driver_role(c)} {cr_id} resume"]


def _on_driver_done(b: Batch, cr_id: str, note: str) -> list[str]:
    """The task notification of an ended Driver: expected after a hand-back, lost otherwise.

    `qa:<cr>` is the CR's QA driver; `stack` is the stack driver."""
    if cr_id == "stack":
        b.data["stack_live"] = False
        return []
    if cr_id.startswith("qa:"):
        c = b.cr(cr_id[3:])
        if c["status"] == "qa" and not c.get("qa_done"):
            c["resumes"] = c.get("resumes", 0) + 1
            if c["resumes"] > MAX_RESUMES:
                b.touch(c, status="blocked", blocked_reason="QA driver lost repeatedly")
                return [f"ask-chief-of-staff blocked {c['id']} its QA driver ended without a result"]
            return [f"spawn qa-driver {c['id']} resume"]
        return []
    c = b.cr(cr_id)
    if c["status"] == "working":
        return _on_driver_lost(b, cr_id, note)
    if c["status"] == "ready":  # handed back in conflict: only now can a new Driver take it
        return _rebase_news(b) + fill_slots(b)
    return []


# ---- orders from the Chief of Staff -----------------------------------------------------------

def _on_order_add(b: Batch, _cr: str, note: str) -> list[str]:
    from .commands import add_cr  # avoid an import cycle
    c = add_cr(b, note)
    return [f"ok add {c['id']}"] + fill_slots(b)


def _on_order_drop(b: Batch, cr_id: str, _note: str) -> list[str]:
    c = b.cr(cr_id)
    if c["status"] in LIVE:
        return [f"cancel {cr_id}", f"ok drop {cr_id}"]
    if c["status"] in {"merged", "landed"}:
        raise ChantierError(f"cannot drop {cr_id}: it is already {c['status']}")
    trash_cr(b, c)
    b.touch(c, status="cancelled")
    return [f"ok drop {cr_id}"] + fill_slots(b)


def _on_order_first(b: Batch, cr_id: str, _note: str) -> list[str]:
    c = b.cr(cr_id)
    c["order"] = min(x["order"] for x in b.data["crs"]) - 1
    b.touch(c)
    out = [f"ok first {cr_id}"]
    if c["status"] in LIVE:
        out.insert(0, f"message {cr_id} first: you are top priority")
    return out + fill_slots(b)


def _on_order_change(b: Batch, cr_id: str, note: str) -> list[str]:
    c = b.cr(cr_id)
    c.setdefault("notes", []).append(f"change: {note}")
    b.touch(c)
    if c["status"] in LIVE:
        return [f"message {cr_id} change {note}", f"ok change {cr_id}"]
    if c["status"] in {"ready", "blocked"}:
        b.touch(c, status="queued")
        return [f"ok change {cr_id}"] + fill_slots(b)
    return [f"ok change {cr_id}"]


def _on_order_merged(b: Batch, cr_id: str, note: str) -> list[str]:
    c = b.cr(cr_id)
    if c["status"] in {"merged", "landed"}:
        return [f"ok merged {cr_id} already merged"]
    if c["status"] == "cancelled":
        raise ChantierError(f"cannot mark cancelled {cr_id} merged")
    if c.get("kind") == "release":
        return [f"ok merged {cr_id}"] + release_merged(b, c, c.get("merge_method") or "by the user")
    extra, actions = merged(b, c)
    return [f"ok merged {cr_id}{extra}"] + actions


def merged(b: Batch, c: dict) -> tuple[str, list[str]]:
    """Archive a merged CR. Returns what to add to the news (the ready CRs sent back to rebase)
    and the actions that follow."""
    archive_cr(b, c)
    b.touch(c, status="merged")
    if _all_merged(b):
        return "", ["land"]
    if b.data["mode"] == "stack":
        return "", [_restack(b)] + fill_slots(b)
    rebase = _rebase_ready(b)
    return (f"; rebase {' '.join(rebase)}" if rebase else ""), fill_slots(b)


def _fetch_default(b: Batch) -> None:
    git("fetch", "--quiet", b.repo.config["remote"], b.repo.config["default_branch"],
        cwd=b.repo.root)


def _conflicts(b: Batch, c: dict, fetch: bool = False) -> bool:
    """Whether the CR's branch no longer merges cleanly into the default branch."""
    if not c.get("branch"):
        return False
    if fetch:
        _fetch_default(b)
    remote, branch = b.repo.config["remote"], b.repo.config["default_branch"]
    # never `--quiet`: with it, git exits 0 on a conflict
    p = subprocess.run(["git", "merge-tree", "--write-tree", f"{remote}/{branch}", c["branch"]],
                       cwd=b.repo.root, capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    if p.returncode > 1:
        raise ChantierError(f"git merge-tree {c['branch']}: {p.stderr.strip()}", EXIT_EXTERNAL)
    return p.returncode == 1


def _rebase_ready(b: Batch) -> list[str]:
    """A ready CR whose PR no longer merges cleanly into the moved default branch goes back to a
    Driver, which ships it again."""
    ready = [c for c in b.data["crs"] if c["status"] == "ready"]
    if not ready or b.data["mode"] == "stack":  # a stack's PRs stand on each other
        return []
    _fetch_default(b)
    out = []
    for c in ready:
        if _conflicts(b, c):
            c.setdefault("notes", []).append(
                f"rebase: {b.repo.config['default_branch']} moved; the PR no longer merges")
            b.touch(c, status="queued")
            out.append(c["id"])
    return out


def _rebase_news(b: Batch) -> list[str]:
    rebase = _rebase_ready(b)
    return [f"ok rebase {' '.join(rebase)}"] if rebase else []


def _on_order_pause(b: Batch, _cr: str, _note: str) -> list[str]:
    b.data["paused"] = True
    return ["ok pause"]


def _on_order_resume(b: Batch, _cr: str, _note: str) -> list[str]:
    b.data["paused"] = False
    b.data["budget_asked"] = False
    return ["ok resume"] + fill_slots(b)


# ---- the release ------------------------------------------------------------------------------

def _release(b: Batch, cr_id: str) -> dict:
    c = b.cr(cr_id)
    if c.get("kind") != "release":
        raise ChantierError(f"{cr_id} is not the batch's release CR", EXIT_USAGE)
    return c


def release_go(b: Batch, c: dict, action: str) -> tuple[str, str]:
    """Spend what allows one irreversible action: `go` and why, `budget`, or `ask`."""
    grant = b.data["release"]
    if _over_budget(b):
        b.log("release-go", c["id"], action=action, result="budget")
        return "budget", ""
    if c.get("approvals"):
        why = f"the user approved: {c['approvals'].pop(0)}"
    elif grant.get("autonomous", 0) > grant.get("published", 0):
        why = (f"the user allowed {grant['autonomous']} releases without asking; "
               f"{grant.get('published', 0)} published")
    else:
        b.log("release-go", c["id"], action=action, result="ask")
        return "ask", ""
    b.touch(c, go=action)
    b.log("release-go", c["id"], action=action, result="go", why=why)
    return "go", why


def _awaits_merge(c: dict) -> bool:
    return c["status"] == "blocked" and bool(c.get("merge_method"))


def _merge_release(b: Batch, c: dict) -> list[str]:
    """The release PR needs no new Driver to merge: allowed, the Foreman merges it; not yet, the
    user is asked, and the approval or the grant comes back here."""
    action = f"merge the release PR {c.get('pr')} ({c['merge_method']})"
    result, _ = release_go(b, c, action)
    if result == "go":
        return [f"merge {c['id']}"]
    reason = f"{'budget' if result == 'budget' else 'approval'}: {action}"
    b.touch(c, blocked_reason=reason)
    return [f"ask-chief-of-staff blocked {c['id']} {reason}"]


def release_merged(b: Batch, c: dict, method: str) -> list[str]:
    """The release PR is merged: the procedure goes on with a new Driver."""
    c.setdefault("notes", []).append(f"merged: {c.get('pr')} ({method})")
    b.touch(c, status="queued", go=None, merge_method=None)
    return fill_slots(b)


def _back_to_release(b: Batch, c: dict, note: str, verb: str) -> list[str]:
    """Record a note for the release's Driver: a live one is told, an ended one is queued."""
    c.setdefault("notes", []).append(note)
    b.touch(c)
    if c["status"] in LIVE:
        return [f"message {c['id']} {note}", f"ok {verb} {c['id']}"]
    if c["status"] in {"ready", "blocked"}:
        b.touch(c, status="queued")
    return [f"ok {verb} {c['id']}"] + fill_slots(b)


def _on_order_fix(b: Batch, cr_id: str, note: str) -> list[str]:
    """A fix the release needs: a CR of the batch; the release starts again once it merges."""
    from .commands import add_cr  # avoid an import cycle
    release = _release(b, cr_id)
    fix = add_cr(b, note)
    fix.update(kind="fix", fix_for=cr_id)
    out = _back_to_release(b, release, f"fix: {fix['id']} must merge first; then start the "
                           "procedure again from its first step", "fix")
    return [a.replace(f"ok fix {cr_id}", f"ok fix {fix['id']} for {cr_id}") for a in out]


def _on_order_approve(b: Batch, cr_id: str, note: str) -> list[str]:
    """The user approved one irreversible action; `chantier release go` spends it, or the merge
    of the release PR that waits for it."""
    c = _release(b, cr_id)
    if not note.strip():
        raise ChantierError("order approve needs the action the user approved", EXIT_USAGE)
    c.setdefault("approvals", []).append(note.strip())
    if _awaits_merge(c):
        c.setdefault("notes", []).append(f"approved: {note.strip()}")
        return _merge_release(b, c) + [f"ok approve {cr_id}"]
    return _back_to_release(b, c, f"approved: {note.strip()}", "approve")


GRANT = f"releases=<n> auto-merge=<{'|'.join(MERGE_METHODS)}|off> budget=<usd>"


def parse_grant(text: str) -> dict:
    """What the user allows without asking: a number of releases, the merge of fixes, and the
    budget they run within. Any of the three."""
    grant = {}
    for word in text.split():
        key, _, value = word.partition("=")
        if key == "releases" and value.isdigit():
            grant["autonomous"] = int(value)
        elif key == "auto-merge" and value in (*MERGE_METHODS, "off"):
            grant["auto_merge"] = None if value == "off" else value
        elif key == "budget" and re.fullmatch(r"\d+(\.\d+)?", value) and float(value) > 0:
            grant["budget_usd"] = float(value)
        else:
            raise ChantierError(f"grant: `{GRANT}`, any of them; not {word!r}", EXIT_USAGE)
    if not grant:
        raise ChantierError(f"grant: `{GRANT}`, any of them", EXIT_USAGE)
    return grant


def check_grant(release: dict, budget: float | None) -> None:
    """Autonomy is always bounded by a budget."""
    if (release.get("autonomous") or release.get("auto_merge")) and not budget:
        raise ChantierError("a release grant needs a batch budget: `budget=<usd>` (or `open "
                            "--budget`)", EXIT_USAGE)


def _on_order_grant(b: Batch, cr_id: str, note: str) -> list[str]:
    c = _release(b, cr_id)
    grant = parse_grant(note)
    if "budget_usd" in grant:
        b.data["budget_usd"] = grant.pop("budget_usd")
        b.data["budget_asked"] = False
    b.data["release"].update(grant)
    check_grant(b.data["release"], b.data.get("budget_usd"))
    if c["status"] == "blocked" and (c.get("blocked_reason") or "").startswith("fix:"):
        c.setdefault("notes", []).append(f"grant: {note.strip()}")  # it waits for its fix
        b.touch(c)
        return [f"ok grant {cr_id}"]
    if _awaits_merge(c):
        c.setdefault("notes", []).append(f"grant: {note.strip()}")
        return _merge_release(b, c) + [f"ok grant {cr_id}"]
    return _back_to_release(b, c, f"grant: {note.strip()}", "grant")


def record_asks(b: Batch, actions: list[str]) -> None:
    """What the Chief of Staff must hear stays in the state until it has read it, whatever
    becomes of the message."""
    for a in actions:
        if a.startswith("ask-chief-of-staff "):
            b.data.setdefault("asks", []).append(
                {"text": a.removeprefix("ask-chief-of-staff "), "sent": now(), "read": None})
