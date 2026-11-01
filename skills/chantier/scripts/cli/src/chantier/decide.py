"""The Foreman's decision table: one event in, the actions to take out (design 5, lever L3).

Every function mutates the locked batch and returns action lines, in the order the Foreman must
do them. An action line is a verb and its arguments:

    spawn <cr> [resume]     start the CR's Driver in the background (or a stack/QA driver)
    cancel <cr>             TaskStop the CR's Driver, then `chantier cancel <cr>`
    message <cr> <text>     SendMessage to the CR's Driver
    spawn stack             start the stack driver; `message stack restack` when it is live
    spawn qa:<cr>           start the CR's QA driver
    ask-chief-of-staff <kind> <text>   one message to the Chief of Staff
    land                    `chantier land <batch>`
    ok <what>               confirm an order to the Chief of Staff
    none                    nothing to do
"""
from __future__ import annotations

from .state import LIVE, Batch, ChantierError, EXIT_USAGE, now

DRIVER_EVENTS = {"hand-back-ready", "hand-back-blocked", "question", "anomaly", "qa-done",
                 "driver-lost", "driver-done"}
MAX_RESUMES = 2
ORDER_EVENTS = {"order-add", "order-drop", "order-first", "order-change", "order-merged",
                "order-pause", "order-resume"}
BATCH_EVENTS = {"start", "tick"}
EVENTS = DRIVER_EVENTS | ORDER_EVENTS | BATCH_EVENTS


def _live(b: Batch) -> list[dict]:
    return [c for c in b.data["crs"] if c["status"] in LIVE]


def _queued(b: Batch) -> list[dict]:
    return sorted((c for c in b.data["crs"] if c["status"] == "queued"), key=lambda c: c["order"])


def _over_budget(b: Batch) -> bool:
    budget = b.data.get("budget_usd")
    return bool(budget) and b.data.get("spent_usd", 0) >= budget


def fill_slots(b: Batch) -> list[str]:
    """Spawn queued CRs while slots are free, the batch is not paused and budget remains."""
    out: list[str] = []
    if b.data.get("paused"):
        return out
    for c in _queued(b):
        if len(_live(b)) >= b.data["slots"]:
            break
        if _over_budget(b):
            if not b.data.get("budget_asked"):
                b.data["budget_asked"] = True
                out.append(f"ask-chief-of-staff budget {b.data.get('spent_usd', 0):.2f}/{b.data['budget_usd']}")
            break
        b.touch(c, status="working")
        b.log("spawn", c["id"])
        out.append(f"spawn {c['id']}")
    return out


def _stack_ready(b: Batch) -> bool:
    active = [c for c in b.data["crs"] if c["status"] not in {"cancelled", "merged", "landed"}]
    return bool(active) and all(c["status"] in {"ready", "blocked"} for c in active)


def _all_merged(b: Batch) -> bool:
    return all(c["status"] in {"merged", "cancelled", "landed"} for c in b.data["crs"])


def _restack(b: Batch) -> str:
    """Message the live stack driver, or start one."""
    if b.data.get("stack_live"):
        return "message stack restack"
    b.data["stack_live"] = True
    return "spawn stack"


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
    stale = b.repo.config.get("stale_minutes", 90)
    out = []
    from .state import age_minutes
    for c in _live(b):
        age = age_minutes(c.get("updated"))
        if age is not None and age > stale:
            out.append(f"message {c['id']} ping: reply with your state (silent {age:.0f} min)")
    return out + fill_slots(b)


# ---- Driver events ----------------------------------------------------------------------------

def _on_hand_back_ready(b: Batch, cr_id: str, note: str) -> list[str]:
    c = b.cr(cr_id)
    if note.startswith("http"):
        c["pr"] = note.split()[0]
    out: list[str] = []
    if c.get("qa") and not c.get("qa_done"):
        b.touch(c, status="qa")
        out.append(f"spawn qa:{cr_id}")
        return out + fill_slots(b)
    b.touch(c, status="ready")
    out += fill_slots(b)
    if b.data["mode"] == "stack":
        if _stack_ready(b):
            ready = [x for x in b.data["crs"] if x["status"] == "ready"]
            out += [_restack(b), f"ask-chief-of-staff stack-ready {_links(b, ready)}"]
    else:
        out.append(f"ask-chief-of-staff ready {cr_id} {c.get('pr') or 'no-pr'}")
    return out


def _on_hand_back_blocked(b: Batch, cr_id: str, note: str) -> list[str]:
    c = b.cr(cr_id)
    b.touch(c, status="blocked", blocked_reason=note)
    out = [f"ask-chief-of-staff blocked {cr_id} {note}".rstrip()] + fill_slots(b)
    if b.data["mode"] == "stack" and _stack_ready(b):
        ready = [x for x in b.data["crs"] if x["status"] == "ready"]
        if ready:
            out += [_restack(b), f"ask-chief-of-staff stack-ready {_links(b, ready)}"]
    return out


def _on_question(b: Batch, cr_id: str, note: str) -> list[str]:
    b.touch(b.cr(cr_id))
    return [f"ask-chief-of-staff question {cr_id} {note}".rstrip()]


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
    return [f"spawn {cr_id} resume round: {note}"]


def _on_qa_done(b: Batch, cr_id: str, note: str) -> list[str]:
    c = b.cr(cr_id)
    findings = int(note.split()[0]) if note.split() and note.split()[0].isdigit() else 0
    c["qa_done"] = True
    if findings:
        b.touch(c)
        return ["none"]
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
    return [f"spawn {cr_id} resume"]


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
            return [f"spawn {cr_id} resume"]
        return []
    c = b.cr(cr_id)
    if c["status"] == "working":
        return _on_driver_lost(b, cr_id, note)
    return []


# ---- orders from the Chief of Staff -----------------------------------------------------------

def _on_order_add(b: Batch, _cr: str, note: str) -> list[str]:
    from .commands import add_cr  # avoid an import cycle
    title = note or "untitled"
    c = add_cr(b, title)
    return [f"ok add {c['id']}"] + fill_slots(b)


def _on_order_drop(b: Batch, cr_id: str, _note: str) -> list[str]:
    c = b.cr(cr_id)
    if c["status"] in LIVE:
        return [f"cancel {cr_id}", f"ok drop {cr_id}"]
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
    b.touch(c, status="merged")
    out = [f"ok merged {cr_id}"]
    if _all_merged(b):
        return out + ["land"]
    if b.data["mode"] == "stack":
        out.append(_restack(b))
    return out + fill_slots(b)


def _on_order_pause(b: Batch, _cr: str, _note: str) -> list[str]:
    b.data["paused"] = True
    return ["ok pause"]


def _on_order_resume(b: Batch, _cr: str, _note: str) -> list[str]:
    b.data["paused"] = False
    b.data["budget_asked"] = False
    return ["ok resume"] + fill_slots(b)
