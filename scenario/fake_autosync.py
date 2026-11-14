"""A stand-in for a planning surface's `scripts/ai-autosync-git.py`, for the scenario. It needs no
dependency. It appends its arguments to `<its own name>.argv` (one JSON line per run) and writes
the state files the real tool would write in `<git dir>/ai-autosync/`:

- `join` writes a participant file and stays until that file is deleted (or 90 s have passed);
- `start` enables the group, `stop` disables it, `approve` records the incident it was given.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path


def option(argv: list[str], name: str) -> str | None:
    return argv[argv.index(name) + 1] if name in argv else None


def put(path: Path, data: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def join(state: Path, argv: list[str]) -> None:
    mine = state / "participants" / f"{os.getpid()}.json"
    put(
        mine,
        {
            "pid": os.getpid(),
            "harness": option(argv, "--harness") or "auto",
            "owner_pid": int(option(argv, "--owner-pid") or 0),
            "session_id": option(argv, "--session-id"),
            "role": "follower",
            "since": time.time(),
        },
    )
    end = time.monotonic() + 90
    while mine.exists() and time.monotonic() < end:
        time.sleep(0.2)


def main(argv: list[str]) -> int:
    here = Path(__file__).resolve()
    with here.with_suffix(".argv").open("a", encoding="utf-8") as log:
        log.write(json.dumps(argv) + "\n")
    git = subprocess.run(
        ["git", "rev-parse", "--absolute-git-dir"], capture_output=True, text=True, check=True
    )
    state = Path(git.stdout.strip()) / "ai-autosync"
    action = argv[0] if argv else ""
    if action == "join":
        join(state, argv)
    elif action in ("start", "stop"):
        enabled = action == "start"
        reason = "started by user" if enabled else "stopped by user"
        put(state / "control.json", {"enabled": enabled, "reason": reason, "updated_at": time.time()})
        print(reason)
    elif action == "approve":
        put(state / "approvals.json", {"approved": argv[2:]})
        print(f"approved {argv[2] if len(argv) > 2 else ''}")
    else:
        print("fake autosync: nothing to do")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
