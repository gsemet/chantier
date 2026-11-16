"""Check which model each chantier role ran on, from a Copilot session's event log.

Reads `events.jsonl` of a Copilot session (`--session <id>`; with none, the most recently modified
folder of `<COPILOT_HOME or ~/.copilot>/session-state/`) and writes nothing.

From each `subagent.started`, `subagent.completed` and `subagent.failed` event it reads `data`'s
`model`, `firstDispatchedModel` and `modelSelectionSource`, the fields CR-296 round 6 recorded
(planning surface: `296-improve-skill-boot/work/handoff.md`, "Model evidence"). It reads no other
field: no source for a field that names the agent was found in the Copilot SDK's published event
schema, so a role's event is matched by order, never by name.

Then one row per role, in `ROLES` order, with the identifier its agent file
`com.github.copilot/agents/chantier-<role>.agent.md` names and the one recorded. Exit 0 when every
role is `ok`, else 1.

With `--probe <identifier>`, it reads only the last ended subagent event (`subagent.completed` or
`subagent.failed`), prints its type and the three fields, then `ran the requested model` (exit 0)
when its `model` equals the identifier, else `ran <model>, not the requested <identifier>` (or
`no ended subagent event`) and exit 1.

    uv run --no-project python evals/kit/copilot_models.py [--session <id>] [--probe <identifier>]
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

# The order the runbook's "Models" section starts the agents in.
ROLES = (
    "cr-driver",
    "stack-driver",
    "qa-driver",
    "release-driver",
    "investigator",
    "coder",
    "inspector",
    "debugger",
    "verifier",
    "conflict-resolver",
    "demo-explorer",
    "spec-writer",
    "spec-critic",
    "retro-critic",
)
EVENTS = ("subagent.started", "subagent.completed", "subagent.failed")
ENDED = ("subagent.completed", "subagent.failed")
FIELDS = ("model", "firstDispatchedModel", "modelSelectionSource")


def expected(role: str) -> str:
    path = ROOT / "com.github.copilot" / "agents" / f"chantier-{role}.agent.md"
    match = re.search(r"^model:\s*\[(.*)\]\s*$", path.read_text(encoding="utf-8"), re.M)
    return match.group(1).split(",")[-1].strip() if match else "unknown"


def session_file(session: str | None) -> Path:
    home = Path(os.environ.get("COPILOT_HOME") or Path.home() / ".copilot")
    states = home / "session-state"
    if session:
        return states / session / "events.jsonl"
    folders = [p for p in states.glob("*") if p.is_dir()] if states.is_dir() else []
    if not folders:
        raise SystemExit(f"no session folder in {states}")
    return max(folders, key=lambda p: p.stat().st_mtime) / "events.jsonl"


def probe(ended: list[dict[str, Any]], wanted: str) -> int:
    """The last ended subagent event only: did it run the requested model? 0 when it did."""
    if not ended:
        print("no ended subagent event")
        return 1
    event = ended[-1]
    data = event.get("data") or {}
    print(f"{event['type']}: " + " ".join(f"{f}={data.get(f, 'absent')}" for f in FIELDS))
    ran = data.get("model")
    if ran == wanted:
        print("ran the requested model")
        return 0
    print(f"ran {ran or 'absent'}, not the requested {wanted}")
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--session", help="the session's id (default: the most recent)")
    parser.add_argument(
        "--probe",
        metavar="IDENTIFIER",
        help="check the last ended subagent event ran this model (a named agent started with it)",
    )
    args = parser.parse_args(argv)
    path = session_file(args.session)
    if not path.is_file():
        print(f"no events file: {path}")
        return 1
    events = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if isinstance(event, dict) and event.get("type") in EVENTS:
            events.append(event)
    ended = [e for e in events if e["type"] in ENDED]
    if args.probe:
        return probe(ended, args.probe)
    for event in events:
        data = event.get("data") or {}
        shown = " ".join(f"{f}={data.get(f, 'absent')}" for f in FIELDS)
        print(f"{event['type']}: {shown}; no agent field in the event")
    count_ok = len(ended) == len(ROLES)
    if not count_ok:
        print(f"{len(ended)} ended events for {len(ROLES)} roles")
    failed = False
    for i, role in enumerate(ROLES):
        want = expected(role)
        if not count_ok:
            print(f"{role}: expected {want}; unmatched (event count)")
            failed = True
            continue
        got = (ended[i].get("data") or {}).get("model") or "not recorded"
        verdict = "ok" if got == want else "MISMATCH"
        failed = failed or verdict != "ok"
        print(f"{role}: expected {want}; recorded {got}; {verdict} (matched by order)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
