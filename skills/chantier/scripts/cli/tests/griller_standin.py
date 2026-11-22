"""The board's Griller tests' stand-in for the host CLI: a real child process that reads its prompt
on standard input, writes a file in the CR's folder and prints a JSON result like Claude Code's
(`result`, `is_error`, `session_id` and its working directory). A word of the prompt asks for more:
`[sleep]` (after the file, sleep), `[child]` (also start a child that sleeps), `[fail]` (an error
text on standard error, exit 3, no JSON), `[move]` (move the CR's folder to `P1` as another session
would, write a file at the old path, write the confirmation file, sleep), `[grilled]` (the answer
ends with the board's line). It is not a test: `test_board_griller.py` runs it."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

SLEEP_S = 60


def _move(folder: Path, confirm: Path) -> None:
    from chantier.core.repo import Repo  # noqa: PLC0415 - slow import, this case only
    from chantier.lifecycle.backlog import move_item  # noqa: PLC0415

    move_item(Repo.find(cwd=Path.cwd(), readonly=True), str(folder), "P1")
    folder.mkdir()  # as a session that writes at the old path would
    (folder / "stray.md").write_text("written at the old path\n", encoding="utf-8")
    confirm.write_text("old path made again\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--folder", required=True)
    ap.add_argument("--file", default="02-answers.md")
    ap.add_argument("--log", required=True)  # the prompts read, one JSON line each
    ap.add_argument("--pids", required=True)  # the stand-in's pid, then its child's
    ap.add_argument("--confirm", required=True)
    ap.add_argument("--session", default="")
    args = ap.parse_args()
    prompt = sys.stdin.buffer.read().decode("utf-8")
    with open(args.log, "a", encoding="utf-8") as log:
        log.write(json.dumps({"prompt": prompt, "session": args.session}) + "\n")
    folder = Path(args.folder)
    if "[fail]" in prompt:
        sys.stderr.write("standin: the host said boom\n")
        return 3
    (folder / args.file).write_text(f"recorded: {prompt[-40:]}\n", encoding="utf-8")
    pids = [os.getpid()]
    if "[child]" in prompt:
        child = subprocess.Popen([sys.executable, "-c", f"import time; time.sleep({SLEEP_S})"])
        pids.append(child.pid)
    Path(args.pids).write_text(" ".join(map(str, pids)), encoding="utf-8")
    if "[move]" in prompt:
        _move(folder, Path(args.confirm))
    if any(word in prompt for word in ("[sleep]", "[child]", "[move]")):
        time.sleep(SLEEP_S)
    answer = f"standin cwd={os.getcwd()}"
    if "[grilled]" in prompt:
        answer += "\n[griller→board] grilled enough: next batch"
    out = {"type": "result", "is_error": False, "result": answer, "session_id": args.session}
    sys.stdout.buffer.write(json.dumps(out, ensure_ascii=False).encode("utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
