"""Check the mod: `claude plugin validate .` then `claude plugin test .`, from the repository's root.

It finds the `claude` binary itself: on the PATH, else the executable of the process
CLAUDE_PID names (on Claude Desktop `claude` is not on the PATH). No binary: it exits 1 and says so.
`validate`'s known warnings (the marketplace description, the missing icon) do not fail it.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def of_process(pid: str) -> str | None:
    """The executable of a running process, or None."""
    if not pid.isdigit():
        return None
    if os.name == "nt":
        cmd = ["powershell.exe", "-NoLogo", "-NoProfile", "-Command", f"(Get-Process -Id {pid}).Path"]
    elif sys.platform == "linux":
        link = Path(f"/proc/{pid}/exe")
        return str(link.resolve()) if link.exists() else None
    else:
        cmd = ["ps", "-p", pid, "-o", "comm="]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, check=False).stdout.strip()
    except OSError:
        return None
    return out if out and Path(out).exists() else None


def find_claude() -> str | None:
    return shutil.which("claude") or of_process(os.environ.get("CLAUDE_PID", ""))


def main() -> int:
    claude = find_claude()
    if claude is None:
        print("just mod: no claude binary found (not on the PATH, and CLAUDE_PID names no process)", file=sys.stderr)
        return 1
    print(f"just mod: using {claude}", flush=True)
    for step in ("validate", "test"):
        print(f"\n$ claude plugin {step} .", flush=True)
        code = subprocess.run([claude, "plugin", step, "."], cwd=ROOT, check=False).returncode
        if code != 0:
            print(f"just mod: claude plugin {step} failed ({code})", file=sys.stderr)
            return code
    return 0


if __name__ == "__main__":
    sys.exit(main())
