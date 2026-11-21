#!/usr/bin/env python3
"""Global scenario: one whole chantier batch, end to end, through the real CLI.

A scripted Foreman reads the batch's state and does what its card leaves it (fills the slots,
asks the Chief of Staff, merges what the user allowed, cleans up, pauses); scripted
Drivers create their worktree, commit, rebase, push and open their PRs against a bare origin and
a fake `gh` (or `glab`), and use the CLI for its record (`round`, `gate`, `ship`, `handback`).
The Chief of Staff steers with `chantier order`. Nothing calls a model: the scripted agents prove
the frame, and the checks are on what the CLI refuses, records and reports.

    just scenario [--unit NAME]... [--forge github|gitlab] [--jobs N] [--keep] [--verbose]

The scenario is a table of independent units (`UNITS`), each run by a child process of its own, in
a temporary world of its own, `--jobs` at a time (4 by default). Exit 0 when every check of every
unit passes and no unit hangs; a unit over its budget only prints a warning. The transcript is
written to scenario/results/scenario-<time>-<pid>.md and each unit's own files to
scenario/results/<time>-<pid>/ (ignored by git).
"""

from __future__ import annotations

import argparse
from collections.abc import Callable
import hashlib
import html
import http.client
import json
import contextlib
import os
import posixpath
import queue
import re
import shlex
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

import psutil

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent / "skills" / "chantier"
FAKE = {"github": ("gh", Path(__file__).with_name("fake_gh.py")),
        "gitlab": ("glab", Path(__file__).with_name("fake_glab.py"))}
PR_LINK = {"github": "https://github.com/acme/demo/pull/",
           "gitlab": "https://gitlab.example.com/acme/demo/-/merge_requests/"}
FAKE_USAGE = Path(__file__).with_name("fake_session_usage.py")
LOG: list[str] = []
CHECKS = {"pass": 0, "fail": 0}
GATE = f'"{sys.executable}" -m compileall -q .'  # what the project's AGENTS.md names: no uv start per gate
FROM_AGENTS_MD = ("--default-branch", "main")
TRAILER = "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
BODY = ("## Summary\n\n{title}.\n\n## Deliverables\n\nNone.\n\n## Blast radius\n\nGrade: 1\n\n"
        "## Autonomous decisions\n\nNone.\n\n## Known gaps\n\nNone.\n\n"
        "<details>\n<summary>Details</summary>\n\n"
        "## Changes\n\nNone.\n\n## Impacts\n\nNone.\n\n## Test plan\n\nNone.\n\n"
        "## Internal references\n\n{cr}\n\n</details>\n")
LIVE = {"working"}
ENDED = {"merged", "cancelled"}
BACK_NOTES = ("rebase:", "merged:")
OPENED: dict[str, str] = {}  # the PR the scripted Driver opened for a CR


# The units: {name: (budget in seconds, forges, [case, ...])}. Each unit is one child process in a
# world of its own; a unit over its budget only warns (the budget is one literal per unit, easy to
# edit), a unit past its hang timeout (the larger of 600 s and 4 times its budget) is killed and
# fails the run. A case is a function of CASES at the end of this file. `parallel`'s first case is
# the main batch's sections; GitLab runs only the `gitlab` unit.
UNITS = {
    "parallel": (350, ["github"], ["scenario", "close_batch", "retro_cases"]),
    "stack": (
        750,
        ["github"],
        ["stack_batch", "start_base_forge", "base_from_pr", "stack_waiver", "ready_words",
         "ready_words_unplaced", "forge_stack_cli", "stack_hold", "park_live", "hold_live"],
    ),
    "release": (
        585,
        ["github"],
        [
            "release",
            "granted_fixes",
            "release_last",
            "release_on_stack",
            "release_merge_on_approval",
        ],
    ),
    "gates": (
        610,
        ["github"],
        [
            "rails",
            "gate_parallel",
            "cancel_during_gate",
            "stop_own_gate",
            "handback_proofs",
            "gate_proof",
            "gate_next_merge",
            "gate_carry",
            "gate_carry_stack",
        ],
    ),
    "series-deps": (380, ["github"], ["batch_modes", "dependencies", "early_conflict",
                                      "changes_tree"]),
    "direct": (220, ["github"], ["direct_batch", "seat_handover", "foreman_in_a_worktree",
                                 "empty_batch", "running_batch"]),
    "surface-board": (
        660,
        ["github"],
        ["remote_board", "forge_hub", "outside_poller", "typed_waits", "surface_server",
         "external_surface", "surface_writer", "cr_summary"],
    ),
    "qa-driver": (255, ["github"], ["lost_messages", "qa_on_head", "driver_liveness", "restore_cr"]),
    "gitlab": (115, ["gitlab"], ["gitlab_ship_merge", "forge_stack_cli", "typed_waits"]),
}
JOBS = 4  # units run at once, by default
HANG_FLOOR_S = 600  # a unit is hung past max(this, 4 times its budget)

COMMANDS = [0]  # the processes the scenario itself starts (the CLI's own children are not counted)
TIMES: list[tuple[str, float, int]] = []  # (case or section, seconds, commands)
FAILED: list[str] = []  # the labels of the failed checks, for the unit's JSON
_popen_init = subprocess.Popen.__init__


def _counting_init(self, *args, **kwargs):  # subprocess.run goes through Popen: one place counts
    COMMANDS[0] += 1
    _popen_init(self, *args, **kwargs)


def count_commands() -> None:
    """A unit's process counts the processes it starts; the parent counts none."""
    subprocess.Popen.__init__ = _counting_init


class timed:
    """`with timed("name"):` adds one row (seconds, commands started inside) to TIMES."""

    def __init__(self, name: str):
        self.name = name

    def __enter__(self):
        self.t0, self.c0 = time.monotonic(), COMMANDS[0]
        return self

    def __exit__(self, *exc):
        TIMES.append((self.name, time.monotonic() - self.t0, COMMANDS[0] - self.c0))
        return False


_SECTION: list[timed | None] = [None]


def section_end() -> None:
    if _SECTION[0] is not None:
        _SECTION[0].__exit__()
        _SECTION[0] = None


def section(name: str) -> None:
    """Close the running section of the main batch and open the next one."""
    section_end()
    _SECTION[0] = timed(f"section {name}")
    _SECTION[0].__enter__()


def timing_table() -> list[str]:
    rows = ["| case or section | seconds | commands |", "| --- | ---: | ---: |"]
    rows += [f"| {n} | {s:.1f} | {c} |" for n, s, c in TIMES]
    rows.append(
        f"| total of the rows | {sum(s for _, s, _ in TIMES):.1f} | {sum(c for _, _, c in TIMES)} |"
    )
    return rows


def note(line: str) -> None:
    LOG.append(line)
    if ARGS.verbose:
        print(line)


def check(label: str, ok: bool, detail: str = "") -> None:
    CHECKS["pass" if ok else "fail"] += 1
    if not ok:
        FAILED.append(label)
    note(f"- [{'x' if ok else ' '}] {label}{'' if ok else f' — {detail}'}")
    if not ok and not ARGS.verbose:
        print(f"FAIL {label}: {detail}")


def prompt_block(out: list[str], role: str) -> list[str]:
    """A Driver's skeleton in a command's output: its heading, then the indented lines."""
    at = next((i for i, ln in enumerate(out) if ln.startswith(f"{role} prompt (")), None)
    if at is None:
        return []
    end = at + 1
    while end < len(out) and out[end].startswith("  "):
        end += 1
    return out[at:end]


def stack_take_rows(out: list[str]) -> list[str]:
    """`take stack`'s chain line and CR rows: before the skeleton, with no `timing:` line."""
    at = next((i for i, ln in enumerate(out) if ln.startswith("stack-driver prompt (")), len(out))
    return [ln for ln in out[:at] if not ln.startswith("timing: ")]


def check_worker_writes_line(w, cr: str, out: list[str], label: str) -> None:
    """After a `take` or a `round`, the worker `writes:` line is bare: no parenthetical, two
    absolute paths, the CR's worktree first, then its folder; the Verifier's scratch folder
    follows `folder:` inside that folder."""
    at = next((i for i, ln in enumerate(out) if ln.lstrip().startswith("worker writes line (")), -1)
    line = out[at + 1].strip() if at >= 0 and at + 1 < len(out) else ""
    paths = line.removeprefix("writes: ").split("; ")
    folder = next((ln.split(" (")[0].removeprefix("folder: ") for ln in out
                   if ln.startswith("folder: ")), "")
    scratch = [ln for ln in out if ln.startswith("scratch: ")]
    check(f"`{label}` prints the worker `writes:` line bare (no parenthetical), worktree first, "
          "both paths absolute, and the scratch folder inside the CR folder",
          line.startswith("writes: ") and "(" not in line and len(paths) == 2
          and all(Path(p).is_absolute() for p in paths)
          and paths[0] == Path(w.cr(cr)["worktree"]).as_posix() and paths[1] == folder
          and scratch == [f"scratch: {folder}/work/scratch"], str(out))


def check_driver_skeleton(w, target: str, out: list[str]) -> None:
    """After a `take`, the skeleton of the CR's Driver: no `writes:` line for a release or stack
    driver and the stack rows in the stack driver's; for any other CR one `writes:` line naming
    the CR's folder, with an absolute archive path when `take` printed an `archive:` line."""
    kind = "stack" if target == "stack" else w.cr(target).get("kind", "change")
    role = {"stack": "stack-driver", "release": "release-driver"}.get(kind, "cr-driver")
    block = prompt_block(out, role)
    writes = [ln for ln in block if ln.startswith("  writes:")]
    label = f"`take {target}` prints the {role} prompt, copied whole"
    if role != "cr-driver":
        rows = (
            [ln for ln in out[: out.index(block[0])] if ln.startswith(("the stack of", "CR-"))]
            if block and role == "stack-driver"
            else []
        )
        check(
            f"{label}, with no `writes:` line" + (" and the stack's rows" if rows else ""),
            bool(block)
            and not writes
            and (role != "stack-driver" or (rows and all(f"  {ln}" in block for ln in rows))),
            str(block),
        )
        return
    folder = next(
        (ln.split(" (")[0].removeprefix("folder: ") for ln in out if ln.startswith("folder: ")),
        None,
    )
    archive = next(
        (ln.split(" at ", 1)[1] for ln in out if ln.startswith("archive: in the PR at ")), None
    )
    paths = writes[0].removeprefix("  writes: ").split("; ") if writes else []
    check(
        f"{label}, with one `writes:` line: the CR folder"
        + (", then the absolute archive path" if archive else ""),
        bool(block)
        and len(writes) == 1
        and paths[:1] == [folder]
        and (
            archive is None
            or (len(paths) == 2 and Path(paths[1]).is_absolute() and paths[1].endswith(archive))
        ),
        str(block),
    )


def unit_name(word: str) -> str:
    """A lease's unit: `CR-106` for `106`, `cr-106` and `CR-106`; `STACK` for the stack."""
    word = word.upper()
    return f"CR-{word}" if word.isdigit() else word


def stamp_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class World:
    def __init__(self, root: Path):
        self.root = root
        self.work = root / "proj"
        self.state = self.work / ".agents" / "changes"
        self.gh_state = root / "gh-state.json"
        exe, _ = FAKE[ARGS.forge]
        self.fake = root / "bin" / (f"{exe}.cmd" if sys.platform == "win32" else exe)
        self.env = {**os.environ, "PYTHONPATH": str(SKILL / "scripts" / "cli" / "src"),
                    "CHANTIER_SKILL_DIR": str(SKILL), "FAKE_GH_STATE": str(self.gh_state),
                    "CHANTIER_CLAUDE_PROJECTS": str(root / "claude-projects"),
                    "CLAUDE_CODE_ENTRYPOINT": "claude-desktop", "CHANTIER_HOST": "claude",
                    "CLAUDE_CODE_SESSION_ID": "uuid-chief",  # the Chief of Staff's session
                    # a board's API: it looks every 1 s, holds a long-poll 6 s, ticks and waits for a hello 5 s
                    "CHANTIER_API_TEST_TIMES": "1:6:5:5"}
        for var in ("CHANTIER_ROOT", "CHANTIER_BATCH", "CHANTIER_PLUGIN_ROOT",
                    "COPILOT_AGENT_SESSION_ID"):
            self.env.pop(var, None)
        # the fake forge CLI comes first on PATH: a stacked CR's base is read from the forge by
        # `take`, `handoff` and `ship`, and the scenario never reaches a real forge
        path_key = next(k for k in self.env if k.upper() == "PATH")
        self.env[path_key] = f"{self.fake.parent}{os.pathsep}{self.env[path_key]}"
        self.last_stderr = ""
        self.last_out: list[str] = []
        self.name = ""  # the running batch's id, `batch-<n>`: the CLI numbers it
        self.leases: dict[str, int] = {}  # the number `take` printed, by unit (upper case)

    def sh(self, *args, cwd=None):
        return subprocess.run(args, cwd=cwd or self.work, check=True, capture_output=True,
                              text=True).stdout.strip()

    def build(self) -> None:
        origin = self.root / "origin.git"
        self.sh("git", "init", "--quiet", "--bare", "-b", "main", str(origin), cwd=self.root)
        self.sh("git", "init", "--quiet", "-b", "main", str(self.work), cwd=self.root)
        self.sh("git", "config", "user.name", "scenario")
        self.sh("git", "config", "user.email", "scenario@example.com")
        (self.work / "app.py").write_text("def login():\n    return True\n")
        (self.work / "AGENTS.md").write_text(
            f"# Project instructions\n\nDefault branch: `main`. Remote: `origin`.\n"
            f"Long gate, before a PR: `{GATE}`. Merge by rebase.\n"
            "Commits and PRs: see [CONTRIBUTING.md](CONTRIBUTING.md).\n")
        (self.work / "CONTRIBUTING.md").write_text(
            "# Contributing\n\nPR titles: `feat: <subject>`. Fill every section of the PR template.\n")
        (self.work / ".gitignore").write_text("__pycache__/\n")
        self.sh("git", "add", ".")
        self.sh("git", "commit", "--quiet", "-m", "init", "-m", TRAILER)
        self.sh("git", "remote", "add", "origin", str(origin))
        self.sh("git", "push", "--quiet", "-u", "origin", "main")
        _, script = FAKE[ARGS.forge]
        gh = self.fake
        gh.parent.mkdir()
        if sys.platform == "win32":
            gh.write_text(f'@"{sys.executable}" "{script}" %*\r\n')
        else:
            gh.write_text(f"#!/bin/sh\nexec {sys.executable} {script} \"$@\"\n")
            gh.chmod(0o755)
        self.gh(next_pr=40)

    def gh(self, **kw) -> None:
        d = json.loads(self.gh_state.read_text()) if self.gh_state.exists() else {}
        d.update(kw)
        self.gh_state.write_text(json.dumps(d))

    def forge(self, *args) -> tuple[int, str, str]:
        """The Driver's or the Foreman's own call to the forge's CLI (the fake one)."""
        p = subprocess.run([str(self.fake), *args], cwd=self.work, env=self.env,
                           capture_output=True, text=True, encoding="utf-8")
        note(f"    $ {FAKE[ARGS.forge][0]} {' '.join(args[:4])}…  → exit {p.returncode}")
        return p.returncode, p.stdout.strip(), p.stderr.strip()

    @staticmethod
    def words(args) -> list[str]:
        """The command's words, without the global `--project <name>` in front."""
        words = [str(a) for a in args]
        return words[2:] if words[:1] == ["--project"] else words

    def lease_unit(self, args) -> str | None:
        """The unit a Driver's lease-guarded command works on (`round`, `ship`, `handback`,
        `release start|go|published`, the stack driver's writing forms), else None."""
        words = self.words(args)
        if not words or "--epoch" in words or "--lease" in words or "--reclaim" in words:
            return None
        if words[0] in ("round", "ship", "handback") and len(words) > 1:
            return unit_name(words[1])
        if words[0] == "release" and len(words) > 2 and words[1] in ("start", "go", "published"):
            return unit_name(words[2])
        if words[0] == "forge-stack" and len(words) > 1 and words[1] != "show":
            return "STACK"
        if words[0] == "stack":
            rest = [a for i, a in enumerate(words[1:], 1) if a != "--batch"
                    and words[i - 1] != "--batch"]
            return "STACK" if rest else None
        return None

    def chantier(self, *args, env=None, expect=0, cwd=None, lease=True, stdin=None):
        """`lease=False` runs a Driver's command without the number `take` printed (a missing
        lease case)."""
        unit = self.lease_unit(args) if lease else None
        if unit and self.leases.get(unit):
            args = (*args, "--lease", self.leases[unit])
        p = subprocess.run([sys.executable, "-m", "chantier", *map(str, args)], cwd=cwd or self.work,
                           env={**self.env, **(env or {})}, capture_output=True, text=True,
                           encoding="utf-8", input=stdin)
        out = p.stdout.strip().splitlines()
        self.last_stderr = p.stderr.strip()
        self.last_out = out
        note(f"    $ chantier {' '.join(map(str, args))}  → exit {p.returncode}")
        for ln in out + ([f"stderr: {self.last_stderr}"] if self.last_stderr else []):
            note(f"      {ln}")
        said = self.words(args)
        if p.returncode == 0 and said[:1] == ["handback"] and len(said) > 1:
            self.leases.pop(unit_name(said[1]), None)  # a hand-back ends the lease
        if p.returncode == 0 and said[:2] == ["agents", "set"] and said[3:4] == ["-"]:
            self.leases.pop(unit_name(said[2]), None)  # the Driver ended: the clearance ends it
        if p.returncode == 0 and said[:1] == ["take"] and len(said) > 1 and out:
            # a CR's `take` prints it on its first line, `take stack` in its `lease: stack <n>` fact
            m = (re.search(r", lease (\d+) until", out[0])
                 or next(filter(None, (re.match(r"\s*lease: stack (\d+) ", ln) for ln in out)), None))
            if m:
                self.leases[unit_name(said[1])] = int(m[1])  # the Driver keeps the number
        if expect is not None and p.returncode != expect:
            check(f"chantier {' '.join(map(str, args))} exits {expect}", False,
                  f"exit {p.returncode}: {self.last_stderr[:200]}")
        return p.returncode, out

    def verified(self, cr, **kw):
        """The Verifier's end: its proof note at the head it judged, then `verdict VERIFIED`."""
        raw = str(cr).upper()
        c = self.cr(raw if raw.startswith("CR-") else f"CR-{raw}")
        head = subprocess.run(["git", "-C", c["worktree"], "rev-parse", "HEAD"], capture_output=True,
                              text=True, encoding="utf-8", check=True).stdout.strip()
        note_file = self.at(c["path"]) / "work" / "verify.md"
        note_file.parent.mkdir(parents=True, exist_ok=True)
        note_file.write_text(f"Head: {head}\n", encoding="utf-8", newline="\n")
        return self.chantier("verdict", cr, "VERIFIED", **kw)
    def ready(self, cr, link, expect=0):
        """The Driver's end: the long gate and the Verifier's verdict at the head, then `handback ready`."""
        self.chantier("gate", cr, GATE, expect=None)
        self.verified(cr, expect=None)
        return self.chantier("handback", cr, "ready", link, expect=expect)

    def batch(self):
        return json.loads((self.folder() / "batch.json").read_text())

    def folder(self, name=None):
        return self.state / "4-batch"

    def start(self, *args, **kw):
        """`open` takes no name: the batch is `batch-<n>`, and it is the one running batch."""
        code, out = self.chantier("open", *args, **kw)
        if code == 0:
            self.leases.clear()  # a new batch, new leases
            self.name = out[0].split()[1]
        return code, out

    def reset(self) -> None:
        """Sweep what an earlier case left open: `open` refuses a second batch."""
        if (self.state / "4-batch").is_dir():
            shutil.rmtree(self.state / "4-batch")
        self.leases.clear()

    def cr(self, cr_id):
        return next(c for c in self.batch()["crs"] if c["id"] == cr_id)

    def at(self, path):
        """A recorded CR path in the planning folder."""
        return self.state / str(path)


def open_pr(w: World, cr_id: str, title: str, base: str = "main") -> str:
    """The Driver opens the PR with the forge's CLI, from the body it wrote."""
    c = w.cr(cr_id)
    body = w.at(c["path"]) / "work" / "pr-body.md"
    if ARGS.forge == "github":
        _, out, _ = w.forge("pr", "create", "--base", base, "--head", c["branch"], "--title",
                            title, "--body-file", str(body))
        return out.splitlines()[-1]
    _, out, _ = w.forge("api", "projects/local/merge_requests", "--method", "POST",
                        "--raw-field", f"source_branch={c['branch']}", "--raw-field",
                        f"target_branch={base}", "--raw-field", f"title={title}")
    return json.loads(out)["web_url"]


def forge_base(w: World, link: str, base: str) -> None:
    """What the stack driver does on the forge: the PR at `link` now targets `base`."""
    n = link.rstrip("/").rsplit("/", 1)[-1]
    state = json.loads(w.gh_state.read_text())
    if ARGS.forge == "github":
        state.setdefault("bases", {})[n] = base
    else:
        state.setdefault("mrs", {}).setdefault(n, {"state": "opened", "draft": False,
                                                    "source_branch": "", "web_url": link})
        state["mrs"][n]["target_branch"] = base
    w.gh_state.write_text(json.dumps(state))


def forge_draft(w: World, link: str, draft: bool) -> None:
    """What the Driver does on the forge (`pr ready`, `mr update --draft`): the PR at `link` is
    now a draft, or out of draft."""
    n = link.rstrip("/").rsplit("/", 1)[-1]
    state = json.loads(w.gh_state.read_text())
    if ARGS.forge == "github":
        drafts = {int(x) for x in state.get("drafts", [])} - {int(n)}
        state["drafts"] = sorted(drafts | ({int(n)} if draft else set()))
    else:
        state.setdefault("mrs", {}).setdefault(n, {"state": "opened", "target_branch": "main",
                                                    "source_branch": "", "web_url": link})
        state["mrs"][n]["draft"] = draft
    w.gh_state.write_text(json.dumps(state))


def forge_calls(w: World) -> list[list[str]]:
    """The calls the fake forge logged, in order."""
    log = w.root / "gh-state.json.calls"
    return [json.loads(x) for x in log.read_text().splitlines()] if log.exists() else []


def merge_pr(w: World, pr: str) -> tuple[int, str]:
    """A merge with the forge's CLI, by the project's method (rebase)."""
    if ARGS.forge == "github":
        code, _, err = w.forge("pr", "merge", pr, "--rebase")
    else:
        code, _, err = w.forge("api", f"projects/local/merge_requests/{pr.rsplit('/', 1)[-1]}/merge",
                               "--method", "PUT")
    return code, err


def land(w: World, branch: str, extra: tuple[str, str] | None = None) -> str:
    """The user's merge reaches the bare origin: the CR's commits land on `main` by rebase (the
    project's method), with git from a scratch clone outside the project, never through the fake
    forge. With `extra` (a path and its content), a commit adding that file lands instead."""
    scratch = w.root / "landing"
    if not scratch.is_dir():
        w.sh("git", "clone", "--quiet", str(w.root / "origin.git"), str(scratch), cwd=w.root)
        w.sh("git", "config", "user.name", "scenario", cwd=scratch)
        w.sh("git", "config", "user.email", "scenario@example.com", cwd=scratch)
    w.sh("git", "fetch", "--quiet", "origin", cwd=scratch)
    if extra:
        w.sh("git", "checkout", "--quiet", "--detach", "origin/main", cwd=scratch)
        (scratch / extra[0]).write_text(extra[1])
        w.sh("git", "add", "-f", "--", extra[0], cwd=scratch)
        w.sh("git", "commit", "--quiet", "-m", f"add {extra[0]}", "-m", TRAILER, cwd=scratch)
    else:
        w.sh("git", "checkout", "--quiet", "--detach", f"origin/{branch}", cwd=scratch)
        w.sh("git", "rebase", "--quiet", "origin/main", cwd=scratch)
    w.sh("git", "push", "--quiet", "origin", "HEAD:main", cwd=scratch)
    return w.sh("git", "rev-parse", "HEAD", cwd=scratch)


class Foreman:
    """Does what foreman.md leaves it, from `batch.json` (a real one reads `chantier status`):
    the pending orders, the asks, the merges the user allowed, the free slots, the QA drivers,
    the cleanup, the pause."""

    def __init__(self, w: World, epoch: int):
        self.w, self.epoch = w, epoch
        self.started: list[str] = []
        self.asked: list[str] = []
        self.messages: list[str] = []
        self.cancelled: list[str] = []
        self.qa: list[str] = []  # the folders of the QA drivers it started
        self.told: set = set()
        self.facts: list[str] = []
        self.paused = False
        self.git_main: list[tuple[str, ...]] = []  # every git command it ran in the main checkout

    def git(self, *args: str) -> subprocess.CompletedProcess:
        """The Foreman's git in the main checkout; the commands are kept for a check."""
        self.git_main.append(args)
        return subprocess.run(["git", *args], cwd=self.w.work, capture_output=True, text=True,
                              encoding="utf-8")

    def fast_forward(self, cr: str) -> str:
        """foreman.md, "The main checkout after a merge": steps 2 to 5 (step 1 reads the rules,
        which say nothing against it here), then the `main checkout:` note on the CR."""
        remote, default = "origin", "main"
        why = None
        branch = self.git("symbolic-ref", "--quiet", "--short", "HEAD").stdout.strip()
        if branch != default:
            why = f"on {branch}, not {default}" if branch else "detached HEAD"
        if why is None:
            dirty = [ln[3:] for ln in self.git("status", "--porcelain",
                                               "--untracked-files=no").stdout.splitlines()]
            if dirty:
                why = f"tracked changes: {', '.join(dirty[:3])}"
        if why is None:
            p = self.git("fetch", remote, default)
            if p.returncode:
                why = f"fetch failed: {p.stderr.strip()}"
        line = None
        if why is None:
            p = self.git("merge", "--ff-only", "--no-overwrite-ignore", f"{remote}/{default}")
            sha7 = self.git("rev-parse", "--short=7", "HEAD").stdout.strip()
            text = p.stdout + p.stderr
            if p.returncode == 0:
                line = (f"already at {sha7}" if "Already up to date" in text
                        else f"fast-forwarded to {sha7}")
            elif "Not possible to fast-forward" in text or "diverging" in text:
                why = f"diverged from {remote}/{default}"
            elif "untracked working tree files would be overwritten" in text:
                paths = [ln.strip() for ln in text.splitlines() if ln.startswith(("\t", " "))
                         and ln.strip() and not ln.strip().startswith(("Please", "Aborting"))]
                why = f"untracked file in the way: {paths[0] if paths else '?'}"
            else:
                why = text.strip().splitlines()[0] if text.strip() else "git refused"
        if line is None:
            line = f"not fast-forwarded: {why}"
        self.w.chantier("note", cr, f"main checkout: {line}")
        return line

    def worktree_check(self, session: str, cwd: Path | None = None) -> bool:
        """foreman.md's worktree check, before the epoch is claimed: in a linked worktree (`--git-dir`
        differs from `--git-common-dir`) take no CR and ask; else claim the epoch."""
        cwd = cwd or self.w.work
        git_dir, common = (
            (cwd / ln).resolve() for ln in self.w.sh("git", "rev-parse", "--git-dir",
                                                     "--git-common-dir", cwd=cwd).splitlines())
        if git_dir != common:
            self.ask(f"blocked {self.w.name} this session is in the worktree {cwd}; "
                     "start the Foreman on the main checkout")
            return False
        self.w.chantier("foreman", "set", session, "--epoch", self.epoch, cwd=cwd)
        return True

    def ask(self, text: str) -> None:
        self.asked.append(text)
        self.w.chantier("asks", "--", *text.split(" "))

    def ask_once(self, key: tuple, text: str) -> None:
        if key not in self.told:
            self.told.add(key)
            self.ask(text)

    def take(self, target: str, note_: str | None = None) -> int:
        """`take`, then the Driver (a scripted one) with the facts in its prompt. The id of the
        Driver that ended is cleared first, as the card says: `take` refuses a recorded one."""
        if target != "stack" and self.w.cr(target).get("agent"):
            self.w.chantier("agents", "set", target, "-", "--epoch", self.epoch)
        code, facts = self.w.chantier("take", target, "--epoch", self.epoch,
                                      *(["--note", note_] if note_ else []), expect=None)
        if code:
            return code
        self.facts = facts
        check_driver_skeleton(self.w, target, facts)
        self.started.append(f"{target} {note_}" if note_ else target)
        self.w.chantier("agents", "set", target, f"agent-{len(self.started)}",
                        "--epoch", self.epoch)
        if target != "stack":
            start_driver(self.w, target)
        return 0

    def remove_merged(self) -> None:
        """Before `pause`: the merged CRs' worktrees and branches, the Foreman's own hands."""
        for c in self.w.batch()["crs"]:
            if c["status"] != "merged":
                continue
            if Path(c["worktree"]).is_dir():
                self.git("worktree", "remove", c["worktree"])
            # the PR is merged (status above), the check the card asks for; -d would refuse
            # after a rebase or squash merge
            self.git("branch", "-D", c["branch"])

    def merge(self, c: dict) -> None:
        """What the user allowed the Foreman to merge: a release's fix under the grant, the
        release PR after `release go`. Done with the forge's CLI, recorded with `order merged`."""
        cr = c["id"]
        if c.get("kind") in ("release", "fix"):
            action = f"merge the {c['kind']} PR {c['pr']}"
            code, out = self.w.chantier("release", "go", cr, "--note", action, expect=None)
            if code == 5:
                self.ask_once((cr, "budget"), f"budget {out[0]}")
                return
            if code:
                self.ask_once((cr, "approval", c["pr"]), f"blocked {cr} approval: {action}")
                return
        code, err = merge_pr(self.w, c["pr"])
        if code:
            self.ask_once((cr, "refused", err), f"refused {cr} {err}")
            return
        if self.w.cr(cr).get("agent"):  # the Driver ended: its id is cleared, as the card asks
            self.w.chantier("agents", "set", cr, "-", "--epoch", self.epoch)
        self.w.chantier("order", "merged", cr, "--epoch", self.epoch)
        self.fast_forward(cr)
        self.ask(f"merged {cr} {c['pr']}")

    def do_order(self, d: dict, o: dict) -> bool:
        """The Foreman's part; False when the order stays pending until a Driver takes it."""
        c = next((x for x in d["crs"] if x["id"] == o["cr"]), None)
        rel = next((x for x in d["crs"] if x["id"] == o.get("fix_for")), None)
        if o["kind"] == "qa":  # the order stays pending until its QA driver ends
            if o["cr"] not in self.qa:
                self.qa.append(o["cr"])
            return False
        if o["kind"] == "drop" and c and c["status"] in LIVE:
            self.cancelled.append(c["id"])
            self.w.chantier("cancel", c["id"], "--epoch", self.epoch)
        elif o["kind"] == "note" and c and c["status"] in LIVE:
            self.messages.append(f"{c['id']} {o['note']}")
        elif o["kind"] == "approve" and c and c.get("kind") == "release" \
                and c["status"] == "ready":
            pass  # the word waits in the record for the Driver the merge starts: no take
        elif o["kind"] in ("note", "rounds", "approve", "grant") and c \
                and c["status"] in {"ready", "blocked"} \
                and not (c.get("blocked_reason") or "").startswith(("fix:", "merge:")):
            return False  # a Driver takes it with that note; the order is done then
        elif o["kind"] == "budget" and any(
                x["status"] == "blocked" and (x.get("blocked_reason") or "").startswith("budget")
                for x in d["crs"]):
            return False
        elif o["kind"] == "add" and rel and rel["status"] in LIVE:
            self.messages.append(f"{rel['id']} fix {d['crs'][-1]['id']}")
        self.w.chantier("order", "done", o["id"], "--epoch", self.epoch)
        return True

    def candidates(self, d: dict) -> list[tuple[dict, str | None, dict | None]]:
        """Who a free slot goes to, in order: a queued CR (with the note that says why it is
        back), then a ready or blocked CR a pending order sends back."""
        out = []
        pending = [o for o in d["orders"] if not o["done"]]
        for c in sorted(d["crs"], key=lambda c: c["order"]):
            reason = c.get("blocked_reason") or ""
            if c["status"] == "queued":
                last = next((n for n in reversed(c.get("notes") or [])
                             if not n.startswith(("main checkout:", "wait:"))), "")
                out.append((c, last if last.startswith(BACK_NOTES) else None, None))
            elif c["status"] == "blocked" and reason.startswith("fix:"):
                fixes = [x for x in d["crs"] if x.get("fix_for") == c["id"]]
                if fixes and all(x["status"] == "merged" for x in fixes):
                    out.append((c, f"fix merged: {reason}", None))
            elif c["status"] in {"ready", "blocked"}:
                o = next((o for o in pending if o["cr"] == c["id"]
                          and o["kind"] in ("note", "rounds", "approve", "grant")), None)
                if o is None and reason.startswith("budget"):
                    o = next((o for o in pending if o["kind"] == "budget"), None)
                if o and o["kind"] == "approve" and c.get("kind") == "release" \
                        and c["status"] == "ready":
                    o = None  # done at once by do_order, never a take
                if o and not reason.startswith(("fix:", "merge:")):
                    out.append((c, f"{o['kind']}: {o['note']}", o))
        return out

    def turn(self) -> None:
        d = self.w.batch()
        merged = [o for o in d["orders"] if not o["done"] and o["kind"] == "merged"]
        if merged:  # the user's merges: one attempt after the last, before any `order done`
            self.fast_forward(merged[-1]["cr"])
        elif d["status"] == "paused" and not self.paused and d["crs"] \
                and all(c["status"] in ENDED for c in d["crs"]):
            # the CLI paused the batch at the last merge, which it recorded as done: the last
            # merge's fast-forward still runs, on the paused batch
            last = [c for c in d["crs"] if c["status"] == "merged"
                    and not any(n.startswith("main checkout:") for n in c.get("notes", []))]
            if last:
                self.fast_forward(max(last, key=lambda c: c["merged_at"] or "")["id"])
        for o in d["orders"]:
            if not o["done"]:
                self.do_order(d, o)
        d = self.w.batch()
        for c in sorted(d["crs"], key=lambda c: c["order"]):
            reason = c.get("blocked_reason") or ""
            if c["status"] == "blocked":
                if c.get("kind") == "release" and reason.startswith("merge:"):
                    self.merge(c)  # what the user allowed
                    continue
                self.ask_once((c["id"], "blocked", reason), f"blocked {c['id']} {reason}")
            elif c["status"] == "ready":
                grant = d.get("release") or {}
                if (c.get("kind") == "release" and c.get("pr")
                        and grant.get("autonomous", 0) > grant.get("published", 0)):
                    self.merge(c)  # the release PR's merge, only under the grant
                    continue
                if (c["id"], "ready", c.get("pr")) in self.told:
                    continue
                self.told.add((c["id"], "ready", c.get("pr")))
                if c.get("kind") == "fix" and (d.get("release") or {}).get("fixes"):
                    self.merge(c)
                else:
                    word = "ready-to-merge" if c.get("pr_draft") is False else "pr-in-draft"
                    self.ask(f"{word} {c['id']} {c['pr']}")
                    if d["mode"] == "parallel":
                        self.early_conflicts(d, c)
        d = self.w.batch()
        # a slot is a running Driver: a CR working, or a QA order not done
        live = sum(c["status"] in LIVE for c in d["crs"]) \
            + sum(o["kind"] == "qa" and not o["done"] for o in d["orders"])
        for c, note_, o in self.candidates(d):
            if live >= d["slots"]:
                break
            code = self.take(c["id"], note_)
            if code == 0:
                live += 1
                if o:
                    self.w.chantier("order", "done", o["id"], "--epoch", self.epoch)
            elif code == 5:
                self.ask(f"budget {self.w.last_stderr}")
                break
            elif c.get("kind") != "release":
                self.ask(f"refused {c['id']} {self.w.last_stderr}")
        d = self.w.batch()
        if d["crs"] and all(c["status"] in ENDED for c in d["crs"]) \
                and all(o["done"] for o in d["orders"]):
            if d["status"] == "paused":  # the CLI paused it at the last end and cleaned
                self.paused = True
            else:  # the CLI did not (its line says what blocked): the Foreman's own pause
                self.remove_merged()
                self.w.chantier("pause", "--epoch", self.epoch)
                self.paused = True

    def early_conflicts(self, d: dict, c: dict) -> None:
        """foreman.md, "An early conflict check (parallel batch)": the new ready CR against each
        other ready CR with an open PR, by `git merge-tree` only; one note per conflicting pair,
        one ask for the hand-back; a pair already noted is left out."""
        by_id = {cr["id"]: cr for cr in d["crs"]}

        def pair_noted(a: str, b: str) -> bool:
            return any(n.startswith(f"early conflict: with {y}:")
                       for x, y in ((a, b), (b, a)) for n in by_id[x].get("notes", []))

        hits: list[tuple[str, list[str]]] = []
        for o in sorted(d["crs"], key=lambda o: o["order"]):
            if (o["id"] == c["id"] or o["status"] != "ready" or not o.get("pr")
                    or c["id"] in o.get("after", []) or o["id"] in c.get("after", [])
                    or pair_noted(c["id"], o["id"])):
                continue
            p = self.git("merge-tree", "--write-tree", "--name-only", "--no-messages",
                         c["branch"], o["branch"])
            if p.returncode == 1:
                hits.append((o["id"], p.stdout.splitlines()[1:]))
            elif p.returncode:
                first = (p.stderr.strip().splitlines() or ["git refused"])[0]
                self.w.chantier("note", c["id"],
                                f"early conflict check: not run against {o['id']}: {first}")
        for other, paths in hits:
            shown = ", ".join(paths[:5]) + (f" and {len(paths) - 5} more" if len(paths) > 5 else "")
            self.w.chantier("note", c["id"], f"early conflict: with {other}: {shown}")
        if hits:
            self.ask(f"conflict {c['id']} with {', '.join(o for o, _ in hits)}: "
                     f"{', '.join(dict.fromkeys(p for _, ps in hits for p in ps))}; "
                     "switch to a stack?")

    def driver_died(self, cr: str) -> None:
        """A task ended with no hand-back: the facts say where it stood."""
        _, facts = self.w.chantier("handoff", cr)
        if self.w.cr(cr)["status"] in LIVE:
            self.take(cr, f"resume: {facts[0]}")


def start_driver(w: World, cr_id: str) -> None:
    """A Driver's first step: the worktree its prompt names, on the fresh base, or the one an
    earlier Driver left."""
    c = w.cr(cr_id)
    if Path(c["worktree"]).is_dir():
        return
    w.sh("git", "fetch", "--quiet", "origin", "main")
    Path(c["worktree"]).parent.mkdir(exist_ok=True)
    if w.sh("git", "branch", "--list", c["branch"]):
        w.sh("git", "worktree", "add", "--quiet", c["worktree"], c["branch"])
    else:
        w.sh("git", "worktree", "add", "--quiet", "-b", c["branch"], c["worktree"], "origin/main")


def commit(w: World, cr_id: str, filename: str, content: str, subject: str | None = None) -> None:
    """The Driver's own commit: explicit paths, a message by the project's guideline."""
    wt = Path(w.cr(cr_id)["worktree"])
    (wt / filename).write_text(content)
    msg = w.root / "commit-msg.txt"
    msg.write_text(f"{subject or f'{cr_id}: {filename}'}\n\n{TRAILER}\n")
    w.sh("git", "add", "--", filename, cwd=wt)
    w.sh("git", "commit", "--quiet", "-F", str(msg), cwd=wt)


def push(w: World, cr_id: str) -> None:
    """The Driver rebases on the fresh base and pushes with a lease."""
    c = w.cr(cr_id)
    wt = Path(c["worktree"])
    w.sh("git", "fetch", "--quiet", "origin", cwd=wt)
    w.sh("git", "rebase", "--quiet", "origin/main", cwd=wt)
    w.sh("git", "push", "--quiet", "--force-with-lease", "-u", "origin", c["branch"], cwd=wt)


def ship(w: World, cr_id: str, title: str, base: str = "main") -> None:
    """The Driver writes the PR body, pushes, opens or updates the PR itself, then records it.
    `base` is the branch a new PR targets: the CR under it, for a CR that carries its commits."""
    c = w.cr(cr_id)
    body = w.at(c["path"]) / "work" / "pr-body.md"
    body.parent.mkdir(exist_ok=True)
    push(w, cr_id)
    first = cr_id not in OPENED
    body.write_text(BODY.format(title=c["title"], cr=cr_id))
    link = OPENED.setdefault(cr_id, open_pr(w, cr_id, title, base) if first else c["pr"])
    w.chantier("ship", cr_id, link)


def driver_round(w: World, cr_id: str, filename: str, content: str, base: str = "main") -> None:
    """A round counted, a Coder's change, then the Driver's commit, long gate and ship."""
    w.chantier("round", cr_id, "--note", f"edit {filename}")
    commit(w, cr_id, filename, content)
    w.chantier("gate", cr_id, GATE)
    ship(w, cr_id, f"feat: {filename.removesuffix('.py')}", base)


def prepare_cr(w: World, title: str, priority: str = "P1") -> tuple[Path, Path]:
    _, out = w.chantier("file", title)
    inbox = w.work / out[0].removeprefix("filed ").split(";", 1)[0]
    (inbox / "01-intent.md").write_text(f"# {title}\n\nThe original request is in intake.\n")
    (inbox / "02-answers.md").write_text("# Decisions\n\nNo open questions.\n")
    (inbox / "03-change-spec.md").write_text(f"# {title}\n\nImplement {title}.\n")
    _, out = w.chantier("triage", inbox, "--priority", priority)
    backlog = w.work / out[0].removeprefix("triaged ").rsplit(" (", 1)[0]
    return inbox, backlog


def drop_then_cancel(w: World, cr: str, epoch: int, env=None) -> tuple[int, list[str]]:
    """The user's drop to the trash and the Foreman's `cancel` of it: `cancel` follows a drop
    order, which the Foreman marks done once the CR is cancelled (here before, so a last CR
    pauses the batch at the cancel)."""
    _, out = w.chantier("order", "drop", cr, "--note", "trash", env=env)
    order = re.search(r"order (O-\d+)", out[0]).group(1)
    w.chantier("order", "done", order, "--epoch", epoch, env=env)
    return w.chantier("cancel", cr, "--epoch", epoch, env=env)


def lease_cases(w: World) -> None:
    """Two Drivers hold a lease each (`take` gave CR-101 and CR-102 theirs). A stale number is
    `claim lost` and a missing one is refused, nothing recorded; a CI watch run under `lease hold`
    keeps CR-102's lease live past the shortened TTL (3 s), and it is not expired."""
    section("3a. Leases: a stale one, and a CI watch under `lease hold`")
    note("\n## 3a. Leases: a stale one, and a CI watch under `lease hold`")
    rounds = w.cr("CR-101")["round"]
    code, _ = w.chantier("round", "CR-101", "--lease", 9, expect=3)
    check("a stale lease: `round CR-101 --lease 9` exits 3 with `claim lost` and records nothing",
          code == 3 and "claim lost" in w.last_stderr and "stop now: nothing recorded" in w.last_stderr
          and w.cr("CR-101")["round"] == rounds, w.last_stderr)
    code, _ = w.chantier("round", "CR-101", lease=False, expect=2)
    check("a `round` with no lease is refused, naming the number `take` printed",
          code == 2 and "needs --lease" in w.last_stderr and w.cr("CR-101")["round"] == rounds,
          w.last_stderr)
    number, ttl = w.leases["CR-102"], {"CHANTIER_LEASE_TEST_TTL": "3"}
    watch, release = w.root / "ci_watch.py", w.root / "ci_watch.release"
    release.unlink(missing_ok=True)
    watch.write_text("import os, sys, time\nend = time.time() + 60\n"
                     "while not os.path.exists(sys.argv[1]) and time.time() < end:\n"
                     "    time.sleep(0.05)\n", encoding="utf-8")
    w.chantier("lease", "CR-102", "renew", "--lease", number, env=ttl)  # expires in 3 s
    proc = subprocess.Popen(
        [sys.executable, "-m", "chantier", "lease", "CR-102", "hold", "--lease", str(number), "--",
         sys.executable, str(watch), str(release)], cwd=w.work, env={**w.env, **ttl},
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8")
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline and not list(w.state.glob(".lease-hold.CR-102.*.run")):
        time.sleep(0.1)
    expires = w.cr("CR-102")["lease"]["expires"]
    over = datetime.strptime(expires, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    while datetime.now(timezone.utc) <= over + timedelta(seconds=1) and time.monotonic() < deadline:
        time.sleep(0.2)  # no longer than the TTL: the lease's own expiry passes while the watch runs
    code, out = w.chantier("lease", "CR-102")
    check("a CI watch under `lease hold` past the shortened TTL keeps the lease live, not "
          "expired, and `lease` says it is held",
          datetime.now(timezone.utc) > over and out and "live until" in out[0]
          and "held by 1 background task" in out[0] and "not confirmed" not in out[0], str(out))
    release.touch()
    _, err = proc.communicate(timeout=60)
    check("the held command ends: `lease hold` exits 0", proc.returncode == 0, err)
    w.chantier("lease", "CR-102", "renew", "--lease", number)  # the normal life again


def scenario(w: World) -> None:
    section("1. Setup and preflight")
    note("## 1. Setup and preflight")
    code, out = w.chantier("preflight", env={"CLAUDE_CODE_ENTRYPOINT": "claude-vscode",
                                             "CHANTIER_HOST": ""}, expect=2)
    check("preflight refuses Claude in VS Code (P1) and says to start nothing",
          code == 2 and out[0].startswith("P1 FAIL") and out[-1].endswith("start nothing"))
    home = w.root / "home"  # a home of its own: the developer's settings are not read
    homes = {"HOME": str(home), "USERPROFILE": str(home)}
    code, out = w.chantier("preflight", env=homes)
    check("preflight passes on Claude Desktop with no setup, and an in-project repository has no "
          "P14 line", code == 0 and out[-1] == "preflight passed"
          and not any(ln.startswith("P14") for ln in out), str(out))
    p5 = next((ln for ln in out if ln.startswith("P5")), "")
    check("preflight's P5 line holds the `--no-sync` and sync sentence on Windows only",
          ("dev mode on Windows: $CHANTIER runs --no-sync; sync with uv sync --locked --project "
           in p5) == (os.name == "nt"), p5)
    p10 = next((ln for ln in out if ln.startswith("P10")), "")
    check("preflight warns (P10) on the allow rules missing from the settings, names one, and "
          "still passes", p10.startswith("P10 warn")
          and "git push --force-with-lease -u origin chantier/*" in p10, p10)
    check("the P10 warning names no `release create` rule (a publication stays asked by the host)",
          "release create" not in p10, p10)
    sys.path.insert(0, str(SKILL / "scripts" / "cli" / "src"))
    from chantier.commands.allow_samples import filled_allow
    from chantier.launch import dev_rule, plugin_rule
    from chantier.plugin_files import is_dev_checkout

    (home / ".claude").mkdir(parents=True)
    user = ["git push --force-with-lease -u origin chantier/*",
            "git push --force-with-lease=chantier/* origin *chantier/*"]
    (home / ".claude" / "settings.json").write_text(
        json.dumps({"permissions": {"allow": [f"{t}({r})" for r in user
                                              for t in ("Bash", "PowerShell")]}}), encoding="utf-8")
    code, out = w.chantier("preflight", env=homes)
    p10 = next((ln for ln in out if ln.startswith("P10")), "")
    check("preflight (P10) judges equivalence: the user's own force-push forms are not named, the "
          "`-C` form still is", code == 0 and p10.startswith("P10 warn")
          and "add Bash(git push --force-with-lease" not in p10
          and "add Bash(git -C * push --force-with-lease -u origin chantier/*)" in p10, p10)
    if ARGS.forge == "github":  # P10 asks `gh extension list` (the fake `gh`, first on PATH)
        path_key = next(k for k in w.env if k.upper() == "PATH")
        fake_gh = {**homes, path_key: f"{w.fake.parent}{os.pathsep}{w.env[path_key]}"}

        def p10_line(**env: str) -> str:  # a stack: the capability that holds `gh stack view`
            _, lines = w.chantier("preflight", "--mode", "stack", env={**fake_gh, **env})
            return " | ".join(ln for ln in lines if ln.startswith("P10"))
        w.gh(extensions=["gh stack\tgithub/gh-stack\tv0.3.0"])
        check("preflight --mode stack (P10) names `gh stack view` when `gh extension list` names "
              "the extension",
              "gh stack view" in p10_line())
        w.gh(extensions=[])
        folder = w.root / "xdg" / "gh" / "extensions" / "gh-stack"
        folder.mkdir(parents=True)
        check("with no extension listed, P10 does not name `gh stack view`, a `gh-stack` folder "
              "does not count", "gh stack view" not in p10_line(XDG_DATA_HOME=str(w.root / "xdg"),
                                                                LOCALAPPDATA=str(w.root / "xdg")))
    (home / ".claude" / "settings.json").write_text(
        json.dumps({"permissions": {"allow": list(filled_allow())}}), encoding="utf-8")
    code, out = w.chantier("preflight", env=homes)
    check("preflight says P10 ok once the rules are in the home settings", code == 0
          and any(ln.startswith("P10 ok") for ln in out), str(out))
    code, out = w.chantier("preflight", "--autonomous-releases", "1", env=homes)
    rel = next((ln for ln in out if ln.startswith("P10 warn") and "release on its own" in ln), "")
    check("preflight --autonomous-releases 1 warns (P10) with the release rules and still passes",
          code == 0 and "gh release create*" in rel and "gh pr merge*" in rel
          and "gh api -X PUT repos/*/pulls/*/merge-async*" in rel
          and out[-1] == "preflight passed", rel)
    broad = ["uvx --from * chantier *", "uv run --no-sync --project * chantier *",
             "uv run --script * *"]
    (home / ".claude" / "settings.json").write_text(
        json.dumps({"permissions": {"allow": [f"Bash({r})" for r in broad]}}), encoding="utf-8")
    code, out = w.chantier("preflight", env=homes)
    p10 = next((ln for ln in out if ln.startswith("P10")), "")
    mine = {"uvx --from * chantier *": None if is_dev_checkout() else plugin_rule,
            "uv run --no-sync --project * chantier *": dev_rule if is_dev_checkout() else None,
            "uv run --script * *": None}
    root = SKILL.parents[1].resolve()
    check("preflight (P10) names a broad chantier rule as letting any command through, with its "
          "file, the real-path rule that replaces it only for the scenario's mode, and still "
          "passes", code == 0 and out[-1] == "preflight passed" and p10.startswith("P10 warn")
          and "broad rules let any command through" in p10
          and all(f"Bash({r}) (" in p10 and "settings.json" in p10 for r in broad)
          and all(f"replaced by Bash({fn(root)})" in p10 for fn in mine.values() if fn)
          and p10.count("no chantier command needs it") == sum(fn is None for fn in mine.values()),
          p10)
    check("nothing was written in the working tree", w.sh("git", "status", "--porcelain") == "")
    _, out = w.chantier("rules")
    check("`rules` lists the project's instructions and what they link, with line counts",
          out[0].startswith((w.work / "AGENTS.md").as_posix()) and "lines)" in out[0]
          and out[1].startswith((w.work / "CONTRIBUTING.md").as_posix()), str(out))

    section("2. The Chief of Staff opens the batch and starts the Foreman")
    note("\n## 2. The Chief of Staff opens the batch and starts the Foreman")
    items = [prepare_cr(w, title) for title in
             ("Fix login timeout", "Add CSV export", "Dark mode", "Audit log")]
    code, _ = w.chantier("open", "Fix login", *FROM_AGENTS_MD, expect=1)
    check("a raw title cannot bypass the prepared CR", code == 1 and items[0][1].is_dir())
    _, spare = prepare_cr(w, "Spare item", "P2")
    _, out = w.chantier("triage", spare, "--priority", "P3")
    moved = spare.parent.parent / "P3" / spare.name
    check("`triage` moves a backlog item to the new priority",
          out[0].endswith("(P3)") and moved.is_dir() and not spare.exists(), str(out))
    code, _ = w.chantier("triage", moved, "--priority", "P3", expect=2)
    check("`triage` to the same priority is refused: already P3",
          "already P3" in w.last_stderr, w.last_stderr)
    code, _ = w.chantier("triage", w.state / "STATUS.md", "--priority", "P1", expect=1)
    check("`triage` of another path says what it expects", "2-backlog/P<n>/<item>" in w.last_stderr,
          w.last_stderr)
    w.chantier("abandon", moved)
    w.chantier("file", "Spare item twice")
    code, _ = w.chantier("file", "Spare item twice", expect=2)
    check("`file` of an existing slug exits 2 and names `--slug`", "--slug" in w.last_stderr,
          w.last_stderr)
    w.chantier("abandon", w.work / ".agents/changes/1-inbox/spare-item-twice")
    _, out = w.start(*(str(backlog) for _, backlog in items),
                     "--slots", 2, "--budget", 50, *FROM_AGENTS_MD)
    check("`open` says what comes next, then where each folder moved",
          out[1].startswith("next:") and "2-backlog/P1/" in out[2] and "-> 4-batch/1-pending/" in out[2],
          str(out))
    check("the batch is numbered, has no name, and `--batch` takes the number",
          w.name == "batch-01" and (w.folder() / "batch.json").is_file()
          and w.chantier("status", "--batch", "1")[0] == 0
          and w.chantier("status", "--batch", "batch-01")[0] == 0, w.name)
    opened_record(w)
    _, first = w.chantier("status")
    check("`status` prints the last closed batch on its second line: none yet",
          len(first) > 1 and first[1] == "last closed: none", str(first[:2]))
    board = (w.state / "STATUS.md").read_text(encoding="utf-8")
    batch_report = (w.folder() / "STATUS.md").read_text(encoding="utf-8")
    check("a spend not priced yet is unknown, never $0.00: `status`, the batch's STATUS.md and the board",
          w.batch()["spent_usd"] is None and "spent unknown" in first[0] and "spent $0.00" not in first[0]
          and "spent unknown" in batch_report and "spent $0.00" not in batch_report
          and "unknown" in board and "$0.00" not in board, f"{first[0]}\n{batch_report}\n{board}")
    w.chantier("foreman", "set", "local_foreman1", "--epoch", 1)
    fm = Foreman(w, epoch=1)
    w.chantier("foreman", "transcript", "uuid-foreman", "--epoch", 1)
    d = w.batch()
    check("four CRs, each with a branch and a worktree named, none created: the CLI changes "
          "nothing in git",
          len(d["crs"]) == 4 and all(c["branch"].startswith(f"chantier/{w.name}/cr-10")
                                     and not Path(c["worktree"]).exists() for c in d["crs"]))
    code, _ = w.chantier("gate", "CR-103", GATE, expect=2)
    check("a command that needs the worktree says who creates it",
          code == 2 and "its Driver creates it" in w.last_stderr, w.last_stderr)
    check("opening moves the entire prepared folders into 1-pending",
          all(not backlog.exists() for _, backlog in items)
          and all("4-batch/1-pending/" in c["path"]
                  and (w.state / c["path"] / "intake/request.md").is_file()
                  and (w.state / c["path"] / "03-change-spec.md").is_file() for c in d["crs"]))
    fm.turn()
    check("the Foreman gives two CRs to Drivers (two slots)", fm.started == ["CR-101", "CR-102"])
    check("each Driver created its worktree and branch on the fresh default branch",
          all(Path(w.cr(x)["worktree"]).is_dir() and w.sh("git", "rev-parse", "HEAD", cwd=Path(
              w.cr(x)["worktree"])) == w.sh("git", "rev-parse", "origin/main")
              for x in ("CR-101", "CR-102")) and not Path(w.cr("CR-103")["worktree"]).exists())
    check("`take` prints the facts for the prompt: the CLI, the cards, the base, the rounds",
          any(ln.startswith("cli: uv run --no-sync --project ") for ln in fm.facts)
          and any(ln.startswith("cards: ") and "references/" in ln for ln in fm.facts)
          and any("base origin/main" in ln for ln in fm.facts)
          and any(ln == "rounds: 0 of 3" for ln in fm.facts), str(fm.facts))
    vi = next((i for i, ln in enumerate(fm.facts)
               if ln.startswith("verifier prompt, opening lines")), -1)
    check("`take` prints the Verifier's opening lines: the first line and the card's `Read` line "
          "(the scripted Driver builds no worker prompt, so it copies none)",
          vi >= 0 and fm.facts[vi + 1].startswith("  chantier verifier for CR-10")
          and "references/verifier.md;" in fm.facts[vi + 2]
          and fm.facts[vi + 2].startswith("  Read "), str(fm.facts))
    check_worker_writes_line(w, fm.started[-1], fm.facts, "take " + fm.started[-1])
    code, _ = w.chantier("take", "CR-103", "--epoch", 1, expect=2)
    check("a third Driver is refused: no free slot", code == 2 and "no free slot" in w.last_stderr)
    check("a taken CR is working", w.cr("CR-101")["status"] == "working")
    _, added = prepare_cr(w, "Waits in the backlog", "P3")
    board = (w.state / "STATUS.md").read_text(encoding="utf-8")
    check("the board shows the open batch and what `triage` just moved",
          f"[{w.name}](4-batch/STATUS.md)" in board and "Fix login timeout" in board
          and "| P3 |" in board and "Waits in the backlog" in board, board)

    section("3. CR-101: one round, the Driver's own push and PR, hand-back")
    note("\n## 3. CR-101: one round, the Driver's own push and PR, hand-back")
    _, out = w.chantier("round", "CR-101", "--note", "round 1")
    check("`round` counts the round and prints the facts", w.cr("CR-101")["round"] == 1
          and out[0] == "round 1 of 3 for CR-101" and any(ln == "rounds: 1 of 3" for ln in out),
          str(out))
    check_worker_writes_line(w, "CR-101", out, "round CR-101")
    lease_cases(w)
    sheet = lambda cr: json.loads((w.at(w.cr(cr)["path"]) / "STATUS.json").read_text(encoding="utf-8"))
    row = lambda cr: next(r for r in json.loads((w.folder() / "STATUS.json").read_text(
        encoding="utf-8"))["crs"] if r["cr"] == cr)
    check("`round` records the step `coder r1`: the CR's STATUS.json and its batch row say it",
          w.cr("CR-101")["phase"] == "coder" and sheet("CR-101")["phase"] == "coder r1"
          and row("CR-101")["phase"] == "coder r1")
    code, out = w.chantier("phase", "CR-101", "inspector")
    check("`phase` records the inspector's step and prints `ok` and the context line",
          code == 0 and out[0] == "ok" and out[1].startswith("context: ")
          and sheet("CR-101")["phase"] == "inspector r1", str(out))
    w.chantier("phase", "CR-101", "gate", "scenario")
    _, status = w.chantier("status")
    check("`phase gate scenario` shows in the CR's STATUS.json, `chantier status` and the batch's "
          "STATUS.md Step cell",
          sheet("CR-101")["phase"] == "gate scenario" and sheet("CR-101")["phase_at"]
          and any(ln.startswith("CR-101 ") and "| step: gate scenario" in ln for ln in status)
          and "| gate scenario |" in (w.folder() / "STATUS.md").read_text(encoding="utf-8")
          and "**Step:** gate scenario" in (w.at(w.cr("CR-101")["path"]) / "STATUS.md").read_text(
              encoding="utf-8"), str(status))
    events = [json.loads(ln) for ln in (w.folder() / "events.jsonl").read_text(
        encoding="utf-8").splitlines() if ln.strip()]
    check("the event `phase` is in `events.jsonl` and not in the CR's Progress steps",
          any(e["kind"] == "phase" and e["cr"] == "CR-101" and e["phase"] == "gate"
              and e["note"] == "scenario" for e in events)
          and not any("hase" in s["name"] for s in sheet("CR-101")["steps"]))
    code, _ = w.chantier("handback", "CR-101", "ready", "done", expect=2)
    check("no hand-back ready before a PR is recorded", code == 2 and "PR recorded" in w.last_stderr)
    wt = Path(w.cr("CR-101")["worktree"])
    commit(w, "CR-101", "login.py", "TIMEOUT_S = 30\n")
    code, out = w.chantier("gate", "CR-101", GATE)
    check("the long gate runs the project's command in the worktree and records the head",
          code == 0 and out[0].startswith(f"pass {GATE} at ") and out[1].startswith("log "), str(out))
    ship(w, "CR-101", "feat: login")
    check("`ship` records the Driver's PR with its head, and nothing off",
          w.cr("CR-101")["pr"].startswith(PR_LINK[ARGS.forge]) and w.cr("CR-101")["head"]
          and len(w.last_out) == 1, str(w.last_out))
    (wt / "login.py").write_text("TIMEOUT_S = 31\n")
    _, out = w.chantier("ship", "CR-101", w.cr("CR-101")["pr"])
    check("`ship` reports an uncommitted change the PR does not hold",
          any(ln.startswith("off: uncommitted changes") and "login.py" in ln for ln in out), str(out))
    (wt / "login.py").write_text("TIMEOUT_S = 30\n")
    code, _ = w.chantier("ship", "CR-101", "not a link", expect=1)
    check("the PR link is the forge's", code == 1)
    pr101 = w.cr("CR-101")["pr"]
    _, out = w.ready("CR-101", pr101)
    check("a hand-back writes the state and prints the line to send",
          out[0] == f"[driver CR-101→foreman] hand-back ready to merge {pr101}"
          and w.cr("CR-101")["status"] == "ready", str(out))
    check("after `handback ready` the step is null", sheet("CR-101")["phase"] is None
          and row("CR-101")["phase"] is None and "phase" not in w.cr("CR-101"))
    fm.turn()
    check("hand-back frees a slot: CR-103 taken", fm.started[-1] == "CR-103")
    check("the Chief of Staff is told CR-101 is ready with its PR",
          fm.asked[-1] == f"ready-to-merge CR-101 {pr101}")
    fm.turn()
    check("a second turn with nothing new does nothing", fm.started[-1] == "CR-103"
          and fm.asked[-1] == f"ready-to-merge CR-101 {pr101}")
    code, _ = w.chantier("handback", "CR-101", "ready", pr101, expect=2)
    check("a CR without a Driver cannot be handed back", code == 2)
    code, _ = w.chantier("round", "CR-101", expect=2)
    check("a CR without a Driver runs no round", code == 2)

    section("4. CR-102: two rounds")
    note("\n## 4. CR-102: two rounds")
    driver_round(w, "CR-102", "export.py", "def export():\n    return 'csv'\n")
    w.chantier("note", "CR-102", "CI red: the product; export header missing")
    driver_round(w, "CR-102", "export.py", "def export():\n    return 'id,name\\n'\n")
    w.ready("CR-102", w.cr("CR-102")["pr"])
    fm.turn()
    check("a second ready CR goes to the Chief of Staff",
          fm.asked[-1].startswith(f"ready-to-merge CR-102 {PR_LINK[ARGS.forge]}"))
    check("no conflict, no ask: merge-tree ran for CR-102 against CR-101, no `conflict` ask and "
          "no `early conflict:` note",
          any(g[0] == "merge-tree" and g[-2:] == (w.cr("CR-102")["branch"], w.cr("CR-101")["branch"])
              for g in fm.git_main)
          and not any(a.startswith("conflict ") for a in fm.asked)
          and not any(n.startswith("early conflict:") for c in w.batch()["crs"]
                      for n in c.get("notes", [])), str(fm.asked))

    section("5. Steering: the user drops CR-103, adds an item, changes CR-101")
    note("\n## 5. Steering: the user drops CR-103, adds an item, changes CR-101")
    _, out = w.chantier("order", "drop", "CR-103", "--note", "trash")
    check("`chantier order` prints the message with an order id, and what it did",
          out[0] == "[chief-of-staff→foreman] order O-1: drop CR-103 6-trash"
          and "live" in out[1], str(out))
    # Windows finds a process by its command line only, so the sleeper names its worktree
    wt103 = w.cr("CR-103")["worktree"]
    sleeper = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(300)", wt103],
                               cwd=wt103)
    fm.turn()
    deadline = time.monotonic() + 5
    while sleeper.poll() is None and time.monotonic() < deadline:
        time.sleep(0.05)
    check("dropping a live CR cancels it and stops its processes",
          fm.cancelled == ["CR-103"] and sleeper.poll() is not None
          and w.cr("CR-103")["status"] == "cancelled")
    check("a dropped CR goes to the trash with its work, under the date",
          re.search(r"6-trash/\d{6}-\d{4}-103-", w.cr("CR-103")["path"])
          and (w.state / w.cr("CR-103")["path"] / "02-answers.md").is_file()
          and "⚪ dropped" in (w.state / w.cr("CR-103")["path"] / "STATUS.md").read_text("utf-8"))
    check("the freed slot goes to CR-104", "CR-104" in fm.started)
    _, out = w.chantier("order", "done", "O-1", "--epoch", 1)
    check("an order read twice is done once", out == ["O-1 already done"])
    _, added = prepare_cr(w, "Rate limit the login endpoint")
    _, out = w.chantier("order", "add", "--note", str(added))
    check("an added item becomes CR-105 at once", out[1] == "added CR-105, queued", str(out))
    fm.turn()
    check("CR-105 has a worktree and takes the second free slot",
          fm.started[-1] == "CR-105" and w.cr("CR-105")["status"] == "working"
          and Path(w.cr("CR-105")["worktree"]).is_dir())
    _, out = w.chantier("order", "note", "CR-101", "--note", "change: also log the timeout")
    check("a note on a ready CR is recorded; the CR stays ready for the Foreman to decide",
          w.cr("CR-101")["status"] == "ready" and w.cr("CR-101")["notes"][-1]
          == "change: also log the timeout", str(out))
    _, out = w.chantier("status")
    check("status shows the pending order", any(ln.startswith("orders pending: O-") and "note CR-101"
                                                in ln for ln in out), str(out))
    w.chantier("agents", "set", "CR-101", "-", "--epoch", 1)  # its Driver ended with the hand-back
    code, _ = w.chantier("take", "CR-101", "--note", "change", "--epoch", 1, expect=2)
    check("it waits for a slot", code == 2 and "no free slot" in w.last_stderr)
    fm.turn()
    check("the Foreman keeps the order pending while no slot is free",
          not all(o["done"] for o in w.batch()["orders"]))

    section("6. A Foreman restart: the old one is refused")
    note("\n## 6. A Foreman restart: the old one is refused")
    w.chantier("foreman", "set", "local_foreman2", "--epoch", 2)
    w.chantier("foreman", "transcript", "uuid-foreman", "--epoch", 2)
    code, _ = w.chantier("status", "--refresh", "--epoch", 1, expect=3)
    check("a stale Foreman (epoch 1) is refused with exit 3, in the Foreman's number and not "
          "in the word epoch", code == 3 and "Foreman n°1" in w.last_stderr
          and "Foreman n°2" in w.last_stderr and " epoch " not in w.last_stderr, w.last_stderr)
    code, _ = w.chantier("foreman", "set", "local_second", "--epoch", 2, expect=3)
    check("a second session cannot claim an epoch already claimed (exit 3)",
          code == 3 and w.batch()["foreman"] == "local_foreman2")
    fm.epoch = 2

    section("7. CR-104 is lost, then hands back; CR-105 and CR-101 run")
    note("\n## 7. CR-104 is lost, then hands back; CR-105 and CR-101 run")
    w.chantier("phase", "CR-104", "ci")
    check("`phase ci` reads `CI`", w.cr("CR-104")["phase"] == "ci"
          and json.loads((w.at(w.cr("CR-104")["path"]) / "STATUS.json").read_text(
              encoding="utf-8"))["phase"] == "CI")
    fm.driver_died("CR-104")
    check("a `take` clears the step", "phase" not in w.cr("CR-104"))
    check("a Driver that ends without a hand-back is replaced from the facts",
          fm.started[-1].startswith("CR-104 resume: CR-104 \"Audit log\" (change) working"),
          fm.started[-1])
    driver_round(w, "CR-104", "audit.py", "AUDIT = []\n")
    w.ready("CR-104", w.cr("CR-104")["pr"])
    driver_round(w, "CR-105", "ratelimit.py", "LIMIT = 10\n")
    w.ready("CR-105", w.cr("CR-105")["pr"])
    fm.turn()
    check("the change on CR-101 reaches a new Driver, with the note, and the order is done",
          fm.started[-1] == "CR-101 note: change: also log the timeout"
          and all(o["done"] for o in w.batch()["orders"]), str(fm.started))
    w.ready("CR-101", pr101)
    fm.turn()
    _, out = w.chantier("status")
    check("status shows every CR", all(f"CR-10{i}" in "\n".join(out) for i in range(1, 6)))
    _, out = w.chantier("log", "CR-104")
    check("`log` tells a CR's story", any(" take " in ln for ln in out)
          and any(" round " in ln for ln in out) and any(" ship " in ln for ln in out)
          and any(" handback " in ln for ln in out), str(out))
    status_files(w)
    trashed = w.cr("CR-103")["path"]
    w.chantier("cancel", "CR-103", "--epoch", 2)
    check("a second cancel leaves the trashed CR where it is", w.cr("CR-103")["path"] == trashed)

    section("8. The user merges; the Foreman cleans up and pauses the batch")
    note("\n## 8. The user merges; the Foreman cleans up and pauses the batch")
    code, _ = w.chantier("pause", "--epoch", 2, expect=2)
    check("pause is refused while PRs are not merged", code == 2 and w.batch()["status"] == "running")
    fake_transcripts(w, w.batch())
    orders = len(w.batch()["orders"])
    local = w.work / "local-notes.txt"  # the user's own untracked file
    local.write_text("mine\n")
    planning = sorted(p.relative_to(w.work).as_posix() for p in (w.work / ".agents").rglob("*")
                      if p.is_file() and "4-batch" not in p.parts)
    head0 = w.sh("git", "rev-parse", "HEAD")
    land(w, w.cr("CR-101")["branch"])  # the user's merge reaches origin; nothing is moved yet
    check("the user's merge landed on origin by rebase, through no forge call, and the main "
          "checkout has not moved by itself",
          w.sh("git", "rev-parse", "origin/main") == head0
          and w.sh("git", "rev-parse", "HEAD") == head0
          and w.sh("git", "ls-remote", "origin", "refs/heads/main").split()[0] != head0)
    _, out = w.chantier("order", "merged", "CR-101")
    check("`order merged` moves the CR to 3-done at once and records the time",
          w.cr("CR-101")["status"] == "merged" and "4-batch/3-done/" in w.cr("CR-101")["path"]
          and (w.state / w.cr("CR-101")["path"] / "03-change-spec.md").is_file()
          and re.fullmatch(r"20\d\d-\d\d-\d\dT\d\d:\d\d:\d\dZ", w.cr("CR-101")["merged_at"]),
          str(out))
    fm.turn()
    remote = w.sh("git", "ls-remote", "origin", "refs/heads/main").split()[0]
    check("fast-forward done: the main checkout is at origin/main, with the file CR-101 added, "
          "the user's untracked file and the untracked planning folder intact, and the note says so",
          w.sh("git", "rev-parse", "HEAD") == remote == w.sh("git", "rev-parse", "origin/main")
          and (w.work / "login.py").read_text() == "TIMEOUT_S = 30\n"
          and local.read_text() == "mine\n"
          and planning == sorted(p.relative_to(w.work).as_posix()
                                 for p in (w.work / ".agents").rglob("*")
                                 if p.is_file() and "4-batch" not in p.parts)
          and w.cr("CR-101")["notes"][-1] == f"main checkout: fast-forwarded to {remote[:7]}",
          str(w.cr("CR-101")["notes"][-3:]))

    # CR-102: a tracked file of the main checkout is changed, the fast-forward is refused
    land(w, w.cr("CR-102")["branch"])
    head1 = w.sh("git", "rev-parse", "HEAD")
    (w.work / "app.py").write_text("def login():\n    return False  # the user's edit\n")
    w.chantier("order", "merged", "CR-102")
    fm.turn()
    check("refused on a tracked change: HEAD has not moved, the change is kept, the note says why",
          w.sh("git", "rev-parse", "HEAD") == head1
          and "the user's edit" in (w.work / "app.py").read_text()
          and not (w.work / "export.py").exists()
          and w.cr("CR-102")["notes"][-1] == "main checkout: not fast-forwarded: tracked changes: app.py",
          str(w.cr("CR-102")["notes"][-2:]))
    w.sh("git", "checkout", "--quiet", "--", "app.py")  # the user undoes the change

    # CR-104: it tries again at the next merge and catches up
    land(w, w.cr("CR-104")["branch"])
    w.chantier("order", "merged", "CR-104")
    fm.turn()
    remote = w.sh("git", "ls-remote", "origin", "refs/heads/main").split()[0]
    check("the next merge tries again: the checkout catches up with origin/main, CR-102's file included",
          w.sh("git", "rev-parse", "HEAD") == remote and (w.work / "export.py").is_file()
          and (w.work / "audit.py").is_file()
          and w.cr("CR-104")["notes"][-1] == f"main checkout: fast-forwarded to {remote[:7]}",
          str(w.cr("CR-104")["notes"][-2:]))

    # CR-105: an untracked file is in the way, the fast-forward is refused and the file kept
    (w.work / "ratelimit.py").write_text("MINE = True\n")
    land(w, w.cr("CR-105")["branch"])
    head2 = w.sh("git", "rev-parse", "HEAD")
    for cr_id in ("CR-101", "CR-102", "CR-104", "CR-105"):  # each Driver ended: its id is cleared
        if w.cr(cr_id).get("agent"):
            w.chantier("agents", "set", cr_id, "-", "--epoch", fm.epoch)
    leftover = Path(w.cr("CR-101")["worktree"]) / "wip.txt"  # git refuses to remove this worktree
    leftover.write_text("uncommitted\n")
    _, last_out = w.chantier("order", "merged", "CR-105")
    d = w.batch()
    check("the last `order merged` pauses the batch, and prints the cleanup and the pause",
          d["status"] == "paused" and d["paused"] and all(o["done"] for o in d["orders"])
          and any(ln.startswith("paused batch-") for ln in last_out)
          and not any("pause --epoch" in ln and "not paused" in ln for ln in last_out)
          and any(ln.startswith("next: the retro") for ln in last_out), str(last_out))
    check("it removed the merged worktrees and branches; the cancelled one stays, and the one "
          "with an uncommitted file is kept with its branch, a `not removed` line saying so",
          all(Path(c["worktree"]).exists() == (c["status"] == "cancelled" or c["id"] == "CR-101")
              for c in d["crs"])
          and not any(w.sh("git", "branch", "--list", c["branch"]) for c in d["crs"]
                      if c["status"] == "merged" and c["id"] != "CR-101")
          and w.sh("git", "branch", "--list", w.cr("CR-101")["branch"])
          and any(ln.startswith("cleanup: CR-101 worktree") and "not removed:" in ln
                  for ln in last_out)
          and any(ln.startswith("kept: remove them") for ln in last_out), str(last_out))
    fm.turn()
    check("refused with an untracked file in the way: HEAD has not moved, the file is intact, "
          "the note names it",
          w.sh("git", "rev-parse", "HEAD") == head2
          and (w.work / "ratelimit.py").read_text() == "MINE = True\n"
          and w.cr("CR-105")["notes"][-1]
          == "main checkout: not fast-forwarded: untracked file in the way: ratelimit.py",
          str(w.cr("CR-105")["notes"][-2:]))
    (w.work / "ratelimit.py").unlink()
    fm.fast_forward("CR-105")
    check("with the file gone, the next attempt fast-forwards",
          w.sh("git", "rev-parse", "HEAD") == w.sh("git", "ls-remote", "origin",
                                                  "refs/heads/main").split()[0]
          and (w.work / "ratelimit.py").is_file(), str(w.cr("CR-105")["notes"][-2:]))
    # the same, with a file ignored by the project's own exclude list
    (w.work / ".git" / "info" / "exclude").write_text("kept.cache\n")
    (w.work / "kept.cache").write_text("mine too\n")
    land(w, "", extra=("kept.cache", "theirs\n"))
    head3 = w.sh("git", "rev-parse", "HEAD")
    fm.fast_forward("CR-105")
    check("refused with an ignored file in the way (`--no-overwrite-ignore`): HEAD has not moved, "
          "the file is intact, the note names it",
          w.sh("git", "rev-parse", "HEAD") == head3
          and (w.work / "kept.cache").read_text() == "mine too\n"
          and w.cr("CR-105")["notes"][-1]
          == "main checkout: not fast-forwarded: untracked file in the way: kept.cache",
          str(w.cr("CR-105")["notes"][-2:]))
    (w.work / "kept.cache").unlink()
    (w.work / ".git" / "info" / "exclude").write_text("")
    fm.fast_forward("CR-105")
    check("the Foreman's git in the main checkout is only symbolic-ref, status, fetch, "
          "`merge --ff-only --no-overwrite-ignore`, rev-parse, worktree remove, branch -D and "
          "`merge-tree --write-tree`",
          all(g[0] in {"symbolic-ref", "status", "fetch", "rev-parse", "worktree", "branch"}
              or g[:3] == ("merge", "--ff-only", "--no-overwrite-ignore")
              or g[:2] == ("merge-tree", "--write-tree") for g in fm.git_main)
          and any(g[0] == "merge" for g in fm.git_main), str(sorted({g[0] for g in fm.git_main})))
    local.unlink()
    check("the Foreman saw the CLI's pause", fm.paused)
    d = w.batch()
    check("merged CR folders wait intact in 3-done until the close",
          all(re.search(r"4-batch/3-done/\d{3}-", c["path"])
              and (w.state / c["path"] / "03-change-spec.md").is_file()
              and (w.state / c["path"] / "STATUS.md").is_file()
              and (w.state / c["path"] / "STATUS.json").is_file()
              for c in d["crs"] if c["status"] == "merged"))
    report = (w.folder() / "STATUS.md").read_text(encoding="utf-8")
    check("the batch's STATUS.md, once paused, lists every CR",
          "paused" in report and all(c["id"].removeprefix("CR-") in report for c in d["crs"]))
    board_index(w, d)
    prs = {c["id"]: c["pr"] for c in d["crs"] if c["pr"]}
    check("four PRs were opened on the fake forge by the Drivers", len(set(prs.values())) == 4)

    section("9. Cost")
    note("\n## 9. Cost")
    code, out = w.chantier("cost", "--by", "cr", "--batch", w.name)
    check("Claude cost prices the Foreman and each Driver",
          code == 0 and out[:2] == [f"{w.name}: $1.608 over 94 model calls",
                                    "foreman: $0.391 (30 calls)"]
          and sorted(l.split(";")[0] for l in out[2:-3])
          == [f"CR-10{i}: $0.304 (16 calls" for i in (1, 2, 4, 5)], str(out))
    check(
        "the batch's spend is priced and stored",
        abs(w.batch()["spent_usd"] - 1.608) < 0.001,
        str(w.batch().get("spent_usd")),
    )
    w.chantier("status", "--refresh", "--batch", w.name)
    _, priced = w.chantier("status", "--batch", w.name)
    unnamed = {"CHANTIER_BATCH": ""}
    paused = w.batch()["status"] == "paused"
    for form in (("--by", "cr"), ("--explain",)):
        _, named = w.chantier("cost", *form, "--batch", w.name)
        code, bare = w.chantier("cost", *form, env=unnamed, expect=None)
        check(f"the only paused batch is read by `cost {' '.join(form)}` with no --batch",
              paused and code == 0 and bare[:2] == named[:2], f"{code} {bare[:2]} {named[:2]}")
    code, _ = w.chantier("status", env=unnamed, expect=None)
    check("the only paused batch is read by `status` with no --batch", paused and code == 0, str(code))
    code, _ = w.chantier("asks", env=unnamed, expect=None)
    check("a command that writes refuses a paused batch by name, with `--batch <name>` and no `open`",
          paused and code != 0 and f"--batch {w.name}" in w.last_stderr
          and "chantier open" not in w.last_stderr, w.last_stderr)
    batch_report = (w.folder() / "STATUS.md").read_text(encoding="utf-8")
    board = (w.state / "STATUS.md").read_text(encoding="utf-8")
    check("once the spend is priced, `status`, the batch's STATUS.md and the board show a dollar figure",
          re.search(r"spent \$\d+\.\d\d", priced[0]) and re.search(r"spent \$\d+\.\d\d", batch_report)
          and re.search(r"\$\d+\.\d\d of \$50", board), f"{priced[0]}\n{batch_report}\n{board}")

    section("11. Event log")
    note("\n## 11. Event log")
    events = (w.folder() / "events.jsonl").read_text().splitlines()
    kinds = {json.loads(e)["kind"] for e in events}
    check("events.jsonl holds the whole story",
          {"open", "take", "round", "gate", "ship", "note", "handback",
           "order", "order-done", "cancel", "pause"} <= kinds, str(sorted(kinds)))
    calls = (w.root / "gh-state.json.calls").read_text()
    created, merged = (("create", '"merge"'), ('"POST"', '/merge"'))[ARGS.forge == "gitlab"]
    check("only the agents called the forge: the Drivers created the PRs, nobody merged",
          created in calls and merged not in calls and "edit" not in calls and '"PUT"' not in calls,
          calls[-300:])
    section_end()


class BoardProc:
    """A `chantier board` run in the background: its printed lines are read as they come."""

    def __init__(self, w: World, *args, cwd=None, env: dict | None = None):
        self.p = subprocess.Popen([sys.executable, "-m", "chantier", *map(str, args)],
                                  cwd=cwd or w.work, env={**w.env, **(env or {})}, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, text=True, encoding="utf-8")
        self.lines: "queue.Queue[str]" = queue.Queue()
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self) -> None:
        for line in self.p.stdout:
            self.lines.put(line.rstrip("\r\n"))

    def line(self, timeout: float = 20) -> str | None:
        try:
            return self.lines.get(timeout=timeout)
        except queue.Empty:
            return None

    def stop(self) -> None:
        if self.p.poll() is None:
            self.p.terminate()
            try:
                self.p.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.p.kill()
        for stream in (self.p.stdout, self.p.stderr):
            if stream:
                stream.close()


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Link:
    """What a board's start line says: the address, the key, the planning folder."""

    LINE = re.compile(r"^board on http://(?P<host>[^/]+):(?P<port>\d+)/\?k=(?P<key>\S+) over (?P<over>.+)$")

    def __init__(self, line: str | None):
        found = self.LINE.match(line or "")
        self.ok = found is not None
        self.host = found["host"] if found else ""
        self.port = int(found["port"]) if found else 0
        self.key = found["key"] if found else ""
        self.over = found["over"] if found else ""

    @property
    def cookie(self) -> dict[str, str]:
        return {"Cookie": f"chantier_board={self.key}"}


def fetch(port: int, path: str, method: str = "GET", headers: dict | None = None,
          body: bytes | None = None) -> tuple[int, dict, bytes]:
    """One request to a board, with no proxy and no redirect followed: the status, the headers
    (names in lower case) and the body. `path` is already percent-encoded."""
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    try:
        conn.request(method, path, body, headers or {})
        r = conn.getresponse()
        return r.status, {k.lower(): v for k, v in r.getheaders()}, r.read()
    finally:
        conn.close()


def jget(port: int, link: Link, path: str, headers: dict | None = None) -> tuple[int, dict, dict]:
    """A GET with the cookie, its body read as JSON ({} when it is not)."""
    code, head, raw = fetch(port, path, headers={**link.cookie, **(headers or {})})
    try:
        return code, head, json.loads(raw.decode("utf-8"))
    except ValueError:
        return code, head, {}


def op(port: int, link: Link, name: str, args: dict | None = None,
       headers: dict | None = None) -> tuple[int, dict, dict]:
    """One op of protocol 1 over HTTP (`POST /api/v1/call/<op>`) with the cookie: the status, the
    headers and the result's `data` (with the `error` text when it has none)."""
    code, head, raw = fetch(port, f"/api/v1/call/{name}", "POST",
                            {**link.cookie, "Content-Type": "application/json", **(headers or {})},
                            json.dumps(args or {}).encode("utf-8"))
    try:
        got = json.loads(raw.decode("utf-8"))
    except ValueError:
        return code, head, {}
    data = got.get("data") if isinstance(got, dict) else None
    out = dict(data) if isinstance(data, dict) else {}
    if isinstance(got, dict) and "error" in got:
        out.setdefault("error", got["error"])
    return code, head, out


def sibling(name: str) -> str:
    """The path of a route of the versions before protocol 1: the `v1` folder's sibling; it is a 404."""
    return urllib.parse.urljoin("/api/v1/", f"../{name}")


def folder_state(root: Path) -> dict:
    """Every file of a folder with its size and modification time: what a read-only run must keep."""
    return {p.relative_to(root).as_posix(): (p.stat().st_size, p.stat().st_mtime_ns)
            for p in sorted(root.rglob("*")) if p.is_file()}


def settled_live(port: int, link: Link, project: str, timeout: float = 30) -> dict:
    """The costs' answer once the board's live figure has been computed."""
    end = time.monotonic() + timeout
    while True:
        _, _, costs = op(port, link, "costs.get", {"project": project})
        live = costs.get("live")
        if live and not live["computing"] or time.monotonic() > end:
            return costs
        time.sleep(0.3)


def exits(proc: BoardProc, timeout: float = 25) -> int | None:
    try:
        return proc.p.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        return None


API_PUSH_S = 1.0  # the first number of CHANTIER_API_TEST_TIMES: the push loop's look, in seconds
API_ORIGIN = "http://127.0.0.1:{}".format


def close_code(ws, timeout: float = 15) -> int | None:
    """Read a WebSocket until it closes: the close code the server sent (None when it never closed)."""
    from websockets.exceptions import ConnectionClosed
    try:
        while True:
            ws.recv(timeout=timeout)
    except ConnectionClosed as e:
        return e.rcvd.code if e.rcvd else None
    except TimeoutError:
        return None


def frame_of(ws, kind: str, match=None, timeout: float = 15) -> dict | None:
    """The next frame of this kind (ticks and other kinds are passed over), None after `timeout`."""
    end = time.monotonic() + timeout
    while (left := end - time.monotonic()) > 0:
        try:
            got = json.loads(ws.recv(timeout=left))
        except TimeoutError:
            return None
        if got.get("t") == kind and (match is None or match(got)):
            return got
    return None


def board_api(w: World, port: int, link: Link, project: str):
    """Protocol 1 against the real `chantier board` process: the WebSocket with the cookie, a
    `chantier file` seen as an event, a write over the socket and its `board` line, the HTTP
    binding and its long-poll, the foreign origin, an old route, the probe. It returns a welcomed
    WebSocket left open for the caller's 1001 check at the board's stop."""
    from websockets.exceptions import InvalidStatus
    from websockets.sync.client import connect
    url = f"ws://127.0.0.1:{port}/api/v1/ws"
    hello = json.dumps({"t": "hello", "protocol": 1, "client": "scenario/1"})
    own = {"Cookie": link.cookie["Cookie"]}

    def open_socket(headers: dict, origin: str | None = None):
        ws = connect(url, additional_headers=headers, origin=origin, compression=None, proxy=None,
                     open_timeout=10)
        ws.send(hello)
        return ws

    def forge_lines() -> list[dict]:
        path = w.state / "forge-journal.jsonl"
        return ([json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()]
                if path.is_file() else [])

    ws = open_socket(own, API_ORIGIN(port))
    welcome = frame_of(ws, "welcome") or {}
    probe = fetch(port, "/api/board", headers=link.cookie)
    seen = json.loads(probe[2].decode("utf-8")) if probe[0] == 200 else {}
    check("the WebSocket with the cookie from the board's own origin gets `welcome`: protocol 1, "
          "the 20 ops and 6 topics, the server's PID as the probe's",
          welcome.get("protocol") == 1 and len(welcome.get("ops", [])) == 20
          and len(welcome.get("topics", [])) == 6 and "board.get" in welcome["ops"]
          and welcome["server"]["pid"] == seen.get("pid"), str(welcome)[:300])
    check("`GET /api/board` holds the probe's fields only, `protocols: [1]`",
          set(seen) == {"board", "version", "pid", "served", "surface", "protocols"}
          and seen["protocols"] == [1], str(seen))
    old = fetch(port, sibling("projects/x/state"), headers=link.cookie)[0]
    old_post = fetch(port, sibling("seats"), "POST",
                     {**link.cookie, "Content-Type": "application/json"}, b"{}")[0]
    check("a route of the versions before protocol 1 answers 404, a `POST` with the cookie too",
          old == 404 and old_post == 404, f"{old} {old_post}")
    # a project subscription, then `chantier file` run as a command: an event within a look and 2 s
    ws.send(json.dumps({"t": "sub", "id": "p", "topic": "project", "args": {"project": project}}))
    answer = frame_of(ws, "result", lambda f: f["id"] == "p") or {}
    first = frame_of(ws, "event", lambda f: f["sub"] == "p") or {}
    while settling := frame_of(ws, "event", lambda f: f["sub"] == "p", API_PUSH_S + 1.5):
        first = settling  # the live reading settles: the rev is steady after that
    check("a `project` subscription answers `result` 200, then an `event` with the state and its rev",
          answer.get("status") == 200 and first.get("rev") and "batch" in first.get("data", {}),
          str(answer)[:200])
    w.chantier("file", "Scenario socket idea")
    filed = time.monotonic()
    got = frame_of(ws, "event", lambda f: f["sub"] == "p" and f["rev"] != first["rev"]
                   and any(i["item"] == "scenario-socket-idea"
                           for i in f["data"]["backlog"]["inbox"]), API_PUSH_S + 2)
    took = time.monotonic() - filed
    check("`chantier file` in the same project reaches the subscriber as an event with a new rev "
          f"within the push loop's look plus 2 s ({took:.1f} s)", got is not None, str(first.get("rev")))
    # a write over the socket, and the `board` line it leaves, seen by an `events` subscription
    before = len(forge_lines())
    ws.send(json.dumps({"t": "sub", "id": "e", "topic": "events", "args": {"project": project}}))
    frame_of(ws, "result", lambda f: f["id"] == "e")
    ws.send(json.dumps({"t": "call", "id": "m", "op": "backlog.move",
                        "args": {"project": project, "items": ["scenario-socket-idea"], "to": "P3"}}))
    moved = frame_of(ws, "result", lambda f: f["id"] == "m") or {}
    lines = forge_lines()
    check("`backlog.move` over the WebSocket moves the folder and writes exactly one `board@1` line",
          moved.get("status") == 200 and (w.state / "2-backlog" / "P3" / "scenario-socket-idea").is_dir()
          and len(lines) == before + 1 and lines[-1]["type"] == "board@1"
          and lines[-1]["action"] == "move" and lines[-1]["items"] == ["scenario-socket-idea"],
          f"{moved} {lines[-1:]}")
    said = frame_of(ws, "event", lambda f: f["sub"] == "e" and f["data"]["lines"])
    check("an `events` subscription gets that line, with its `seq`",
          said is not None and said["data"]["lines"][-1]["seq"] == lines[-1]["seq"]
          and said["data"]["lines"][-1]["type"] == "board@1", str(said)[:300])
    ws.close()
    # the HTTP binding: a read, a write, a long-poll woken by `chantier file`
    code, head, board = op(port, link, "board.get")
    check("over HTTP `board.get` answers the board with `X-Chantier-Now`",
          code == 200 and board.get("board") is True and "x-chantier-now" in head, f"{code} {head}")
    code, _, body = op(port, link, "backlog.move",
                       {"project": project, "items": ["scenario-socket-idea"], "to": "inbox"})
    check("over HTTP `backlog.move` writes (the folder is back in the inbox)",
          code == 200 and (w.state / "1-inbox" / "scenario-socket-idea").is_dir(), f"{code} {body}")
    _, _, state = op(port, link, "project.state", {"project": project})
    wait: dict = {}

    def poll() -> None:
        rev = state["rev"]
        end = time.monotonic() + 30
        while time.monotonic() < end and not wait.get("done"):
            sub = {"key": "p", "topic": "project", "args": {"project": project}, "rev": rev}
            code, _, raw = fetch(port, "/api/v1/poll", "POST",
                                 {**link.cookie, "Content-Type": "application/json"},
                                 json.dumps({"subs": [sub]}).encode("utf-8"))
            for event in json.loads(raw.decode("utf-8") or "{}").get("events", []) if code == 200 else []:
                rev = event["rev"]
                wait["done"] = any(i["item"] == "scenario-poll-idea"
                                   for i in event["data"]["backlog"]["inbox"])

    poller = threading.Thread(target=poll)
    poller.start()
    time.sleep(1)  # the poll is held
    w.chantier("file", "Scenario poll idea")
    poller.join(40)
    check("a long-poll over HTTP answers with the project's event once `chantier file` ran",
          wait.get("done") is True, str(wait))
    # the key from a foreign origin: the cookie is refused, the header is not
    foreign = API_ORIGIN(free_port())
    try:
        open_socket(own, foreign)
        refused = None
    except InvalidStatus as e:
        refused = e.response.status_code
    check("the cookie from a foreign origin: HTTP 401 and no socket on the upgrade", refused == 401
          and op(port, link, "board.get", None, {"Origin": foreign})[0] == 401, str(refused))
    other = open_socket({"X-Chantier-Board-Key": link.key}, foreign)
    check("the key in a header from a foreign origin is accepted, over the WebSocket and over HTTP",
          (frame_of(other, "welcome") or {}).get("protocol") == 1
          and fetch(port, "/api/v1/call/board.get", "POST",
                    {"X-Chantier-Board-Key": link.key, "Origin": foreign,
                     "Content-Type": "application/json"}, b"{}")[0] == 200, "")
    other.close()
    keyless = connect(url, compression=None, proxy=None, open_timeout=10)
    keyless.send(json.dumps({"t": "hello", "protocol": 1, "client": "scenario/1", "key": "wrong"}))
    said = frame_of(keyless, "error") or {}
    check("a `hello` with a wrong key gets an `error` frame `key` and the close code 4401",
          said.get("code") == "key" and close_code(keyless) == 4401, str(said))
    held = open_socket(own, API_ORIGIN(port))
    frame_of(held, "welcome")
    return held


def board_writes(w: World, port: int, link: Link, project: str) -> None:
    """The web board's writes on the backlog (CR-226), as ops of protocol 1 over HTTP: moves, a
    filed idea, an edited file, the next-batch marker, the journal; every refusal writes nothing."""
    base = f"/api/v1/projects/{project}"

    def call(verb: str, name: str, data: dict, headers: dict | None = None) -> tuple[int, dict]:
        """`name` is the old route's last words (`backlog/move`), `verb` its method, unused."""
        code, _, body = op(port, link, name.replace("/", ".").replace("-", "_"),
                           {"project": project, **data}, headers)
        return code, body

    def place(slug: str) -> str | None:
        for where in ("1-inbox", "2-backlog/P1", "2-backlog/P2", "2-backlog/P3", "2-backlog/P4",
                      "3-ready"):
            if (w.state / where / slug).is_dir():
                return where
        return None

    def journal_count() -> int:
        return op(port, link, "journal.get", {"project": project})[2].get("count", -1)

    def forge_lines() -> list[dict]:
        path = w.state / "forge-journal.jsonl"
        return ([json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()]
                if path.is_file() else [])

    slug = "board-inbox-item"
    for to, where in (("P2", "2-backlog/P2"), ("3-ready", "3-ready"), ("inbox", "1-inbox")):
        code, body = call("POST", "backlog/move", {"items": [slug], "to": to})
        check(f"`backlog.move` to {to} moves the folder and says so in the journal",
              code == 200 and body.get("ok") and place(slug) == where
              and slug in body["journal"][-1]["text"], f"{code} {body}")
    count = journal_count()
    code, body = call("POST", "backlog/move", {"items": [slug], "to": "inbox"})
    check("a move to the item's own column writes nothing", code == 200 and journal_count() == count,
          f"{code} {body}")
    for bad in ("4-batch-item", "../x", "board-working"):
        code, body = call("POST", "backlog/move", {"items": [bad], "to": "P1"})
        check(f"a move of {bad!r}, not in the backlog, is refused", code == 409
              and not body.get("ok"), f"{code} {body}")
    seen = forge_lines()
    check("the three moves made one `board@1` line each in the project's `forge-journal.jsonl` and "
          "the refused ones none; git ignores the file",
          [(e["v"], e["source"], e["audience"], e["type"], e["action"], e["items"], e["wakes"])
           for e in seen]
          == [(2, "board", ["project"], "board@1", "move", [slug], True)] * 3
          and [e["seq"] for e in seen] == [1, 2, 3]
          and w.sh("git", "check-ignore", ".agents/changes/forge-journal.jsonl").strip() != "",
          str(seen))
    code, body = call("POST", "backlog/new", {"text": "# Board filed idea\r\n\r\nbody é\r\n"})
    filed = w.state / "1-inbox" / "board-filed-idea"
    request = filed / "intake" / "request.md"
    check("`backlog.new` files the text byte for byte in 1-inbox",
          code == 200 and request.is_file()
          and request.read_bytes() == "# Board filed idea\r\n\r\nbody é\r\n".encode("utf-8"),
          f"{code} {body}")
    code, body = call("POST", "backlog/new", {"text": "# Board filed idea\n\nbody"})
    check("a second idea with the same slug is refused: already exists",
          code == 409 and "already exists" in body.get("error", ""), f"{code} {body}")
    rel = request.relative_to(w.state).as_posix()
    code, head, raw = fetch(port, f"{base}/file?path={rel}", headers=link.cookie)
    sha = head.get("x-chantier-sha256", "")
    check("`GET file` of a text file carries the SHA-256 of its bytes",
          code == 200 and sha == hashlib.sha256(request.read_bytes()).hexdigest(), sha)
    edit = {"item": "board-filed-idea", "path": request.relative_to(filed).as_posix(),
            "text": "# Board filed idea\n\nedited\n", "base_sha256": sha}
    code, body = call("PUT", "backlog/file", edit)
    check("`backlog.file` with the right hash writes the text and keeps CRLF",
          code == 200 and request.read_bytes() == b"# Board filed idea\r\n\r\nedited\r\n"
          and body.get("sha256") == hashlib.sha256(request.read_bytes()).hexdigest(),
          f"{code} {body}")
    kept = request.read_bytes()
    code, body = call("PUT", "backlog/file", {**edit, "text": "stale"})
    check("`backlog.file` with the old hash answers 409 and changes nothing",
          code == 409 and request.read_bytes() == kept, f"{code} {body}")
    state_before = folder_state(w.state)
    refused = (("board-filed-idea", "STATUS.md"), ("board-filed-idea", "../board-ready-item/x.md"),
               ("board-filed-idea", "notes.txt"), ("board-working", "01-intent.md"),
               ("anything", "a.md"))
    codes = [call("PUT", "backlog/file", {"item": i, "path": p, "text": "x", "base_sha256": sha})[0]
             for i, p in refused]
    check("an edit of STATUS.md, `..`, a non-Markdown file, a batch CR or an archive slug is "
          "refused and writes nothing",
          all(c in (400, 409) for c in codes) and folder_state(w.state) == state_before, str(codes))
    code, body = call("POST", "backlog/next-batch", {})
    marker = json.loads((w.state / "next-batch.json").read_text(encoding="utf-8"))
    ready = sorted(p.name for p in (w.state / "3-ready").iterdir() if p.is_dir())
    check("`backlog.next_batch` writes next-batch.json with the sorted slugs of 3-ready",
          code == 200 and marker["crs"] == ready and bool(marker["declared_at"]), f"{code} {marker}")
    code, labelled = call("POST", "backlog/labels", {"items": ["board-backlog-item", slug],
                                                    "add": "docs"})
    code2, _ = call("POST", "backlog/group", {"items": ["board-backlog-item", slug], "name": "g1"})
    st = op(port, link, "project.state", {"project": project})[2]
    items = {i["item"]: i for col in st["backlog"].values() for i in col}
    check("labels and a group show in the state, with the next batch and the journal count",
          code == 200 and code2 == 200 and "docs" in items[slug]["labels"]
          and items[slug]["group"] == "g1" and st["next_batch"]["crs"] == ready
          and st["journal"]["count"] == journal_count(), str(st.get("journal")))
    call("POST", "backlog/move", {"items": [slug], "to": "P4"})
    items = {i["item"]: i for col in op(port, link, "project.state",
                                         {"project": project})[2]["backlog"].values() for i in col}
    check("a post-it moved alone leaves its group", items[slug]["group"] is None
          and items["board-backlog-item"]["group"] == "g1", str(items[slug]))
    check("the journal file is ignored by git",
          w.sh("git", "check-ignore", ".agents/changes/board-journal.jsonl").strip() != "")
    code, _ = call("POST", "journal/rescan", {})
    check("`journal.rescan` empties the journal", code == 200 and journal_count() == 0)
    board_running_lane(w, call, project, port, link)
    where = "/api/v1/call/backlog.move"
    check("a write with no key answers 401", fetch(port, where, "POST",
          {"Content-Type": "application/json"}, b"{}")[0] == 401)
    check("a write with the cookie from a foreign `Origin` answers 401", call(
          "POST", "backlog/move", {}, {"Origin": "http://evil.example"})[0] == 401)
    check("a write whose body is not JSON answers 415", fetch(
          port, where, "POST", {**link.cookie, "Content-Type": "text/plain"}, b"{}")[0] == 415)


def board_running_lane(w: World, call, project: str, port: int, link: Link) -> None:
    """The running batch's lane (CR-427): a drop writes only the mark (the batch is open here), a CR
    whose grill has not started is refused, and a move back to a row clears the mark."""
    slug = "board-inbox-item"
    folder = next(w.state.glob(f"[12]-*/**/{slug}"))
    mark = folder / "work" / "running-batch"
    journal = w.state / "forge-journal.jsonl"
    seen = len(journal.read_text(encoding="utf-8").splitlines())
    (folder / "work").mkdir(exist_ok=True)
    (folder / "work" / "specifying").write_text(
        "2026-11-21T00:00:00Z spec-writer\n", encoding="utf-8"
    )
    code, body = call("POST", "backlog/move", {"items": [slug], "to": "running-batch"})
    batch = w.batch()["id"]
    fresh = [json.loads(x) for x in journal.read_text(encoding="utf-8").splitlines()][seen:]
    check(
        "`backlog.move` to `running-batch` writes the mark naming the batch and moves no folder",
        code == 200
        and mark.is_file()
        and mark.read_text().split()[-1] == batch
        and folder.is_dir(),
        f"{code} {body}",
    )
    check(
        "it appends one `board@1` line with the action `running-batch`",
        [(e["type"], e["action"], e["items"]) for e in fresh]
        == [("board@1", "running-batch", [slug])],
        str(fresh),
    )
    st = op(port, link, "project.state", {"project": project})[2]
    items = {i["item"]: i for col in st["backlog"].values() for i in col}
    check(
        "`project.state` shows the item with `running_batch` naming the batch",
        items[slug]["running_batch"] == batch,
        str(items[slug].get("running_batch")),
    )
    code, out = w.chantier("status")
    check(
        "`status` lists the CR on its `running batch:` line",
        code == 0 and any(ln.startswith("running batch:") and slug in ln for ln in out),
        str(out),
    )
    other = w.state / "1-inbox" / "board-filed-idea"
    (other / "02-answers.md").write_text("# Answers\n", encoding="utf-8")
    before = folder_state(w.state)
    code, body = call(
        "POST", "backlog/move", {"items": ["board-filed-idea"], "to": "running-batch"}
    )
    check(
        "a grilled CR whose spec-writer has not started is refused, 409, and writes nothing",
        code == 409
        and "the grill is not finished" in body.get("error", "")
        and not (other / "work" / "running-batch").exists()
        and folder_state(w.state) == before,
        f"{code} {body}",
    )
    call("POST", "backlog/move", {"items": [slug], "to": "P2"})
    back = w.state / "2-backlog" / "P2" / slug
    check(
        "the marked CR moved back to `P2` loses its mark",
        back.is_dir() and not (back / "work" / "running-batch").exists(),
    )


def forge_pr(w: World, link: str, **fields: object) -> None:
    """What the forge holds of the PR at `link`, in GraphQL words (`state`, `isDraft`, `mergeable`,
    `baseRefName`, `mergedAt`, `closedAt`, `checks`): the fake `gh` answers the board's PRs page."""
    n = link.rstrip("/").rsplit("/", 1)[-1]
    state = json.loads(w.gh_state.read_text())
    state.setdefault("prs", {}).setdefault(n, {}).update(fields)
    w.gh_state.write_text(json.dumps(state))


def record_pr(w: World, cr: str, link: str) -> None:
    """The record's own edit: the CR `cr` has the PR at `link` (what `ship` writes)."""
    d = w.batch()
    next(c for c in d["crs"] if c["id"] == cr)["pr"] = link
    (w.folder() / "batch.json").write_text(json.dumps(d, indent=2))


def board_prs(w: World, port: int, link: Link, project: str, ids: tuple[str, str, str, str]) -> None:
    """The PRs page (CR-302): the batch's PRs read on the forge against the record, read-only."""
    one, two, three, four = ids
    url = "https://github.com/acme/demo/pull/{}".format
    args = {"project": project}
    first_call = len(forge_calls(w))

    def rows() -> tuple[dict, dict]:
        code, _, got = op(port, link, "prs.get", args)
        return got, ({r["cr"]: r for r in got.get("rows", [])} if code == 200 else {})

    def kept() -> dict:
        """The planning folder, but for the one file a read may write (CR-303's signal)."""
        return {k: v for k, v in folder_state(w.state).items() if k != "forge-journal.jsonl"}

    def untouched(note: str, then) -> tuple[dict, dict]:
        folder = kept()
        porcelain = w.sh("git", "status", "--porcelain", "--", ".agents/changes")
        found = then()
        check(f"{note}: nothing was written in the planning folder but `forge-journal.jsonl`, nor "
              "its git status",
              kept() == folder
              and w.sh("git", "status", "--porcelain", "--", ".agents/changes") == porcelain)
        return found

    def journal_entries() -> list[dict]:
        """The merges of the journal: the board's backlog writes share the file."""
        path = w.state / "forge-journal.jsonl"
        found = ([json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()]
                 if path.is_file() else [])
        return [e for e in found if e["type"] == "merged@1"]

    def signal_lines(*args) -> list[str]:
        w.chantier(*args, expect=None)
        return [x for x in w.last_out if x.startswith("forge saw merged")]

    record_pr(w, two, url(902))
    record_pr(w, three, url(903))
    check("`prs.get` with no key answers 401", fetch(port, "/api/v1/call/prs.get", "POST", body=b"{}")[0] == 401)
    got, by = untouched("a read of the PRs", rows)
    shown = w.cr(one)["pr"]
    check("`prs.get` holds one row per CR with a PR, read on the forge, none with a PR missing",
          {r["cr"] for r in got.get("rows", [])} == {one, two, three}
          and got["batch"] == w.batch()["id"] and got["error"] is None and got["read_at"]
          and got["all_done"] is False
          and all(r["state"] == "open" and r["checks"] == "green" and not r["conflicting"]
                  and not r["checking"] for r in by.values()), str(got))
    to_review = {c["cr"]: c["to_review"]
                 for c in op(port, link, "project.state", {"project": project})[2]["batch"]["crs"]}
    check("a row has the PR, its CR and its title, and is ready now only when the record says the "
          "CR is to review and the forge agrees",
          by[one]["pr"] == shown and by[one]["title"] and "kind" in by[one]
          and by[one]["ready_now"] is to_review[one] and not by[two]["ready_now"], str(by))
    forge_pr(w, shown, state="MERGED", mergedAt="2026-11-16T10:00:00Z")
    forge_pr(w, url(903), mergeable="CONFLICTING", checks="FAILURE")
    record_pr(w, four, url(904))
    forge_pr(w, url(904), isDraft=True, checks=None)
    got, by = untouched("a second read", rows)
    check("a PR merged on the forge and not in the record says so, with the branch it went into",
          by[one]["state"] == "merged" and by[one]["merged_into"]["branch"] == "main"
          and by[one]["disagrees"] == "merged on the forge, not recorded yet: tell the Chief of Staff"
          and not got["all_done"], str(by[one]))
    check("a conflicting PR, a draft and a PR with no check run yet are told apart; a check the "
          "forge has not computed is `being checked`, never `none`",
          by[three]["conflicting"] and by[three]["checks"] == "failing"
          and by[four]["state"] == "draft" and by[four]["checking"] is True
          and by[four]["checks"] != "none", str((by[three], by[four])))
    wanted = (f"forge saw merged: {one} {shown} into main at 2026-11-16T10:00:00Z; "
              f"for the Chief of Staff: order merged {one}")
    check("the merge the board saw is one line of `forge-journal.jsonl`, once, never published",
          [(e["cr"], e["pr"], e["into"], e["into_cr"], e["merged_at"]) for e in journal_entries()]
          == [(one, shown, "main", None, "2026-11-16T10:00:00Z")]
          and w.sh("git", "check-ignore", ".agents/changes/forge-journal.jsonl").strip() != "",
          str(journal_entries()))
    rows()
    check("a second read of the same merge writes no second line", len(journal_entries()) == 1)
    check("`status` prints the `forge saw merged` line for the Chief of Staff",
          signal_lines("status") == [wanted], str(w.last_out))
    orders = w.batch()["orders"]
    check("the Foreman's heartbeat `status --refresh --batch --epoch` prints it too and the "
          "batch's orders are unchanged",
          signal_lines("status", "--refresh", "--batch", w.batch()["id"], "--epoch", 1) == [wanted]
          and w.batch()["orders"] == orders, str(w.last_out))
    code, _ = w.chantier("order", "merged", one, "--epoch", 1, expect=None)
    check("`status` no longer prints the line once the merge is recorded, the file untouched",
          code == 0 and signal_lines("status") == [] and len(journal_entries()) == 1, str(w.last_out))
    got, by = rows()
    check("`order merged` makes the disagreement go", code == 0 and by[one]["disagrees"] is None
          and by[one]["state"] == "merged", f"{code} {by.get(one)}")
    forge_pr(w, url(902), state="CLOSED", closedAt="2026-11-16T10:05:00Z")
    forge_pr(w, url(903), state="MERGED", mergedAt="2026-11-16T10:06:00Z", mergeable="UNKNOWN")
    forge_pr(w, url(905), state="MERGED", mergedAt="2026-11-16T10:07:00Z")
    record_pr(w, four, url(905))
    got, by = rows()
    check("with every PR merged or closed the page says all done",
          got["all_done"] is True and by[two]["state"] == "closed" and by[two]["closed_at"]
          and by[three]["state"] == "merged" and by[four]["state"] == "merged", str(got))
    _, out = w.chantier("order", "add", "--note", str(prepare_cr(w, "Board late arrival")[1]))
    late = w.batch()["crs"][-1]["id"]
    record_pr(w, late, url(906))
    got, by = rows()
    check("a CR added after the page was all done brings a new row, and the page is not all done",
          late in by and by[late]["state"] == "open" and got["all_done"] is False, f"{out} {got}")
    calls = forge_calls(w)[first_call:]
    check("the page only read the forge: every call is an `api graphql` query, none a mutation",
          bool(calls) and all(c[:2] == ["api", "graphql"]
                              and not any(a == "-X" or a.startswith("query=mutation") for a in c)
                              for c in calls), str(calls[:1]))


def forge_hub(w: World) -> None:
    """CR-358: one forge hub per surface and machine, and the watchers that wake each session."""
    note("\n## 16d. The forge hub: one reader of the forge for a surface, and `chantier watch`")
    sw = SurfaceWorld(w.root / "hub")
    sw.root.mkdir()
    sw.build()
    url = "https://github.com/acme/demo/pull/{}".format
    server_json = sw.surface / ".git" / "chantier" / "server.json"
    quick = {"CHANTIER_HUB_TEST_TIMES": "1:4"}  # the hub reads every 1 s, a watcher ends 4 s on
    slow = {"CHANTIER_HUB_TEST_TIMES": "30:4"}  # the hub reads once at its start, then 30 s on
    procs: list[BoardProc] = []
    mine = {"demo": {910, 911, 912, 913, 914, 915}, "other": {920}}
    setup = [0]

    def folder(project: str) -> Path:
        return sw.surface / "projects" / project / "changes"

    def batch(project: str) -> dict:
        return json.loads((folder(project) / "4-batch" / "batch.json").read_text(encoding="utf-8"))

    def edit(project: str, cr: str, **fields: object) -> None:
        d = batch(project)
        next(c for c in d["crs"] if c["id"] == cr).update(fields)
        (folder(project) / "4-batch" / "batch.json").write_text(json.dumps(d, indent=2))

    def journal(project: str = "demo") -> list[dict]:
        path = folder(project) / "forge-journal.jsonl"
        lines = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
        whole = []
        for x in lines:  # a line being appended is not a line yet
            with contextlib.suppress(ValueError):
                whole.append(json.loads(x))
        return whole

    def record() -> dict:
        """The `hub` entry of `server.json`."""
        try:
            return json.loads(server_json.read_text(encoding="utf-8")).get("hub", {})
        except (OSError, ValueError):
            return {}

    def until(then, timeout: float = 40) -> bool:
        end = time.monotonic() + timeout
        while not (found := then()) and time.monotonic() < end:
            time.sleep(0.25)
        return bool(found)

    def asked(call: list[str]) -> list[int]:
        query = next(a for a in call if a.startswith("query="))
        return [int(n) for n in re.findall(r"\bp(\d+): pullRequest", query)]

    def graphql() -> list[list[str]]:
        return [c for c in forge_calls(sw)[setup[0]:] if c[:2] == ["api", "graphql"]]

    def reads(project: str) -> int:
        """The hub's reads of a project so far: the `api graphql` calls naming its PRs."""
        return len([c for c in graphql() if set(asked(c)) <= mine[project]])

    def ended(proc: BoardProc, timeout: float = 60) -> list[str]:
        """What a watcher printed until it exited."""
        try:
            proc.p.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            return ["(still running)"]
        got = []
        while (x := proc.line(2)) is not None:
            got.append(x)
        return got

    def watcher(project: str, *args, env: dict = quick) -> BoardProc:
        procs.append(BoardProc(sw, "--project", project, "watch", *args, cwd=sw.surface, env=env))
        return procs[-1]

    def merged(number: int, at: str) -> None:
        forge_pr(sw, url(number), state="MERGED", mergedAt=at)

    def says(cr: str, number: int, at: str) -> str:
        return (f"forge saw merged: {cr} {url(number)} into main at {at}; "
                f"for the Chief of Staff: order merged {cr}")

    cli_form = (f'uv run --no-sync --project "{SKILL.parents[1].resolve().as_posix()}" chantier '
                f'--project "{(sw.surface / "projects" / "demo").resolve().as_posix()}"')
    not_running = "watch: not running: for the Chief of Staff, start in the background: "

    def no_watcher(n: int) -> str:
        return (f"{not_running}{cli_form} watch --after {n}; after the user's no, at each user "
                f"message: {cli_form} watch --once --after {n}")

    def cursor(n: int) -> str:
        return ("watch: " + f"{a_batch} still running: for the Chief of Staff, start again in the "
                f"background now: {cli_form} watch --after {n}")

    sw.chantier("init")
    sw.chantier("init", project="other")
    items = [sw.prepare(f"Hub A{n}") for n in range(1, 7)]
    sw.chantier("open", *items, "--direct", "--slots", 2, *FROM_AGENTS_MD)
    a_batch = batch("demo")["id"]
    sw.chantier("foreman", "set", "uuid-chief", "--epoch", 1, "--batch", a_batch)
    _, out = sw.chantier("open", sw.prepare("Hub B1", project="other"), "--direct", "--slots", 1,
                         *FROM_AGENTS_MD, project="other")
    b_batch = out[0].split()[1]
    sw.chantier("foreman", "set", "uuid-chief", "--epoch", 1, "--batch", b_batch, project="other")
    a = [c["id"] for c in batch("demo")["crs"]]
    b1 = batch("other")["crs"][0]["id"]
    for cr, number in zip(a, range(910, 916)):
        edit("demo", cr, pr=url(number))
    edit("other", b1, pr=url(920))
    edit("demo", a[3], status="ready", pr_draft=False)  # the one CR the record holds ready to merge
    before = {(p, f): (folder(p) / "4-batch" / f).read_bytes()
              for p in ("demo", "other") for f in ("batch.json", "events.jsonl")
              if (folder(p) / "4-batch" / f).is_file()}
    setup[0] = len(forge_calls(sw))
    _, out = sw.chantier("status", expect=None)
    check("`status` of a running batch with no watcher names the hub (none yet) and ends with the "
          "`watch: not running` line and the command to run, no `watch: chantier watch` line",
          "forge hub: none running" in out and bool(out)
          and out[-1] == no_watcher(0) and "--batch" not in out[-1]
          and not any(x.startswith("watch: chantier watch") for x in out), str(out))
    sw.chantier("watch", "--after", 5, expect=1)
    check("`watch --after` past the journal's end exits 1", "past the journal's end" in sw.last_stderr,
          sw.last_stderr)
    try:
        # 1. two watchers, one hub, one read per project with an open PR each cycle
        wa = watcher("demo")
        start = wa.line()
        check("the first watcher takes the hub lock and says so",
              (start or "").startswith("watch: demo from cursor 0 for project") and (start or "").endswith(", the hub"),
              str(start))
        wb = watcher("other")
        start_b = wb.line()
        check("a watcher of the other project of the surface is not the hub",
              (start_b or "").startswith("watch: other from cursor 0")
              and not (start_b or "").endswith(", the hub"), str(start_b))
        began = time.monotonic()
        until(lambda: reads("demo") >= 3 and reads("other") >= 3)
        span = time.monotonic() - began
        found = record()
        first_hub = found.get("pid")
        check("the `hub` entry of `server.json` names one PID (a process of its own, neither watcher's argument vector) and "
              "a read per project of the surface",
              isinstance(first_hub, int) and set(found.get("projects", {})) == {"demo", "other"}
              and record().get("pid") == first_hub, str(found))
        _, out = sw.chantier("status", expect=None)
        check("`status` names the hub's PID while it runs",
              any(x.startswith(f"forge hub: PID {first_hub},") for x in out), str(out))
        check("while the session's watchers run, `status` holds the `pull path` line and "
              "no `watch: not running` line",
              any(x.startswith("watch: this session's watcher runs; pull path: ") and
                  x.endswith(" watch --once --after 0") for x in out)
              and not any(x.startswith("watch: not running") for x in out), str(out))
        sets = [asked(c) for c in graphql()]
        check("each cycle makes one `api graphql` call per project with an open PR: every call names "
              "one project's PRs, and no more than one hub's worth were made",
              all(set(x) in (mine["demo"], mine["other"]) for x in sets)
              and reads("demo") <= span + 3 and reads("other") <= span + 3,
              f"{sets[:3]} {reads('demo')} {reads('other')} in {span:.1f} s")
        # 2. a merge in A: A's watcher ends on it, B's keeps running and takes the lock
        merged(910, "2026-11-16T10:00:00Z")
        got = ended(wa)
        check("A's watcher ends with the `forge saw merged` line and its cursor",
              got == [says(a[0], 910, "2026-11-16T10:00:00Z"), cursor(1)], str(got))
        entries = journal()
        check("the journal holds the merge once, written by the hub, and git ignores the file",
              [(e["v"], e["seq"], e["source"], e["audience"], e["type"], e["cr"]) for e in entries]
              == [(2, 1, "hub", ["project"], "merged@1", a[0])]
              and sw.sh("git", "check-ignore", "projects/demo/changes/forge-journal.jsonl",
                        cwd=sw.surface).strip() != "", str(entries))
        _, out = sw.chantier("status", expect=None)
        check("after A's watcher ended and before it is restarted, `status` ends with the "
              "`watch: not running` line and the journal's last seq",
              bool(out) and out[-1] == no_watcher(1), str(out[-2:]))
        check("B's watcher keeps running and takes the lock",
              until(lambda: record().get("pid") not in (None, first_hub)) and wb.p.poll() is None, str(record()))
        reached = reads("other")
        check("the next cycles still read the forge, for B's PRs too",
              until(lambda: reads("other") > reached), str(graphql()[-2:]))
        check("the hub changed neither project's `batch.json` nor `events.jsonl`",
              all((folder(p) / "4-batch" / f).read_bytes() == v for (p, f), v in before.items()),
              "a record changed")
        # 3. restarted with --after: nothing replayed; two merges within the quiet: one end
        wa = watcher("demo", "--after", 1)
        wg = watcher("demo", "--after", 1, "--for", "role:griller")
        start_g = wg.line()
        check("a watcher started with `--for role:griller` lists its subscription",
              (start_g or "").startswith("watch: demo from cursor 1 for project")
              and ", role:griller" in (start_g or ""), str(start_g))
        start = wa.line()
        check("a watcher restarted with `--after 1` is not the hub and replays nothing",
              (start or "").startswith("watch: demo from cursor 1")
              and not (start or "").endswith(", the hub") and wa.line(2) is None, str(start))
        merged(911, "2026-11-16T10:01:00Z")
        until(lambda: len(journal()) == 2)
        merged(912, "2026-11-16T10:01:30Z")
        got = ended(wa)
        check("two merges within the quiet give one end with both lines",
              got == [says(a[1], 911, "2026-11-16T10:01:00Z"), says(a[2], 912, "2026-11-16T10:01:30Z"),
                      cursor(3)], str(got))
        check("the `--for role:griller` watcher, the merge being for the project, ends with the same lines",
              ended(wg) == got, str(got))
        # 4. a ready PR whose checks fail: a line for the watcher, none in `status`
        forge_pr(sw, url(913), checks="FAILURE", headRefOid="feedface0123456789012345678901234567890a")
        wa = watcher("demo", "--after", 3)
        wa.line()
        got = ended(wa)
        red = (f"forge saw checks red: {a[3]} {url(913)} at feedfac, ready to merge in the record; "
               "for the Chief of Staff: tell the user, record nothing")
        check("a ready PR's failing checks end the watcher with the `forge saw checks red` line",
              got == [red, cursor(4)], str(got))
        _, out = sw.chantier("status", expect=None)
        check("`status` does not print the checks-red line, and prints the three merges",
              not any("checks red" in x for x in out)
              and len([x for x in out if x.startswith("forge saw merged:")]) == 3, str(out))
        # 5. recording: `order merged` twice, the second answers `already merged`
        sw.chantier("order", "merged", a[0], "--epoch", 1, "--batch", a_batch)
        sw.chantier("order", "merged", a[0], "--epoch", 1, "--batch", a_batch, expect=None)
        check("`order merged` twice: the second answers `already merged`",
              f"{a[0]} already merged" in "\n".join(sw.last_out) + sw.last_stderr,
              f"{sw.last_out} {sw.last_stderr}")
        # 6. a merge the board's PRs page reads first: the hub writes no second line
        wb.stop()
        # the board is the surface server now: it takes the hub lock and reads the forge once at its
        # start, then every 30 s, so its PRs page reads the merge first
        board = BoardProc(sw, "board", "--project", "demo", "--host", "127.0.0.1", "--port", 0,
                          cwd=sw.surface, env=slow)
        procs.append(board)
        link = Link(board.line())
        wa = watcher("demo", "--after", 4)
        wa.line()
        until(lambda: bool(record().get("projects", {}).get("demo", {}).get("read_at")))
        merged(914, "2026-11-16T10:03:00Z")
        code, _, _ = op(link.port, link, "prs.get", {"project": "demo"})
        check("the board's PRs page reads the merge first and writes its line",
              code == 200 and [(e["seq"], e["source"], e["cr"]) for e in journal()][-1:] == [(5, "board", a[4])],
              str(journal()[-1:]))
        got = ended(wa)
        check("the watcher wakes on the board's line",
              got == [says(a[4], 914, "2026-11-16T10:03:00Z"), cursor(5)], str(got))
        wa = watcher("demo", "--after", 5)
        wa.line()
        seen = len(graphql())
        until(lambda: len(graphql()) >= seen + 1, 45)
        check("the hub's reads of the same merge write no second line",
              [e["source"] for e in journal()] == ["hub", "hub", "hub", "hub", "board"], str(journal()))
        # 7. the batch ends and pauses: A's watcher keeps running, and the board's writes wake it
        for cr in (a[1], a[2], a[4]):
            sw.chantier("order", "merged", cr, "--epoch", 1, "--batch", a_batch)
        sw.chantier("order", "drop", a[3], "--note", "trash", "--batch", a_batch)
        sw.chantier("order", "drop", a[5], "--note", "trash", "--batch", a_batch)
        time.sleep(7)  # longer than a watcher's quiet and than the hub's cycle
        _, out = sw.chantier("status", expect=None)
        check("A's batch is paused and A's watcher keeps running; `status` holds the `pull path` line",
              batch("demo")["status"] == "paused" and wa.p.poll() is None
              and any(x.startswith("watch: this session's watcher runs; pull path: ") for x in out)
              and not any(x.startswith("watch: not running") for x in out), f"{batch('demo')['status']} {out}")
        def write(project: str, text: str) -> int:
            return op(link.port, link, "backlog.new", {"project": project, "text": text})[0]

        check("a board write on A", write("demo", "Rescan idea one") == 200)
        got = ended(wa)
        told = ("board wrote (new): " in (got or [""])[0] and "for the Chief of Staff: tell the user, "
                "act on nothing" in got[0])
        check("A's watcher, its batch paused, ends on the board's line, with the restart of its batch",
              len(got) == 2 and told and got[1] == cursor(6), str(got))
        _, out = sw.chantier("watch", "--once", "--after", 5)
        check("`watch --once --after 5` prints the same line, then the cursor and the pull command, "
              "and takes no lock",
              len(out) == 2 and out[0] == got[0]
              and out[1] == ("watch: cursor 6; next, at the user's next message: "
                             f"{cli_form} watch --once --after 6"), str(out))
        sw.chantier("watch", "--once", expect=1)
        check("`watch --once` with no `--after` exits 1 and says it needs one",
              "needs --after" in sw.last_stderr, sw.last_stderr)
        wa = watcher("demo", "--after", 6)
        wa.line()
        check("a board write on the other project", write("other", "Rescan idea two") == 200)
        time.sleep(7)
        check("it does not end A's watcher, and lands in the other project's journal, not A's",
              wa.p.poll() is None and [e["type"] for e in journal("other")] == ["board@1"]
              and len(journal()) == 6, f"{wa.p.poll()} {journal('other')}")
        sw.chantier("seat", "take", "sess-z", "--env", "remote", "--title", "[Remote] Proj", "--link",
                    "link-z", env={"CLAUDE_CODE_SESSION_ID": "uuid-chief-b"})
        got = ended(wa)
        check("another session's `seat take` ends A's watcher with the seat line",
              got == ["watch: the seat of demo is another session's now; ended"], str(got))
        wb = watcher("other")
        wb.line()
        merged(915, "2026-11-16T10:04:00Z")
        seen = len(graphql())
        until(lambda: len(graphql()) >= seen + 1, 45)
        check("a PR merged after the pause writes no line for A, and the hub no longer reads its PRs",
              len(journal()) == 6 and not any(x != [920] for x in map(asked, graphql()[seen:])),
              str(journal()[-1:]))
        # 8. nothing but read-only `api graphql` calls, and B's record is as it was
        calls = forge_calls(sw)[setup[0]:]
        check("no `gh` call but `api graphql` queries (no mutation) was made by the hub or the board",
              bool(calls) and all(c[:2] == ["api", "graphql"] and not any(
                  x == "-X" or x.startswith("query=mutation") for x in c) for c in calls), str(calls[:1]))
        check("B's `batch.json` and `events.jsonl` are as the hub found them, and B's journal holds its board line only",
              all((folder("other") / "4-batch" / f).read_bytes() == v
                  for (p, f), v in before.items() if p == "other") and [e["type"] for e in journal("other")] == ["board@1"],
              str(journal("other")))
        # 9. a journal from before (version 0 lines): a board write appends a version 2 line after
        # them, and the watcher started with the printed `--after` prints it once
        (one,) = journal("other")
        old = {"seq": 1, "t": one["t"], "by": "board", "kind": one["type"].split("@")[0],
               **{k: one[k] for k in ("action", "items", "text", "wakes")}}
        (folder("other") / "forge-journal.jsonl").write_text(json.dumps(old) + os.linesep, encoding="utf-8")
        wb.stop()
        wb = watcher("other", "--after", 1)
        wb.line()
        check("a board write on a journal of version 0 lines", write("other", "Rescan idea three") == 200)
        got = ended(wb)
        after = journal("other")
        check("the version 0 line is kept as written, the board's line follows it in version 2, "
              "and the watcher prints that line once",
              after[0] == old and (after[1]["v"], after[1]["seq"], after[1]["source"], after[1]["audience"])
              == (2, 2, "board", ["project"]) and len(got) == 2 and got[0].startswith("board wrote (new): "),
              f"{after} {got}")
    finally:
        for proc in reversed(procs):
            proc.stop()


def outside_poller(w: World) -> None:
    """An outside poller writes issue events into the journal: `interests`, `journal add` and the
    watcher that tells the line; the hub reads no issue."""
    note("\n## 16d2. An outside poller: `interests`, `journal add issue@1`, and `chantier watch`")
    sw = SurfaceWorld(w.root / "poller")
    sw.root.mkdir()
    sw.build()
    sw.chantier("init")
    link = "https://acme.atlassian.net/browse/PAY-12"
    journal = sw.state / "forge-journal.jsonl"
    folders = []
    for title in ("Poller inbox", "Poller backlog"):
        _, out = sw.chantier("file", title)
        inbox = sw.surface / out[0].removeprefix("filed ").split(";", 1)[0]
        (inbox / "01-intent.md").write_text(f"# {title}\n\nissue: {link}\n", encoding="utf-8")
        folders.append(inbox)
    _, out = sw.chantier("triage", folders[1], "--priority", "P2")
    moved = sw.surface / out[0].removeprefix("triaged ").rsplit(" (", 1)[0]
    by = [folders[0].relative_to(sw.state).as_posix(), moved.relative_to(sw.state).as_posix()]
    code, out = sw.chantier("interests", "--kind", "issue", "--json")
    got = json.loads(out[0]) if out else {}
    check("`interests --kind issue --json` lists the link once per CR folder, read by the outside "
          "poller, exit 0",
          code == 0 and got.get("errors") == []
          and [(i["ref"], i["tracker"], i["read_by"], i["by"]) for i in got.get("interests", [])]
          == [(link, "jira", "outside", b) for b in by], str(out))
    calls = len(forge_calls(sw))
    watcher = BoardProc(sw, "--project", "demo", "watch", cwd=sw.surface,
                        env={"CHANTIER_HUB_TEST_TIMES": "1:4"})
    try:
        watcher.line()
        payload = json.dumps({"tracker": "jira", "ref": link, "event": "commented",
                              "at": "2026-11-20T09:14:00Z", "text": "keep the old column order"})
        folders_text = ", ".join(by)
        written = f"journal: seq 1 issue@1 commented on {link} ({folders_text})"
        code, out = sw.chantier("journal", "add", "issue@1", "--json", "-", stdin=payload)
        check("`journal add issue@1 --json -` writes the event and names its folders",
              code == 0 and out == [written], str(out))
        got = []
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline and watcher.p.poll() is None:
            if (x := watcher.line(1)) is not None:
                got.append(x)
        check("the watcher ends and prints the `tracker saw` line",
              watcher.p.poll() is not None
              and f'tracker saw commented on {link} ({folders_text}): "keep the old column order"; '
              "for the Chief of Staff: tell the user in one line, record nothing" in got, str(got))
    finally:
        watcher.stop()
    before = journal.read_bytes()
    code, out = sw.chantier("journal", "add", "issue@1", "--json", "-", stdin=payload)
    check("the same add again says it is already there and the journal is unchanged",
          code == 0 and out == ["journal: already there (seq 1)"] and journal.read_bytes() == before,
          str(out))
    refused = [
        ("a ref no CR names", "issue@1", {"ref": link + "0"}, 2, "is no CR's issue"),
        ("a payload with a `cr` key", "issue@1", {"cr": "CR-1"}, 1, "cr: Extra inputs"),
        ("a type other than issue@1", "merged@1", {}, 2, "is not written from outside"),
    ]
    for label, kind, change, expect, text in refused:
        code, _ = sw.chantier("journal", "add", kind, "--json", "-", expect=None,
                              stdin=json.dumps({**json.loads(payload), **change}))
        check(f"{label} is refused (exit {expect}) and the journal is unchanged",
              code == expect and text in sw.last_stderr and journal.read_bytes() == before,
              f"{code} {sw.last_stderr}")
    check("the fake `gh` was never called: the hub read no issue", len(forge_calls(sw)) == calls,
          str(forge_calls(sw)[calls:]))


def typed_waits_gitlab(w: World) -> None:
    """CR-409 on GitLab: a Driver blocks with `--wait pipeline`, the fake `glab` turns the head
    green, the hub tells it once, the Foreman clears the wait and takes the CR back. The approval
    half is not proved on GitLab (no account), so it is not played."""
    note("\n## 16f. Typed waits on GitLab: `--wait pipeline`, and the hub's `wait-cleared` line")
    sw = SurfaceWorld(w.root / "waits")
    sw.root.mkdir()
    sw.build()
    link = PR_LINK["gitlab"] + "940"
    sha = "c" * 40
    batch_file = sw.state / "4-batch" / "batch.json"
    procs: list[BoardProc] = []

    def cleared() -> list[tuple[str, str]]:
        path = sw.state / "forge-journal.jsonl"
        lines = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
        found = []
        for x in lines:
            with contextlib.suppress(ValueError):
                e = json.loads(x)
                if e["type"] == "wait-cleared@1":
                    found.append((e["wait"], e["wait_type"]))
        return found

    def until(then, timeout: float = 40) -> bool:
        end = time.monotonic() + timeout
        while not (found := then()) and time.monotonic() < end:
            time.sleep(0.25)
        return bool(found)

    sw.chantier("init")
    sw.chantier("open", sw.prepare("Waits GL"), "--direct", "--slots", 1, *FROM_AGENTS_MD)
    d = json.loads(batch_file.read_text(encoding="utf-8"))
    cr, batch = d["crs"][0]["id"], d["id"]
    sw.chantier("foreman", "set", "uuid-chief", "--epoch", 1, "--batch", batch)
    d = json.loads(batch_file.read_text(encoding="utf-8"))
    d["crs"][0].update(pr=link, status="working", head=sha)
    batch_file.write_text(json.dumps(d, indent=2))
    where = ("--epoch", 1, "--batch", batch)
    forge_pr(sw, link, diffHeadSha=sha, headPipeline={"status": "RUNNING"})
    code, _ = sw.chantier("handback", cr, "blocked", "waits: the pipeline", "--wait", "pipeline",
                          "--batch", batch, expect=None)
    waits = json.loads(batch_file.read_text(encoding="utf-8"))["crs"][0].get("waits", [])
    check("a Driver's blocked hand-back with `--wait pipeline` records one wait on the head and "
          "the merge request", code == 0 and [(x["id"], x["type"], x["ref"], x["link"])
                                               for x in waits] == [("w1", "pipeline", sha, link)],
          str(waits))
    try:
        board = BoardProc(sw, "board", "--project", "demo", "--host", "127.0.0.1", "--port", 0,
                          cwd=sw.surface, env={"CHANTIER_HUB_TEST_TIMES": "1:4"})
        procs.append(board)
        board.line()
        time.sleep(4)
        check("the hub tells nothing while the pipeline runs", not cleared(), str(cleared()))
        forge_pr(sw, link, diffHeadSha=sha, headPipeline={"status": "SUCCESS"})
        check("the hub tells the pipeline wait once the fake forge shows the head green",
              until(lambda: bool(cleared())) and cleared() == [("w1", "pipeline")], str(cleared()))
        time.sleep(4)
        check("it tells it once, whatever the number of cycles", len(cleared()) == 1,
              str(cleared()))
        sw.chantier("wait", cr, "clear", "w1", *where)
        code, _ = sw.chantier("take", cr, "--note", "the pipeline is green", "--epoch", 1,
                            "--batch", batch, expect=None)
        check("the Foreman clears the wait and takes the CR back",
              code == 0 and cleared() == [("w1", "pipeline")]
              and all(x.get("cleared_at") for x in json.loads(
                  batch_file.read_text(encoding="utf-8"))["crs"][0]["waits"]),
              f"{code} {cleared()}")
    finally:
        for proc in reversed(procs):
            proc.stop()


def typed_waits(w: World) -> None:
    """CR-409: a CR records what it waits for; the hub tells the wait the forge shows met, once."""
    if ARGS.forge == "gitlab":
        return typed_waits_gitlab(w)
    note("\n## 16f. Typed waits: `wait add`, `status`, and the hub's `wait-cleared` line")
    sw = SurfaceWorld(w.root / "waits")
    sw.root.mkdir()
    sw.build()
    url = "https://github.com/acme/demo/pull/{}".format
    sha = "c" * 40
    batch_file = sw.state / "4-batch" / "batch.json"
    procs: list[BoardProc] = []

    def journal() -> list[dict]:
        path = sw.state / "forge-journal.jsonl"
        lines = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
        whole = []
        for x in lines:
            with contextlib.suppress(ValueError):
                whole.append(json.loads(x))
        return whole

    def cleared() -> list[tuple[str, str]]:
        return [(e["wait"], e["wait_type"]) for e in journal() if e["type"] == "wait-cleared@1"]

    def until(then, timeout: float = 40) -> bool:
        end = time.monotonic() + timeout
        while not (found := then()) and time.monotonic() < end:
            time.sleep(0.25)
        return bool(found)

    sw.chantier("init")
    sw.chantier("open", sw.prepare("Waits A1"), "--direct", "--slots", 1, *FROM_AGENTS_MD)
    d = json.loads(batch_file.read_text(encoding="utf-8"))
    cr, batch = d["crs"][0]["id"], d["id"]
    sw.chantier("foreman", "set", "uuid-chief", "--epoch", 1, "--batch", batch)
    d = json.loads(batch_file.read_text(encoding="utf-8"))
    d["crs"][0].update(pr=url(940), status="working", head=sha)
    batch_file.write_text(json.dumps(d, indent=2))
    where = ("--epoch", 1, "--batch", batch)
    sw.chantier("wait", cr, "add", "merge", "--note", "after the user", *where)
    sw.chantier("wait", cr, "add", "approval", "--note", "a review", *where)
    sw.chantier("wait", cr, "add", "pipeline", "--note", "the checks", *where)
    sw.chantier("wait", cr, "add", "answer", "--ref", "which port?", "--note", "ask", *where)
    waits = json.loads(batch_file.read_text(encoding="utf-8"))["crs"][0]["waits"]
    check("`wait add` records four waits, ids w1..w4, the forge ones on the CR's PR",
          [(x["id"], x["type"]) for x in waits]
          == [("w1", "merge"), ("w2", "approval"), ("w3", "pipeline"), ("w4", "answer")]
          and [x["link"] for x in waits[:3]] == [url(940)] * 3, str(waits))
    _, out = sw.chantier("status", "--batch", batch, expect=None)
    check("`status` shows the waits on the CR's row",
          any(cr in x and "| waits: merge, approval, pipeline, answer" in x for x in out), str(out))
    try:
        board = BoardProc(sw, "board", "--project", "demo", "--host", "127.0.0.1", "--port", 0,
                          cwd=sw.surface, env={"CHANTIER_HUB_TEST_TIMES": "1:4"})
        procs.append(board)
        board.line()
        forge_pr(sw, url(940), reviewDecision="APPROVED", headRefOid=sha)
        check("the hub tells the met approval and pipeline waits, and not the merge or the answer",
              until(lambda: len(cleared()) >= 2) and sorted(cleared()) == [("w2", "approval"),
                                                                           ("w3", "pipeline")],
              str(cleared()))
        time.sleep(4)
        check("it tells each once, whatever the number of cycles", len(cleared()) == 2,
              str(cleared()))
        _, out = sw.chantier("status", "--batch", batch, expect=None)
        check("`status` still lists the waits as open until the steering session clears them",
              any(cr in x and "| waits: merge, approval, pipeline, answer" in x for x in out),
              str(out))
        sw.chantier("wait", cr, "clear", "w2", *where)
        sw.chantier("wait", cr, "clear", "w3", *where)
        _, out = sw.chantier("status", "--batch", batch, expect=None)
        check("cleared waits leave the row", any(cr in x and "| waits: merge, answer" in x
                                                 for x in out), str(out))
        forge_pr(sw, url(940), state="MERGED", mergedAt="2026-11-20T10:00:00Z")
        check("the merge wait is told when the PR merges",
              until(lambda: ("w1", "merge") in cleared()), str(cleared()))
    finally:
        for proc in reversed(procs):
            proc.stop()


def surface_server(w: World) -> None:
    """CR-386: one surface server per surface and machine, `chantier board`, that is also the hub."""
    note("\n## 16e. The surface server: the board is the forge hub, `server.json` holds its state")
    sw = SurfaceWorld(w.root / "server")
    sw.root.mkdir()
    sw.build()
    url = "https://github.com/acme/demo/pull/{}".format
    git = sw.surface / ".git" / "chantier"
    quick = {"CHANTIER_HUB_TEST_TIMES": "1:4"}
    procs: list[BoardProc] = []
    batch_file = sw.state / "4-batch" / "batch.json"

    def state() -> dict:
        try:
            return json.loads((git / "server.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def until(then, timeout: float = 40) -> bool:
        end = time.monotonic() + timeout
        while not (found := then()) and time.monotonic() < end:
            time.sleep(0.25)
        return bool(found)

    def journal() -> list[dict]:
        path = sw.state / "forge-journal.jsonl"
        return ([json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()]
                if path.is_file() else [])

    def graphql() -> list[list[str]]:
        return [c for c in forge_calls(sw) if c[:2] == ["api", "graphql"]]

    def watcher(*args) -> BoardProc:
        procs.append(BoardProc(sw, "--project", "demo", "watch", *args, cwd=sw.surface, env=quick))
        return procs[-1]

    def ended(proc: BoardProc, timeout: float = 60) -> list[str]:
        try:
            proc.p.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            return ["(still running)"]
        got = []
        while (x := proc.line(2)) is not None:
            got.append(x)
        return got

    def start_board() -> BoardProc:
        procs.append(BoardProc(sw, "board", "--project", "demo", "--host", "127.0.0.1", "--port", 0,
                               cwd=sw.surface, env=quick))
        return procs[-1]

    def run_board(project: str, *extra) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, "-m", "chantier", "board", "--project", project,
                               "--host", "127.0.0.1", "--port", "0", *extra], cwd=sw.surface,
                              env={**sw.env, **quick}, capture_output=True, text=True,
                              encoding="utf-8", timeout=60)

    def hub_line() -> str:
        _, out = sw.chantier("status", expect=None)
        return next((x for x in out if x.startswith("forge hub:")), "")

    def server_pid() -> int | None:
        """The board's PID as `server.json` names it (a launcher may sit between us and it)."""
        return state().get("server", {}).get("pid")

    def kill_server() -> None:
        pid = server_pid()
        if pid and pid != os.getpid():  # the migration's record names this very process
            with contextlib.suppress(OSError):
                # a hard kill, no cleanup runs: SIGKILL on POSIX (the dead-entry takeover), and
                # `os.kill` ends the process outright on Windows
                os.kill(pid, getattr(signal, "SIGKILL", signal.SIGTERM))

    sw.chantier("init")
    sw.chantier("init", project="other")
    items = [sw.prepare(f"Server A{n}") for n in range(1, 4)]
    sw.chantier("open", *items, "--direct", "--slots", 2, *FROM_AGENTS_MD)
    d = json.loads(batch_file.read_text(encoding="utf-8"))
    a = [c["id"] for c in d["crs"]]
    sw.chantier("foreman", "set", "uuid-chief", "--epoch", 1, "--batch", d["id"])
    for c, number in zip(d["crs"], range(930, 933)):
        c["pr"] = url(number)
    batch_file.write_text(json.dumps(d, indent=2))
    record = batch_file.read_bytes()
    try:
        # 1. the board is the server and the hub
        board = start_board()
        link = Link(board.line())
        until(lambda: bool(state().get("hub", {}).get("projects")))
        found = state()
        pid = server_pid()
        check("`server.json` names the board's PID in `server` and in `hub`, and the key",
              isinstance(pid, int) and found.get("hub", {}).get("pid") == pid
              and found.get("key") == link.key, str(found))
        check("the git folder holds `server.json` and no `board.json` or `hub.json`",
              not (git / "board.json").exists() and not (git / "hub.json").exists(),
              str(list(git.iterdir())))
        check("`status` prints the server's PID as the hub",
              hub_line().startswith(f"forge hub: PID {pid}, the surface server"), hub_line())
        # 2. a second board answers with the first one's address, whichever project it serves
        for project, extra in (("demo", ()), ("other", ("--seat", "sess-o"))):
            p = run_board(project, *extra)
            check(f"a second `board {' '.join(extra)}` answers `board already running at`",
                  p.returncode == 0 and p.stdout.startswith("board already running at "),
                  p.stdout + p.stderr)
        # 3. a watcher started while the board runs is not the hub; the hub's line wakes it
        wa = watcher()
        start = wa.line()
        check("a watcher started while the board runs is not the hub",
              (start or "").startswith("watch: demo from cursor 0")
              and not (start or "").endswith(", the hub"), str(start))
        forge_pr(sw, url(930), state="MERGED", mergedAt="2026-11-16T10:00:00Z")
        got = ended(wa)
        check("a merge on the forge ends the watcher with the `forge saw merged` line",
              bool(got) and got[0].startswith(f"forge saw merged: {a[0]} {url(930)} into main at ")
              and f"order merged {a[0]}" in got[0], str(got))
        check("the journal holds the merge once, written by the hub",
              [(e["source"], e["type"], e["cr"]) for e in journal()] == [("hub", "merged@1", a[0])],
              str(journal()))
        # 4. the board stops: a watcher is the hub; the board returns: the watcher yields
        kill_server()
        board.stop()
        wb = watcher("--after", 1)
        start = wb.line()
        check("with the board stopped, a watcher is the hub", (start or "").endswith(", the hub"),
              str(start))
        check("`status` says the hub is a watcher",
              until(lambda: ", a watcher," in hub_line()), hub_line())
        board = start_board()
        link = Link(board.line())
        check("the board starts: the watcher yields and `status` names the server",
              until(lambda: server_pid() not in (None, pid)
                    and state().get("hub", {}).get("pid") == server_pid() and wb.p.poll() is None)
              and hub_line().startswith(f"forge hub: PID {server_pid()}, the surface server"),
              f"{state()} {hub_line()}")
        mark = len(graphql())
        time.sleep(6)
        reads = len(graphql()) - mark
        # one project has open PRs (`demo`), the hub's cycle is 1 s: one read per cycle, so 6 s hold
        # 6 reads, give or take the one a window edge adds or drops; a second reader would give 12
        check("the server reads the forge once per cycle for the one project with an open PR, "
              "and no second hub reads", 5 <= reads <= 7, f"{reads} reads in 6 s, 1 s cycles")
        # 5. the server is killed: a watcher takes the lock
        kill_server()
        board.stop()
        check("the server killed hard, a watcher takes the hub lock and `status` says so",
              until(lambda: ", a watcher," in hub_line(), 60), hub_line())
        forge_pr(sw, url(931), state="MERGED", mergedAt="2026-11-16T10:01:00Z")
        got = ended(wb)
        check("the next merge still wakes the watcher",
              bool(got) and got[0].startswith(f"forge saw merged: {a[1]} {url(931)} into main"),
              str(got))
        # 6. the migration of an earlier version's `board.json`
        for proc in procs:
            proc.stop()
        (git / "server.json").unlink(missing_ok=True)
        old = {"key": "k" * 43, "created": "2026-01-01T00:00:00Z",
               "running": {"pid": os.getpid(), "host": "127.0.0.1", "port": free_port(),
                           "version": "0.0.1", "served": "x",
                           "started": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}}
        (git / "board.json").write_text(json.dumps(old), encoding="utf-8")
        p = run_board("demo")
        said = p.stdout + p.stderr
        check("a live older board in `board.json` refuses the new one with its stop command, the "
              "key moves to `server.json` and `board.json` is gone",
              p.returncode != 0 and "then run board again" in said
              and state().get("key") == old["key"] and not (git / "board.json").exists(),
              f"{said} {state()}")
        # 7. the record is as it was, only read-only calls were made, the folder holds the state
        calls = forge_calls(sw)
        check("the batch record is unchanged and only read-only `api graphql` calls were made",
              batch_file.read_bytes() == record and bool(calls)
              and all(c[:2] == ["api", "graphql"] and not any(
                  x == "-X" or x.startswith("query=mutation") for x in c) for c in calls),
              str(calls[:1]))
        names = {x.name for x in git.iterdir() if not x.name.startswith("watch-")}
        check("`chantier/` holds only `server.json`, `server.json.lock`, `hub.lock`, `writer.lock`, `writer.wake` and `watch-*` entries",
              names <= {"server.json", "server.json.lock", "hub.lock", "writer.lock", "writer.wake"}, str(sorted(names)))
    finally:
        kill_server()
        for proc in reversed(procs):
            proc.stop()


def remote_board(w: World) -> None:
    note("\n## 16c. The remote board: the web board's server, behind a key")
    w.reset()
    (w.state / "seat.json").unlink(missing_ok=True)
    titles = ("Board working", "Board blocked", "Board queued <b>bold</b> title", "Board last")
    items = [prepare_cr(w, t)[1] for t in titles]
    _, with_bom = prepare_cr(w, "Board backlog item", "P2")
    for name in ("01-intent.md", "03-change-spec.md"):  # a Windows editor's byte-order mark
        path = with_bom / name
        path.write_bytes(b"\xef\xbb\xbf" + path.read_bytes())
    _, ready = prepare_cr(w, "Board ready item")
    w.chantier("triage", ready, "--ready")
    w.chantier("file", "Board inbox item")
    w.start(*items, "--direct", "--slots", 2, *FROM_AGENTS_MD)
    w.env["CHANTIER_BATCH"] = w.name
    w.chantier("seat", "take", "s-1", "--env", "remote", "--title", "[Remote] 💬 Proj · CoS",
               "--link", "link-s1")
    w.chantier("foreman", "set", "uuid-chief", "--epoch", 1)
    w.chantier("foreman", "transcript", "uuid-chief", "--epoch", 1)
    one, two, three, four = (c["id"] for c in w.batch()["crs"])
    for cr in (one, two):
        w.chantier("take", cr, "--epoch", 1)
        w.chantier("agents", "set", cr, f"agent-{cr}", "--epoch", 1)
        start_driver(w, cr)
    driver_round(w, one, "board1.py", "N = 1\n")
    w.chantier("handback", two, "blocked", "question: which colour?")
    slug = "".join(ch if ch.isalnum() else "-" for ch in str(w.work.resolve()))
    chief = w.root / "claude-projects" / slug / "uuid-chief.jsonl"  # the Chief of Staff's transcript
    chief.parent.mkdir(parents=True, exist_ok=True)
    chief.write_text(json.dumps({"type": "assistant", "timestamp": datetime.now(timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%S.000Z"), "message": {"id": "c1", "stop_reason": "end_turn", "model": "claude-sonnet-5-5", "usage": {
            "input_tokens": 10, "output_tokens": 100, "cache_read_input_tokens": 0}}}) + "\n")
    w.chantier("status", "--refresh", "--epoch", 1)
    own = json.loads((w.folder() / "STATUS.json").read_text(encoding="utf-8"))
    recorded = w.batch()
    porcelain = w.sh("git", "status", "--porcelain", "--", ".agents/changes")
    procs: list[BoardProc] = []

    def board(*args, cwd=None) -> BoardProc:
        procs.append(BoardProc(w, *args, cwd=cwd))
        return procs[-1]

    try:
        # 1. the start lines: a free port, the key in the link, nothing else on a loopback address
        first = board("board", "--host", "127.0.0.1", "--port", 0, "--seat", "s-1")
        line = first.line()
        link = Link(line)
        port = link.port
        check(
            "`board` on a loopback address with `--port 0` prints the picked port and the link with "
            "its key, and nothing else",
            link.ok
            and port > 0
            and link.over == w.state.resolve().as_posix()
            and first.line(0.5) is None,
            str(line),
        )
        # 2. the key
        key_file = Path(w.sh("git", "rev-parse", "--path-format=absolute", "--git-common-dir")) \
            / "chantier" / "server.json"
        check("the key is kept in the git folder's `chantier/server.json`",
              key_file.is_file() and json.loads(key_file.read_text(encoding="utf-8"))["key"] == link.key,
              str(key_file))
        refused = [fetch(port, p)[0] for p in ("/", "/api/board", "/js/main.js",
                                               "/api/v1/projects/x/file?path=a.md")]
        check("with no key `/`, `/api/board`, a static file and a file answer 401", refused == [401] * 4,
              str(refused))
        code, head, _ = fetch(port, f"/?k={link.key}")
        cookie = head.get("set-cookie", "")
        check("`/?k=<key>` answers 303 with the cookie (HttpOnly, SameSite=Strict) and a relative "
              "`Location` with no `k`",
              code == 303 and head.get("location") == "./" and f"chantier_board={link.key}" in cookie
              and "HttpOnly" in cookie and "SameSite=Strict" in cookie, f"{code} {head}")
        code, head, _ = fetch(port, "/?k=wrong")
        check("a wrong key answers 401 and sets no cookie", code == 401 and "set-cookie" not in head,
              str(code))
        code, head, _ = fetch(port, "/caf%C3%A9%20dir/x?k=" + link.key + "&q=a%20b%C3%A9")
        where = head.get("location", "")
        check("the 303 is relative and keeps a query with spaces and non-ASCII letters, encoded",
              code == 303 and where.startswith("./x?") and "k=" not in where
              and " " not in where and "%C3%A9" in where.split("?", 1)[1], where)
        code, head, _ = fetch(port, f"/?k={link.key}", "DELETE")
        check("`DELETE` with the good key answers 405 and no cookie",
              code == 405 and "set-cookie" not in head, f"{code} {head}")
        code, head, _ = fetch(port, f"/?k={link.key}", "PUT")
        check("`PUT` with only `?k` answers 401 (a write needs the cookie or the header) and no cookie",
              code == 401 and "set-cookie" not in head, f"{code} {head}")
        code, _, _ = fetch(port, "/?k=wrong", "PUT")
        check("`PUT` with a bad key answers 401", code == 401, str(code))
        code, _, _ = fetch(port, "/api/board", headers={"X-Chantier-Board-Key": link.key})
        check("the key in the `X-Chantier-Board-Key` header opens the API, with no cookie", code == 200)
        # 3. the page and the frame
        code, head, page = fetch(port, "/", headers=link.cookie)
        policy = head.get("content-security-policy", "")
        check("`GET /` with the cookie is HTML in UTF-8, its policy `script-src 'self'` with no "
              "`unsafe-inline`, nothing sniffed",
              code == 200 and head["content-type"] == "text/html; charset=utf-8"
              and "script-src 'self'" in policy and "unsafe-inline" not in policy
              and head["x-content-type-options"] == "nosniff", f"{code} {head}")
        code, head, _ = fetch(port, "/js/main.js", headers=link.cookie)
        etag = head.get("etag", "")
        check("`js/main.js` answers as text/javascript with an ETag",
              code == 200 and head["content-type"].startswith("text/javascript") and etag, str(head))
        check("the policy allows scripts, styles, images and fetches from `'self'` only",
              all(f"{d} 'self'" in policy for d in ("script-src", "style-src", "img-src", "connect-src"))
              and "http" not in policy and "*" not in policy, policy)
        wanted = ["/js/main.js", *re.findall(r'(?:href|src)="([^"]+)"', page.decode())]
        seen, bad = set(), []
        while wanted:
            name = "/" + wanted.pop().lstrip("/")
            if name in seen or not name.endswith((".js", ".css")):
                continue
            seen.add(name)
            code, head, body = fetch(port, name, headers=link.cookie)
            kind = "text/css" if name.endswith(".css") else "text/javascript"
            if code != 200 or not head.get("content-type", "").startswith(kind):
                bad.append((name, code, head.get("content-type")))
            for ref in re.findall(r"from '(\.[^']+)'", body.decode()):
                wanted.append(posixpath.normpath(f"{name.rsplit('/', 1)[0]}/{ref}"))
        check("every module and stylesheet the page loads answers 200 with its JavaScript or CSS type",
              bool(seen) and not bad, str(bad))
        code, _, _ = fetch(port, "/js/main.js", headers={**link.cookie, "If-None-Match": etag})
        check("a static file asked again with its ETag answers 304", code == 304, str(code))
        # 4. the API
        code, _, api = op(port, link, "board.get")
        project = api["projects"][0]["id"] if api.get("projects") else ""
        check("`board.get`: one project, `surface: false`, the seat counted",
              code == 200 and api.get("board") is True and api["surface"] is False
              and len(api["projects"]) == 1 and api["seats"] == 1 and api["served"] == link.over, str(api))
        check("a board of an in-project folder has `writer: {state: off}`, no `autosync` key, and runs no writer",
              api.get("writer") == {"state": "off"} and "autosync" not in api
              and jget(port, link, sibling("autosync"))[0] == 404, str(api.get("writer")))
        settled_live(port, link, project)
        base = f"/api/v1/projects/{project}"
        asked = {"project": project}
        code, _, data = op(port, link, "project.state", asked)
        rows = {c["cr"]: c for c in (data.get("batch") or {}).get("crs", [])}
        labels = {c["cr"]: c["label"] for c in own["crs"]}
        check("`state` holds each CR of the batch with its `label` as STATUS.json says it, and the "
              "fields the views need",
              code == 200 and set(rows) == set(labels) and len(rows) == 4
              and all(rows[k]["label"] == v for k, v in labels.items())
              and all({"round_limit", "after", "chain_place", "base", "to_review", "updated", "branch"}
                      <= set(r) for r in rows.values())
              and {"asks_unread", "last_event_at"} <= set(api["projects"][0]),
              f"{code} {sorted(rows)}")
        check("the read data names `phase` (`coder r1`, `waits for the user`) and `next_to_start` on "
              "the queued CR of the lowest order with nothing to wait for, and on none once the "
              "budget is spent",
              rows[one]["phase"] == "coder r1" and rows[two]["phase"] == "waits for the user"
              and rows[three]["phase"] is None
              and [k for k, r in rows.items() if r["next_to_start"]] == [three], str(rows))
        batch_file = w.folder() / "batch.json"
        original = batch_file.read_bytes()
        before = batch_file.stat()
        batch_file.write_text(json.dumps({**json.loads(original), "budget_usd": 1, "spent_usd": 2}),
                              encoding="utf-8")
        _, _, spent = op(port, link, "project.state", asked)
        batch_file.write_bytes(original)
        os.utime(batch_file, ns=(before.st_atime_ns, before.st_mtime_ns))  # the rev fingerprints mtime
        check("with the budget spent no CR is next to start",
              not any(r["next_to_start"] for r in spent["batch"]["crs"]), str(spent["batch"]["crs"]))
        backlog = data.get("backlog", {})
        check("it holds the inbox, `P2` and `3-ready` items with their `grill`, and a title's markup "
              "comes back as text",
              "board-inbox-item" in [i["item"] for i in backlog.get("inbox", [])]
              and "board-backlog-item" in [i["item"] for i in backlog.get("P2", [])]
              and "board-ready-item" in [i["item"] for i in backlog.get("3-ready", [])]
              and all("grill" in i for k in ("inbox", "P2", "3-ready") for i in backlog.get(k, []))
              and "Board queued <b>bold</b> title" in {r["title"] for r in rows.values()}, str(backlog))
        check("a title written with a byte-order mark is cleaned of it",
              [i["title"] for i in backlog.get("P2", []) if i["item"] == "board-backlog-item"]
              == ["Board backlog item"],
              str(backlog.get("P2")))
        rev = data.get("rev", "")
        same = op(port, link, "project.state", {**asked, "rev": rev})
        check("`project.state` asked again with its `rev` answers `changed: false` with the same rev",
              rev and same[0] == 200 and same[2].get("changed") is False and same[2].get("rev") == rev,
              str(same[2])[:200])
        stale = op(port, link, "project.state", {**asked, "rev": "stale"})
        check("a stale `rev` gets the state again", stale[0] == 200 and "batch" in stale[2])
        # 5. the files (the folder's state is taken once the test files are in)
        spec_dir = w.at(w.cr(one)["path"]).relative_to(w.state).as_posix()
        picture = w.at(w.cr(one)["path"]) / "work" / "shot.png"
        picture.parent.mkdir(parents=True, exist_ok=True)
        picture.write_bytes(b"\x89PNG\r\n\x1a\n")
        lock = w.at(w.cr(one)["path"]) / ".lock"
        lock.write_text("x")
        before = folder_state(w.state)
        code, _, listing = op(port, link, "project.tree", {**asked, "path": spec_dir})
        names = [f["path"] for f in listing.get("files", [])]
        check("`tree` lists a CR folder's files, nested ones included, and no lock",
              code == 200 and f"{spec_dir}/03-change-spec.md" in names
              and f"{spec_dir}/work/shot.png" in names and f"{spec_dir}/.lock" not in names, str(names))
        spec_url = urllib.parse.quote(f"{spec_dir}/03-change-spec.md")
        code, head, text = fetch(port, f"{base}/file?path={spec_url}", headers=link.cookie)
        check("`file` gives the specification as text", code == 200 and b"Board working" in text
              and head["content-type"].startswith("text/plain"), str(head))
        code, head, _ = fetch(port, f"{base}/file?path=" + urllib.parse.quote(f"{spec_dir}/work/shot.png"),
                              headers=link.cookie)
        check("`file` gives an image with its type", code == 200 and head["content-type"] == "image/png",
              str(head))
        outside = [urllib.parse.quote(p) for p in ("../AGENTS.md", "../../AGENTS.md",
                                                   str(w.work / "AGENTS.md"), "nothing/here.md",
                                                   f"{spec_dir}/.lock")]
        check("`file` answers 404 for a path outside the planning folder, an absolute one, a missing "
              "one and a lock file",
              all(fetch(port, f"{base}/file?path={p}", headers=link.cookie)[0] == 404 for p in outside)
              and fetch(port, "/elsewhere", headers=link.cookie)[0] == 404, str(outside))
        # 6. costs and the rule for writes
        code, _, _ = op(port, link, "costs.recompute", asked)
        check("`costs.recompute` answers 202", code == 202, str(code))
        costs = settled_live(port, link, project)
        live = costs.get("live") or {}
        check("`costs.get` then gives a live figure equal to the one `status --refresh` recorded from "
              "the same transcripts",
              live.get("error") is None and live.get("spent_usd") is not None
              and abs(live["spent_usd"] - recorded["spent_usd"]) < 0.001, str(costs))
        shown = live.get("receipt") or {}
        check("the live figure carries the receipt: its split adds up to `spent_usd` within a cent",
              shown.get("split")
              and abs(sum(p["usd"] for p in shown["split"]) - live["spent_usd"]) <= 0.0101
              and "steering" in shown and "drivers" in shown, str(shown))
        code, _, _ = op(port, link, "costs.recompute", asked, {"Origin": "http://evil.example"})
        check("a call with the cookie from a foreign `Origin` answers 401", code == 401, str(code))
        code, _, _ = fetch(port, "/api/v1/call/costs.recompute", "POST",
                           {"X-Chantier-Board-Key": link.key, "Origin": "http://evil.example",
                            "Content-Type": "application/json"}, json.dumps(asked).encode())
        check("a call with the key in the header from a foreign `Origin` is accepted", code == 202,
              str(code))
        check("`PUT` answers 405", fetch(port, "/api/board", "PUT", link.cookie)[0] == 405)
        live_once(w, one)
        # 7. nothing written
        check("nothing was written in the planning folder, its files, sizes and times, nor its git status",
              folder_state(w.state) == before
              and w.sh("git", "status", "--porcelain", "--", ".agents/changes") == porcelain,
              str(set(folder_state(w.state).items()) ^ set(before.items())))
        board_writes(w, port, link, project)
        lock.unlink()
        board_prs(w, port, link, project, (one, two, three, four))
        held = board_api(w, port, link, project)
        # 8. a second board, a port held
        again = [sys.executable, "-m", "chantier", "board", "--host", "127.0.0.1", "--port", str(port)]
        p = subprocess.run([*again, "--seat", "s-1"], cwd=w.work, env=w.env, capture_output=True,
                           text=True, encoding="utf-8", timeout=30)
        check("a second `board` on the same address says it is running, with the same link, exit 0",
              p.returncode == 0 and p.stdout.strip()
              == f"board already running at http://127.0.0.1:{port}/?k={link.key}", p.stdout + p.stderr)
        # 9. the seat moves: the board stops by itself, a new one has the same link
        w.chantier("seat", "take", "s-2", "--over", "s-1")
        check("when the seat moves the board stops by itself, exit 0", exits(first) == 0)
        check("the board stopping closes the open WebSocket with 1001 (going away)",
              close_code(held) == 1001, str(close_code(held)))
        second = board("board", "--host", "127.0.0.1", "--port", port, "--seat", "s-2")
        again_link = Link(second.line())
        check("a board for the new seat starts on the same port with the same link",
              again_link.ok and again_link.port == port and again_link.key == link.key
              and op(port, link, "board.get")[2].get("seats") == 1)
        p = subprocess.run([*again, "--seat", "s-3"], cwd=w.work, env=w.env, capture_output=True,
                           text=True, encoding="utf-8", timeout=30)
        check("`board --seat s-3` registers the seat on the running board",
              p.returncode == 0 and p.stdout.startswith("board already running at ")
              and op(port, link, "board.get")[2].get("seats") == 2, p.stdout + p.stderr)
        w.chantier("seat", "take", "s-3", "--over", "s-2")
        fetch(port, "/api/board", headers=link.cookie)  # the board checks its seats at each request
        check("the seat moving from s-2 to s-3 keeps the board running",
              second.p.poll() is None and fetch(port, "/api/board", headers=link.cookie)[0] == 200)
        # one board per repository, whatever the port: `--port 0` with a live board reuses it
        p = subprocess.run([sys.executable, "-m", "chantier", "board", "--host", "127.0.0.1", "--port",
                            "0"], cwd=w.work, env=w.env, capture_output=True, text=True,
                           encoding="utf-8", timeout=30)
        check("a second `board --port 0` with a live board of the repository prints `board already "
              "running at` its link, exit 0, and starts none",
              p.returncode == 0
              and p.stdout.strip() == f"board already running at http://127.0.0.1:{port}/?k={link.key}",
              p.stdout + p.stderr)
        p = subprocess.run([sys.executable, "-m", "chantier", "board", "--host", "127.0.0.1", "--port",
                            "0", "--ui", "none", "--seat", "s-1"], cwd=w.work, env=w.env,
                           capture_output=True, text=True, encoding="utf-8", timeout=30)
        check("`board --ui none` on a running board prints `board already running at` its link and "
              "the `--ui not applied` line, exits 0, and the board still serves the shipped client",
              p.returncode == 0
              and p.stdout.splitlines()[:1] == [f"board already running at http://127.0.0.1:{port}/?k={link.key}"]
              and p.stdout.splitlines()[-1] == "--ui not applied: a board already serves this surface; stop it to change what it serves"
              and fetch(port, "/js/main.js", headers=link.cookie)[0] == 200, p.stdout + p.stderr)
        check("the live board's `server` entry in `server.json` names its PID, port and version, "
              "and `/api/board` answers the same PID",
              json.loads(key_file.read_text(encoding="utf-8")).get("server", {}).get("port") == port
              and json.loads(key_file.read_text(encoding="utf-8"))["server"]["pid"]
              == jget(port, link, "/api/board")[2].get("pid"), key_file.read_text(encoding="utf-8"))
        w.chantier("seat", "take", "s-4", "--over", "s-3")
        check("the board whose seats are gone stops by itself, with no request of ours",
              exits(second) == 0)
        check("a board that stops removes its `server` and `hub` entries from `server.json`, the "
              "key stays",
              not {"server", "hub"} & set(json.loads(key_file.read_text(encoding="utf-8")))
              and json.loads(key_file.read_text(encoding="utf-8"))["key"] == link.key)
        # `--ui`: another folder, none, a folder with no page
        ui_dir = w.root / "own-ui"
        ui_dir.mkdir(exist_ok=True)
        (ui_dir / "index.html").write_text("<!doctype html><p>own-ui-marker</p>", encoding="utf-8")
        (ui_dir / "app.js").write_text("export const mine = 1;\n", encoding="utf-8")
        own_ui = board("board", "--host", "127.0.0.1", "--port", 0, "--ui", ui_dir)
        own_link = Link(own_ui.line())
        code, head, page = fetch(own_link.port, "/", headers=own_link.cookie)
        check("`board --ui <folder>` serves that folder's `index.html` at `/` with the policy, its "
              "`app.js` as JavaScript, none of the shipped client's files, and the API",
              own_link.ok and code == 200 and b"own-ui-marker" in page
              and "script-src 'self'" in head.get("content-security-policy", "")
              and fetch(own_link.port, "/app.js", headers=own_link.cookie)[1].get("content-type", "")
              .startswith("text/javascript")
              and fetch(own_link.port, "/js/main.js", headers=own_link.cookie)[0] == 404
              and fetch(own_link.port, "/api/board", headers={"X-Chantier-Board-Key": own_link.key})[0] == 200,
              f"{code} {head}")
        own_ui.stop()
        no_ui = board("board", "--host", "127.0.0.1", "--port", 0, "--ui", "none")
        no_link = Link(no_ui.line())
        code, _, page = fetch(no_link.port, "/", headers=no_link.cookie)
        check("`board --ui none` answers 404 with the line naming the API's doc outside `/api/`, the "
              "API answers, and `board.get` over HTTP gives 200",
              no_link.ok and code == 404
              and page.decode().strip() == "this server serves no UI: see docs/server-api.md"
              and fetch(no_link.port, "/api/board", headers={"X-Chantier-Board-Key": no_link.key})[0] == 200
              and op(no_link.port, no_link, "board.get")[0] == 200, f"{code} {page}")
        no_ui.stop()
        empty = w.root / "empty-ui"
        empty.mkdir(exist_ok=True)
        recorded_before = key_file.read_text(encoding="utf-8")
        p = subprocess.run([sys.executable, "-m", "chantier", "board", "--host", "127.0.0.1", "--port",
                            "0", "--ui", str(empty)], cwd=w.work, env=w.env, capture_output=True,
                           text=True, encoding="utf-8", timeout=30)
        check("`board --ui` naming a folder with no `index.html` exits 1 with the one line, prints no "
              "start line and records no board",
              p.returncode == 1 and not p.stdout.strip()
              and p.stderr.strip() == f"error: --ui {empty}: not a folder with an index.html: give a "
              "folder of static files, or none"
              and key_file.read_text(encoding="utf-8") == recorded_before, p.stdout + p.stderr)
        # a board started by hand (no `--seat`) records a session's seat and follows none
        late = board("board", "--host", "127.0.0.1", "--port", 0)
        late_link = Link(late.line())
        p = subprocess.run([sys.executable, "-m", "chantier", "board", "--host", "127.0.0.1", "--port",
                            str(late_link.port), "--seat", "s-4"], cwd=w.work, env=w.env,
                           capture_output=True, text=True, encoding="utf-8", timeout=30)
        registered = op(late_link.port, late_link, "board.get")[2].get("seats")
        w.chantier("seat", "take", "s-5", "--over", "s-4")
        # the board checks its seats at each request: the same `gone()` a watch would call
        fetch(late_link.port, "/api/board", headers=late_link.cookie)
        check("a board started by hand registers a session's seat and keeps serving when that "
              "session goes",
              late_link.ok and p.returncode == 0 and p.stdout.startswith("board already running at ")
              and registered == 1
              and late.p.poll() is None
              and fetch(late_link.port, "/api/board", headers=late_link.cookie)[0] == 200,
              p.stdout + p.stderr)
        late.stop()  # the next checks expect no live board
        code, _ = w.chantier("live", "--once", expect=None)
        check("once the board has stopped, `live --once` exits 4: no board runs for this surface",
              code == 4 and "no board runs for this surface" in w.last_stderr, w.last_stderr)
        # a port held by another program, with no live board to reuse
        with socket.socket() as held:
            held.bind(("127.0.0.1", 0))
            held.listen()
            busy = held.getsockname()[1]
            p = subprocess.run([sys.executable, "-m", "chantier", "board", "--host", "127.0.0.1",
                                "--port", str(busy)], cwd=w.work, env=w.env, capture_output=True,
                               text=True, encoding="utf-8", timeout=30)
        check("a port held by another program exits 4 with one `board not started` line naming the port"
              " and `--port`",
              p.returncode == 4 and len(p.stderr.strip().splitlines()) == 1
              and p.stderr.startswith("error: board not started: ") and not p.stdout.strip()
              and f"port {busy}" in p.stderr and "--port" in p.stderr, p.stderr)
        # 10. a wider address says so; the clock
        wide = board("board", "--host", "0.0.0.0", "--port", 0)
        head, warning = wide.line(), wide.line()
        if (warning or "").startswith("on this machine: "):  # printed when the main link is not loopback
            warning = wide.line()
        check("an address beyond this machine prints the second line, the link in the first",
              Link(head).ok and (warning or "").startswith("board: listens on the local network (0.0.0.0)"),
              f"{head} / {warning}")
        wide.stop()
        # the default stays on this machine, and a key replaced while the board runs revokes the old link
        mine = board("board", "--port", 0)
        mine_head = mine.line()
        mine_link = Link(mine_head)
        check("`board --port 0` with no `--host` and no `chantier.yaml` listens on 127.0.0.1: its first "
              "line is the link on 127.0.0.1, it opens, `server.json` records that host, and no "
              "other line follows",
              mine_link.ok and (mine_head or "").startswith("board on http://127.0.0.1:")
              and fetch(mine_link.port, f"/?k={mine_link.key}")[0] == 303
              and json.loads(key_file.read_text(encoding="utf-8"))["server"]["host"] == "127.0.0.1"
              and mine.line(0.5) is None, str(mine_head))
        p = subprocess.run([sys.executable, "-m", "chantier", "board", "--new-key"], cwd=w.work,
                           env=w.env, capture_output=True, text=True, encoding="utf-8", timeout=30)
        renewed = re.match(r"^board already running at http://127\.0\.0\.1:(\d+)/\?k=(\S+)$",
                           p.stdout.strip())
        new_key = renewed[2] if renewed else ""
        old_code = fetch(mine_link.port, f"/?k={mine_link.key}")[0]
        new_code, new_head, _ = fetch(mine_link.port, f"/?k={new_key}")
        check("a second `board --new-key` on a running board prints `board already running at` a link "
              "with another key: the first link answers 401, the new one 303 with a cookie of "
              "`Max-Age=2592000`",
              p.returncode == 0 and renewed is not None and new_key != mine_link.key
              and old_code == 401 and new_code == 303
              and "Max-Age=2592000" in new_head.get("set-cookie", ""), p.stdout + p.stderr)
        mine.stop()
        yaml_net = w.work / "chantier.yaml"
        yaml_net.write_text("board:\n  host: network\n", encoding="utf-8")
        net = board("board", "--port", 0)
        net_head, net_next = net.line(), net.line()
        net_link = Link(net_head)
        recorded_host = json.loads(key_file.read_text(encoding="utf-8")).get("server", {}).get("host")
        if net_link.ok and net_link.host != "127.0.0.1":  # (a) the runner has a network address
            local = re.match(r"^on this machine: http://127\.0\.0\.1:(\d+)/\?k=(\S+)$", net_next or "")
            third = net.line()
            ok = (fetch(net_link.port, f"/?k={net_link.key}")[0] == 303 and recorded_host == "0.0.0.0"
                  and local is not None and fetch(int(local[1]), f"/?k={local[2]}")[0] == 303
                  and (third or "").startswith("board: listens on the local network ("))
        else:  # (b) no network address: this machine only, and it says so
            ok = (net_link.ok and net_link.host == "127.0.0.1"
                  and fetch(net_link.port, f"/?k={net_link.key}")[0] == 303
                  and net_next == "board: no local network address found; on this machine only")
        check("`board.host: network` in chantier.yaml with `--port 0`: either the link on a network "
              "address (`server.json` records 0.0.0.0, then the `on this machine:` link, then the "
              "`board: listens on the local network (` line), or the link on 127.0.0.1 and the "
              "`no local network address found` line",
              ok, f"{net_head} / {net_next} / {recorded_host}")
        net.stop()
        yaml_net.unlink()
        timed = board("board", "--host", "127.0.0.1", "--port", 0, "--clock", "2026-01-02T03:04:05Z")
        tlink = Link(timed.line())
        _, thead, tapi = op(tlink.port, tlink, "board.get")
        check("`--clock` fixes `now` in the answers and in `X-Chantier-Now`",
              tapi.get("now") == "2026-01-02T03:04:05Z"
              and thead.get("x-chantier-now") == "2026-01-02T03:04:05Z", str(tapi.get("now")))
        timed.stop()
        # 11. chantier.yaml
        yaml = w.work / "chantier.yaml"
        for attempt in range(2):  # a port free a moment ago can be taken by another unit: one retry
            other = free_port()
            yaml.write_text(f"board:\n  port: {other}\n", encoding="utf-8")
            configured = board("board")
            line = configured.line()
            if line is not None and line.startswith(f"board on http://127.0.0.1:{other}/?k="):
                break
            configured.stop()
        check("`board.port` of chantier.yaml sets the port of a board with no option",
              line is not None and line.startswith(f"board on http://127.0.0.1:{other}/?k="), str(line))
        configured.stop()
        for bad, wrong in (("port: abc", "port"), ("color: red", "color")):
            yaml.write_text(f"board:\n  host: network\n  {bad}\n", encoding="utf-8")
            code, out = w.chantier("playbook", expect=None)
            problem = "chantier.yaml:3: board: " in "\n".join(out) and wrong in "\n".join(out)
            code_board, _ = w.chantier("board", "--port", 0, expect=None)
            check(f"an invalid `board` ({bad}) is reported by `playbook` with its line, and the board "
                  "refuses to start with it",
                  code == 2 and problem and code_board == 2 and "chantier.yaml:3: board: " in w.last_stderr,
                  f"{out} / {w.last_stderr}")
        yaml.write_text("board:\n  host: 127.0.0.1\n", encoding="utf-8")
        code, out = w.chantier("playbook", expect=None)
        code_board, _ = w.chantier("board", "--port", 0, expect=None)
        check("a fixed `board.host` (127.0.0.1) in chantier.yaml is refused by `playbook` and by "
              "`board`, exit 2, with the message pointing to `--host`",
              code == 2 and "--host" in "\n".join(out) and code_board == 2 and "--host" in w.last_stderr,
              f"{out} / {w.last_stderr}")
        yaml.unlink()
        side = w.work / "chantier.yml"  # `.yml` alone is read like `.yaml`
        side.write_text("board:\n  host: network\n  port: abc\n", encoding="utf-8")
        code, out = w.chantier("playbook", expect=None)
        check("`chantier.yml` alone is read like `chantier.yaml`: its problem names it, with its line",
              code == 2 and "chantier.yml:3: board: " in "\n".join(out), str(out))
        yaml.write_text("board:\n  port: 1\n", encoding="utf-8")
        code, out = w.chantier("playbook", expect=None)
        check("`chantier.yaml` and `chantier.yml` together exit 2, naming both",
              code == 2 and "chantier.yaml and chantier.yml are both present: keep one" in "\n".join(out),
              str(out))
        side.unlink()
        yaml.unlink()
    finally:
        for proc in procs:
            proc.stop()
        (w.work / "chantier.yaml").unlink(missing_ok=True)
        (w.work / "chantier.yml").unlink(missing_ok=True)
        w.env.pop("CHANTIER_BATCH", None)
        for seat in ("s-5", "s-2", "s-1"):
            w.chantier("seat", "leave", seat, expect=None)
        w.reset()


def live_once(w: World, working: str) -> None:
    """`chantier live --once` on each transport against the running board: the working CR in the
    tasks, `working 1` in the header, and nothing written (git status, journal)."""
    journal = w.state / "forge-journal.jsonl"
    before = (journal.read_bytes() if journal.is_file() else b"",
              w.sh("git", "status", "--porcelain", "--", ".agents/changes"))
    for extra in ((), ("--transport", "http")):
        code, out = w.chantier("live", "--once", *extra, expect=None)
        shown = "\n".join(out)
        cells = [x.split("│") for x in out]  # the Tasks panel is the last one on its rows
        tasks = [c[-2] for c in cells if len(c) > 2 and c[-2].strip().startswith(f"{working} ")]
        check(f"`{' '.join(('live', '--once', *extra))}` exits 0 and shows the working CR in "
              "Tasks and `working 1` in the header",
              code == 0 and "working 1" in shown and bool(tasks), shown + w.last_stderr)
    after = (journal.read_bytes() if journal.is_file() else b"",
             w.sh("git", "status", "--porcelain", "--", ".agents/changes"))
    check("`live --once` wrote nothing: the planning folder's git status and its journal are unchanged",
          after == before, str(after != before))


def seat_handover(w: World) -> None:
    """Two Chief of Staff sessions on one repository: the seat, the refused take-over, the
    take-over on purpose, and the new session steering the same direct batch."""
    note("\n## 16b. The seat and the hand-over between two Chief of Staff sessions")
    b_env = {"CLAUDE_CODE_SESSION_ID": "uuid-chief-b"}
    _, item = prepare_cr(w, "Seat work")
    w.reset()
    w.start(item, "--direct", "--slots", 1, *FROM_AGENTS_MD)
    w.env["CHANTIER_BATCH"] = w.name
    w.chantier("seat", "take", "sess-a", "--env", "remote", "--title", "[Remote] 💬 Proj · CoS",
               "--link", "link-a")
    seat = json.loads((w.state / "seat.json").read_text(encoding="utf-8"))
    check("`seat take` writes one file with the session, transcript, env, title and link, no date",
          set(seat) == {"session", "transcript", "env", "title", "link"}
          and seat["transcript"] == "uuid-chief", str(seat))
    w.chantier("seat", "take", "sess-b", env=b_env, expect=2)
    check("a second session is refused the seat, and told to take it over only on the user's word",
          "sess-a" in w.last_stderr and "--over" in w.last_stderr, w.last_stderr)
    w.chantier("seat", "take", "sess-b", "--over", "sess-x", env=b_env, expect=2)
    check("`--over` must name the session that holds the seat", "sess-a" in w.last_stderr,
          w.last_stderr)
    w.chantier("seat", "take", "sess-b", "--over", "sess-a", "--env", "remote", env=b_env)
    d = w.batch()
    check("`seat take --over` hands the seat and the batch's Chief of Staff transcript over, "
          "keeping the earlier one",
          d["chief_transcript"] == "uuid-chief-b"
          and d["chief_transcripts"] == ["uuid-chief", "uuid-chief-b"], str(d))
    _, out = w.chantier("seat", "get")
    check("`seat get` names the new holder", out[0].startswith("seat sess-b "), str(out))
    w.chantier("seat", "leave", "sess-a", expect=2)
    w.chantier("foreman", "set", "uuid-chief-b", "--epoch", 1, env=b_env)
    w.chantier("foreman", "transcript", "uuid-chief-b", "--epoch", 1, env=b_env)
    check("the new session claims the epoch and the steering stays direct",
          w.batch()["steering"] == "direct", str(w.batch()["steering"]))
    w.chantier("status", "--refresh", "--epoch", 0, expect=3)
    slug = "".join(ch if ch.isalnum() else "-" for ch in str(w.work.resolve()))
    projects = w.root / "claude-projects" / slug
    projects.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    call = json.dumps({"type": "assistant", "timestamp": now, "message": {
        "id": "seat", "stop_reason": "end_turn", "model": "claude-sonnet-5-5", "usage": {
            "input_tokens": 10, "output_tokens": 100, "cache_read_input_tokens": 0}}}) + "\n"
    for name in ("uuid-chief", "uuid-chief-b"):  # each Chief of Staff session has its own file
        if not (projects / f"{name}.jsonl").is_file():
            (projects / f"{name}.jsonl").write_text(call, encoding="utf-8")
    code, _ = w.chantier("cost")
    check("`cost` prices two Chief of Staff sessions, blocked by neither's file", code == 0,
          w.last_stderr)
    code, _ = drop_then_cancel(w, w.batch()["crs"][0]["id"], 1, env=b_env)
    check("the automatic pause at the last cancel prices two Chief of Staff sessions, blocked by "
          "neither's file", code == 0 and w.batch()["status"] == "paused"
          and not w.batch()["summary"][0].startswith("Spent: unknown"), w.last_stderr)
    code, _ = w.chantier("close", "--batch", w.name, "--yes", env=b_env)
    check("`close` prices two Chief of Staff sessions, blocked by neither's file", code == 0,
          w.last_stderr)
    w.chantier("seat", "leave", "sess-b", env=b_env)
    _, out = w.chantier("seat", "get")
    check("`seat leave` frees the seat", out == ["seat none"], str(out))
    w.env.pop("CHANTIER_BATCH", None)
    w.reset()


def direct_batch(w: World) -> None:
    """A batch steered by the Chief of Staff itself, from `open` to `close`, priced with one steering
    row and a Chief of Staff line that leaves the steering window out; then a Foreman takes it over."""
    note("\n## 16. Direct mode: the Chief of Staff steers the batch")
    slug = "".join(ch if ch.isalnum() else "-" for ch in str(w.work.resolve()))
    chief = w.root / "claude-projects" / slug / "uuid-chief.jsonl"
    kept = chief.read_text(encoding="utf-8") if chief.is_file() else None
    sub = chief.with_suffix("") / "subagents"
    t0, t1 = "2026-03-01T00:00:00Z", "2026-03-01T01:00:00Z"  # the opening, then the claim

    def at(minutes: int) -> str:
        return (datetime.fromisoformat(t1.replace("Z", "+00:00")) + timedelta(minutes=minutes)
                ).strftime("%Y-%m-%dT%H:%M:%S.000Z")

    def msg(mid: str, stamp: str) -> str:
        return json.dumps({"type": "assistant", "timestamp": stamp, "message": {
            "id": mid, "stop_reason": "end_turn", "model": "claude-sonnet-5-5", "usage": {
                "input_tokens": 10, "output_tokens": 1_000_000, "cache_read_input_tokens": 20_000,
                "cache_creation": {"ephemeral_1h_input_tokens": 2_000}}}}) + "\n"

    def edit(**fields) -> None:
        state = w.folder() / "batch.json"
        state.write_text(json.dumps({**w.batch(), **fields}))

    def money(out: list[str], start: str) -> float:
        line = next(ln for ln in out if ln.startswith(start))
        return float(re.search(r"\$(\d+\.\d+)", line)[1])

    code, out = w.chantier("preflight", env={"CLAUDE_CODE_ENTRYPOINT": "cli"}, expect=2)
    check("preflight refuses a terminal session while a Foreman must start", code == 2
          and out[0].startswith("P1 FAIL"), str(out))
    code, out = w.chantier("preflight", "--direct", env={"CLAUDE_CODE_ENTRYPOINT": "cli"})
    check("`preflight --direct` passes P1 on any Claude Code entry point and leaves P2 out",
          code == 0 and out[0].startswith("P1 ok") and "P2" not in "\n".join(out), str(out))
    _, item = prepare_cr(w, "Direct work")
    _, extra = prepare_cr(w, "Direct extra")
    _, extra_after = prepare_cr(w, "Direct extra after the takeover")
    _, later = prepare_cr(w, "Direct after the pause")
    _, later2 = prepare_cr(w, "Direct after the pause, too")
    _, rel_item = prepare_cr(w, "Direct release")
    w.reset()
    code, out = w.chantier("open", item, "--direct", *FROM_AGENTS_MD, env={"CLAUDE_CODE_SESSION_ID": ""},
                           expect=2)
    check("`open --direct` needs the Chief of Staff's own session id", code == 2
          and "session id" in w.last_stderr, w.last_stderr)
    w.start(item, "--direct", "--slots", 1, *FROM_AGENTS_MD)
    w.env["CHANTIER_BATCH"] = w.name
    check("`open --direct` records the steering, and says to steer it yourself",
          w.batch()["steering"] == "direct" and w.last_out[1].endswith("then steer it yourself")
          and "steering direct" in w.last_out[0]
          and "Steering: direct" in (w.folder() / "brief.md").read_text(encoding="utf-8"),
          str(w.last_out))
    _, out = w.chantier("status")
    check("`status` and STATUS.md show who steers and the shape",
          " steering direct (the Chief of Staff) shape parallel " in out[0]
          and "steered by the Chief of Staff (direct mode) · independent PRs (parallel)" in
          (w.folder() / "STATUS.md").read_text(encoding="utf-8")
          and json.loads((w.folder() / "STATUS.json").read_text(encoding="utf-8"))["steering"]
          == "direct", str(out))
    kept_batch = w.batch()
    state = w.folder() / "batch.json"
    for fields, words, what in (({"mode": "series"}, " shape series ", "series for a --mode series batch"),
                                ({"mode": "stack"}, " shape stack ", "stack for a --mode stack batch"),
                                ({"steering": None}, " steering unknown ", "steering unknown, not foreman, "
                                 "when batch.json has no steering")):
        state.write_text(json.dumps({k: v for k, v in {**kept_batch, **fields}.items() if v is not None}))
        _, out = w.chantier("status")
        check(f"`status` says {what}", words in out[0], str(out))
    w.chantier("order", "note", w.batch()["crs"][0]["id"], "--note", "a batch.json without a steering")
    check("STATUS.json says null for a steering it does not know",
          json.loads((w.folder() / "STATUS.json").read_text(encoding="utf-8"))["steering"] is None
          and "steering unknown" in (w.folder() / "STATUS.md").read_text(encoding="utf-8"))
    state.write_text(json.dumps(kept_batch))
    w.chantier("foreman", "set", "uuid-chief", "--epoch", 1)
    w.chantier("foreman", "transcript", "uuid-chief", "--epoch", 1)
    edit(created=t0, foreman_claims=[{"transcript": "uuid-chief", "since": t1}])
    code, _ = w.chantier("order", "qa", "--note", "try it", expect=2)
    check("`order qa` is refused on a running direct batch",
          "a running direct batch takes no QA" in w.last_stderr and len(w.batch()["crs"]) == 1,
          w.last_stderr)

    # The heartbeat says something true: the minutes since the last `status --refresh --epoch`.
    def hb_line(out: list[str]) -> str:
        return re.search(r"heartbeat (.*?) spent ", out[0])[1]

    def hb_minutes(text: str) -> int:
        return int(re.match(r"(\d+) min", text)[1])

    def events(kind: str) -> int:
        return sum(1 for ln in (w.folder() / "events.jsonl").read_text(encoding="utf-8").splitlines()
                   if json.loads(ln).get("kind") == kind)

    check("a batch that never woke prints `heartbeat never`", w.batch()["heartbeat"] is None
          and hb_line(w.chantier("status")[1]) == "never")
    _, out = w.chantier("status", "--refresh", "--epoch", 1, expect=None)
    check("a batch's first wake prints `heartbeat 0 min` with no gap, and logs its event",
          hb_line(out) == "0 min" and w.batch()["heartbeat"] and events("heartbeat") == 1, str(out))
    old = (datetime.now(timezone.utc) - timedelta(minutes=45)).strftime("%Y-%m-%dT%H:%M:%SZ")
    edit(heartbeat=old)
    _, out = w.chantier("status")
    check("`status` prints the minutes since the last wake", abs(hb_minutes(hb_line(out)) - 45) <= 1,
          str(out))
    _, out = w.chantier("status", "--refresh", expect=None)
    check("`status --refresh` with no epoch moves no heartbeat and still prints the true age",
          w.batch()["heartbeat"] == old and abs(hb_minutes(hb_line(out)) - 45) <= 1
          and events("heartbeat") == 1, str(out))
    _, out = w.chantier("status", "--refresh", "--epoch", 1, expect=None)
    check("a wake records the heartbeat and prints the gap since the wake before",
          w.batch()["heartbeat"] != old and events("heartbeat") == 2
          and re.fullmatch(r"0 min \((44|45|46) min since the last\)", hb_line(out)) is not None,
          str(out))
    _, out = w.chantier("status")
    check("the status after a wake prints `heartbeat 0 min`", hb_line(out) == "0 min", str(out))
    before = (w.folder() / "batch.json").read_bytes()
    code, _ = w.chantier("status", "--stop-heartbeat", "--epoch", 2, expect=3)
    check("recording the stop with a stale epoch is refused and changes nothing",
          code == 3 and (w.folder() / "batch.json").read_bytes() == before, w.last_stderr)
    code, out = w.chantier("status", "--stop-heartbeat", "--epoch", 1)
    _, out = w.chantier("status")
    check("recording the stop makes `status` print `heartbeat stopped`, logs one event, and shows "
          "the mark in STATUS.json",
          hb_line(out) == "stopped" and events("heartbeat_stopped") == 1
          and json.loads((w.folder() / "STATUS.json").read_text(encoding="utf-8"))
          ["heartbeat_stopped"], str(out))
    _, out = w.chantier("status", "--refresh", expect=None)
    check("a refresh with no epoch leaves the stop in place", hb_line(out) == "stopped", str(out))
    _, out = w.chantier("status", "--refresh", "--epoch", 1, expect=None)
    check("the next wake clears the stop and prints its gap", w.batch()["heartbeat_stopped"] is None
          and re.fullmatch(r"0 min \(\d+ min since the last\)", hb_line(out)) is not None, str(out))
    _, out = w.chantier("order", "add", "--note", str(extra))
    check("`order add` queues a CR on a running direct batch",
          any("queued" in ln for ln in out) and len(w.batch()["crs"]) == 2
          and w.batch()["crs"][1]["status"] == "queued", str(out))
    moved = w.batch()["crs"][1]["id"]
    _, out = w.chantier("order", "drop", moved, "--note", "P3")
    left = w.batch()["crs"][1]
    check("the CR added to the running direct batch can be dropped again, to the backlog P3",
          left["status"] == "cancelled" and left["left_to"] == "2-backlog/P3"
          and re.fullmatch(r"2-backlog/P3/\d+-[\w-]+", left["path"]) is not None
          and any(ln.startswith(f"dropped {moved} to 2-backlog/P3: ") for ln in out), str(out))
    shelf_dir = w.state / left["path"]
    formerly = json.loads((shelf_dir / "formerly.json").read_text("utf-8")) if (
        shelf_dir / "formerly.json").is_file() else {}
    check("a CR moved to the backlog keeps its folder and its work, a `formerly.json`, and its "
          "STATUS.md says where it went",
          formerly.get("cr") == moved and formerly.get("batch") == w.name
          and (shelf_dir / "03-change-spec.md").is_file()
          and "⚪ dropped to 2-backlog/P3" in (shelf_dir / "STATUS.md").read_text("utf-8"),
          str(formerly))
    moved_number = int(moved.removeprefix("CR-"))
    kept_branch = bool(w.sh("git", "branch", "--list", left["branch"]))
    _, out = w.chantier("order", "add", "--note", left["path"])
    back = [c for c in w.batch()["crs"] if c["id"] == moved]
    joins = (f"{moved} joins with its branch {left['branch']} and no PR" if kept_branch
             else f"{moved} joins fresh: its branch {left['branch']} is gone")
    check("the CR dropped to the backlog comes back by `order add` under its number, as the same "
          "entry, queued, in `1-pending`, with no `formerly.json`, and the `joins` line says "
          "what became of its branch",
          len(back) == 1 and back[0]["status"] == "queued" and "left_to" not in back[0]
          and back[0]["path"].startswith("4-batch/1-pending/")
          and re.fullmatch(rf"4-batch/1-pending/0*{moved_number}-[\w-]+", back[0]["path"])
          and not (w.state / back[0]["path"] / "formerly.json").exists()
          and not shelf_dir.exists() and joins in out, str(out))
    w.chantier("order", "drop", moved, "--note", "trash")
    check("the CR that came back is dropped to the trash again, as before",
          w.cr(moved)["status"] == "cancelled" and w.cr(moved)["left_to"] == "6-trash",
          str(w.cr(moved)))
    fm = Foreman(w, epoch=1)
    fm.turn()
    cr = w.batch()["crs"][0]["id"]
    check("the Chief of Staff, as steering session, starts the Driver as a Foreman does",
          fm.started == [cr] and w.cr(cr)["status"] == "working", str(fm.started))
    sub.mkdir(parents=True, exist_ok=True)

    # outside the window: an earlier session, then a call after the opening and before the claim;
    # inside it: two calls of the steering and three of its Driver
    def wake(stamp: str) -> str:
        return json.dumps({"type": "user", "timestamp": stamp, "message": {"content": "go"}}) + "\n"

    def uses(mid: str, stamp: str, *blocks) -> str:  # a call whose record carries tool uses
        return json.dumps({"type": "assistant", "timestamp": stamp, "message": {
            "id": mid, "model": "claude-sonnet-5-5", "content": list(blocks), "usage": {
                "input_tokens": 10, "output_tokens": 1_000_000, "cache_read_input_tokens": 20_000,
                "cache_creation": {"ephemeral_1h_input_tokens": 2_000}}}}) + "\n"

    def boundary(stamp: str) -> str:
        return json.dumps({"type": "system", "subtype": "compact_boundary", "timestamp": stamp}) + "\n"

    answers = {"type": "tool_use", "name": "Edit", "input": {"file_path": "x/02-answers.md"}}
    writer_use = {"type": "tool_use", "name": "Agent", "input": {"subagent_type": "chantier:spec-writer"}}
    # a steering turn that only names a specification (a Driver's prompt) and reads one: it stays
    # on the steering row, not on the grill line
    names_spec = {"type": "tool_use", "name": "Agent", "input": {
        "subagent_type": "chantier:cr-driver", "prompt": "work from x/03-change-spec.md"}}
    reads_spec = {"type": "tool_use", "name": "Read", "input": {"file_path": "x/03-change-spec.md"}}
    # before the opening: a compaction and a grill turn of an earlier batch (in the whole session
    # only); in the window: two steering calls, a turn that only names a specification, a grill turn, a spec-writer turn, two compactions,
    # and a call repeated after the first of them (same message id: priced once)
    chief.write_text(
        msg("c-old", "2000-01-01T00:00:00.000Z") + boundary("2000-01-01T00:00:01.000Z")
        + wake("2000-01-01T00:00:02.000Z") + uses("c-oldg", "2000-01-01T00:00:03.000Z", answers)
        + wake("2026-03-01T00:09:00.000Z") + msg("c-pre", "2026-03-01T00:10:00.000Z") + wake(at(5)) + msg("c-in1", at(10))
        + msg("c-in2", at(20)) + wake(at(21)) + uses("c-g1", at(22), answers)
        + wake(at(23)) + uses("c-g2", at(24), writer_use) + boundary(at(25)) + boundary(at(26))
        + msg("c-g2", at(27))
        + wake(at(28)) + uses("c-nm", at(29), names_spec, reads_spec), encoding="utf-8")
    driver = sub / "agent-agent-1.jsonl"
    driver.write_text("".join(msg(f"d{i}", at(15)) for i in range(3)), encoding="utf-8")
    driver.with_suffix("").with_suffix(".meta.json").write_text(
        json.dumps({"agentType": "cr-driver"}), encoding="utf-8")
    driver_round(w, cr, "direct.py", "DIRECT = True\n")
    w.ready(cr, w.cr(cr)["pr"])
    fm.turn()
    w.chantier("order", "merged", cr, "--epoch", fm.epoch)  # the steering session's own merge
    check("in a direct batch the steering session's `order merged --epoch` of the last CR pauses",
          w.batch()["status"] == "paused", str(w.batch()["status"]))
    fm.turn()
    check("a direct batch runs from open to the pause", fm.paused and w.batch()["status"] == "paused",
          str(w.batch()["status"]))
    _, out = w.chantier("cost")
    cost_out = out
    ROW, STEER, GRILL, WHOLE = ("Chief of Staff, steering the batch: ",
                                "Chief of Staff, steering the batch (outside the budget): ",
                                "Chief of Staff, grill and specifications with the user (outside the budget): ",
                                "Chief of Staff, whole session: ")
    lines = [ln for ln in out if ln.startswith(("Foreman", ROW, "Driver"))]
    printed = [int(a.replace(".", "")) for ln in lines for a in re.findall(r"\$(\d+\.\d{3}) \(", ln)]
    check("`cost` shows one 'Chief of Staff, steering the batch' row without the grill turns, no "
          "'Foreman' row, and the lines add up",
          [ln.split(":")[0] for ln in lines] == ["Chief of Staff, steering the batch", "Driver cr-driver"]
          and "(3 calls," in lines[0] and "(3 calls," in lines[1]
          and out[0].split()[1] == f"${sum(printed) / 1000:.3f}"
          and not any("Chief of Staff (steering)" in ln for ln in out), str(out))
    steering = money(out, ROW)
    one = steering / 3  # a call of the Chief of Staff's transcript
    a, b, whole = money(out, STEER), money(out, GRILL), money(out, WHOLE)
    paren = re.search(r"\(\$(\d+\.\d{2}) of it in the batch's spend\)",
                      next(ln for ln in out if ln.startswith(WHOLE)))
    inside = float(paren.group(1)) if paren else -1.0
    check("the Chief of Staff's lines add up: the steering row's three calls (one of them names and reads a specification: steering), one steering call "
          "before the claim, the two grill and specification turns (the repeated call priced once), "
          "and the whole session holds the steering window and names the part in the batch's spend",
          abs(a - one) <= 0.02 and abs(b - 2 * one) <= 0.02
          and abs((whole - inside) - 5 * one) <= 0.03
          and abs(inside - float(out[0].split()[1][1:])) <= 0.01 and whole >= steering
          and "(1 calls)" in next(ln for ln in out if ln.startswith(STEER))
          and "(2 calls, 0 spec-writers, 0 spec critics)" in next(ln for ln in out if ln.startswith(GRILL))
          and abs(w.batch()["spent_usd"] - float(out[0].split()[1][1:])) <= 0.01
          and abs(float(out[0].split()[1][1:]) - 2 * steering) <= 0.02,
          f"{out} (steering ${steering})")
    check("the whole-session line counts the compactions of the window, not the one before it",
          "2 compactions since the batch opened" in next(ln for ln in out if ln.startswith(WHOLE)),
          str(out))
    _, by_cr = w.chantier("cost", "--by", "cr")
    check("`cost --by cr` names the steering role by the mode: the Chief of Staff, no 'foreman:'",
          by_cr[1].startswith("Chief of Staff, steering the batch, and its own subagents: $")
          and not any(ln.startswith("foreman:") for ln in by_cr), str(by_cr))
    _, out = w.chantier("cost", "--summary")
    check("the summary splits the steering under its own name", out[1].startswith(
          "Chief of Staff, steering the batch $") and "Foreman" not in out[1]
          and any(ln.startswith(GRILL) for ln in out), str(out))
    # no line that starts with "Driver" names the steering session; its figure is the steering row's
    named = ("chief-of-staff", "Chief of Staff", "Foreman")
    _, pause_summary = w.chantier("cost", "--summary")
    status_md = (w.folder() / "STATUS.md").read_text(encoding="utf-8").splitlines()
    every = out + cost_out + w.batch()["summary"] + status_md + pause_summary
    check("a direct batch: no line that starts with `Driver` names the steering session, in `cost`, "
          "`cost --summary`, the pause summary and STATUS.md's Cost; the steering figure is the row's",
          not any(re.match(r"(- )?Driver", ln) and any(n in ln for n in named) for ln in every)
          and abs(float(re.match(r"Chief of Staff, steering the batch \$(\d+\.\d\d)", out[1])[1])
                  - steering) <= 0.006, str(every))
    # the spec-writer and spec-critic transcripts on the grill line are pytest's (test_cost_reading.py)
    # a subagent no Driver owns is the steering session's own: its own line, not a Driver's
    own = sub / "agent-agent-own.jsonl"
    own.write_text("".join(msg(f"o{i}", at(31)) for i in range(2)), encoding="utf-8")
    own.with_suffix("").with_suffix(".meta.json").write_text(
        json.dumps({"agentType": "Explore"}), encoding="utf-8")
    _, out = w.chantier("cost")
    check("`cost` puts a subagent the steering session ran itself on its own line, not on a Driver",
          any(ln.startswith("Chief of Staff's own subagents") and "(2 calls," in ln for ln in out)
          and not any(ln.startswith("Driver") and "Explore" in ln for ln in out), str(out))
    own.unlink()
    own.with_suffix("").with_suffix(".meta.json").unlink()
    # a paused batch takes any number of new CRs and stays paused; the first `take` runs it again
    paused_at = w.batch()["paused"]
    summary = w.batch()["summary"]
    for n, folder in enumerate((later, later2), start=3):
        w.chantier("order", "add", "--note", str(folder))
        b = w.batch()
        b = w.batch()  # the paused batch's order add checks are close_refusals' alone
        assert b["status"] == "paused" and len(b["crs"]) == n
    cr2, cr3 = w.batch()["crs"][2]["id"], w.batch()["crs"][3]["id"]
    check("both new CRs are in the paused batch", {cr2, cr3} <= {c["id"] for c in w.batch()["crs"]})
    check("a CR added after the move to the backlog gets a number above the moved one's",
          int(cr2.removeprefix("CR-")) > moved_number and int(cr3.removeprefix("CR-")) > moved_number,
          f"{cr2} {cr3} {moved}")
    fm.turn()
    b = w.batch()
    check("the first `take` sets the paused direct batch running again",
          b["status"] == "running" and "paused" not in b and "summary" not in b
          and cr2 in fm.started and w.cr(cr2)["status"] == "working", str(fm.started))
    kinds = [json.loads(e)["kind"] for e in
             (w.folder() / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    check("the first `take` says the batch was paused, and the event log has `reopen` before "
          "that `take`", "was paused: running again" in "\n".join(fm.facts)
          and "reopen" in kinds and kinds[::-1].index("take") < kinds[::-1].index("reopen"),
          str(kinds[-8:]))
    check("that `take` ends with the `watch: not running` line, not indented, after the Driver "
          "prompt block", bool(fm.facts) and fm.facts[-1].startswith(
              "watch: not running: for the Chief of Staff, start in the background: ")
          and " watch --after " in fm.facts[-1] and "--batch" not in fm.facts[-1]
          and sum(x.startswith("watch: not running") for x in fm.facts) == 1, str(fm.facts[-3:]))
    for cr_n, name in ((cr2, "direct2.py"), (cr3, "direct3.py")):
        if cr_n not in fm.started:
            fm.turn()
        check(f"the reopened direct batch starts {cr_n}", cr_n in fm.started
              and w.cr(cr_n)["status"] == "working", str(fm.started))
        driver_round(w, cr_n, name, f"DIRECT = {name!r}\n")
        w.ready(cr_n, w.cr(cr_n)["pr"])
        fm.turn()
        w.chantier("order", "merged", cr_n)
        fm.turn()
    check("the reopened direct batch pauses again", fm.paused and w.batch()["status"] == "paused",
          str(w.batch()["status"]))
    os.utime(chief, None)  # the Chief of Staff's own session is written by the very call that closes
    driver_kept = driver.read_text(encoding="utf-8")
    runs(driver, driver_kept)  # a Driver with a step under way is not
    code, _ = w.chantier("close", "--batch", w.name, "--yes", expect=2)
    check("`close` still sees a Driver that runs, on a direct batch, and not the Chief of Staff's "
          "own transcript, which ends on a tool call", "transcript uuid-chief agent-agent-1 "
          "still runs" in w.last_stderr and "transcript uuid-chief still" not in w.last_stderr
          and "transcript uuid-chief cannot" not in w.last_stderr, w.last_stderr)
    driver.write_text(driver_kept, encoding="utf-8")
    os.utime(chief, None)
    clear_agents(w)
    code, out = w.chantier("close", "--batch", w.name, "--yes")
    check("`close` is not blocked by the Chief of Staff's own fresh transcript", code == 0
          and not (w.folder() / "batch.json").exists(), str(out))

    # a Foreman takes the batch over: the steering switches, the old epoch is refused
    w.reset()
    shutil.rmtree(sub)
    _, other = prepare_cr(w, "Direct then Foreman")
    w.start(other, "--direct", "--slots", 1, *FROM_AGENTS_MD)
    w.env["CHANTIER_BATCH"] = w.name
    w.chantier("foreman", "set", "uuid-chief", "--epoch", 1)
    w.chantier("foreman", "transcript", "uuid-chief", "--epoch", 1)
    edit(created=t0, foreman_claims=[{"transcript": "uuid-chief", "since": t1}])
    w.chantier("order", "add", "--release", "--note", str(rel_item))
    check("`order add --release` is accepted on a running direct batch",
          len(w.batch()["crs"]) == 2 and w.batch()["crs"][1].get("kind") == "release",
          str(w.last_out))
    w.chantier("foreman", "set", "local_foreman_next", "--epoch", 2)
    w.chantier("foreman", "transcript", "uuid-foreman", "--epoch", 2)
    foreman_file = chief.with_name("uuid-foreman.jsonl")  # the Foreman's own, seeded in this unit
    if not foreman_file.is_file():
        foreman_file.write_text(msg("fm-1", at(40)), encoding="utf-8")
    d = w.batch()
    code, _ = w.chantier("status", "--refresh", "--epoch", 1, expect=3)
    check("a later epoch from another transcript switches the steering to Foreman, and refuses "
          "the old epoch", d["steering"] == "foreman" and code == 3
          and [c["transcript"] for c in d["foreman_claims"]] == ["uuid-chief", "uuid-foreman"]
          and any(json.loads(e)["kind"] == "steering" for e in
                  (w.folder() / "events.jsonl").read_text(encoding="utf-8").splitlines()), str(d))
    _, out = w.chantier("status")
    check("`status` now says Foreman", " steering Foreman shape parallel " in out[0], str(out))
    w.chantier("order", "add", "--note", str(extra_after))
    check("a batch steered by a Foreman takes added work", len(w.batch()["crs"]) == 3)
    _, out = w.chantier("cost")
    labels = [ln.split(":")[0] for ln in out if ln.startswith(("Foreman:", "Chief of Staff, steering the batch:"))]
    check("each steering session is priced under its own name", labels == [
        "Chief of Staff, steering the batch", "Foreman"] or labels == [
        "Foreman", "Chief of Staff, steering the batch"],
          str(out))
    _, by_cr = w.chantier("cost", "--by", "cr")
    check("`cost --by cr` of a taken-over direct batch names both steering sessions",
          any(ln.startswith("Chief of Staff, steering the batch, and the Foreman, with their own "
                            "subagents: $") for ln in by_cr)
          and not any(ln.startswith("foreman:") for ln in by_cr), str(by_cr))

    # the Chief of Staff takes the batch back from the Foreman: direct again, both stints priced
    now_dt = datetime.now(timezone.utc)
    later_stamp = (now_dt + timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%S.000Z")  # after claim 3
    chief.write_text(msg("c-out", at(-30)) + msg("c-s1", at(10)) + msg("c-s2", later_stamp),
                     encoding="utf-8")  # c-out: between the opening and the first claim
    foreman_file.write_text(msg("fm-1", at(40)), encoding="utf-8")
    foreman_kept = foreman_file.read_text(encoding="utf-8")
    w.chantier("foreman", "set", "uuid-chief", "--epoch", 3)
    code, out = w.chantier("foreman", "transcript", "uuid-chief", "--epoch", 3)
    d = w.batch()
    steering_events = [json.loads(e) for e in (w.folder() / "events.jsonl").read_text(
        encoding="utf-8").splitlines() if json.loads(e).get("kind") == "steering"]
    check("the Chief of Staff's claim of the next number makes the Foreman batch direct again, says "
          "so, logs a second steering event, and records the returning transcript as a claim",
          d["steering"] == "direct" and any(ln.startswith("steering direct:") for ln in out)
          and [e["steering"] for e in steering_events] == ["foreman", "direct"]
          and [c["transcript"] for c in d["foreman_claims"]] == ["uuid-chief", "uuid-foreman",
                                                                 "uuid-chief"], str(d))
    w.chantier("status", "--refresh", "--epoch", 2, expect=3)
    check("the replaced Foreman's number is refused", True)
    _, out = w.chantier("status")
    check("`status` and STATUS.md say direct again", " steering direct (the Chief of Staff) " in out[0]
          and "direct mode" in (w.folder() / "STATUS.md").read_text(encoding="utf-8"), str(out))
    _, out = w.chantier("cost")
    own = next(ln for ln in out if ln.startswith("Chief of Staff, steering the batch: "))
    old = next(ln for ln in out if ln.startswith("Foreman: "))
    outside = [ln for ln in out if ln.startswith(
        "Chief of Staff, steering the batch (outside the budget)")]
    check("`cost` prices the Chief of Staff's two windows in the batch's spend and the Foreman's "
          "window between them; only the call before the first claim is outside the budget",
          "(2 calls," in own and "(1 calls," in old
          and len(outside) == 1 and "(1 calls)" in outside[0], str(out))
    probe_costs = ("import json,sys;from pathlib import Path;from chantier.core.repo import Repo;"
                   "from chantier.board.costs import compute;r=Path(sys.argv[1]);"
                   "print(json.dumps(compute(Repo(r,r/'.git',{},None,None))['receipt']['outside']"
                   "['steering']))")
    done = subprocess.run([sys.executable, "-c", probe_costs, str(w.work)], env=w.env, cwd=w.work,
                          capture_output=True, text=True, encoding="utf-8")
    figure = json.loads(done.stdout or "null") or {}
    check("the board's receipt holds the same steering outside the budget as `cost`'s line, on "
          "the direct batch that was a Foreman's", bool(outside) and figure.get("calls") == 1
          and f"${figure.get('usd', 0):.2f} since the batch opened" in outside[0],
          done.stdout + done.stderr)
    foreman_file.write_text(foreman_kept + call_line("Bash"), encoding="utf-8")
    os.utime(chief, None)
    code, out = w.chantier("close", "--batch", w.name, expect=None)
    text = "\n".join(out) + "\n" + w.last_stderr
    check("`close` does not name the replaced Foreman's transcript as a cause, which ends on a tool "
          "call (listed apart)", "transcript uuid-foreman still runs" not in text
          and "uuid-foreman cannot be read" not in text, text)
    foreman_file.write_text(foreman_kept, encoding="utf-8")

    # a Foreman-opened batch switched to direct with a CR working under the old Foreman
    w.reset()
    _, started = prepare_cr(w, "Foreman then direct")
    _, queued = prepare_cr(w, "Foreman then direct, queued")
    w.start(started, "--slots", 1, *FROM_AGENTS_MD)
    w.env["CHANTIER_BATCH"] = w.name
    w.chantier("order", "add", "--note", str(queued))
    w.chantier("foreman", "set", "local_foreman_one", "--epoch", 1)
    w.chantier("foreman", "transcript", "uuid-foreman", "--epoch", 1)
    fm = Foreman(w, epoch=1)
    fm.turn()
    cr = w.batch()["crs"][0]["id"]
    driver_round(w, cr, "switch.py", "SWITCH = True\n")
    pr, branch, tree = w.cr(cr)["pr"], w.cr(cr)["branch"], w.cr(cr)["worktree"]
    agent = w.cr(cr)["agent"]
    old_driver = foreman_file.with_suffix("") / "subagents" / f"agent-{agent}.jsonl"
    old_driver.parent.mkdir(parents=True, exist_ok=True)
    ended = "".join(msg(f"od{i}", at(15)) for i in range(2))
    runs(old_driver, ended)
    code, out = w.chantier("close", "--batch", w.name, expect=None)
    text = "\n".join(out) + "\n" + w.last_stderr
    check("`close` (no --yes) shows the old Driver running while its file ends on a tool call",
          f"agent-{agent} still runs" in text, text)
    old_driver.write_text(ended, encoding="utf-8")
    code, out = w.chantier("close", "--batch", w.name, expect=None)
    text = "\n".join(out) + "\n" + w.last_stderr
    check("`close` shows the old Driver ended once its file ends on a final reply",
          f"agent-{agent} still runs" not in text
          and f"agent-{agent} cannot be read" not in text, text)
    w.chantier("foreman", "set", "uuid-chief", "--epoch", 2)
    code, out = w.chantier("foreman", "transcript", "uuid-chief", "--epoch", 2)
    check("the claim switches that batch to direct", w.batch()["steering"] == "direct"
          and any(ln.startswith("steering direct:") for ln in out), str(out))
    w.chantier("agents", "set", cr, "-", "--epoch", 2)
    w.chantier("handoff", cr)
    code, _ = w.chantier("take", cr, "--note", "resume: switch to direct mode", "--epoch", 2)
    queued_cr = w.batch()["crs"][1]
    check("the restart path is accepted; the CR keeps its branch, worktree and PR, and the queued CR "
          "stays queued", code == 0 and w.cr(cr)["status"] == "working" and w.cr(cr)["pr"] == pr
          and w.cr(cr)["branch"] == branch and w.cr(cr)["worktree"] == tree
          and Path(tree).is_dir() and queued_cr["status"] == "queued", str(w.cr(cr)))
    probe = ("import json,sys;from pathlib import Path;from chantier.core.repo import Repo;"
             "from chantier.board.state import project_state;r=Path(sys.argv[1]);"
             "print(json.dumps(project_state('p',Repo(r,r/'.git',{},None,None),False,None)['batch']"
             "['steering']))")
    done = subprocess.run([sys.executable, "-c", probe, str(w.work)], env=w.env, cwd=w.work,
                          capture_output=True, text=True, encoding="utf-8")
    check("the board's state says the batch is direct", json.loads(done.stdout or "null") == "direct",
          done.stdout + done.stderr)
    w.env.pop("CHANTIER_BATCH", None)
    w.reset()
    if kept is None:
        chief.unlink()
    else:
        chief.write_text(kept, encoding="utf-8")


def foreman_in_a_worktree(w: World) -> None:
    note("\n## 17. A Foreman started in a worktree stops before it claims its epoch")
    prepared = prepare_cr(w, "Worktree guard")[1]
    w.reset()
    w.start(str(prepared), *FROM_AGENTS_MD)
    w.env["CHANTIER_BATCH"] = w.name
    linked = w.root / "foreman-session"
    w.sh("git", "worktree", "add", "--quiet", "--detach", str(linked), "origin/main")
    fm = Foreman(w, epoch=1)
    check("in a linked worktree the worktree check stops", fm.worktree_check("local_wt", linked) is False)
    d = w.batch()
    check("no epoch claimed, no CR taken, and the Chief of Staff hears it",
          not d.get("foreman") and all(c["status"] == "queued" for c in d["crs"])
          and not fm.started and len(fm.asked) == 1 and fm.asked[0].startswith("blocked "),
          str(fm.asked))
    code, out = w.chantier("asks", expect=None)
    check("the ask is recorded", code == 0 and any("worktree" in ln for ln in out), str(out))
    w.chantier("asks", "--read", "all")
    check("on the main checkout the same worktree check claims the epoch",
          fm.worktree_check("local_main") is True and w.batch()["foreman"] == "local_main")
    w.sh("git", "worktree", "remove", "--force", str(linked))


def status_files(w: World) -> None:
    c = w.cr("CR-104")
    folder = w.state / c["path"]
    text = (folder / "STATUS.md").read_text(encoding="utf-8")
    check("a CR's STATUS.md says where it stands and links back to its batch",
          all(part in text for part in ("**Now:**", "**Next:**", "## Progress", "- [x] Round 1",
                                        "- [x] Long gate", "- [x] Shipped", "- [x] Handed back",
                                        "## Documents", "[specification](03-change-spec.md)",
                                        "## Where", f"[{w.name}](../../STATUS.md)")), text)
    view = json.loads((folder / "STATUS.json").read_text(encoding="utf-8"))
    check("its STATUS.json says the same, with more",
          view["cr"] == "CR-104" and view["state"] == "ready" and view["step"] == "Notify"
          and view["pr"]["url"] == c["pr"] and view["steps"], str(view))
    board = (w.state / "STATUS.md").read_text(encoding="utf-8")
    batch = (w.folder() / "STATUS.md").read_text(encoding="utf-8")
    check("the status cell gives the pastille, the state, the step and the round",
          "🟢 ready to merge Notify 1/3" in board and "🟢 ready to merge Notify 1/3" in batch, board)
    index = json.loads((w.state / "STATUS.json").read_text(encoding="utf-8"))
    rows = [r for b in index["batches"] for r in b["crs"]]
    own = json.loads((w.folder() / "STATUS.json").read_text(encoding="utf-8"))["crs"]
    check("the index gives each batch its heartbeat and pending orders, and each CR row its "
          "blocked reason, silent time and folder, relative to .agents/changes/ in the batch's file too",
          index["schema"] == 3 and rows
          and all({"heartbeat", "orders_pending"} <= set(b) for b in index["batches"])
          and [b["mode"] for b in index["batches"] if b["batch"] == w.name]
          == [json.loads((w.folder() / "STATUS.json").read_text(encoding="utf-8"))["mode"]]
          and all({"blocked", "silent_minutes", "folder"} <= set(r) for r in rows + own)
          and all((w.state / r["folder"] / "STATUS.json").is_file()
                  for r in rows + own if r["folder"]), str(rows[:1]))
    check("a CR that is not working has no silent time, and none is blocked here",
          all(r["silent_minutes"] is None and r["blocked"] is None
              for r in rows if r["state"] == "ready"), str(rows))
    links = [(w.state, ln) for ln in re.findall(r"\]\(([^)h][^)]*)\)", board)]
    links += [(w.folder(), ln) for ln in re.findall(r"\]\(([^)h][^)]*)\)", batch)]
    check("every link of the board and the batch resolves",
          links and all((start / ln).exists() for start, ln in links), str(links))


def board_index(w: World, d: dict) -> None:
    """The index the CR board reads: the merged and trashed CRs, their totals and the limit."""
    path = w.state / "STATUS.json"
    index = json.loads(path.read_text(encoding="utf-8"))
    merged = {c["id"] for c in d["crs"] if c["status"] == "merged"}
    got = {e["cr"]: e for e in index["merged"]}
    check("the index lists the merged CRs with their state, batch, PR, cost, time and folder",
          merged <= set(got) and index["merged_total"] >= len(merged)
          and all(got[i]["state"] == "merged" and got[i]["batch"] == w.name
                  and got[i]["pr"] and got[i]["cost_usd"] is not None
                  and re.fullmatch(r"20\d\d-\d\d-\d\dT\d\d:\d\d:\d\dZ", got[i]["when"])
                  and (w.state / got[i]["path"] / "STATUS.json").is_file()
                  for i in merged), str(index["merged"]))
    check("the index lists the trashed CR, with a total",
          any(e["cr"] == "CR-103" and e["state"] == "cancelled" for e in index["trashed"])
          and index["trashed_total"] >= 1, str(index["trashed"]))
    merged_before = index["merged_total"]
    stage = w.state / "5-archives"
    stage.mkdir(exist_ok=True)
    made = []
    for n in range(60):  # older than any real archive, none with a STATUS.json
        folder = stage / f"250101-{n // 60:02d}{n % 60:02d}-padding-{n}"
        folder.mkdir()
        made.append(folder)
        (folder / "01-intent.md").write_text(f"# Padding {n}\n", encoding="utf-8")
    w.chantier("file", "Board index probe")  # rewrites the index
    index = json.loads(path.read_text(encoding="utf-8"))
    whens = [e["when"] for e in index["merged"]]
    bare = [e for e in index["merged"] if e["cr"] is None]
    check("the index keeps the last 50 merged CRs, newest first, and counts them all",
          len(index["merged"]) == 50 and index["merged_total"] == merged_before + 60
          and whens == sorted(whens, reverse=True) and not any("padding" in e["path"] for e in index["merged"][:len(merged)]),
          f"{len(index['merged'])} of {index['merged_total']}")
    check("a folder without a STATUS.json gives its title and null for the rest",
          all(e["title"].startswith("Padding") and e["state"] is None and e["pr"] is None
              and e["cost_usd"] is None and e["batch"] is None for e in bare) and bare,
          str(bare[:1]))
    for folder in made:
        shutil.rmtree(folder)
    # the spec-writer's state, read from the folder: none, specifying, then specified
    probe = next(r for r in index["backlog"] if r["title"].startswith("Board index probe"))
    item = w.state / probe["path"]

    refreshes = [0]

    def spec_of() -> object:
        refreshes[0] += 1
        w.chantier("file", f"Spec state refresh {refreshes[0]}")  # rewrites the index
        again = json.loads(path.read_text(encoding="utf-8"))["backlog"]
        return next(r for r in again if r["path"] == probe["path"]).get("spec")

    check("an inbox item with no specification has no spec state", probe.get("spec") is None
          and spec_of() is None, str(probe))
    (item / "work").mkdir(exist_ok=True)
    (item / "work" / "specifying").write_text("2026-11-07T10:00:00Z agent-1\n", encoding="utf-8")
    check("work/specifying makes the item `specifying`, in STATUS.json and STATUS.md",
          spec_of() == "specifying" and "specifying" in (w.state / "STATUS.md").read_text(
              encoding="utf-8"), "")
    (item / "03-change-spec.md").write_text("# Spec\n", encoding="utf-8")
    check("a specification still being written stays `specifying`", spec_of() == "specifying", "")
    (item / "work" / "specifying").unlink()
    check("the specification without work/specifying makes it `specified`", spec_of() == "specified"
          and "specified" in (w.state / "STATUS.md").read_text(encoding="utf-8"), "")


def age_sessions(w: World, seconds: int = 600) -> None:
    """The session files of the fixture, last written `seconds` ago: `close` reads their times."""
    then = time.time() - seconds
    for base in ("claude-projects", "copilot-home"):
        for f in (w.root / base).rglob("*"):
            if f.is_file():
                os.utime(f, (then, then))


def turn_line(kind: str, block: dict, stop: str | None = None) -> str:
    """One `user` or `assistant` record of a Claude transcript, as `close` reads its end."""
    message = {"role": kind, "content": [block]}
    if kind == "assistant":
        message["stop_reason"] = stop
    return json.dumps({"type": kind, "message": message}) + "\n"


def call_line(name: str, ident: str = "tu-1") -> str:
    return turn_line("assistant", {"type": "tool_use", "id": ident, "name": name, "input": {}},
                     "tool_use")


def result_line(ident: str = "tu-1") -> str:
    return turn_line("user", {"type": "tool_result", "tool_use_id": ident, "content": "ok"})


def runs(f: Path, kept: str) -> None:
    """The agent's transcript `kept`, then a tool's result with no assistant record after it: it
    reads as still running, whatever the file's age. `kept` alone makes it ended."""
    f.write_text(kept + call_line("Bash") + result_line(), encoding="utf-8")


def clear_agents(w: World) -> None:
    """The Foreman's `agents set <cr> -` for every CR and order at the batch's end: `close` judges
    the agents the batch still holds, and one with no transcript cannot be read."""
    state = w.folder() / "batch.json"
    d = json.loads(state.read_text(encoding="utf-8"))
    state.write_text(json.dumps({
        **d, "crs": [{**c, "agent": None} for c in d["crs"]],
        "orders": [{**o, "agent": None} for o in d["orders"]]}), encoding="utf-8")


def priced_foreman(w: World) -> None:
    """Give the running batch a Foreman transcript with one priced call, written long ago: `close`
    prices the batch before anything is touched, and refuses a batch it cannot price."""
    slug = "".join(ch if ch.isalnum() else "-" for ch in str(w.work.resolve()))
    f = w.root / "claude-projects" / slug / "uuid-closing.jsonl"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps({"type": "assistant", "message": {
        "id": "closing", "stop_reason": "end_turn", "model": "claude-sonnet-5-5", "usage": {
            "input_tokens": 10, "output_tokens": 300, "cache_read_input_tokens": 20_000,
            "cache_creation": {"ephemeral_1h_input_tokens": 2_000}}}}) + "\n")
    then = time.time() - 600
    os.utime(f, (then, then))
    state = w.folder() / "batch.json"
    d = json.loads(state.read_text())
    d.pop("foreman_transcripts", None)
    state.write_text(json.dumps({**d, "foreman_transcript": "uuid-closing"}))


MYSTERY_CALL = json.dumps({"type": "assistant", "message": {
    "id": "mys-1", "stop_reason": "end_turn", "model": "mystery-model", "usage": {"input_tokens": 1000, "output_tokens": 2000}}}) + "\n"
DATED_CALL = MYSTERY_CALL.replace("mys-1", "mys-2").replace("mystery-model", "mystery-model-20270101")
MYSTERY_PRICES = ("prices:\n  mystery-model:\n    input: 1\n    cache_write_5m: 1\n"
                  "    cache_write_1h: 1\n    cache_read: 1\n    output: 1\n")


def unpriced_model(w: World, main: Path, name: str) -> None:
    """One call of a model with no price: counted and named, never priced, never a block; the
    figures are a floor everywhere. A price in `chantier.yaml` prices it, the dated id too."""
    yaml = w.work / "chantier.yaml"
    before = main.read_text()
    _, out = w.chantier("cost", "--batch", name)
    total, calls = float(re.search(r"\$(\d+\.\d{3}) over", out[0])[1]), int(re.search(r"over (\d+) ", out[0])[1])
    main.write_text(before + MYSTERY_CALL)
    code, out = w.chantier("cost", "--batch", name)
    shared = [ln for ln in out if re.match(r"(Foreman|Driver|Worker|Agent)\b", ln)]
    check("a model with no price: `cost` says `at least` with the priced calls and counts the others "
          "apart", code == 0 and out[0] == f"{name}: at least ${total:.3f} over {calls} priced model "
          "calls; 1 calls of mystery-model not priced", str(out))
    check("each share reads `share not measured` and the ratio `not measured (calls not priced)`, "
          "with the one line that gives the id to add",
          shared and all("share not measured" in ln for ln in shared)
          and "Orchestration (steering + Drivers): not measured (calls not priced)" in out
          and out.count("mystery-model has no price: add it under prices: in chantier.yaml "
                        "(exact id: mystery-model)") == 1, str(out))
    _, out = w.chantier("cost", "--explain", "--batch", name)
    check("`--explain` names the model with `(not priced)` and the shares as of the priced calls",
          any("model claude-sonnet-5-5, mystery-model (not priced)" in ln or
              "mystery-model (not priced)" in ln for ln in out)
          and any("cost of the priced calls:" in ln for ln in out), str(out))
    _, out = w.chantier("cost", "--summary", "--batch", name)
    check("`--summary` gives `at least`, the not-priced calls, and `not measured` shares",
          out[0].startswith("Total: at least $") and out[0].endswith("; 1 calls of mystery-model not priced")
          and "(not measured)" in out[1] and "(%)" not in out[1], str(out))
    code, out = w.chantier("status", "--refresh", "--batch", name)
    check("`status --refresh` records the floor and does not say `spend not updated`",
          code == 0 and not any("spend not updated" in ln for ln in out)
          and any(ln.startswith("spent at least $") and "1 calls of mystery-model not priced" in ln
                  for ln in out) and w.batch()["unpriced"] == {"mystery-model": 1}, str(out))
    _, out = w.chantier("status", "--batch", name)
    report = (w.folder() / "STATUS.md").read_text(encoding="utf-8")
    board = (w.state / "STATUS.md").read_text(encoding="utf-8")
    data = json.loads((w.folder() / "STATUS.json").read_text(encoding="utf-8"))
    check("`status`, the batch's STATUS.md, its STATUS.json and the board say `at least`",
          re.search(r"spent at least \$\d+\.\d\d of \$50", out[0])
          and re.search(r"spent at least \$\d+\.\d\d", report)
          and re.search(r"at least \$\d+\.\d\d of \$50", board)
          and data["unpriced"] == {"mystery-model": 1} and data["priced"] is True,
          f"{out[0]}\n{report}\n{board}")
    # a price of the project's prices it, with no release; the dated id by the same entry
    yaml.write_text(MYSTERY_PRICES, encoding="utf-8")
    code, out = w.chantier("cost", "--batch", name)
    check("a `prices:` entry in chantier.yaml prices the call: no `at least`, the total grows by the "
          "expected amount", code == 0 and out[0].startswith(f"{name}: $")
          and "at least" not in "\n".join(out)
          and abs(float(re.search(r"\$(\d+\.\d{3}) over", out[0])[1]) - total - 0.003) <= 0.0011
          and f"over {calls + 1} model calls" in out[0], str(out))
    main.write_text(before + MYSTERY_CALL + DATED_CALL)
    code, out = w.chantier("cost", "--batch", name)
    check("a dated id (mystery-model-20270101) is priced by the same entry",
          code == 0 and "at least" not in "\n".join(out)
          and abs(float(re.search(r"\$(\d+\.\d{3}) over", out[0])[1]) - total - 0.006) <= 0.0016
          and f"over {calls + 2} model calls" in out[0], str(out))
    _, out = w.chantier("playbook")
    check("`playbook` prints the `prices:` line", "prices: mystery-model (repository, above the "
          "built-in table)" in out, str(out))
    yaml.write_text("prices:\n  mystery-model:\n    input: 1\n", encoding="utf-8")
    code, out = w.chantier("cost", "--batch", name, expect=2)
    check("a chantier.yaml that is not valid makes `cost` refuse with its line, never price with the "
          "file ignored", code == 2 and "chantier.yaml:2:" in w.last_stderr
          and "$CHANTIER playbook" in w.last_stderr and not out, w.last_stderr)
    yaml.unlink()
    main.write_text(before + MYSTERY_CALL)


def close_refusals(w: World) -> None:
    """A paused batch shows its cost to date; the first `take` reopens it; `close` refuses while any
    CR, order, stack agent or lease shows that something runs."""
    name, state = w.name, w.folder() / "batch.json"
    slug = "".join(ch if ch.isalnum() else "-" for ch in str(w.work.resolve()))
    main = w.root / "claude-projects" / slug / "uuid-foreman.jsonl"
    sub = main.with_suffix("") / "subagents"
    w.chantier("status", "--refresh", "--batch", name)
    code, out = w.chantier("status", "--batch", name)
    d = w.batch()
    check("`pause` records the cost to date, in the summary and in `status`",
          "paused, cost to date" in out[0] and d["summary"][-1].startswith("To date")
          and not any("Not final" in ln for ln in d["summary"])
          and d["status"] == "paused" and d.get("paused"), str(out))
    before = state.read_text()
    code, _ = w.chantier("pause", "--batch", name, "--epoch", 2, expect=2)
    check("a second `pause` on a paused batch is refused and changes nothing",
          code == 2 and "already paused" in w.last_stderr and "first `take`" in w.last_stderr
          and state.read_text() == before,
          w.last_stderr)
    w.chantier("status", "--refresh", "--batch", name)
    report = (w.folder() / "STATUS.md").read_text(encoding="utf-8")
    header = re.search(r"spent \$(\d+\.\d\d)([^·\n]*)", report)
    total = re.search(r"Total: \$(\d+\.\d\d)", report)
    check("STATUS.md shows one total in its header and its Cost section, marked (to date)",
          header and total and header[1] == total[1] and "(to date)" in header[2]
          and "To date" in report and "Not final" not in report
          and report.startswith(f"# {w.name}: paused") and "## Paused" in report, report)

    # a call made after the pause is spend
    late = json.dumps({"type": "assistant", "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"), "message": {
        "id": "after-pause", "stop_reason": "end_turn", "model": "claude-sonnet-5-5", "usage": {
            "input_tokens": 10, "output_tokens": 100_000, "cache_read_input_tokens": 20_000,
            "cache_creation": {"ephemeral_1h_input_tokens": 2_000}}}}) + "\n"
    main.write_text(main.read_text() + late)
    code, out = w.chantier("cost", "--batch", name)
    check("a call made after the pause shows in `cost`",
          out[0] == f"{name}: $2.618 over 95 model calls", str(out))

    # new work leaves the paused batch paused; the first `take` sets it running again
    paused_d = w.batch()
    added = prepare_cr(w, "Work after the pause")[1]
    code, out = w.chantier("order", "add", "--batch", name, "--note", str(added))
    d = w.batch()
    new = d["crs"][-1]["id"]
    check("`order add` on a paused batch leaves it paused, keeps its pause and summary, queues the "
          "CR, with a line that says so",
          d["status"] == "paused" and d.get("paused") == paused_d["paused"]
          and d.get("summary") == paused_d["summary"] and w.cr(new)["status"] == "queued"
          and any("stays paused: the first `take` sets it running again" in ln for ln in out),
          str(out))
    code, _ = w.chantier("order", "add", "--batch", name, "--note", str(added), expect=None)
    check("a CR folder already queued in the paused batch is refused, the batch unchanged",
          code != 0 and len(w.batch()["crs"]) == len(d["crs"]), w.last_stderr)
    for extra in ((), ("--yes",)):
        code, out = w.chantier("close", "--batch", name, *extra, expect=2)
        check(f"`close{' --yes' if extra else ''}` on the paused batch names what holds it, with the "
              "queued CR, not a bare usage error",
              code == 2 and f"cannot close {name}, something still runs" in w.last_stderr
              and f"{new} is queued" in w.last_stderr and "paused: none" not in w.last_stderr
              and (w.folder() / "batch.json").is_file(), w.last_stderr)
    # a refused take leaves the batch paused and unchanged (no free slot)
    held = state.read_text()
    state.write_text(json.dumps({**json.loads(held), "slots": 0}))
    zero = state.read_text()
    code, _ = w.chantier("take", new, "--epoch", 2, expect=None)
    # the budget check refreshes the spend and records it even when `take` is then refused: the
    # spend's own fields (and the paused batch's cost summary) are the only thing that moves
    spend_keys = {"spent_usd", "spent_at", "unpriced", "summary", "crs"}
    after = w.batch()
    check("a refused `take` on a paused batch leaves it paused and unchanged, but for the spend",
          code != 0 and w.batch()["status"] == "paused"
          and {k: v for k, v in after.items() if k not in spend_keys}
          == {k: v for k, v in json.loads(zero).items() if k not in spend_keys}
          and [(c["id"], c["status"]) for c in after["crs"]]
          == [(c["id"], c["status"]) for c in json.loads(zero)["crs"]], w.last_stderr)
    # the budget is checked on the transcripts' spend: a budget below it refuses the `take` although
    # the stored figure is far below the budget, and the refreshed figure is recorded and dated
    stale = {**json.loads(held), "budget_usd": 0.5, "spent_usd": 0.01}
    stale.pop("spent_at", None)
    state.write_text(json.dumps(stale))
    code, _ = w.chantier("take", new, "--epoch", 2, expect=None)
    refused = w.last_stderr
    _, shown = w.chantier("status", "--batch", name)
    d = w.batch()
    check("a `take` is refused (exit 5) on the spend read from the transcripts, not on the stored "
          "figure; `status` shows the refreshed figure, `, 0 min old`, and the batch's STATUS.json "
          "and the index's entry of that batch (the pane's source) have the same `spent_at`",
          code == 5 and "budget spent" in refused and w.cr(new)["status"] == "queued"
          and d["spent_usd"] > 1 and d["spent_at"]
          and re.search(r" spent \$\d+\.\d\d of \$0\.5, 0 min old", shown[0])
          and json.loads((w.folder() / "STATUS.json").read_text(encoding="utf-8"))["spent_at"]
          == d["spent_at"]
          and [b["spent_at"] for b in json.loads((w.state / "STATUS.json").read_text(
              encoding="utf-8"))["batches"] if b["batch"] == name] == [d["spent_at"]],
          f"{code} {refused} {shown[0]}")
    state.write_text(held)
    # the steering takes it, without --batch: the CR is found in a paused batch, which runs again
    unpriced_model(w, main, name)  # a call of a model with no price is in the transcript now
    code, out = w.chantier("take", new, "--epoch", 2)
    d = w.batch()
    check("`take` on a queued CR is not refused for a model with no price, and the batch keeps "
          "its calls apart", d["status"] == "running" and d.get("unpriced") == {"mystery-model": 1},
          str(d.get("unpriced")))
    check("`take` finds a paused batch's CR and sets the batch running again, with a line that "
          "says so", d["status"] == "running" and "paused" not in d and "summary" not in d
          and any("was paused: running again" in ln for ln in out) and w.cr(new)["status"] == "working",
          str(out))
    main.write_text(main.read_text().replace(MYSTERY_CALL, ""))  # the later steps price as before
    w.chantier("order", "note", "--note", "the user's word, not yet read")  # holds the pause
    drop_then_cancel(w, new, 2)
    check("the last cancel, with a note order pending, does not pause the batch",
          w.batch()["status"] == "running", str(w.batch()["status"]))
    for o in w.batch()["orders"]:
        if not o["done"]:
            w.chantier("order", "done", o["id"], "--epoch", 2)
    for extra in ((), ("--yes",)):
        code, out = w.chantier("close", "--batch", name, *extra, expect=2)
        check(f"`close{' --yes' if extra else ''}` on a running batch where nothing runs says it is not "
              "paused and `pause --epoch <n>` comes first",
              code == 2 and "not paused" in w.last_stderr
              and "`pause --epoch <n>` comes first" in w.last_stderr
              and "paused: none" not in w.last_stderr and (w.folder() / "batch.json").is_file(), w.last_stderr)
    _, out = w.chantier("pause", "--epoch", 2)
    d = w.batch()
    check("`pause` runs again at the end of the reopened batch, and counts the later call",
          d["status"] == "paused" and d["paused"] and "Total: $2.62" in "\n".join(d["summary"]),
          str(d.get("summary")))
    check("`pause` prints the cost summary, past ten lines and not cut, ending with the to-date line",
          any(ln.startswith("Total: $") for ln in out) and out[0].startswith(f"paused {name}")
          and out[-1].startswith("To date") and not any("more lines" in ln for ln in out), str(out))
    # a call made after the LAST pause: `close` counts it, `pause` could not
    w.paused_total = float(re.search(r"Total: \$(\d+\.\d\d)", "\n".join(d["summary"]))[1])
    later = json.loads(late)
    later["message"]["id"] = "after-last-pause"
    later["message"]["usage"]["output_tokens"] = 50_000
    later["timestamp"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    main.write_text(main.read_text() + json.dumps(later) + "\n")

    # close refuses, naming the cause, with and without --yes. The batch holds no agent: each CR's
    # and order's `agent` is cleared (`agents set <cr> -`, as a Foreman does at a merge); a test
    # holds one by writing it into the record, as `agents set <cr> <id>` would
    d = json.loads(state.read_text())
    d["crs"] = [{**c, "agent": None} for c in d["crs"]]
    d["orders"] = [{**o, "agent": None} for o in d["orders"]]
    base = json.dumps(d)
    state.write_text(base)

    def refused(label: str, text: str | tuple, change: dict | None = None, env: dict | None = None,
                flags: tuple = ()) -> None:
        if change is not None:
            state.write_text(json.dumps({**d, **change}))
        texts = (text,) if isinstance(text, str) else text
        for extra in ((), ("--yes",)):
            code, out = w.chantier("close", "--batch", name, *flags, *extra, env=env, expect=2)
            check(f"`close{' ' + ' '.join(flags) if flags else ''}{' --yes' if extra else ''}` "
                  f"refuses {label}, naming it and deleting nothing",
                  code == 2 and all(t in w.last_stderr for t in texts) and not out
                  and "Nothing was deleted." in w.last_stderr
                  and (w.folder() / "batch.json").is_file(), w.last_stderr)
        state.write_text(base)

    def owns(*ids: str) -> dict:
        """The record where the first CRs hold these agent ids (`agents set <cr> <id>`)."""
        return {"crs": [{**c, "agent": ids[i] if i < len(ids) else None}
                        for i, c in enumerate(d["crs"])]}

    def closes(change: dict | None, *flags: str) -> list[str]:
        """`close` (no --yes) on the record with `change`, which must pass; the record put back."""
        state.write_text(json.dumps({**d, **(change or {})}))
        code, out = w.chantier("close", "--batch", name, *flags)
        state.write_text(base)
        return out

    def bare(f: Path) -> str:
        return f.stem.removeprefix("agent-")

    heading = (f"not agents of {name}, not judged (no word needed; their calls are counted only "
               "up to now): ")

    # the transcripts' ends, never their ages (the files are just written, or aged 10 minutes)
    hint = "close --stopped <name> for each"
    foreman_kept = main.read_text()
    main.write_text(foreman_kept + call_line("Bash"))
    age_sessions(w)
    refused("a Foreman whose last call waits on a tool for 10 minutes",
            ("transcript uuid-foreman still runs", "its tool call Bash has no result yet",
             str(main), hint))
    main.write_text(foreman_kept)
    age_sessions(w)
    files = sorted(sub.glob("agent-*.jsonl"))
    first, second, third = files[:3]
    kept, kept2 = first.read_text(), second.read_text()
    hold1 = owns(bare(first))
    # 1. a held agent (a CR's `agent`) that reads as running refuses, naming it and its file
    runs(first, kept)
    runs(second, kept2)
    refused("a held agent whose last record is a tool's result with no answer",
            (f"transcript uuid-foreman {first.stem} still runs",
             "its last record is a tool's result with no answer yet", str(first), hint), hold1)
    state.write_text(json.dumps({**d, **hold1}))
    w.chantier("close", "--batch", name, expect=2)
    check("the refusal of a held agent does not list the other transcripts",
          second.stem not in w.last_stderr and "not agents of" not in w.last_stderr, w.last_stderr)
    state.write_text(base)
    # 2. the same transcript, its CR's agent cleared: close passes, lists it apart, declares nothing
    # 3. an unrecorded subagent that runs and one whose last line is cut: listed; an ended one is not
    # (a line cut in the middle is not used here: the final cost's pricing refuses any cut record
    # of the session, whoever it belongs to, and the spec leaves the pricing unchanged)
    second.write_text(json.dumps({"type": "system"}) + "\n", encoding="utf-8")
    out = closes(None)
    at = [i for i, ln in enumerate(out) if ln.startswith("not agents of")]
    cost = [i for i, ln in enumerate(out) if ln.startswith("Total: ")]
    check("`close` with the agent's CR cleared passes, prints the final cost, and lists the agent "
          "that runs and the one unreadable apart under a heading (not judged, no word needed, calls "
          "counted only up to now), the ended one not listed, nothing declared stopped",
          at and cost and at[0] < cost[0] and out[at[0]] == heading + "2"
          and any(ln.startswith(f"- transcript uuid-foreman {first.stem} still runs: ")
                  and ln.endswith(f"({first})") for ln in out)
          and any(ln.startswith(f"- transcript uuid-foreman {second.stem} cannot be read: ")
                  and ln.endswith(f"({second})") for ln in out)
          and third.stem not in "\n".join(out)
          and not any(ln.startswith("declared stopped") for ln in out), str(out))
    second.write_text(kept2, encoding="utf-8")
    # 3. a batch whose other transcripts all ended prints no heading; a held agent that ended passes
    first.write_text(kept + call_line("SubagentHandback") + result_line(), encoding="utf-8")
    out = closes(hold1)
    check("`close` passes a held agent that handed back, though its file was just written, and "
          "prints the final cost, with no heading when every other transcript ended",
          any(ln.startswith("Total: ") for ln in out)
          and not any(ln.startswith("not agents of") for ln in out), str(out))
    first.write_text(kept + turn_line("assistant", {"type": "text", "text": "done"}, "end_turn"),
                     encoding="utf-8")
    out = closes(hold1)
    check("`close` passes a held agent whose last record is an `end_turn` message", any(
        ln.startswith("Total: ") for ln in out) and not any(
        ln.startswith("not agents of") for ln in out), str(out))
    # 11. a held agent's cut last line cannot be read, and the flag does not pass it
    first.write_text(kept + '{"type": "assistant", "mess', encoding="utf-8")
    refused("a held agent whose last line is cut JSON",
            (f"transcript uuid-foreman {first.stem} cannot be read",
             "its last line is not complete JSON", str(first)), hold1)
    refused("`--stopped` of a held transcript that cannot be read",
            (f"close --stopped {first.stem}: its transcript cannot be read ({first})",), hold1,
            flags=("--stopped", first.stem))
    first.write_text(kept, encoding="utf-8")
    # a recorded Foreman transcript that is missing
    gone = main.with_name("uuid-gone.jsonl")
    refused("a recorded Foreman transcript that is missing",
            ("transcript uuid-gone cannot be read", "the file is missing", str(gone)),
            {"foreman_transcript": "uuid-gone", "foreman_transcripts": ["uuid-gone"]})
    # 8. --stopped, on a held agent that runs (the stem and the bare id)
    runs(first, kept)
    shelf = [w.folder(), w.state / "5-archives" / "batches"]
    state.write_text(json.dumps({**d, **hold1}))
    for given in (first.stem, bare(first)):
        before = [tree_bytes(p) for p in shelf]
        code, out = w.chantier("close", "--batch", name, "--stopped", given)
        at = [i for i, ln in enumerate(out) if ln.startswith("declared stopped")]
        cost = [i for i, ln in enumerate(out) if ln.startswith("Total: ")]
        check(f"`close --stopped {given}` (no --yes) passes the held agent the user declared "
              "stopped, says so before the cost, and writes nothing",
              code == 0 and [tree_bytes(p) for p in shelf] == before and at and cost
              and out[at[0]].startswith(f"declared stopped on the user's word: {first.stem}: ")
              and str(first) in out[at[0]] and at[0] < cost[0], str(out))
    state.write_text(base)
    # 9. `--stopped` of a subagent the batch does not hold, of an unknown name, of an ended one
    runs(second, kept2)
    refused("`--stopped` of a subagent the batch does not hold",
            (f"close --stopped {second.stem}: not an agent {name} holds; it does not block close, "
             "drop the flag",), hold1, flags=("--stopped", second.stem))
    refused("`--stopped` of a name that is not in the batch, naming the held running agents only",
            (f"close --stopped nobody: no transcript of {name} by that name; still running: "
             f"{first.stem}. Nothing was deleted.",), hold1, flags=("--stopped", "nobody"))
    second.write_text(kept2, encoding="utf-8")
    refused("`--stopped` of a held agent whose transcript shows it ended",
            (f"close --stopped {second.stem}: its transcript shows it ended; drop the flag",),
            owns(bare(first), bare(second)), flags=("--stopped", second.stem))
    # 10. two held agents that run, one named: the other one refuses
    runs(second, kept2)
    refused("two held running agents with one named, the other one",
            (f"transcript uuid-foreman {second.stem} still runs", str(second), hint),
            owns(bare(first), bare(second)), flags=("--stopped", first.stem))
    second.write_text(kept2, encoding="utf-8")
    refused("an open order, though the held running agent is named", "order O-99 (qa) is open",
            {**hold1, "orders": d["orders"] + [{"id": "O-99", "kind": "qa", "cr": "-", "note": "x",
                                                "sent": d["created"], "done": None}]},
            flags=("--stopped", first.stem))
    # 4. a held QA order agent (the order done, its `agent` still set) that runs refuses
    refused("a held QA order's agent that reads as running",
            (f"transcript uuid-foreman {first.stem} still runs", str(first)),
            {"orders": d["orders"] + [{"id": "O-98", "kind": "qa", "cr": "-", "note": "x",
                                       "sent": d["created"], "done": d["created"],
                                       "agent": bare(first)}]})
    # 5. the current Foreman (the last recorded) blocks, an earlier one is listed apart
    early = main.with_name("uuid-earlier-foreman.jsonl")
    two = {"foreman_transcripts": ["uuid-earlier-foreman", "uuid-foreman"],
           "foreman_transcript": "uuid-foreman"}
    first.write_text(kept, encoding="utf-8")
    early.write_text(foreman_kept + call_line("Bash"), encoding="utf-8")
    age_sessions(w)
    out = closes(two)
    check("an earlier Foreman's main transcript that runs does not refuse `close`: it is listed "
          "apart",
          any(ln == heading + "1" for ln in out)
          and any(ln.startswith("- transcript uuid-earlier-foreman still runs: ") for ln in out)
          and any(ln.startswith("Total: ") for ln in out), str(out))
    refused("`--stopped` of an earlier Foreman's session id", (
        f"close --stopped uuid-earlier-foreman: not an agent {name} holds",), two,
            flags=("--stopped", "uuid-earlier-foreman"))
    main.write_text(foreman_kept + call_line("Bash"))
    age_sessions(w)
    refused("the current Foreman (the last recorded) that reads as running",
            ("transcript uuid-foreman still runs", "its tool call Bash has no result yet",
             str(main), hint), two)
    out = closes(two, "--stopped", "uuid-foreman")
    check("`--stopped <current session id>` passes the current Foreman and says so",
          any(ln.startswith("declared stopped on the user's word: uuid-foreman: ") for ln in out)
          and any(ln.startswith("- transcript uuid-earlier-foreman still runs: ") for ln in out),
          str(out))
    main.write_text(foreman_kept)
    early.unlink()
    age_sessions(w)
    # 6. a held Driver that ended, with a subagent of its own that runs: passes, the child is listed
    drv, kid = sub / "agent-drv-9.jsonl", sub / "agent-kid-9.jsonl"
    meta = sub / "agent-kid-9.meta.json"
    drv.write_text(kept + call_line("SubagentHandback") + result_line(), encoding="utf-8")
    runs(kid, kept)
    meta.write_text(json.dumps({"parentAgentId": "drv-9"}))
    out = closes(owns("drv-9"))
    check("a held Driver that ended passes `close`, and its own subagent that runs is listed apart",
          any(ln == heading + "1" for ln in out)
          and any(ln.startswith(f"- transcript uuid-foreman {kid.stem} still runs: ") for ln in out)
          and not any(ln.startswith("declared stopped") for ln in out), str(out))
    runs(drv, kept)
    refused("a held Driver that runs, though its own subagent is not judged",
            (f"transcript uuid-foreman {drv.stem} still runs", hint), owns("drv-9"))
    for f in (drv, kid, meta):
        f.unlink()
    # 7. a held id with no transcript file cannot be read; `agents set <cr> -` is the way out
    ghost = {"crs": [{**c, "agent": "ghost-1"} if i == 0 else c for i, c in enumerate(d["crs"])]}
    cr0 = d["crs"][0]["id"]
    refused("a held id with no transcript, naming `agents set <cr> - --epoch <n>`",
            (f"transcript of ghost-1 ({cr0}) cannot be read: no transcript found",
             f"agents set {cr0} - --epoch <n>"), ghost)
    refused("`--stopped` of a held id with no transcript",
            ("close --stopped ghost-1: its transcript cannot be read (no transcript found)",),
            ghost, flags=("--stopped", "ghost-1"))
    state.write_text(json.dumps({**d, **ghost}))
    w.chantier("agents", "set", cr0, "-", "--epoch", 2)
    code, out = w.chantier("close", "--batch", name)
    check("after `agents set <cr> -` the held id with no transcript no longer refuses `close`",
          code == 0 and any(ln.startswith("Total: ") for ln in out), str(out))
    state.write_text(base)
    # 12. the record causes, unchanged
    first.write_text(kept, encoding="utf-8")
    crs = [{**c, "status": "ready"} if i == 0 else c for i, c in enumerate(d["crs"])]
    refused("a CR that is not merged", f"{d['crs'][0]['id']} is ready", {"crs": crs})
    refused("an open order", "order O-99 (qa) is open", {"orders": d["orders"] + [
        {"id": "O-99", "kind": "qa", "cr": "-", "note": "x", "sent": d["created"], "done": None}]})
    refused("a stack agent", "stack agent agent-stack is recorded", {"stack_agent": "agent-stack"})
    refused("`--stopped` of the stack agent, which no flag passes",
            ("the stack agent is a record cause no flag passes",),
            {"stack_agent": "agent-stack"}, flags=("--stopped", "agent-stack"))
    # a model with no price does not refuse the close: its calls are counted apart, the cost is a floor
    original, aged = main.read_text(), main.stat()
    call = json.dumps({"type": "assistant", "message": {
        "id": "mystery", "stop_reason": "end_turn", "model": "mystery-model", "usage": {"input_tokens": 1, "output_tokens": 1}}}) + "\n"
    main.write_text(original + call)
    os.utime(main, (aged.st_atime, aged.st_mtime))
    code, out = w.chantier("close", "--batch", name)
    text = "\n".join(out)
    check("`close` of a batch with one call of a model with no price exits 0, prints the final cost "
          "as `at least` with the call counted apart and the line that names the id to add, and "
          "deletes nothing",
          code == 0 and re.search(r"Total: at least \$\d+\.\d\d of a \$50 budget; "
                                  r"1 calls of mystery-model not priced", text)
          and "mystery-model has no price: add it under prices: in chantier.yaml "
              "(exact id: mystery-model)" in text
          and "Not final" not in text and (w.folder() / "batch.json").is_file(), text)
    main.write_text(original)
    os.utime(main, (aged.st_atime, aged.st_mtime))
    # nothing at all can be priced (every call is of a model with no price): refused, nothing deleted
    only = main.with_name("uuid-unpriced.jsonl")
    only.write_text(call)
    os.utime(only, (aged.st_atime, aged.st_mtime))
    refused("a batch where nothing can be priced (every call of a model with no price)",
            "its final cost cannot be priced", {"foreman_transcript": "uuid-unpriced",
                                                "foreman_transcripts": ["uuid-unpriced"]})
    only.unlink()
    refused("a batch with no recorded Foreman transcript", "no Foreman transcript recorded",
            {"foreman_transcript": None, "foreman_transcripts": []})

    # Copilot: the session's events file is the only time the CLI reads
    home = w.root / "copilot-home"
    events = home / "session-state" / "uuid-foreman" / "events.jsonl"
    missing = [str(w.root / "missing-session-usage")]
    env = {"COPILOT_HOME": str(home), "CHANTIER_SESSION_USAGE": subprocess.list2cmdline(missing)
           if sys.platform == "win32" else shlex.join(missing)}
    state.write_text(json.dumps({**d, "host": "copilot"}))
    events.parent.mkdir(parents=True, exist_ok=True)
    events.write_text("", encoding="utf-8")
    age_sessions(w)  # no session file is read for a liveness now: only the leases say what runs

    def leased(expires_in_s: int | None) -> dict:
        """A Copilot batch whose first CR holds an agent, with a lease that ends in `expires_in_s`
        seconds (negative: not confirmed), or with none."""
        at = datetime.now(timezone.utc)
        lease = None if expires_in_s is None else {
            "n": 1, "taken": at.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "renewed": at.strftime("%Y-%m-%dT%H:%M:%SZ"), "ended": None,
            "expires": (at + timedelta(seconds=expires_in_s)).strftime("%Y-%m-%dT%H:%M:%SZ")}
        return {"host": "copilot", "heartbeat": None, "crs": [
            {**c, "agent": "agent-a", "lease": lease} if i == 0 else c
            for i, c in enumerate(d["crs"])]}

    cr0 = d["crs"][0]["id"]
    refused("a Copilot batch's held agent whose lease is live",
            (f"agent-a ({cr0}) holds lease 1 until",), leased(600), env=env)
    refused("a Copilot batch's held agent with no lease",
            (f"agent-a ({cr0}): not measured (no lease)",), leased(None), env=env)
    state.write_text(json.dumps({**d, **leased(-3600)}))
    code, out = w.chantier("close", "--batch", name, env=env, expect=2)
    check("on Copilot, a lease that is not confirmed no longer refuses `close`: only the final "
          "cost that cannot be priced does",
          code == 2 and "its final cost cannot be priced" in w.last_stderr
          and "lease" not in w.last_stderr and "not measured" not in w.last_stderr,
          w.last_stderr)
    state.write_text(base)
    # the Chief of Staff's own session writes all the time and never blocks its own close
    os.utime(main.with_name("uuid-chief.jsonl"), None)


def close_batch(w: World) -> None:
    note("\n## 11b. Closing the batch, on the user's word")
    folder, dropped, merged_left = w.folder(), w.cr("CR-103"), w.cr("CR-101")
    name = w.name
    close_refusals(w)
    retro = folder / "retro.md"
    retro_bytes = ("# Retro\n\n## Pause 1\n\n- problem one, long-term fix one\n\n"
                   "## Pause 2\n\n- problem two, long-term fix two\n").encode()
    retro.write_bytes(retro_bytes)
    waiter, waited = (w.batch()["crs"][i]["id"] for i in (1, 0))
    d_wait = w.batch()
    next(c for c in d_wait["crs"] if c["id"] == waiter)["after"] = [waited]
    (folder / "batch.json").write_text(json.dumps(d_wait, indent=2))
    d0 = w.batch()
    crs_before = sorted(c["id"] for c in d0["crs"])
    opened, mode, steering = d0["created"], d0["mode"], d0["steering"]
    running = (w.state / "5-archives" / "batches" / f"{name}.json").read_bytes()
    shelf = tree_bytes(w.state / "5-archives")
    code, out = w.chantier("close", "--batch", name)
    check("`close` alone says what would go, names the dropped CR's worktree and branch, and "
          "touches nothing",
          code == 0 and (folder / "batch.json").is_file() and Path(dropped["worktree"]).is_dir()
          and any(folder.name in ln for ln in out) and "--yes" in out[-1]
          and len(list((folder / "3-done").iterdir())) == 4
          and any(dropped["worktree"] in ln and dropped["branch"] in ln for ln in out)
          and any("CR-101 (merged) worktree" in ln and "CR-103 (dropped) worktree" in ln
                  for ln in out)
          and not any("CR-102 (merged)" in ln for ln in out), str(out))
    batches = w.state / "5-archives" / "batches"
    record_file, report_file = batches / f"{w.name}.json", batches / f"{w.name}.md"
    retro_lines = [ln for ln in out if ln.startswith("retro:")]
    record_lines = [ln for ln in out if ln.startswith("record:")]
    check("`close` alone prints the `retro:` and `record:` lines naming the batch's record, and "
          "touches no byte of the record, the retro or the archives",
          len(retro_lines) == 1 and f"5-archives/batches/{w.name}.md" in retro_lines[0]
          and "4-batch/retro.md" in retro_lines[0] and len(record_lines) == 1
          and f"5-archives/batches/{w.name}.json" in record_lines[0]
          and retro.read_bytes() == retro_bytes and tree_bytes(w.state / "5-archives") == shelf
          and not report_file.exists(), str(out))
    shown = [float(m[1]) for m in (re.match(r"Total: \$(\d+\.\d\d)", ln) for ln in out) if m]
    check("`close` prints the final cost, with a call made after the last `pause` in it",
          shown and shown[0] > w.paused_total and "Not final" not in "\n".join(out)
          and "To date" not in "\n".join(out), f"{out} (last pause: {w.paused_total})")
    first = w.cr("CR-101")
    stamp = datetime.strptime(first["merged_at"], "%Y-%m-%dT%H:%M:%SZ").strftime("%y%m%d-%H%M")
    collision = w.state / "5-archives" / f"{stamp}-{Path(first['path']).name}"
    collision.mkdir(parents=True)
    (collision / "sentinel.txt").write_text("do not overwrite")
    code, _ = w.chantier("close", "--batch", name, "--yes", expect=3)
    check("an archive collision refuses the close and puts everything back",
          code == 3 and (collision / "sentinel.txt").read_text() == "do not overwrite"
          and (w.state / first["path"] / "03-change-spec.md").is_file()
          and (folder / "batch.json").is_file() and (folder / "events.jsonl").is_file()
          and len(list((folder / "3-done").iterdir())) == 4
          and not (w.state / f".closing-{name}").exists(), w.last_stderr)
    check("the archive collision leaves 4-batch/retro.md, the record and no Markdown in place",
          retro.read_bytes() == retro_bytes and record_file.read_bytes() == running
          and not report_file.exists())
    shutil.rmtree(collision)
    report_file.write_text("planted\n")
    code, _ = w.chantier("close", "--batch", name, "--yes", expect=3)
    check("a planted batch-NN.md refuses the close (exit 3), every rename put back, the record "
          "and the retro unchanged byte for byte",
          code == 3 and report_file.read_text() == "planted\n" and retro.read_bytes() == retro_bytes
          and record_file.read_bytes() == running
          and (folder / "batch.json").is_file() and len(list((folder / "3-done").iterdir())) == 4
          and not (w.state / f".closing-{name}").exists(), w.last_stderr)
    report_file.unlink()
    # one agent stopped without its hand-back: the user's word passes it, and the record keeps it
    slug = "".join(ch if ch.isalnum() else "-" for ch in str(w.work.resolve()))
    files = sorted((w.root / "claude-projects" / slug / "uuid-foreman" / "subagents")
                   .glob("agent-*.jsonl"))
    stopped, apart = files[0], files[1]
    runs(stopped, stopped.read_text(encoding="utf-8"))
    runs(apart, apart.read_text(encoding="utf-8"))  # a subagent the batch never recorded: listed
    held = w.batch()
    (folder / "batch.json").write_text(json.dumps({**held, "crs": [
        {**c, "agent": stopped.stem.removeprefix("agent-")} if i == 0 else c
        for i, c in enumerate(held["crs"])]}))  # `agents set <cr> <id>`: the one held agent
    _, out = w.chantier("close", "--batch", name, "--stopped", stopped.stem, "--yes")
    check("`close --yes` deletes the batch's own files, keeps the empty state folders, and "
          "repeats what is left to remove",
          sorted(p.name for p in folder.iterdir()) == ["1-pending", "2-actives", "3-done"]
          and not any(list(p.iterdir()) for p in folder.iterdir())
          and Path(dropped["worktree"]).is_dir() and out[0].endswith("4 CRs archived")
          and any(dropped["worktree"] in ln for ln in out), str(out))
    retro_lines = [ln for ln in out if ln.startswith("retro:")]
    record_lines = [ln for ln in out if ln.startswith("record:")]
    check("`close --yes` says where the retro is kept and that the record is closed",
          len(retro_lines) == 1 and f"5-archives/batches/{w.name}.md" in retro_lines[0]
          and retro_lines[0].startswith("retro: kept in") and len(record_lines) == 1
          and record_lines[0].endswith(".json closed"), str(out))
    total = [float(m[1]) for m in (re.match(r"Total: (?:at least )?\$(\d+\.\d\d)", ln)
                                   for ln in out) if m]
    rec = json.loads(record_file.read_text(encoding="utf-8"))
    said = f"declared stopped on the user's word: {stopped.stem}: "
    entry = (rec.get("stopped_agents") or [{}])[0]
    cost_part = report_file.read_text(encoding="utf-8").split("## Cost")[1].split("## Retro")[0]
    check("`close --stopped <agent> --yes` keeps the declaration: `stopped_agents` in the record "
          "with the agent, its transcript, the cause and the close time, a line under Cost in "
          "batch-NN.md, and the same line in what `close` prints",
          len(rec.get("stopped_agents", [])) == 1 and entry.get("agent") == stopped.stem
          and entry.get("transcript") == str(stopped)
          and entry.get("cause") == "its last record is a tool's result with no answer yet"
          and entry.get("declared") == rec["closed"]
          and f"- Declared stopped on the user's word: {stopped.stem} ({entry.get('cause')})"
          in cost_part and any(ln.startswith(said) and str(stopped) in ln for ln in out),
          f"{rec.get('stopped_agents')} {out}")
    listed = [ln for ln in out if ln.startswith("not agents of")]
    check("`close --yes` lists the unrecorded running subagent apart, before the cost, and keeps "
          "only the declared one in `stopped_agents`",
          len(listed) == 1 and listed[0].endswith(": 1")
          and any(ln.startswith(f"- transcript uuid-foreman {apart.stem} still runs: ") for ln in out)
          and apart.stem not in json.dumps(rec.get("stopped_agents"))
          and apart.stem not in cost_part, str(out))
    check("`batch-NN.json` is closed with its dates, its shape and the final cost the close printed",
          rec["schema"] == 1 and rec["state"] == "closed" and rec["closed"]
          and rec["opened"] == opened and rec["mode"] == mode and rec["steering"] == steering
          and rec["host"] and total and abs(rec["cost_usd"] - total[0]) < 0.0051
          and rec["report"] == f"{w.name}.md" and "backfill" not in rec, f"{rec} {total}")
    check("its CRs carry the result, an archive that exists, the PR, the rounds and the cost",
          sorted(c["cr"] for c in rec["crs"]) == crs_before
          and {c["result"] for c in rec["crs"]} == {"merged", "dropped"}
          and all((w.state / c["archive"]).is_dir() for c in rec["crs"])
          and all(c["archive"].startswith("5-archives/") for c in rec["crs"]
                  if c["result"] == "merged")
          and all(c["archive"].startswith("6-trash/") for c in rec["crs"]
                  if c["result"] == "dropped")
          and all(c["pr"] and c["rounds"] is not None and c["cost_usd"] is not None
                  for c in rec["crs"] if c["result"] == "merged"), str(rec["crs"]))
    order_ids = [c["cr"] for c in rec["crs"]]
    after_before = {c["id"]: list(c.get("after", [])) for c in d0["crs"]}
    check("its CRs carry an integer `order` and an `after` list, as the batch left them, sorted "
          "by `order`",
          all(isinstance(c.get("order"), int) and isinstance(c.get("after"), list)
              for c in rec["crs"])
          and [c["order"] for c in rec["crs"]] == sorted(c["order"] for c in rec["crs"])
          and {c["cr"]: c["after"] for c in rec["crs"]} == {i: after_before[i] for i in order_ids}
          and any(c["after"] == [waited] for c in rec["crs"] if c["cr"] == waiter),
          str(rec["crs"]))
    receipt = rec.get("cost_receipt") or {}
    split = receipt.get("split") or []
    md_drivers = sorted(re.findall(r"Driver (\S+) with its workers: \$(\d+\.\d\d)", cost_part))
    json_drivers = sorted((d["type"], f"{d['usd']:.2f}") for d in receipt.get("drivers", []))
    check("`batch-NN.json` keeps the receipt's figures: a split that adds up to the cost within a "
          "cent, a Steering line, and Driver lines that match the Driver lines of `## Cost`",
          split and abs(sum(p["usd"] for p in split) - rec["cost_usd"]) <= 0.0101
          and {p["part"] for p in split} >= {"steering", "drivers", "workers"}
          and "usd" in receipt.get("steering", {}) and json_drivers == md_drivers
          and ("outside" in receipt), f"{receipt} {md_drivers}")
    models = receipt.get("models")
    check("`batch-NN.json` keeps the receipt's models, adding up to the cost within a cent, and "
          "the calls of each split part",
          isinstance(models, list) and models
          and all(isinstance(m, dict) and {"model", "calls", "usd", "unpriced"} <= set(m)
                  for m in models)
          and abs(sum(m["usd"] for m in models) - rec["cost_usd"]) <= 0.0101
          and all("calls" in p for p in split), f"{models} {split}")
    text = report_file.read_bytes()
    check("`batch-NN.md` holds the table, the cost lines and the retro's two pause sections byte "
          "for byte",
          b"## Completion" in text and b"## Cost" in text and b"- Total: " in text
          and retro_bytes in text and all(c["cr"].encode() in text for c in rec["crs"])
          and not retro.exists(), text.decode("utf-8")[:600])
    check("no retro.md is left in any CR archive, and no <stamp>-batch folder is made",
          not list((w.state / "5-archives").glob("*/retro.md"))
          and not [p for p in (w.state / "5-archives").iterdir()
                   if re.fullmatch(r"\d{6}-\d{4}-batch-\d+", p.name)])
    archived = next((w.state / "5-archives").glob("*-101-fix-login-timeout")) / "STATUS.md"
    check("the merged CRs are in 5-archives, named for their merge time, intact",
          re.fullmatch(rf"{stamp}-101-fix-login-timeout", archived.parent.name)
          and len(list((w.state / "5-archives").glob(f"{stamp[:6]}-*-10[1245]-*"))) >= 4
          and (archived.parent / "03-change-spec.md").is_file(), archived.parent.name)
    page = archived.read_text(encoding="utf-8")
    check("at `close` the archived CR page gives its cost as final, priced to then",
          re.search(r"## Cost\s+\$\d+\.\d\d\.\s*$", page) and "so far" not in page
          and "STATUS.md)" not in page.split("## Documents")[0], page)
    index = json.loads((w.state / "STATUS.json").read_text(encoding="utf-8"))
    cr_archives = [p for p in (w.state / "5-archives").iterdir()
                   if p.is_dir() and p.name != "batches"]
    check("the index does not list `batches` among the merged CRs, nor count it",
          not any("batches" in str(e.get("path")) for e in index["merged"])
          and index["merged_total"] == len(cr_archives), str(index["merged_total"]))
    # the Chief of Staff removes it on the same word, with git
    for left in (dropped, merged_left):
        w.sh("git", "worktree", "remove", "--force", left["worktree"])
        w.sh("git", "branch", "-D", left["branch"])
    check("the dropped CR's and the merged CR's leftover worktrees and branches are gone by the "
          "Chief of Staff's hands",
          not any(Path(c["worktree"]).exists() or w.sh("git", "branch", "--list", c["branch"])
                  for c in (dropped, merged_left)))
    board = (w.state / "STATUS.md").read_text(encoding="utf-8")
    check("the archives and the trash stay, and the board forgets the batch",
          name not in board and "No batch." in board
          and (w.state / dropped["path"] / "STATUS.md").is_file(), board)


def opened_record(w: World) -> None:
    """Step 1: `open` reserves the number by writing the batch's record, as running."""
    path = w.state / "5-archives" / "batches" / f"{w.name}.json"
    d = w.batch()
    rec = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    check("`open` writes `5-archives/batches/batch-NN.json`, running, from the batch's settings",
          rec.get("schema") == 1 and rec["state"] == "running" and rec["batch"] == w.name
          and rec["number"] == int(w.name.removeprefix("batch-")) and rec["opened"] == d["created"]
          and rec["mode"] == d["mode"] and rec["steering"] == d["steering"]
          and rec["host"] == d["host"] and rec["budget_usd"] == d["budget_usd"]
          and rec["crs"] == [] and rec["closed"] is None and rec["cost_usd"] is None
          and rec["report"] is None and "backfill" not in rec
          and "cost_receipt" in rec and rec["cost_receipt"] is None, str(rec))
    ignored = (w.state / ".gitignore").read_text(encoding="utf-8").splitlines()
    check("`open` still writes `.batch-number`, and the record is published, not ignored",
          (w.state / ".batch-number").read_text().strip() == str(rec.get("number"))
          and ".batch-number" in ignored and not any("batches" in ln for ln in ignored),
          str(ignored))


def tree_bytes(folder: Path) -> dict[str, bytes]:
    return {p.relative_to(folder).as_posix(): p.read_bytes()
            for p in sorted(folder.rglob("*")) if p.is_file()}


def retro_cases(w: World) -> None:
    note("\n## 11c. The batch's retro in its record, with no CR archived, or no retro")
    archives = w.state / "5-archives"
    previous = w.name  # closed by 11b
    for label, text in (("a batch of cancelled CRs", "# Retro\n\n## Pause 1\n\n- one, fix one\n"),
                        ("no retro.md", None), ("a whitespace-only retro.md", " \n\t\n")):
        _, item = prepare_cr(w, f"Retro {label}")
        w.reset()
        w.start(str(item), *FROM_AGENTS_MD)
        w.env["CHANTIER_BATCH"] = w.name
        _, head = w.chantier("status")
        check(f"{label}: after a close and a new `open`, `status` names the last closed batch on "
              "its second line",
              len(head) > 1 and head[1].startswith(f"last closed: {previous}, closed 20"),
              str(head[:2]))
        number = int(w.batch()["crs"][0]["id"].removeprefix("CR-"))
        w.chantier("foreman", "set", "local_foreman_retro", "--epoch", 1)
        drop_then_cancel(w, w.batch()["crs"][0]["id"], 1)  # the last end: paused
        priced_foreman(w)
        age_sessions(w)
        retro = w.folder() / "retro.md"
        if text is not None:
            retro.write_text(text, encoding="utf-8", newline="")
        dropped = w.folder() / "retro-dropped.md"
        dropped.write_text("# Dropped\n\n- 1. drop: once, no cost\n", encoding="utf-8")
        before = sorted(p.name for p in archives.iterdir())
        merged_before = json.loads((w.state / "STATUS.json").read_text(encoding="utf-8")).get(
            "merged_total")
        _, out = w.chantier("close", "--batch", w.name)
        lines = [ln for ln in out if ln.startswith("retro:")]
        report = archives / "batches" / f"{w.name}.md"
        if text is not None and text.strip():
            check(f"{label}: `close` alone says the retro goes into the batch's Markdown, and "
                  "touches nothing",
                  len(lines) == 1 and f"5-archives/batches/{w.name}.md" in lines[0]
                  and retro.is_file() and not report.exists()
                  and sorted(p.name for p in archives.iterdir()) == before, str(out))
        else:
            check(f"{label}: `close` prints `retro: no retro`",
                  lines == ["retro: no retro"], str(out))
        _, out = w.chantier("close", "--batch", w.name, "--yes")
        previous = w.name  # the last closed from here on
        check(f"{label}: a record closed without `--stopped` has no `stopped_agents` key",
              "stopped_agents" not in json.loads(
                  (archives / "batches" / f"{previous}.json").read_text(encoding="utf-8"))
              and "Declared stopped" not in report.read_text(encoding="utf-8"), "")
        new = [p for p in archives.iterdir() if p.name not in before]
        body = report.read_text(encoding="utf-8") if report.is_file() else ""
        check(f"{label}: `close --yes` deletes `retro-dropped.md`, whose lines are not in batch-NN.md",
              not dropped.exists() and "once, no cost" not in body, f"{dropped.exists()} {body[:80]}")
        if text is not None and text.strip():
            check(f"{label}: `close --yes` writes batch-NN.md with the retro, and no folder for "
                  "the batch in 5-archives",
                  text in body and "No retro was written." not in body and not new
                  and any(ln.startswith("retro: kept in") and report.name in ln for ln in out),
                  f"{new} {out}")
            board = json.loads((w.state / "STATUS.json").read_text(encoding="utf-8"))
            check(f"{label}: the board neither counts nor lists the batches' records",
                  board.get("merged_total") == merged_before
                  and not any("batches" in str(r.get("path")) for r in board.get("merged", [])),
                  str(board.get("merged_total")))
            w.env.pop("CHANTIER_BATCH", None)
            w.reset()
            _, item2 = prepare_cr(w, f"After {label}")
            w.start(str(item2), *FROM_AGENTS_MD)
            check(f"{label}: the next CR gets the next number",
                  w.batch()["crs"][0]["id"] == f"CR-{number + 1}",
                  f"{w.batch()['crs'][0]['id']} after CR-{number}")
        else:
            check(f"{label}: batch-NN.md says `No retro was written.`, and nothing is created in "
                  "5-archives",
                  "No retro was written." in body and not new and not retro.exists()
                  and "retro: no retro" in out, f"{new} {out}")
        w.env.pop("CHANTIER_BATCH", None)
    w.reset()
    code, _ = w.chantier("status", expect=2)
    check("with no running batch, `status` refuses and names the last closed batch",
          code == 2 and f"; last closed: {previous}" in w.last_stderr, w.last_stderr)




def lock_names(w: World, what: str, slot: int = 1) -> bool:
    """Whether the text of slot `slot`'s lock (`.long-gate.lock`, `.long-gate.<k>.lock`) names
    `what` within thirty seconds (the wait is only bounded, a green run does not use it)."""
    deadline = time.monotonic() + 30
    lock = w.state / (".long-gate.lock" if slot == 1 else f".long-gate.{slot}.lock")
    while time.monotonic() < deadline:
        try:
            with open(lock, encoding="utf-8") as f:  # byte 0 is locked
                f.seek(1)
                if what in f.read():
                    return True
        except OSError:
            pass
        time.sleep(0.05)
    return False


def cancel_during_gate(w: World) -> None:
    note("\n## 18. A cancel during a gate")
    _, item = prepare_cr(w, "Stopped mid gate")
    slow = w.root / "slow_gate.py"
    slow.write_text("import time\ntime.sleep(60)\n")
    gate = f'"{sys.executable}" "{slow}"'
    w.reset()
    w.start(str(item), "--default-branch", "main")
    w.env["CHANTIER_BATCH"] = w.name
    w.chantier("foreman", "set", "local_foreman6", "--epoch", 1)
    Foreman(w, epoch=1).turn()
    cr = w.batch()["crs"][0]["id"]
    running = subprocess.Popen([sys.executable, "-m", "chantier", "gate", cr, gate], cwd=w.work,
                               env=w.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, encoding="utf-8")
    lock_names(w, f"{cr} pid")
    lock_names(w, " pg")
    drop_then_cancel(w, cr, 1)
    out, err = running.communicate(timeout=120)
    check("a cancel stops the suite and moves the CR while its gate runs; the gate ends cleanly",
          "6-trash/" in w.cr(cr)["path"] and out.startswith("FAIL") and "Traceback" not in err
          and "pg" in w.last_out[0], f"{out} {err} {w.last_out}")


def gate_passed(evs, head):
    """The CLI's own reading of the gate events, which it takes as records."""
    sys.path.insert(0, str(SKILL / "scripts" / "cli" / "src"))
    from chantier.commands.crs import gate_passed as passed
    from chantier.core.records import EventRecord
    return passed([EventRecord(**e) for e in evs], head)


def stop_own_gate(w: World) -> None:
    note("\n## 18b. A Driver stops its own long gate; `cancel` needs the epoch")
    sys.path.insert(0, str(SKILL / "scripts" / "cli" / "src"))
    from chantier import procs

    items = [prepare_cr(w, t)[1] for t in ("Stop own gate", "Stop other gate", "Stop merged gate")]
    slow = w.root / "slow_stop.py"
    pidfile = w.root / "slow_stop.pid"
    slow.write_text(f"import os, time\nopen({pidfile.as_posix()!r}, 'w').write(str(os.getpid()))\n"
                    "time.sleep(60)\n")
    slow_gate = f'"{sys.executable}" "{slow}"'
    w.reset()
    w.start(*map(str, items), "--slots", 3, "--default-branch", "main")
    w.env["CHANTIER_BATCH"] = w.name
    w.chantier("foreman", "set", "local_foreman18b", "--epoch", 1)
    Foreman(w, epoch=1).turn()
    one, two, three = (c["id"] for c in w.batch()["crs"])
    wt = Path(w.cr(one)["worktree"])

    def events(cr):
        return [json.loads(ln) for ln in (w.folder() / "events.jsonl").read_text("utf-8").splitlines()
                if json.loads(ln)["kind"] == "gate" and json.loads(ln)["cr"] == cr]

    def logs(cr):
        return sorted((w.at(w.cr(cr)["path"]) / "work" / "gates").glob("*.log"))

    def background(cr):
        p = subprocess.Popen([sys.executable, "-m", "chantier", "gate", cr, slow_gate], cwd=w.work,
                             env=w.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                             encoding="utf-8")
        lock_names(w, f"{cr} pid")
        lock_names(w, " pg")
        return p

    head = w.sh("git", "rev-parse", "HEAD", cwd=wt)
    notes_before = len(w.cr(one).get("notes", []))
    running = background(one)
    code, _ = w.chantier("gate", one, "--stop", expect=None)
    stop_out = w.last_out
    out, err = running.communicate(timeout=120)
    time.sleep(0.5)
    gone = not procs.alive(int(pidfile.read_text()))
    check("`gate <cr> --stop` exits 0 and names the group; the stopped gate says STOPPED, exits 4, "
          "with no traceback; the slow suite is gone",
          code == 0 and any("(pg" in ln for ln in stop_out) and out.startswith("STOPPED")
          and running.returncode == 4 and "Traceback" not in err and gone,
          f"{stop_out} {out} {err} {running.returncode}")
    last = events(one)[-1]
    check("the stop changes nothing else: the CR still works in its folder with its worktree and "
          "no new note; its last gate event is `stopped` at the run's head; the log ends `result: "
          "stopped`",
          w.cr(one)["status"] == "working" and "4-batch/2-actives/" in w.cr(one)["path"].replace(
              "\\", "/") and wt.is_dir() and len(w.cr(one).get("notes", [])) == notes_before
          and last["result"] == "stopped" and last["head"] == head
          and logs(one)[-1].read_text("utf-8").splitlines()[-1].startswith("result: stopped"),
          f"{w.cr(one)} {last}")
    marker = w.root / "second_ran"
    second = f'"{sys.executable}" -c "open({marker.as_posix()!r}, \'w\').close()"'
    n_before = len(events(one))
    p = subprocess.Popen([sys.executable, "-m", "chantier", "gate", one, slow_gate, second],
                         cwd=w.work, env=w.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         text=True, encoding="utf-8")
    lock_names(w, " pg")
    w.chantier("gate", one, "--stop")
    out, err = p.communicate(timeout=120)
    new = events(one)[n_before:]
    check("a stop while the first of two commands runs: the second never starts, the gate exits 4 "
          "and records `stopped` with no `fail` event",
          p.returncode == 4 and out.startswith("STOPPED") and not marker.exists()
          and [e["result"] for e in new] == ["stopped"] and "Traceback" not in err,
          f"{out} {err} {p.returncode} {new}")
    w.chantier("gate", one, GATE)
    check("the lock is free: a second gate runs at once, with no waiting line, and passes",
          "waiting for the long gate" not in logs(one)[-1].read_text("utf-8")
          and gate_passed(events(one), head))
    running = background(one)
    w.chantier("gate", one, "--stop")
    running.communicate(timeout=120)
    _, out = w.chantier("ship", one, "https://example.invalid/pr/0")
    check("a stopped run voids an earlier pass at the same head: `ship` says no long gate passed",
          not gate_passed(events(one), head) and any("no long gate passed" in ln for ln in out),
          str(out))
    other = background(two)
    code, _ = w.chantier("gate", one, "--stop", expect=2)
    check("with another CR's gate holding the lock, `--stop` exits 2, names it and stops nothing",
          code == 2 and two in w.last_stderr + "".join(w.last_out) and other.poll() is None,
          f"{w.last_out} {w.last_stderr}")
    w.chantier("gate", two, "--stop")
    other.communicate(timeout=120)

    def suite_pid():  # the pid the slow suite wrote once it runs
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline and not (pidfile.exists() and pidfile.read_text()):
            time.sleep(0.05)
        return int(pidfile.read_text())

    # a CR that holds the lock while it merges: its own gate is stopped
    pidfile.unlink(missing_ok=True)
    running = background(three)
    pid = suite_pid()
    code, _ = w.chantier("order", "merged", three, "--epoch", 1)
    merged_out = w.last_out
    ended = running.poll() is not None  # the order waited for the gate's process to end
    out, err = running.communicate(timeout=120)
    time.sleep(0.5)
    check("`order merged` stops the CR's own long gate and waits for it to end: its output names "
          "the group, the suite is gone, the gate says STOPPED and exits 4, the last gate event is "
          "`stopped`, the CR is in 3-done",
          code == 0 and ended and any(ln.startswith(f"stopped the long gate of {three} (pg") for ln in merged_out)
          and not procs.alive(pid) and out.startswith("STOPPED") and running.returncode == 4
          and "Traceback" not in err and events(three)[-1]["result"] == "stopped"
          and "3-done" in w.cr(three)["path"].replace("\\", "/"),
          f"{merged_out} {out} {err} {running.returncode} {events(three)[-1:]}")
    code, _ = w.chantier("gate", two, GATE)
    log = logs(two)[-1].read_text("utf-8")
    check("a gate of another CR then runs at once: no waiting line, no `its command still runs`",
          code == 0 and "waiting for the long gate" not in log
          and "its command still runs" not in log, log)

    # a merge with another CR's gate running stops nothing
    pidfile.unlink(missing_ok=True)
    other = background(two)
    pid = suite_pid()
    w.chantier("order", "merged", one)
    check("`order merged` of a CR that does not hold the lock stops nothing: no `stopped` line, "
          "the other CR's suite still runs",
          not any("stopped" in ln for ln in w.last_out) and procs.alive(pid) and other.poll() is None,
          str(w.last_out))
    w.chantier("gate", two, "--stop")
    other.communicate(timeout=120)


def rails(w: World) -> None:
    note("\n## 19. The rails: rounds, slots 0, the budget, the long gate")
    _, a = prepare_cr(w, "Rail one")
    _, b = prepare_cr(w, "Rail two")
    slow = w.root / "slow_long.py"  # a suite that ends when its release file exists (event-driven)
    slow.write_text(
        "import os, sys, time\nend = time.time() + 180\n"
        "while not os.path.exists(sys.argv[1]) and time.time() < end:\n"
        "    time.sleep(0.05)\n"
    )

    def held_suite(name):
        release = w.root / f"release_{name}"
        release.unlink(missing_ok=True)
        return f'"{sys.executable}" "{slow}" "{release}"', release

    def newest_log_of(cr):
        logs = sorted((w.state / w.cr(cr)["path"] / "work" / "gates").glob("*.log"))
        return logs[-1].read_text("utf-8") if logs else ""

    def release_when_logged(cr, text, release, since):
        """The held suite ends once `cr`'s gate has been seen waiting, and at least a second after
        `since`: the check asserts the order, never how long the machine took."""
        end = time.monotonic() + 45
        while text not in newest_log_of(cr) and time.monotonic() < end:
            time.sleep(0.05)
        time.sleep(max(0.0, 1.05 - (time.monotonic() - since)))
        release.touch()

    long_gate, free = held_suite("free")  # already released: this gate returns at once
    free.touch()
    w.reset()
    w.start(str(a), str(b), "--slots", 1, "--budget", 1, "--default-branch", "main")
    w.env["CHANTIER_BATCH"] = w.name
    w.chantier("foreman", "set", "local_foreman7", "--epoch", 1)
    fm = Foreman(w, epoch=1)
    fm.turn()
    one, two = (c["id"] for c in w.batch()["crs"])
    check("one slot: one Driver", fm.started == [one])
    w.chantier("round", one)  # the rounds' refusals are pytest's (test_rail_refusals.py)
    for i in range(2):
        w.chantier("note", one, f"round {i + 1} done")
        w.chantier("round", one)
    w.chantier("order", "rounds", one, "--note", "4")
    fm.turn()  # the Driver is live: the Foreman tells it, the order is done
    w.chantier("note", one, "the limit was raised")
    w.chantier("round", one)
    w.chantier("order", "slots", "--note", "0")
    commit(w, one, "rail.py", "RAIL = 1\n")
    _, out = w.chantier("ship", one, "https://example.invalid/pr/0")
    check("`ship` reports a head not pushed and no long gate passed at it",
          any("is not pushed" in ln for ln in out) and any("no long gate passed" in ln for ln in out),
          str(out))
    ship(w, one, "feat: rail")
    _, out = w.ready(one, w.cr(one)["pr"])
    check("the hand-back stands: CI is the Driver's judgement, not the CLI's",
          w.cr(one)["status"] == "ready", str(out))
    w.chantier("order", "slots", "--note", "1")
    state = w.folder() / "batch.json"
    data = w.batch()
    state.write_text(json.dumps({**data, "spent_usd": 2}))
    fm.turn()
    check("the Foreman asks the Chief of Staff for budget",
          fm.asked[-1].startswith("budget ") and w.cr(two)["status"] == "queued", str(fm.asked))
    w.chantier("order", "budget", "--note", "10")
    fm.turn()
    check("a wider budget lets the next Driver start", fm.started[-1] == two)
    _, out = w.chantier("handoff", one)
    check("`handoff` gives a fresh agent the CR on one screen",
          out[0].startswith(f'{one} "Rail one" (change) ready') and any("rounds: 4 of 4" in ln
                                                                        for ln in out)
          and any(ln.startswith("PR: ") for ln in out), str(out))
    w.chantier("order", "slots", "--note", "2")
    w.chantier("agents", "set", one, "-", "--epoch", 1)
    w.chantier("take", one, "--note", "rebase: main moved; the PR no longer merges", "--epoch", 1)

    def gate_proc(cr, command):
        return subprocess.Popen(
            [sys.executable, "-m", "chantier", "gate", cr, command],
            cwd=w.work,
            env=w.env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )

    command, release = held_suite("one")
    held = gate_proc(one, command)
    lock_names(w, f"{one} pid")
    started = time.monotonic()
    waiter = gate_proc(two, command)
    release_when_logged(two, "waiting for the long gate of", release, started)
    out, _ = waiter.communicate(timeout=120)
    waited = time.monotonic() - started
    held.communicate(timeout=120)
    check(
        "a second long gate waits for the first (one long gate at a time)",
        waiter.returncode == 0
        and waited >= 1
        and "waiting for the long gate of" in newest_log_of(two),
        f"{waited:.1f}s {out}",
    )
    command, release = held_suite("died")
    held = gate_proc(one, command)
    lock_names(w, " pg")
    held.kill()  # the command dies; its suite runs on in its own process group
    held.communicate(timeout=120)
    started = time.monotonic()
    waiter = gate_proc(two, command)
    release_when_logged(two, "its command still runs", release, started)
    out, _ = waiter.communicate(timeout=120)
    waited = time.monotonic() - started
    check(
        "a long gate whose command died still holds the next one while its suite runs",
        waiter.returncode == 0 and waited >= 1 and "its command still runs" in newest_log_of(two),
        f"{waited:.1f}s {out}",
    )

    # the queue: first come, first served
    queue_gate = long_gate  # released: every gate that gets the lock ends at once
    queue = w.state / ".long-gate.queue"

    def tickets():
        return sorted(p for p in queue.glob("[0-9]*")) if queue.is_dir() else []

    def wait_tickets(n):
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline and len(tickets()) < n:
            time.sleep(0.05)

    def queued_gate(cr):
        return subprocess.Popen([sys.executable, "-m", "chantier", "gate", cr, queue_gate],
                                cwd=w.work, env=w.env, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True, encoding="utf-8")

    def gate_events():
        return [json.loads(ln) for ln in (w.folder() / "events.jsonl").read_text("utf-8").splitlines()
                if json.loads(ln)["kind"] == "gate"]

    queue_gate, queue_release = held_suite("queue")  # held until the queue is seen as it should be
    before = len(gate_events())
    first = queued_gate(one)
    lock_names(w, f"{one} pid")
    time.sleep(1.1)  # the logs are named by the second: three gates, three names
    second = queued_gate(two)
    wait_tickets(1)
    time.sleep(1.1)
    third = queued_gate(one)
    wait_tickets(2)
    release_when_logged(one, f"queued ahead: {two}", queue_release, time.monotonic())
    outs = [p.communicate(timeout=180) for p in (first, second, third)]
    order = [e["cr"] for e in gate_events()[before:]]
    third_log = max((w.state / w.cr(one)["path"] / "work" / "gates").glob("*.log")).read_text("utf-8")
    check("long gates take the lock in arrival order; the later waiter's log names the earlier one "
          "(`queued ahead:`); the queue is empty at the end",
          [p.returncode for p in (first, second, third)] == [0, 0, 0] and order == [one, two, one]
          and f"queued ahead: {two}" in third_log and not tickets(), f"{order} {outs} {third_log}")

    queue_gate, queue_release = held_suite("queue2")
    first = queued_gate(one)
    lock_names(w, f"{one} pid")
    time.sleep(1.1)
    dead = queued_gate(two)
    wait_tickets(1)
    dead.kill()  # a waiter whose `gate` command ended leaves its ticket behind
    dead.communicate(timeout=120)
    left = len(tickets())
    time.sleep(1.1)
    next_gate = queued_gate(two)
    release_when_logged(two, "waiting for the long gate of", queue_release, time.monotonic())
    out, _ = next_gate.communicate(timeout=120)
    code = next_gate.returncode
    first.communicate(timeout=180)
    log = newest_log_of(two)
    check("a waiter killed in the queue leaves a ticket that the next gate skips",
          left == 1 and code == 0 and "queued ahead" not in log and not tickets(),
          f"{left} {out} {log} {tickets()}")

    # a pid that a later process reuses is not the one the file recorded
    def newest_log(cr):
        return max((w.state / w.cr(cr)["path"] / "work" / "gates").glob("*.log")).read_text("utf-8")

    sleeper = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(600)"])
    import psutil
    born = psutil.Process(sleeper.pid).create_time()
    gone = subprocess.Popen([sys.executable, "-c", "pass"])
    gone.wait()
    lock = w.state / ".long-gate.lock"

    def reused_lock(cr):
        lock.write_bytes(b"\0" + f"{cr} pid {gone.pid} pg{sleeper.pid}".encode())
        # the lock dates from before the sleeper was created, so the sleeper is a reused pid
        # however long the section runs (within the sleeper's 600 s)
        back = born - 60
        os.utime(lock, (back, back))

    reused_lock(one)
    started = time.monotonic()
    code, out = w.chantier("gate", two, long_gate)
    check("a lock naming a reused pid is not waited for: the next gate runs at once",
          code == 0 and time.monotonic() - started < 60
          and "its command still runs" not in newest_log(two), f"{out} {newest_log(two)}")
    # a waiting gate's ticket that names a reused pid is skipped like a dead one
    (w.state / ".long-gate.queue").mkdir(exist_ok=True)
    stale = w.state / ".long-gate.queue" / f"{int((born - 60) * 10**9):020d}-{sleeper.pid}"
    stale.write_text(f"{one} pid {sleeper.pid}", encoding="utf-8")
    back = born - 60
    os.utime(stale, (back, back))
    code, out = w.chantier("gate", two, queue_gate)
    check("a ticket naming a reused pid is deleted by the next gate and not waited for",
          code == 0 and not stale.exists() and "queued ahead" not in newest_log(two),
          f"{out} {newest_log(two)}")
    reused_lock(one)
    code, out = drop_then_cancel(w, one, 1)
    check("`cancel` does not signal a reused pid: no `pg` in `stopped …`, the process lives on",
          code == 0 and f"pg{sleeper.pid}" not in "".join(out) and sleeper.poll() is None, str(out))
    reused_lock(two)
    code, out = w.chantier("order", "merged", two, "--epoch", 1)
    check("`order merged` does not signal a reused pid: no `stopped` line, the process lives on",
          code == 0 and not any("stopped" in ln for ln in out) and sleeper.poll() is None, str(out))
    lock.write_bytes(b"\0")

    sleeper.kill()
    sleeper.wait()


def gate_parallel(w: World) -> None:
    note("\n## 19b. The long gate: as many at once as chantier.yaml says, a stop per slot, `--first`")
    sys.path.insert(0, str(SKILL / "scripts" / "cli" / "src"))
    from chantier import procs

    items = [prepare_cr(w, t)[1] for t in ("Par one", "Par two", "Par three", "Par four")]
    slow = w.root / "slow_par.py"
    slow.write_text(
        "import os, sys, time\n"
        "open(os.path.join(os.path.dirname(__file__), 'par_' + sys.argv[1] + '.pid'), 'w')"
        ".write(str(os.getpid()))\nend = time.time() + 180  # ends on its release file\n"
        "release = os.path.join(os.path.dirname(__file__), 'par_' + sys.argv[1] + '.release')\n"
        "while not os.path.exists(release) and time.time() < end:\n    time.sleep(0.05)\n"
    )
    yaml = w.work / "chantier.yaml"
    yaml.unlink(missing_ok=True)
    w.reset()
    w.start(*map(str, items), "--slots", 4, "--default-branch", "main")
    w.env["CHANTIER_BATCH"] = w.name
    w.chantier("foreman", "set", "local_foreman19b", "--epoch", 1)
    Foreman(w, epoch=1).turn()
    one, two, three, four = (c["id"] for c in w.batch()["crs"])
    queue = w.state / ".long-gate.queue"

    def release(name):
        (w.root / f"par_{name}.release").touch()

    def spawn(cr, name, hold=True):
        """A long gate whose suite ends on `release(name)`; with `hold` False it ends at once."""
        (w.root / f"par_{name}.release").unlink(missing_ok=True)
        if not hold:
            release(name)
        gate = f'"{sys.executable}" "{slow}" {name}'
        return subprocess.Popen([sys.executable, "-m", "chantier", "gate", cr, gate], cwd=w.work,
                                env=w.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, encoding="utf-8")

    def log(cr):
        return max((w.at(w.cr(cr)["path"]) / "work" / "gates").glob("*.log")).read_text("utf-8")

    def tickets():
        return sorted(queue.glob("[0-9]*")) if queue.is_dir() else []

    def wait_tickets(n):
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline and len(tickets()) < n:
            time.sleep(0.05)

    def suite_pid(name):  # the pid the slow suite wrote once it runs
        pidfile = w.root / f"par_{name}.pid"
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline and not (pidfile.exists() and pidfile.read_text()):
            time.sleep(0.05)
        return int(pidfile.read_text())

    def kinds(kind):
        return [json.loads(ln) for ln in (w.folder() / "events.jsonl").read_text("utf-8").splitlines()
                if json.loads(ln)["kind"] == kind]

    def activity():
        _, o = w.chantier("status", "--refresh", "--epoch", 1, expect=None)
        return {ln.split()[1]: ln for ln in o if ln.startswith("activity ")}

    # E5. the move-up, with one long gate at a time
    yaml.write_text("long_gate:\n  parallel: 1\n", encoding="utf-8")
    first = spawn(one, "q1")
    lock_names(w, f"{one} pid")
    second = spawn(two, "q2", hold=False)
    wait_tickets(1)
    time.sleep(1.1)  # the logs are named by the second
    third = spawn(three, "q3", hold=False)
    wait_tickets(2)
    code, _ = w.chantier("gate", three, "--first", expect=2)
    refusal = w.last_stderr
    code1, _ = w.chantier("gate", three, "--first", "--epoch", 1, GATE, expect=1)
    code2, out = w.chantier("gate", three, "--first", "--epoch", 1)
    lines = activity()
    check("E5: `gate <cr> --first` without `--epoch` exits 2 with the refusal's text, with a command exits 1, "
          "and with `--epoch` prints where the gate went and records `gate-first`",
          code == 2 and "the steering session's command" in refusal and code1 == 1 and code2 == 0
          and out == [f"moved the long gate of {three} to the head of the queue (ahead of: {two})"]
          and [e["cr"] for e in kinds("gate-first")] == [three], f"{refusal} {out}")
    check("E5: `status` shows `gate queued behind` the holder for the moved gate while it waits",
          lines[three] == f"activity {three} gate queued behind {one}", str(lines))
    release("q1")  # the holder ends: the queue empties by its order
    for p in (first, second, third):
        p.communicate(timeout=180)
    order = [e["cr"] for e in kinds("gate")][-3:]
    code, out = w.chantier("gate", two, "--first", "--epoch", 1)
    check("E5: the moved gate runs before the earlier one; `--first` of a CR with no ticket says there is "
          "nothing to move and exits 0; no `first-*` marker is left",
          order == [one, three, two] and code == 0 and any("nothing to move" in ln for ln in out)
          and not list(queue.glob("first-*")) and not tickets(), f"{order} {out}")

    # E2, E3. two at once
    yaml.write_text("long_gate:\n  parallel: 2\n", encoding="utf-8")
    first = spawn(one, "a1")
    named1 = lock_names(w, f"{one} pid")
    second = spawn(two, "a2")
    named2 = lock_names(w, f"{two} pid", 2) and lock_names(w, " pg", 2)
    wait3 = spawn(three, "a3", hold=False)
    wait_tickets(1)
    time.sleep(1.1)
    wait4 = spawn(four, "a4", hold=False)
    wait_tickets(2)
    lines = activity()
    check("E2: with `parallel: 2` two long gates run at once, one in each slot",
          named1 and named2 and first.poll() is None and second.poll() is None)
    check("E3: both running CRs show `gate running`, the waiting ones `gate queued behind <one>, <two>`",
          lines[one] == f"activity {one} gate running" and lines[two] == f"activity {two} gate running"
          and lines[three] == f"activity {three} gate queued behind {one}, {two}"
          and lines[four] == f"activity {four} gate queued behind {one}, {two}", str(lines))
    release(
        "a2"
    )  # the second ends, then the two waiters run in their arrival order, then the first
    outs = [p.communicate(timeout=240) for p in (second, wait3, wait4)]
    release("a1")
    outs.append(first.communicate(timeout=240))
    order = [e["cr"] for e in kinds("gate")][-4:]
    check("E2: the second gate ran with no waiting line and ended before the first; a third waited "
          "naming both holders; the waiters took a slot in arrival order",
          "waiting for the long gate" not in log(two)
          and re.search(rf"waiting for the long gate of {one} pid .* and {two} pid ", log(three))
          and [p.returncode for p in (first, second, wait3, wait4)] == [0, 0, 0, 0]
          and order == [two, three, four, one] and not tickets(), f"{order} {outs} {log(three)}")

    # E4. a stop acts on its slot only
    first = spawn(one, "hold")
    lock_names(w, " pg")
    held_pid = suite_pid("hold")
    second = spawn(two, "stop")
    lock_names(w, " pg", 2)
    two_pid = suite_pid("stop")
    code, _ = w.chantier("gate", two, "--stop")
    out, err = second.communicate(timeout=120)
    time.sleep(0.5)
    check("E4: `gate <cr> --stop` stops the suite of its own slot only: its gate says STOPPED and exits 4, "
          "the other slot's suite runs on",
          code == 0 and out.startswith("STOPPED") and second.returncode == 4 and not procs.alive(two_pid)
          and procs.alive(held_pid) and first.poll() is None and "Traceback" not in err, f"{out} {err}")
    second = spawn(two, "merge")
    lock_names(w, " pg", 2)
    two_pid = suite_pid("merge")
    def stopped_events():
        return [e for e in kinds("gate") if e["cr"] == two and e.get("result") == "stopped"]

    stopped_before = len(stopped_events())
    code, _ = w.chantier("order", "merged", two, "--epoch", 1)
    ended = second.poll() is not None  # the order waited for the gate's process to end
    out, err = second.communicate(timeout=120)
    time.sleep(0.5)
    last = log(two).rstrip("\n").splitlines()[-1]
    check("E4: `order merged` stops its CR's gate only, and waits for it to end before the move",
          code == 0 and ended and out.startswith("STOPPED") and second.returncode == 4
          and "Traceback" not in err and re.fullmatch(r"result: stopped at \S+: no pass", last)
          and len(stopped_events()) == stopped_before + 1
          and "3-done" in w.cr(two)["path"].replace("\\", "/")
          and not procs.alive(two_pid) and procs.alive(held_pid)
          and first.poll() is None, f"{out} {err} {last} {second.returncode}")
    third = spawn(three, "cancel")
    lock_names(w, " pg", 2)
    three_pid = suite_pid("cancel")
    code, _ = w.chantier("gate", four, "--stop", expect=2)
    named = w.last_stderr + "".join(w.last_out)
    check("E4: `gate <cr> --stop` with no slot naming the CR exits 2, names the running CRs and stops nothing",
          code == 2 and one in named and three in named and "not stopped" in named
          and procs.alive(three_pid) and procs.alive(held_pid), named)
    drop_then_cancel(w, three, 1)
    third.communicate(timeout=120)
    time.sleep(0.5)
    check("E4: `cancel` stops its CR's suite only",
          not procs.alive(three_pid) and procs.alive(held_pid) and first.poll() is None)
    w.chantier("gate", one, "--stop")
    first.communicate(timeout=120)
    yaml.unlink(missing_ok=True)
    (w.state / ".long-gate.2.lock").unlink(missing_ok=True)


def driver_liveness(w: World) -> None:
    note("\n## 12c. A Driver that dies: activity lines, the restart path, the `context:` hand-back")
    items = [prepare_cr(w, t)[1] for t in ("Live one", "Live two", "Live three")]
    w.reset()
    w.start(*(str(p) for p in items), "--slots", 3, *FROM_AGENTS_MD)
    w.env["CHANTIER_BATCH"] = w.name
    w.chantier("foreman", "set", "uuid-live", "--epoch", 1)
    w.chantier("foreman", "transcript", "uuid-live", "--epoch", 1)
    one, two, three = (c["id"] for c in w.batch()["crs"])
    for cr in (one, two, three):
        w.chantier("take", cr, "--epoch", 1)
        w.chantier("agents", "set", cr, f"agent-{cr}", "--epoch", 1)
        start_driver(w, cr)
    slug = "".join(ch if ch.isalnum() else "-" for ch in str(w.work.resolve()))
    chief = w.root / "claude-projects" / slug / "uuid-live.jsonl"
    chief.parent.mkdir(parents=True, exist_ok=True)
    chief.write_text(json.dumps({"type": "assistant", "timestamp": datetime.now(timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%S.000Z"), "message": {"id": "l1", "model": "claude-sonnet-5-5", "usage": {
            "input_tokens": 10, "output_tokens": 100, "cache_read_input_tokens": 0}}}) + "\n")
    sub = chief.with_suffix("") / "subagents"  # a Driver of the first CR and its worker
    sub.mkdir(parents=True, exist_ok=True)
    (sub / f"agent-agent-{one}.jsonl").write_text("{}\n")
    (sub / "agent-w1.jsonl").write_text("{}\n")
    (sub / "agent-w1.meta.json").write_text(json.dumps({"parentAgentId": f"agent-{one}"}))
    me = os.getpid()  # a live process, older than the lock written now
    lock = w.state / ".long-gate.lock"
    lock.write_bytes(b"\0" + f"{three} pid {me}".encode())
    code, out = w.chantier("status", "--refresh", "--epoch", 1, expect=None)
    lines = {ln.split()[1]: ln for ln in out if ln.startswith("activity ")}
    check("`status --refresh` gives one activity age per working CR, and no longest silent Driver",
          code == 0 and set(lines) == {one, two, three}
          and re.fullmatch(rf"activity {one} \d+ min", lines[one])
          and lines[two] == f"activity {two} not measured"
          and lines[three] == f"activity {three} gate running"
          and not any("longest silent" in ln for ln in out), str(out))
    queue = w.state / ".long-gate.queue"
    queue.mkdir(exist_ok=True)
    ticket = queue / f"{time.time_ns():020d}-{me}"
    ticket.write_text(f"{two} pid {me}", encoding="utf-8")

    def activity_lines():
        _, o = w.chantier("status", "--refresh", "--epoch", 1, expect=None)
        return {ln.split()[1]: ln for ln in o if ln.startswith("activity ")}

    lines = activity_lines()
    check("a live ticket of the queue gives `gate queued behind <holder>`, and `status` keeps it",
          lines[two] == f"activity {two} gate queued behind {three}" and ticket.exists(), str(lines))
    lock.write_bytes(b"\0")
    lines = activity_lines()
    check("with the lock empty and a live ticket alone the line is `gate queued`",
          lines[two] == f"activity {two} gate queued", str(lines))
    done = subprocess.Popen([sys.executable, "-c", "pass"])
    done.wait()
    lock.write_bytes(b"\0" + f"{three} pid {done.pid}".encode())
    ticket.write_text(f"{two} pid {done.pid}", encoding="utf-8")
    lines = activity_lines()
    check("a lock or a ticket naming a dead pid is no gate: an age, never `gate running` or "
          "`gate queued`",
          lines[three] == f"activity {three} not measured" and lines[two] == f"activity {two} not measured"
          and ticket.exists(), str(lines))
    ticket.unlink()
    lock.unlink()
    w.chantier("agents", "set", one, "-", "--epoch", 1)
    _, out = w.chantier("note", one, "no Driver recorded")
    check("`note` prints `context: not measured (no agent recorded)` with no agent recorded",
          out == ["ok", "context: not measured (no agent recorded)"], str(out))
    w.chantier("agents", "set", one, f"agent-{one}", "--epoch", 1)
    _, out = w.chantier("note", one, "agent without a record")
    check("`note` says so when the recorded agent's transcript is missing",
          out[1].startswith("context: not measured (no transcript found"), str(out))

    def usage_line(mid, inp, write, read):
        return json.dumps({"type": "assistant", "message": {"id": mid, "model": "claude-sonnet-5-5",
                           "usage": {"input_tokens": inp, "output_tokens": 5,
                                     "cache_creation": {"ephemeral_5m_input_tokens": write,
                                                        "ephemeral_1h_input_tokens": 30},
                                     "cache_read_input_tokens": read}}})
    (sub / f"agent-agent-{one}.jsonl").write_text(
        usage_line("d1", 100, 0, 8870) + "\n"
        + json.dumps({"type": "system", "subtype": "compact_boundary"}) + "\n"
        + usage_line("d2", 10, 200, 4000) + "\n" + json.dumps({"type": "user"}) + "\n",
        encoding="utf-8")
    _, out = w.chantier("note", one, "context measured")
    check("`note` prints the last call's prompt size: input, cache writes and cache reads of "
          "the recorded agent's transcript",
          out == ["ok", f"context: 4240 tokens (agent agent-{one})"], str(out))
    _, out = w.chantier("cost", "--by", "cr", expect=None)
    line = next((ln for ln in out if ln.startswith(f"{one}:")), "")
    check("`cost --by cr` shows the Driver's peak context and compactions on the CR's line",
          "Driver peak context 9,000 tokens, 1 compaction)" in line, str(out))
    def tool_line(name):
        return json.dumps({"type": "assistant", "message": {"id": "t", "content": [
            {"type": "tool_use", "name": name, "input": {}}]}})

    def flagged(cr, agent):
        _, o = w.chantier("status")
        return any(ln.startswith(f"{cr} ") and f"Driver {agent} ended, no hand-back recorded" in ln
                   for ln in o)

    events = w.folder() / "events.jsonl"
    log_before = events.read_text("utf-8")
    ended = sub / f"agent-agent-{one}.jsonl"
    ended.write_text(tool_line("SubagentHandback") + "\n" + json.dumps({"type": "user"}) + "\n",
                     encoding="utf-8")
    check("status flags a working CR whose Driver's last tool call is the host's hand-back",
          flagged(one, f"agent-{one}"), "no flag")
    with ended.open("a", encoding="utf-8") as f:
        f.write(tool_line("PowerShell") + "\n")
    check("a Driver that went on after its hand-back (a later tool call) is not flagged",
          not flagged(one, f"agent-{one}"), "flagged")
    check("`status` writes no event for the flag",
          events.read_text("utf-8") == log_before, "status logged")
    def task_status(agent, status, ago=0):
        at = datetime.now(timezone.utc) - timedelta(seconds=ago)
        with chief.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"type": "attachment", "timestamp": at.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
                                "attachment": {"type": "task_status", "taskId": agent,
                                               "status": status}}) + "\n")

    def stopped(cr, agent):
        _, o = w.chantier("status")
        return any(ln.startswith(f"{cr} ") and f"Driver {agent} stopped from outside, no hand-back "
                   "recorded" in ln for ln in o)

    task_status(f"agent-{one}", "killed")
    check("status flags a working CR whose recorded agent the host reports stopped (a `killed` "
          "`task_status` record), and not as `ended`",
          stopped(one, f"agent-{one}") and not flagged(one, f"agent-{one}"), "no flag")
    task_status(f"agent-{one}", "running")
    check("a later `task_status` record for the agent clears the flag (the last record decides)",
          not stopped(one, f"agent-{one}"), "still flagged")
    task_status(f"agent-{two}", "killed")
    check("a `killed` record for another agent flags nothing on this CR",
          not stopped(one, f"agent-{one}") and stopped(two, f"agent-{two}"), "wrong flag")
    task_status(f"agent-{one}", "killed", ago=3600)
    check("a `killed` record older than the agent's `agent` event flags nothing (the scan's bound)",
          not stopped(one, f"agent-{one}"), "flagged")
    check("`status` writes no event for the stopped flag",
          events.read_text("utf-8") == log_before, "status logged")
    w.chantier("agents", "set", "stack", "agent-stack", "--epoch", 1)

    def stack_flagged():
        _, o = w.chantier("status", "--refresh", "--epoch", 1, expect=None)
        return any(ln.startswith("activity stack ") and "Driver agent-stack stopped from outside, "
                   "no hand-back recorded" in ln for ln in o)

    task_status("agent-stack", "killed")
    check("`status --refresh` flags the stack driver's `activity stack` line when the host reports "
          "it stopped", stack_flagged(), "no flag")
    with chief.open("a", encoding="utf-8") as f:  # a record with no timestamp, then a stamped one
        f.write(json.dumps({"type": "attachment", "attachment": {
            "type": "task_status", "taskId": "agent-stack", "status": "killed"}}) + "\n")
    task_status("agent-stack", "running")
    check("a later timestamped record overrides an earlier record with no timestamp",
          not stack_flagged(), "still flagged")
    w.chantier("agents", "set", "stack", "-", "--epoch", 1)
    rounds = w.cr(one)["round"]
    w.chantier("agents", "set", one, "-", "--epoch", 1)
    task_status(f"agent-{one}", "killed")
    _, out = w.chantier("status")
    check("after `agents set <cr> -` the row shows `no Driver recorded` and no stopped flag",
          any(ln.startswith(f"{one} working") and "no Driver recorded" in ln for ln in out)
          and not any("stopped from outside" in ln for ln in out if ln.startswith(one)), str(out))
    code, _ = w.chantier("take", one, "--note", "resume: stopped from outside: x", "--epoch", 1)
    check("the restart `take` after an outside stop is accepted, no round counted",
          code == 0 and w.cr(one)["round"] == rounds, w.last_stderr)
    w.chantier("agents", "set", one, f"agent-{one}-s2", "--epoch", 1)
    task_status(f"agent-{one}-s2", "killed")
    check("a second Driver's `killed` record flags it", stopped(one, f"agent-{one}-s2"), "no flag")
    w.chantier("agents", "set", one, "-", "--epoch", 1)
    code, _ = w.chantier("take", one, "--note", "resume: stopped from outside: x", "--epoch", 1)
    check("a second outside stop is restarted the same way: accepted, no round counted, no block",
          code == 0 and w.cr(one)["round"] == rounds and w.cr(one)["status"] == "working",
          w.last_stderr)
    w.chantier("agents", "set", one, f"agent-{one}-s3", "--epoch", 1)
    (sub / f"agent-agent-{three}.jsonl").write_text(tool_line("SubagentHandback") + "\n",
                                                    encoding="utf-8")
    w.chantier("handback", three, "blocked", "question: x")
    _, out = w.chantier("status")
    check("once the hand-back is recorded the row shows blocked, with no flag",
          any(ln.startswith(f"{three} blocked") for ln in out)
          and not any("ended, no hand-back recorded" in ln for ln in out if ln.startswith(three)),
          str(out))
    w.chantier("agents", "set", three, "-", "--epoch", 1)
    w.chantier("take", three, "--note", "resume: x", "--epoch", 1)
    w.chantier("agents", "set", three, f"agent-{three}", "--epoch", 1)
    chief.unlink()
    shutil.rmtree(sub)
    code, out = w.chantier("status", "--refresh", "--epoch", 1, expect=None)
    check("with no readable session record the line says not measured, and the exit code is the "
          "spend's own", code == 4 and f"activity {one} not measured" in out
          and any(ln.startswith("spend not updated") for ln in out), str(out))
    code, _ = w.chantier("take", one, "--epoch", 1, expect=2)
    check("`take` of a working CR without a note is refused (exit 2)",
          code == 2 and "only with `--note`" in w.last_stderr, w.last_stderr)
    code, _ = w.chantier("take", one, "--note", "resume: x", "--epoch", 1, expect=2)
    check("`take` of a CR with an agent recorded is refused, naming `agents set <cr> -`",
          code == 2 and f"agents set {one} -" in w.last_stderr, w.last_stderr)
    rounds = w.cr(one)["round"]
    w.chantier("agents", "set", one, "-", "--epoch", 1)
    _, out = w.chantier("status")
    check("status flags a working CR with no Driver recorded",
          any(ln.startswith(f"{one} working") and "no Driver recorded" in ln for ln in out), str(out))
    check("a working CR with no agent recorded gets no `ended` flag",
          not any("ended, no hand-back recorded" in ln for ln in out if ln.startswith(one)), str(out))
    code, out = w.chantier("take", one, "--note", "resume: x", "--epoch", 1)
    _, facts = w.chantier("handoff", one)
    kinds = [json.loads(ln) for ln in (w.folder() / "events.jsonl").read_text("utf-8").splitlines()]
    check("after `agents set <cr> -` the restart is accepted: same slots held, no round counted, "
          "the note in the facts, the take logged as a restart",
          code == 0 and "(3 of 3 slots held)" in out[0] and w.cr(one)["round"] == rounds
          and w.cr(one)["notes"][-1] == "back to a Driver: resume: x"
          and any("resume: x" in ln for ln in facts)
          and [e for e in kinds if e["kind"] == "take" and e["cr"] == one][-1].get("restart") is True,
          str(out))
    w.chantier("agents", "set", one, f"agent-{one}-2", "--epoch", 1)
    data = w.batch()
    (w.folder() / "batch.json").write_text(json.dumps({**data, "budget_usd": 1, "spent_usd": 2}))
    w.chantier("agents", "set", one, "-", "--epoch", 1)
    code, _ = w.chantier("take", one, "--note", "resume: x", "--epoch", 1, expect=5)
    check("a restart past the budget is refused (exit 5)", code == 5, w.last_stderr)
    (w.folder() / "batch.json").write_text(json.dumps(data))
    code, out = w.chantier("handback", two, "blocked", "context: stopped at the tests, run them next")
    check("`handback blocked context:` leaves the CR blocked and prints the restart line, not the "
          "ask line", code == 0 and w.cr(two)["status"] == "blocked"
          and w.cr(two)["blocked_reason"].startswith("context:")
          and any("restarts a fresh Driver" in ln for ln in out)
          and not any("asks the Chief of Staff" in ln for ln in out), str(out))
    rounds = w.cr(two)["round"]
    w.chantier("agents", "set", two, "-", "--epoch", 1)
    code, _ = w.chantier("take", two, "--note", "resume: context", "--epoch", 1)
    check("a fresh Driver takes it back with the note, the round unchanged",
          code == 0 and w.cr(two)["status"] == "working" and w.cr(two)["round"] == rounds,
          w.last_stderr)
    code, out = w.chantier("handback", two, "blocked",
                           "context: closing: VERIFIED at abc1234; next: description pass")
    check("`handback blocked context: closing:` leaves the CR blocked and prints the closing-step "
          "line, not the out-of-context or ask line",
          code == 0 and w.cr(two)["status"] == "blocked"
          and w.cr(two)["blocked_reason"].startswith("context: closing:")
          and any("for the closing step" in ln for ln in out)
          and not any("out of context" in ln or "asks the Chief of Staff" in ln for ln in out),
          str(out))
    rounds = w.cr(two)["round"]
    w.chantier("agents", "set", two, "-", "--epoch", 1)
    code, _ = w.chantier("take", two, "--note", "resume: closing", "--epoch", 1)
    check("a fresh Driver takes the closing step back with `resume: closing`, the round unchanged",
          code == 0 and w.cr(two)["status"] == "working" and w.cr(two)["round"] == rounds,
          w.last_stderr)
    cards = HERE.parent / "skills" / "chantier" / "references"
    foreman = (cards / "foreman.md").read_text(encoding="utf-8")
    driver = (cards / "driver.md").read_text(encoding="utf-8")
    check("foreman.md names the suspect rule, the two proofs of death, the new-epoch rule, the "
          "`context:` case and what counts toward `ended twice`; driver.md lists `context:`",
          all(s in foreman for s in ("**Suspect:**", "**Proof of death**", "new Foreman epoch",
                                     "blocked context: …", "driver ended twice", "do not."))
          and "`context: <where it stopped" in driver
          and "`resume: closing`" in driver and "`context: closing:" in driver
          and "resume: closing" in foreman)
    flat_driver, flat_foreman = " ".join(driver.split()), " ".join(foreman.split())
    check("driver.md names the 115,000-token closing threshold and the three `closing:` step notes; "
          "foreman.md names the second `context: closing:` ask",
          "115,000 tokens" in flat_driver and "100,000 tokens" not in flat_driver
          and "100,000 tokens" not in flat_foreman and "`closing: body posted at <sha7>`" in flat_driver
          and "`closing: description pass VERIFIED at <sha7>`" in flat_driver
          and "`closing: PR ready`" in flat_driver and "`closing: PR kept draft on <base>`" in flat_driver
          and "second `context: closing:` hand-back" in flat_foreman
          and "`question <cr> driver out of context twice`" in flat_foreman)


def handback_proofs(w: World) -> None:
    note("\n## 12b. Handback ready needs two proofs at the PR's head: a long gate and a verdict")
    _, item = prepare_cr(w, "Proof one")
    w.reset()
    w.start(str(item), "--slots", 1, *FROM_AGENTS_MD)
    w.env["CHANTIER_BATCH"] = w.name
    w.chantier("foreman", "set", "local_foreman8", "--epoch", 1)
    fm = Foreman(w, epoch=1)
    fm.turn()
    cr = w.batch()["crs"][0]["id"]
    num = cr.removeprefix("CR-")
    folder = w.at(w.cr(cr)["path"])

    def log_events(kind):
        return [json.loads(ln) for ln in (w.folder() / "events.jsonl").read_text("utf-8").splitlines()
                if json.loads(ln)["kind"] == kind and json.loads(ln)["cr"] == cr]

    commit(w, cr, "proof.py", "PROOF = 1\n")
    ship(w, cr, "feat: proof")
    link = w.cr(cr)["pr"]
    code, _ = w.chantier("handback", cr, "ready", link, expect=2)
    check("`handback ready` with no long gate passed is refused, naming the long gate",
          code == 2 and "no long gate passed" in w.last_stderr, w.last_stderr)
    gate_two = f"\"{sys.executable}\" -c \"print(1)\""
    code, out = w.chantier("gate", num, GATE, gate_two)
    runs = {e.get("run") for e in log_events("gate")}
    check("a two-command gate passes: one pass line each, one run id, and `gate` takes a bare number",
          code == 0 and out[0].startswith(f"pass {GATE} at ") and out[1].startswith("pass ")
          and out[2].startswith("log ") and len(runs) == 1 and None not in runs, str(out))
    code, _ = w.chantier("handback", cr, "ready", link, expect=2)
    check("`handback ready` with the gate but no verdict is refused, naming the verdict",
          code == 2 and "no verdict VERIFIED" in w.last_stderr
          and "no long gate passed" not in w.last_stderr, w.last_stderr)
    wt_path = w.cr(cr)["worktree"]
    verify_note = folder / "work" / "verify.md"
    before = len(log_events("verdict"))
    code, _ = w.chantier("verdict", cr, "VERIFIED", expect=2)
    check("`verdict VERIFIED` with no work/verify.md is refused, naming the file and `no such file`, "
          "and logs no event",
          code == 2 and "work/verify.md" in w.last_stderr and "no such file" in w.last_stderr
          and len(log_events("verdict")) == before, w.last_stderr)
    previous = subprocess.run(["git", "-C", wt_path, "rev-parse", "HEAD~1"], capture_output=True,
                              text=True, encoding="utf-8", check=True).stdout.strip()
    verify_note.parent.mkdir(parents=True, exist_ok=True)
    verify_note.write_text(f"Head: {previous}\n", encoding="utf-8", newline="\n")
    code, _ = w.chantier("verdict", cr, "VERIFIED", expect=2)
    check("`verdict VERIFIED` with a stale `Head:` line is refused, naming the other head, and "
          "logs no event",
          code == 2 and f"its Head: line names {previous[:7]}" in w.last_stderr
          and len(log_events("verdict")) == before, w.last_stderr)
    verify_note.unlink()
    code, _ = w.chantier("verdict", cr, "NOT VERIFIED")
    check("`verdict NOT VERIFIED` is accepted with no note: one event",
          code == 0 and len(log_events("verdict")) == before + 1, w.last_stderr)
    w.verified(num)
    w.chantier("verdict", cr, "NOT VERIFIED")
    code, _ = w.chantier("handback", cr, "ready", link, expect=2)
    check("a VERIFIED then a NOT VERIFIED at the same head refuses: the last verdict decides",
          code == 2 and "NOT VERIFIED" in w.last_stderr, w.last_stderr)
    code, _ = w.chantier("verdict", cr, "maybe", expect=1)
    check("a verdict is VERIFIED or NOT VERIFIED, nothing else, and the refusal quotes the word "
          "given and names both accepted words",
          code == 1 and '"maybe"' in w.last_stderr and "VERIFIED" in w.last_stderr
          and '"NOT VERIFIED"' in w.last_stderr, w.last_stderr)
    w.verified(cr)
    check("a later VERIFIED at the head lets the last verdict through",
          [e["result"] for e in log_events("verdict")][-1] == "VERIFIED"
          and len(log_events("verdict")) == 4)
    # a new commit, shipped: the gate and the verdict above are of the old head
    commit(w, cr, "proof2.py", "PROOF = 2\n")
    ship(w, cr, "feat: proof")
    code, _ = w.chantier("handback", cr, "ready", link, expect=2)
    check("a verdict and a gate made before a new commit do not count at the new head",
          code == 2 and "no long gate passed" in w.last_stderr
          and "no verdict VERIFIED" in w.last_stderr, w.last_stderr)
    code, _ = w.chantier("handback", cr, "ready", link, "--no-gate", "", expect=1)
    check("`--no-gate` with an empty reason is a usage error", code == 1, w.last_stderr)
    rule = "AGENTS.md declares no long gate for this change"
    code, _ = w.chantier("handback", cr, "ready", link, "--no-gate", rule, expect=2)
    check("`--no-gate` with no verdict at the head is refused", code == 2
          and "no verdict VERIFIED" in w.last_stderr and "no long gate" not in w.last_stderr,
          w.last_stderr)
    # the gate that fails on its second command stops there and logs no pass for it
    bad = f"\"{sys.executable}\" -c \"import sys; sys.exit(3)\""
    never = f"\"{sys.executable}\" -c \"print(2)\""
    code, out = w.chantier("gate", cr, GATE, bad, never, expect=4)
    gates = log_events("gate")
    check("a gate whose second command fails stops there and logs no pass for it (exit 4)",
          code == 4 and out[1].startswith("FAIL ") and not any("print(2)" in ln for ln in out[:2])
          and [e["result"] for e in gates[-2:]] == ["pass", "fail"]
          and not any(e["command"] == never for e in gates), str(out))
    code, _ = w.chantier("handback", cr, "ready", link, expect=2)
    check("a gate that failed leaves no gate passed at the head", code == 2
          and "no long gate passed" in w.last_stderr, w.last_stderr)
    w.verified(cr)
    _, out = w.chantier("handback", f"cr-{num}", "ready", link, "--no-gate", rule)
    check("`--no-gate <rule>` with a verdict is accepted: the reason is on the printed line, in "
          "the event and in STATUS.md",
          w.cr(cr)["status"] == "ready" and rule in out[0]
          and log_events("handback")[-1].get("no_gate") == rule
          and any("Long gate" in ln and rule in ln for ln in (folder / "STATUS.md").read_text(
              "utf-8").splitlines()), str(out))
    w.chantier("order", "slots", "--note", "2")
    fm.take(cr, "recheck the gates")
    facts = fm.facts
    check("`take` prints the two-gate checklist, marks following the events",
          any(ln.startswith("gates before handback ready") for ln in facts)
          and any(ln.startswith("  [ ] long gate") for ln in facts)
          and any(ln.startswith("  [x] verdict") for ln in facts), str(facts))
    w.chantier("gate", cr, GATE)
    _, out = w.chantier("handoff", cr)
    check("`handoff` prints the checklist too, with the gate now marked",
          any(ln.startswith("  [x] long gate") for ln in out)
          and any(ln.startswith("  [x] verdict") for ln in out), str(out))
    _, out = w.chantier("handback", num, "ready", link)
    check("after a passed gate and `verdict VERIFIED` at the head, `handback ready` is accepted",
          w.cr(cr)["status"] == "ready" and out[0].startswith(f"[driver {cr}"), str(out))
    code, out = w.chantier("ship", num, link)
    check("`ship`, `gate`, `handback` and `verdict` all resolve a bare number, or `cr-<n>`, to "
          f"{cr}", code == 0 and out[0].startswith("recorded "), str(out))

    # a ready CR goes back to its Driver by `take --note`, and hands back again
    handbacks = len(log_events("handback"))
    code, _ = w.chantier("handback", cr, "ready", link, expect=2)
    check("`handback ready` on a ready CR is refused with the `take` that reopens it",
          code == 2 and "is ready" in w.last_stderr and f"take {cr} --note" in w.last_stderr
          and "then hand back again" in w.last_stderr and w.cr(cr)["status"] == "ready"
          and len(log_events("handback")) == handbacks, w.last_stderr)
    _, out = w.chantier("order", "note", cr, "--note", "rebase: main moved")
    check("`order note` on a ready CR names the `take`",
          any(f"take {cr} --note" in ln for ln in out), str(out))
    before = w.cr(cr)["round"]
    w.chantier("agents", "set", cr, "-", "--epoch", 1)  # `take` wants the recorded agent cleared first
    w.chantier("take", cr, "--epoch", 1, "--note", "rebase: main moved")
    commit(w, cr, "rebased.py", "REBASED = 1\n")
    for extra in ([], ["--no-gate", rule]):
        code, _ = w.chantier("handback", cr, "ready", link, *extra, expect=2)
        check("after a commit with no `ship`, `handback ready` names the head `ship` recorded, "
              "alone" + (", with `--no-gate`" if extra else ""),
              code == 2 and "is not the head ship recorded" in w.last_stderr
              and f"ship {cr}" in w.last_stderr and "no long gate passed" not in w.last_stderr
              and "no verdict VERIFIED" not in w.last_stderr, w.last_stderr)
    ship(w, cr, "feat: rebased")
    code, _ = w.chantier("handback", cr, "ready", link, expect=2)
    check("after `ship`, the gate and the verdict are wanted at the new head",
          code == 2 and "no long gate passed" in w.last_stderr
          and "no verdict VERIFIED" in w.last_stderr, w.last_stderr)
    w.chantier("gate", cr, GATE)
    w.verified(cr)
    w.chantier("handback", cr, "ready", link)
    check("with `ship`, the gate and a verdict at the new head, the CR hands back ready again, "
          "in the same round", w.cr(cr)["status"] == "ready" and w.cr(cr)["round"] == before)
    w.chantier("agents", "set", cr, "-", "--epoch", 1)
    w.chantier("take", cr, "--epoch", 1, "--note", "answer: go")
    w.chantier("handback", cr, "blocked", "question: x")
    code, _ = w.chantier("handback", cr, "blocked", "question: y", expect=2)
    check("a second hand-back on a blocked CR is refused with the `take` that reopens it",
          code == 2 and "is blocked" in w.last_stderr and f"take {cr} --note" in w.last_stderr,
          w.last_stderr)
    # a blocked CR whose Driver is still recorded hands back ready, with no `take`
    code, _ = w.chantier("handback", cr, "ready", link, expect=2)
    check("`handback ready` on a blocked CR with no Driver recorded is refused with the `take` "
          "that reopens it", code == 2 and "is blocked" in w.last_stderr
          and f"take {cr} --note" in w.last_stderr and w.cr(cr)["status"] == "blocked",
          w.last_stderr)
    w.chantier("agents", "set", cr, "drv-x", "--epoch", 1)
    commit(w, cr, "unblocked.py", "UNBLOCKED = 1\n")
    ship(w, cr, "feat: unblocked")
    code, _ = w.chantier("handback", cr, "ready", link, "--no-gate", rule, expect=2)
    check("a ready hand-back from a blocked CR still wants a verdict VERIFIED at its head: refused, "
          "the CR still blocked", code == 2 and "no verdict VERIFIED" in w.last_stderr
          and w.cr(cr)["status"] == "blocked", w.last_stderr)
    w.chantier("gate", cr, GATE)
    w.verified(cr)
    _, out = w.chantier("handback", cr, "ready", link)
    _, events = w.chantier("log", cr)
    check("the recorded Driver of a blocked CR hands back ready: ready, the block cleared, a note "
          "and the event say what it left, the printed line says it was blocked",
          w.cr(cr)["status"] == "ready" and not w.cr(cr).get("blocked_reason")
          and "ready after blocked: question: x" in w.cr(cr)["notes"]
          and any(" handback " in ln and "from_blocked=question: x" in ln for ln in events)
          and out[-1].endswith("; it was blocked: question: x"), str(out))
    # the user merges the PR while its Driver is still finishing
    w.chantier("agents", "set", cr, "-", "--epoch", 1)
    w.chantier("take", cr, "--epoch", 1, "--note", "answer: go")
    w.chantier("order", "merged", cr)
    code, _ = w.chantier("handback", cr, "ready", link, expect=2)
    refused = w.last_stderr
    code_note, _ = w.chantier("note", cr, "merged before the hand-back; left undone: none")
    check("a CR merged under its working Driver: `handback` is refused naming `is merged`, and the "
          "Driver's `note` of what it left undone is accepted",
          code == 2 and "is merged: no Driver to hand it back" in refused and code_note == 0
          and w.cr(cr)["status"] == "merged", refused)


def gate_proof(w: World) -> None:
    note("\n## 12c. The gate binds to a commit; the budget bounds the rounds")
    sys.path.insert(0, str(SKILL / "scripts" / "cli" / "src"))
    items = [prepare_cr(w, t)[1] for t in ("Gate head", "Gate abbrev", "Gate short", "Gate budget",
                                           "Gate rounds", "Gate free")]
    w.reset()
    w.start(*map(str, items), "--slots", 6, "--budget", 1, *FROM_AGENTS_MD)
    w.env["CHANTIER_BATCH"] = w.name
    w.chantier("foreman", "set", "local_foreman9", "--epoch", 1)
    Foreman(w, epoch=1).turn()
    a, b, c, d, e, f = (x["id"] for x in w.batch()["crs"])

    def wt(cr):
        return Path(w.cr(cr)["worktree"])

    def head(cr):
        return w.sh("git", "rev-parse", "HEAD", cwd=wt(cr))

    def events(kind, cr):
        return [json.loads(ln) for ln in (w.folder() / "events.jsonl").read_text("utf-8").splitlines()
                if json.loads(ln)["kind"] == kind and json.loads(ln)["cr"] == cr]

    def last_log(cr):
        return max((w.at(w.cr(cr)["path"]) / "work" / "gates").glob("*.log")).read_text(
            "utf-8").splitlines()

    commit(w, a, "g1.py", "G = 1\n")
    w.chantier("gate", a, GATE)
    lines, sha = last_log(a), head(a)
    check("the gate log's first line holds the CR and the 40-character HEAD, and the event the "
          "same SHA; its last line gives the result",
          lines[0].startswith(f"gate {a} branch ") and lines[0].split()[-1] == sha
          and len(sha) == 40 and events("gate", a)[-1]["head"] == sha
          and lines[-1].startswith("result: pass"), str(lines))
    # a dirty tree: nothing runs
    before = len(events("gate", a))
    (wt(a) / "g1.py").write_text("G = 100\n")
    code, _ = w.chantier("gate", a, GATE, expect=2)
    tracked = code == 2 and "commit first" in w.last_stderr
    (wt(a) / "g1.py").write_text("G = 1\n")
    (wt(a) / "loose.txt").write_text("untracked\n")
    code, _ = w.chantier("gate", a, GATE, expect=2)
    (wt(a) / "loose.txt").unlink()
    check("`gate` on a worktree with a modified or an untracked file exits 2 and runs nothing",
          tracked and code == 2 and len(events("gate", a)) == before, w.last_stderr)
    # a gate command that commits: no pass at either head
    code, out = w.chantier("gate", a, "git commit --allow-empty --quiet -m moved", expect=4)
    new = head(a)
    evs = events("gate", a)
    check("a gate command that commits leaves no pass at either head, says the head moved, and "
          "exits 4",
          code == 4 and new != sha and not gate_passed(evs, sha) and not gate_passed(evs, new)
          and any("head moved" in ln for ln in out) and "head moved" in last_log(a)[-1],
          str(out))
    # handback ready: the head, the tree, the push, the gate
    commit(w, a, "g2.py", "G = 2\n")
    w.chantier("gate", a, GATE)
    w.verified(a)
    ship(w, a, "feat: g2")
    link, shipped = w.cr(a)["pr"], head(a)
    check("`ship` records the full SHA of the head in the CR and its event",
          w.cr(a)["head"] == shipped and events("ship", a)[-1]["head"] == shipped
          and len(shipped) == 40)
    commit(w, a, "g3.py", "G = 3\n")
    refusals = []
    for extra in ([], ["--no-gate", "AGENTS.md declares no long gate"]):
        code, _ = w.chantier("handback", a, "ready", link, *extra, expect=2)
        refusals.append(code == 2 and "is not the head ship recorded" in w.last_stderr)
    w.sh("git", "reset", "--hard", "--quiet", shipped, cwd=wt(a))
    (wt(a) / "junk.txt").write_text("loose\n")
    for extra in ([], ["--no-gate", "AGENTS.md declares no long gate"]):
        code, _ = w.chantier("handback", a, "ready", link, *extra, expect=2)
        refusals.append(code == 2 and "uncommitted" in w.last_stderr
                        and "is not the head ship recorded" not in w.last_stderr)
    (wt(a) / "junk.txt").unlink()
    w.sh("git", "update-ref", "-d", f"refs/remotes/origin/{w.cr(a)['branch']}", cwd=wt(a))
    for extra in ([], ["--no-gate", "AGENTS.md declares no long gate"]):
        code, _ = w.chantier("handback", a, "ready", link, *extra, expect=2)
        refusals.append(code == 2 and "not pushed" in w.last_stderr)
    w.sh("git", "fetch", "--quiet", "origin", cwd=wt(a))
    check("`handback ready` exits 2 naming the cause: a commit after `ship`, a dirty tree, a head "
          "not pushed; `--no-gate` waives none of these", all(refusals) and len(refusals) == 6,
          str(refusals))
    commit(w, a, "g4.py", "G = 4\n")
    ship(w, a, "feat: g4")
    w.verified(a)
    code, _ = w.chantier("handback", a, "ready", link, expect=2)
    check("a gate passed only at an earlier head is refused, with that cause alone",
          code == 2 and "no long gate passed" in w.last_stderr
          and "is not the head ship recorded" not in w.last_stderr
          and "not pushed" not in w.last_stderr
          and "uncommitted" not in w.last_stderr, w.last_stderr)
    w.chantier("gate", a, GATE)
    w.chantier("handback", a, "ready", link)
    check("with the commit shipped, clean, pushed, gated and verified, `handback ready` passes",
          w.cr(a)["status"] == "ready")

    # core.abbrev 12: the heads are the full SHA, so `ship` and `handback` agree
    w.sh("git", "config", "core.abbrev", "12")
    try:
        commit(w, b, "g5.py", "G = 5\n")
        w.chantier("gate", b, GATE)
        ship(w, b, "feat: g5")
        w.verified(b)
        w.chantier("handback", b, "ready", w.cr(b)["pr"])
    finally:
        w.sh("git", "config", "--unset", "core.abbrev")
    check("with core.abbrev 12, `gate`, `ship`, `verdict` then `handback ready` succeed",
          w.cr(b)["status"] == "ready" and len(w.cr(b)["head"]) == 40)

    # a record whose heads were short, before the change
    commit(w, c, "g6.py", "G = 6\n")
    w.chantier("gate", c, GATE)
    ship(w, c, "feat: g6")
    w.verified(c)
    long_head = w.cr(c)["head"]
    for name in ("events.jsonl", "batch.json"):
        path = w.folder() / name
        path.write_text(path.read_text("utf-8").replace(long_head, long_head[:7]), encoding="utf-8")
    w.chantier("handback", c, "ready", w.cr(c)["pr"])
    check("a record holding short heads from before the change still reaches `handback ready`",
          w.cr(c)["status"] == "ready" and w.cr(c)["head"] == long_head[:7])

    # the budget bounds the rounds (pytest's: test_rail_refusals.py); a spent one refuses no hand-back
    state = w.folder() / "batch.json"
    state.write_text(json.dumps({**w.batch(), "spent_usd": 2}), encoding="utf-8")
    commit(w, d, "g7.py", "G = 7\n")
    w.chantier("gate", d, GATE)
    ship(w, d, "feat: g7")
    w.chantier("note", d, "still open past the budget")
    w.verified(d)
    w.chantier("handback", d, "ready", w.cr(d)["pr"])
    check("`gate`, `ship`, `note`, `verdict` and `handback` are never refused for the budget",
          w.cr(d)["status"] == "ready")
    state.write_text(json.dumps({**w.batch(), "budget_usd": None, "spent_usd": 2}),
                     encoding="utf-8")
    start_driver(w, f)  # the Driver's first step: the worktree exists when the round is counted
    w.chantier("round", f)
    check("with no budget, `round` is unchanged whatever the spend", w.cr(f)["round"] == 1)
    ring = events("round", f)[-1]
    code, _ = w.chantier("round", f, expect=2)
    check("the `round` event keeps the worktree's head and a fingerprint; a stray round on a "
          "worktree that did not change is refused",
          code == 2 and ring.get("wt_head") == head(f) and ring.get("wt_state")
          and w.cr(f)["round"] == 1 and len(events("round", f)) == 1, w.last_stderr)
    commit(w, f, "g8.py", "G = 8\n")
    w.chantier("round", f)
    check("a `round` passes with no note when the worktree's head changed since the last one",
          w.cr(f)["round"] == 2)
    (wt(f) / "dirty.py").write_text("D = 1\n")
    w.chantier("round", f)
    check("a `round` passes with no note when an untracked file appeared since the last one",
          w.cr(f)["round"] == 3)


def gate_next_merge(w: World) -> None:
    note("\n## 12e. The long gate queue: the next merge of a stack goes first")
    sys.path.insert(0, str(SKILL / "scripts" / "cli" / "src"))
    items = [prepare_cr(w, t)[1] for t in ("Next one", "Next two", "Next three")]
    slow = w.root / "slow_next.py"
    slow.write_text(
        "import os, sys, time\n"
        "release = os.path.join(os.path.dirname(__file__), 'next_' + sys.argv[1] + '.release')\n"
        "end = time.time() + 180\n"
        "while not os.path.exists(release) and time.time() < end:\n    time.sleep(0.05)\n"
    )
    (w.work / "chantier.yaml").unlink(missing_ok=True)
    w.reset()
    w.start(*map(str, items), "--mode", "stack", *FROM_AGENTS_MD)
    w.env["CHANTIER_BATCH"] = w.name
    w.chantier("foreman", "set", "local_foreman12e", "--epoch", 1)
    Foreman(w, epoch=1).turn()
    one, two, three = (c["id"] for c in w.batch()["crs"])
    queue = w.state / ".long-gate.queue"

    def spawn(cr, name, hold=True):
        (w.root / f"next_{name}.release").unlink(missing_ok=True)
        if not hold:
            (w.root / f"next_{name}.release").touch()
        gate = f'"{sys.executable}" "{slow}" {name}'
        return subprocess.Popen(
            [sys.executable, "-m", "chantier", "gate", cr, gate],
            cwd=w.work,
            env=w.env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )

    def wait_tickets(n):
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline and len(list(queue.glob("[0-9]*"))) < n:
            time.sleep(0.05)

    holder = spawn(three, "h")  # the top of the stack runs: it is never stopped
    lock_names(w, f"{three} pid")
    later = spawn(two, "two", hold=False)
    wait_tickets(1)
    time.sleep(1.1)  # the tickets are named by arrival
    next_merge = spawn(one, "one", hold=False)  # the bottom: the next merge, arrived last
    wait_tickets(2)
    _, o = w.chantier("status", "--refresh", "--epoch", 1, expect=None)
    lines = {ln.split()[1]: ln for ln in o if ln.startswith("activity ")}
    check(
        "the next merge's waiting gate and the earlier waiter both show `gate queued behind` the "
        "running gate, which shows `gate running`",
        lines[three] == f"activity {three} gate running"
        and lines[one] == f"activity {one} gate queued behind {three}"
        and lines[two] == f"activity {two} gate queued behind {three}",
        str(lines),
    )
    (w.root / "next_h.release").touch()
    outs = [p.communicate(timeout=180) for p in (holder, later, next_merge)]
    events = [
        json.loads(ln) for ln in (w.folder() / "events.jsonl").read_text("utf-8").splitlines()
    ]
    order = [e["cr"] for e in events if e["kind"] == "gate"][-3:]
    check(
        "in a stack batch the next merge's gate (the bottom CR) runs before an earlier waiter, "
        "after the running gate, which ends with its pass and is not stopped",
        order == [three, one, two]
        and holder.returncode == 0
        and all(e["result"] == "pass" for e in events if e["kind"] == "gate")
        and not list(queue.glob("[0-9]*")),
        f"{order} {outs}",
    )
    w.env.pop("CHANTIER_BATCH", None)
    w.reset()


def gate_carry(w: World) -> None:
    note(
        "\n## 12f. A clean rebase carries the long gate and the verdict; a resolved conflict "
        "carries neither"
    )
    items = [prepare_cr(w, t)[1] for t in ("Carry clean", "Carry conflict", "Carry later")]
    w.reset()
    w.start(*map(str, items), *FROM_AGENTS_MD)
    w.env["CHANTIER_BATCH"] = w.name
    w.chantier("foreman", "set", "local_foreman12f", "--epoch", 1)
    Foreman(w, epoch=1).turn()
    clean, clash, later = (c["id"] for c in w.batch()["crs"])

    def wt(cr):
        return Path(w.cr(cr)["worktree"])

    def events(kind, cr):
        return [
            e
            for e in map(json.loads, (w.folder() / "events.jsonl").read_text("utf-8").splitlines())
            if e["kind"] == kind and e["cr"] == cr
        ]

    for cr, name in ((clean, "carried.py"), (clash, "clash.py"), (later, "later.py")):
        commit(w, cr, name, "CR = 1\n")
        ship(w, cr, f"feat: {name}")
        w.chantier("gate", cr, GATE)
        w.verified(cr)
    old = w.sh("git", "rev-parse", "HEAD", cwd=wt(clean))
    gates = len(events("gate", clean))
    verdicts = len(events("verdict", clean))
    land(w, "main", ("moved.txt", "main moved\n"))
    ship(w, clean, "feat: carried")  # fetch, a clean rebase onto the moved main, push, record
    new = w.sh("git", "rev-parse", "HEAD", cwd=wt(clean))
    link = w.cr(clean)["pr"]
    carry = events("carry", clean)
    gate_ev, verdict_ev = events("gate", clean)[-1], events("verdict", clean)[-1]
    check(
        "after a clean rebase and a `ship`, one `carry` event holds the new head, the base and "
        "`gate_from` and `verdict_from` of the judged head; the gate and the verdict events "
        "carry the `base` they sat on",
        len(carry) == 1
        and carry[0]["head"] == new
        and carry[0]["gate_from"] == old
        and carry[0]["verdict_from"] == old
        and bool(carry[0]["base"])
        and bool(gate_ev.get("base"))
        and bool(verdict_ev.get("base")),
        str(carry),
    )
    status_md = (w.folder() / "STATUS.md").read_text("utf-8")
    check(
        "before any hand-back, `STATUS.md` shows `carried from <sha7>` in the CR's long gate column",
        f"carried from {old[:7]}" in status_md,
        status_md[-400:],
    )
    _, facts = w.chantier("handoff", clean)
    boxes = [ln for ln in facts if ln.lstrip().startswith("[x]")]
    check(
        "after a clean rebase and a `ship`, `handoff` shows the long gate and the verdict boxes "
        "`[x]` with `carried from <sha7>`",
        new != old
        and sum(f"carried from {old[:7]}" in ln for ln in boxes) == 2
        and any("long gate" in ln for ln in boxes)
        and any("verdict" in ln for ln in boxes),
        str(facts),
    )
    _, out = w.chantier("handback", clean, "ready", link)
    done = events("handback", clean)[-1]
    check(
        "a clean rebase onto a moved main: `handback ready` is accepted with no new gate and no new "
        "verdict, the line says `long gate and verdict carried from <sha7> (clean rebase onto "
        "main)` and the event has `gate_from` and `verdict_from`",
        w.cr(clean)["status"] == "ready"
        and len(events("gate", clean)) == gates
        and len(events("verdict", clean)) == verdicts
        and done.get("gate_from") == old
        and done.get("verdict_from") == old
        and f"long gate and verdict carried from {old[:7]} (clean rebase onto main)" in out[0],
        str(out),
    )
    note(f"12f ready line: {out[0]}")
    own_sheet = json.loads((w.at(w.cr(clean)["path"]) / "STATUS.json").read_text(encoding="utf-8"))
    names = [(x["name"], x["verdict"]) for x in own_sheet["steps"]]
    carried = f"carried from {old[:7]}"
    check(
        "the clean CR's steps hold `Verdict | carried from <old7>` after the `Long gate` carried step "
        "and before `Handed back`, in STATUS.json and in STATUS.md",
        ("Long gate", carried) in names
        and names.index(("Verdict", carried)) == names.index(("Long gate", carried)) + 1
        and names[names.index(("Verdict", carried)) + 1][0] == "Handed back"
        and f"- [x] Verdict {carried}" in (w.at(w.cr(clean)["path"]) / "STATUS.md").read_text(
            encoding="utf-8"),
        str(names),
    )
    # the restack after the hand-back: the main moves again, the ready CR is rebased and shipped
    land(w, "main", ("moved2.txt", "main moved again\n"))
    ship(w, clean, "feat: carried")
    again = w.sh("git", "rev-parse", "HEAD", cwd=wt(clean))
    last = events("carry", clean)[-1]
    check(
        "a `ready` CR rebased and shipped again: a `carry` at the new head, the CR stays `ready`, "
        "and a `carry` with `verdict_from` stands at the final head, which the eval kit's C7 rule "
        "reads",
        again != new
        and last["head"] == again
        and bool(last.get("verdict_from"))
        and w.cr(clean)["status"] == "ready",
        str(last),
    )
    # a conflict resolved by hand: the pass at the old head does not carry
    land(w, "main", ("clash.py", "MAIN = 1\n"))
    wc = wt(clash)
    w.sh("git", "fetch", "--quiet", "origin", cwd=wc)
    rebase = subprocess.run(
        ["git", "rebase", "origin/main"],
        cwd=wc,
        capture_output=True,
        text=True,
        env={**os.environ, "GIT_EDITOR": "true"},
    )
    (wc / "clash.py").write_text("CR = 1\nMAIN = 1\n")
    w.sh("git", "add", "--", "clash.py", cwd=wc)
    subprocess.run(
        ["git", "rebase", "--continue"],
        cwd=wc,
        check=True,
        capture_output=True,
        env={**os.environ, "GIT_EDITOR": "true"},
    )
    w.sh(
        "git",
        "push",
        "--quiet",
        "--force-with-lease",
        "-u",
        "origin",
        w.cr(clash)["branch"],
        cwd=wc,
    )
    w.chantier("ship", clash, w.cr(clash)["pr"], "--conflict")
    code, _ = w.chantier("handback", clash, "ready", w.cr(clash)["pr"], expect=2)
    check(
        "a rebase with a resolved conflict: `handback ready` is refused, `no long gate passed` and "
        "`no verdict VERIFIED` each with the `does not carry` clause and its reason; the CR is "
        "not ready",
        rebase.returncode != 0
        and code == 2
        and "no long gate passed at" in w.last_stderr
        and "no verdict VERIFIED at" in w.last_stderr
        and w.last_stderr.count("does not carry: the rebase resolved a conflict") == 2
        and not events("carry", clash)
        and events("ship", clash)[-1].get("conflict") is True
        and w.cr(clash)["status"] != "ready"
        and not events("handback", clash),
        w.last_stderr,
    )
    note(f"12f conflict refusal: {w.last_stderr}")
    # a commit after the verdict: the verdict does not carry, even with a new long gate
    commit(w, later, "later.py", "CR = 2\n")
    ship(w, later, "feat: later")
    w.chantier("gate", later, GATE)
    code, _ = w.chantier("handback", later, "ready", w.cr(later)["pr"], expect=2)
    check(
        "a commit after the verdict, then `ship` and the long gate: `handback ready` is refused, "
        "`no verdict VERIFIED` with `does not carry: the rebase changed the patch`",
        code == 2
        and "no verdict VERIFIED at" in w.last_stderr
        and "does not carry: the rebase changed the patch" in w.last_stderr
        and w.cr(later)["status"] != "ready",
        w.last_stderr,
    )
    w.env.pop("CHANTIER_BATCH", None)
    w.reset()


def gate_carry_stack(w: World) -> None:
    note("\n## 12g. CR-316's shape: a pass carries over a restack onto a rewritten branch")
    items = [prepare_cr(w, t)[1] for t in ("Carry under", "Carry over")]
    w.reset()
    w.start(*map(str, items), "--mode", "stack", *FROM_AGENTS_MD)
    w.env["CHANTIER_BATCH"] = w.name
    w.chantier("foreman", "set", "local_foreman12g", "--epoch", 1)
    Foreman(w, epoch=1).turn()
    under, over = (c["id"] for c in w.batch()["crs"])
    w.chantier("take", "stack", "--epoch", 1)
    w.chantier("agents", "set", "stack", "-", "--epoch", 1)

    def log():
        return list(map(json.loads, (w.folder() / "events.jsonl").read_text("utf-8").splitlines()))

    for cr, name in ((under, "under.py"), (over, "over.py")):
        commit(w, cr, name, "CR = 1\n")
        ship(w, cr, f"feat: {name}")
        w.chantier("gate", cr, GATE)
        w.verified(cr)
    old = w.sh("git", "rev-parse", "HEAD", cwd=Path(w.cr(over)["worktree"]))
    w.chantier("stack", under, over)
    wu, wo = Path(w.cr(under)["worktree"]), Path(w.cr(over)["worktree"])
    w.sh("git", "commit", "--quiet", "--amend", "-m", "feat: under, rewritten", cwd=wu)
    w.sh("git", "push", "--quiet", "--force-with-lease", "origin", w.cr(under)["branch"], cwd=wu)
    w.sh("git", "fetch", "--quiet", "origin", cwd=wo)
    w.sh("git", "rebase", "--quiet", f"origin/{w.cr(under)['branch']}", cwd=wo)
    w.sh("git", "push", "--quiet", "--force-with-lease", "origin", w.cr(over)["branch"], cwd=wo)
    tip = w.sh("git", "rev-parse", f"origin/{w.cr(under)['branch']}", cwd=wo)
    link = w.cr(over)["pr"]
    forge_base(w, link, w.cr(under)["branch"])  # the stack driver retargets the PR with the CR
    w.chantier("ship", over, link)
    gates = len([e for e in log() if e["kind"] == "gate" and e["cr"] == over])
    w.chantier("handback", over, "ready", link)
    carry = [e for e in log() if e["kind"] == "carry" and e["cr"] == over]
    check(
        "a CR gated and verified on one branch, then moved onto the branch of the CR under it "
        "(rewritten): `ship` records a `carry` with that branch's tip as `base`, and `handback "
        "ready` is accepted with no new gate and no new verdict",
        len(carry) == 1
        and carry[0]["gate_from"] == old
        and carry[0]["verdict_from"] == old
        and carry[0]["base"] == tip
        and w.cr(over)["status"] == "ready"
        and gates == len([e for e in log() if e["kind"] == "gate" and e["cr"] == over]),
        str(carry),
    )
    w.env.pop("CHANTIER_BATCH", None)
    w.reset()


def restore_cr(w: World) -> None:
    note("\n## 12d. `restore`: a trashed CR back to the inbox")
    # the inbox restores (whole, clash, --slug, archives) are pytest's: test_opening_and_restore.py
    # a cancelled CR of an open batch
    one, two = (prepare_cr(w, t)[1] for t in ("Restore one", "Restore two"))
    w.reset()
    w.start(str(one), str(two), *FROM_AGENTS_MD)
    w.env["CHANTIER_BATCH"] = w.name
    w.chantier("foreman", "set", "local_foreman10", "--epoch", 1)
    x, y = (k["id"] for k in w.batch()["crs"])
    drop_then_cancel(w, x, 1)
    drop_then_cancel(w, y, 1)
    path = w.at(w.cr(y)["path"])
    code, out = w.chantier("restore", path)
    back = w.state / "1-inbox" / "restore-two"
    check("a former batch CR loses its number and keeps `formerly CR-<n> of <batch>`; the output "
          "says in one line that its branch, worktree and PR stay",
          code == 0 and back.is_dir() and not path.exists() and len(out) == 2
          and f"formerly {y} of {w.name}" in (back / "01-intent.md").read_text("utf-8")
          and w.cr(y)["status"] == "cancelled" and w.cr(y)["branch"] in out[1], str(out))
    priced_foreman(w)
    clear_agents(w)
    code, out = w.chantier("close")
    check("after restoring a cancelled CR of a paused batch, `close` (without `--yes`) still runs",
          code == 0 and out[-1].startswith("ask the user"), str(out))
    number = int(y.removeprefix("CR-"))
    w.reset()
    _, fresh = prepare_cr(w, "Restore number")
    w.start(str(fresh), *FROM_AGENTS_MD)
    new = int(w.batch()["crs"][0]["id"].removeprefix("CR-"))
    check("a CR number taken off a restored folder is never given again", new > number,
          f"{y} then CR-{new}")


def empty_batch(w: World) -> None:
    note("\n## 16d. An empty batch: `open` with no CR is born paused, joined by `order add`")
    _, item = prepare_cr(w, "Empty first")
    w.reset()
    code, out = w.start("--direct", *FROM_AGENTS_MD)
    d = w.batch()
    check("`open` with no CR opens a batch born paused, with no CR and no cost yet",
          code == 0 and d["status"] == "paused" and d["crs"] == [] and d["spent_usd"] is None
          and "no CR, paused" in out[0], str(out))
    check("it is an ordinary batch: no `factory` key in its record, no factory word on its first "
          "line, and no `Factory:` token in its brief",
          "factory" not in d and "factory" not in out[0]
          and "Factory:" not in (w.state / "4-batch" / "brief.md").read_text(encoding="utf-8"),
          str(out))
    w.env["CHANTIER_BATCH"] = w.name
    code, out = w.chantier("status")
    mine = next((ln for ln in out if ln.startswith(w.name)), "")
    check("`status` says `spent none yet` and `no CR yet` for it, never $0.00, and how a CR joins",
          code == 0 and "spent none yet" in mine and mine.endswith("no CR yet")
          and "factory" not in mine and "$0.00" not in mine
          and f"no CR yet: `order add --note <folder> --batch {w.name}` joins one" in out, str(out))
    code, out = w.chantier("order", "add", "--note", str(item), "--batch", w.name)
    check("`order add --note` joins a CR to the empty batch, which stays paused",
          code == 0 and w.batch()["status"] == "paused" and len(w.batch()["crs"]) == 1, str(out))
    w.chantier("foreman", "set", "local_foreman_empty", "--epoch", 1)
    code, out = w.chantier("take", w.batch()["crs"][0]["id"], "--epoch", 1)
    check("the first `take` sets the batch running", code == 0 and w.batch()["status"] == "running",
          str(out))
    w.reset()
    w.start("--direct", *FROM_AGENTS_MD)
    code, out = w.chantier("close", "--yes", "--batch", w.name)
    check("`close --yes` of a batch that held no CR and was never steered archives 0 CRs and "
          "reads its cost `none: no session steered it`",
          code == 0 and "0 CRs archived" in out[0]
          and any("none: no session steered it" in ln for ln in out), str(out))
    w.reset()


def running_batch(w: World) -> None:
    note("\n## 16e. Running batch or next batch: a CR marked for the running batch joins by "
         "`order add` once specified, the batch ends as any other, `triage --ready` joins nothing")
    _, first = prepare_cr(w, "Running first")
    w.reset()
    w.start("--direct", *FROM_AGENTS_MD)
    w.env["CHANTIER_BATCH"] = w.name
    (first / "work").mkdir(exist_ok=True)
    (first / "work" / "specifying").write_text("2026-11-21T00:00:00Z spec-writer\n")
    code, out = w.chantier("triage", first, "--running-batch")
    mark = first / "work" / "running-batch"
    check("`triage --running-batch` marks a CR being specified for the open batch and moves "
          "nothing",
          code == 0 and mark.is_file() and mark.read_text().split()[-1] == w.name
          and first.is_dir() and w.batch()["crs"] == []
          and out[0].startswith(f"{first.name} marked for the running batch {w.name}"), str(out))
    (first / "work" / "specifying").unlink()
    code, out = w.chantier("status")
    check("once its specification is written and the marker gone, `status` names it `written`",
          code == 0 and any(ln.startswith("running batch: 1 CRs marked, not joined: ")
                            and f"{first.name} (written)" in ln for ln in out), str(out))
    code, out = w.chantier("order", "add", "--note", first, "--batch", w.name)
    d = w.batch()
    pending = w.at(d["crs"][0]["path"]) if d["crs"] else first
    check("`order add` places it in `1-pending` and clears the mark",
          code == 0 and len(d["crs"]) == 1 and "1-pending" in d["crs"][0]["path"]
          and not (pending / "work" / "running-batch").exists(), str(out))
    cr = d["crs"][0]["id"]
    w.chantier("foreman", "set", "local_foreman_running", "--epoch", 1)
    code, out = w.chantier("take", cr, "--epoch", 1)
    check("the steering session takes it: the batch runs",
          code == 0 and w.batch()["status"] == "running", str(out))
    code, out = w.chantier("order", "merged", cr)
    check("its end pauses the batch with the ordinary `next:` line: the retro, then the close offer",
          code == 0 and w.batch()["status"] == "paused"
          and any("next: the retro (with its critic), then offer the close" in ln for ln in out),
          str(out))
    _, second = prepare_cr(w, "Running second")
    code, out = w.chantier("order", "add", "--note", second, "--batch", w.name)
    second_cr = w.batch()["crs"][-1]["id"]
    code, out = w.chantier("take", second_cr, "--epoch", 1)
    check("a second CR placed by `order add` before the close starts it again at the next `take`",
          code == 0 and w.batch()["status"] == "running", str(out))
    _, third = prepare_cr(w, "Running third")
    code, out = w.chantier("triage", third, "--ready")
    ready = w.work / out[0].removeprefix("triaged ") if out else third
    check("`triage --ready` of a third CR leaves it in `3-ready`, not joined",
          code == 0 and ready.parent.name == "3-ready" and len(w.batch()["crs"]) == 2, str(out))
    code, out = w.chantier("order", "factory", "on", "--note", "the user's word", expect=1)
    check("`order factory on` is refused (exit usage)", code == 1, w.last_stderr)
    w.reset()


def stack_batch(w: World) -> None:
    note("\n## 13. A stack on request, one open batch, a stack merged in part")
    w.reset()
    bottom, middle, top = (prepare_cr(w, t)[1] for t in ("Stack bottom", "Stack middle", "Stack top"))
    _, joined = prepare_cr(w, "Stack joiner")
    w.start(str(bottom), str(middle), str(top), "--mode", "stack", *FROM_AGENTS_MD)
    d = w.batch()
    check("`open --mode stack` makes a stack of four slots; the batch is `batch-<n>`",
          d["mode"] == "stack" and d["slots"] == 4 and re.fullmatch(r"batch-\d\d", d["id"])
          and d["id"] == w.name and w.folder().name == "4-batch"
          and d["crs"][0]["branch"].startswith(f"chantier/{w.name}/")
          and Path(d["crs"][0]["worktree"]).name == f"{w.name}-{d['crs'][0]['id']}", str(d))
    code, _ = w.chantier("open", str(joined), *FROM_AGENTS_MD, expect=2)
    check("a second `open` is refused while a batch is open, and says which",
          code == 2 and w.name in w.last_stderr and "order add" in w.last_stderr
          and joined.is_dir() and len(list((w.state / "4-batch").glob("batch.json"))) == 1,
          w.last_stderr)
    w.chantier("foreman", "set", "local_foreman8", "--epoch", 1)
    w.env["CHANTIER_BATCH"] = w.name.removeprefix("batch-").lstrip("0")  # the number alone
    fm = Foreman(w, epoch=1)
    fm.turn()
    one, two, three = (c["id"] for c in w.batch()["crs"])
    base = {c: w.chantier("handoff", c)[1] for c in (one, two, three)}
    _, stacked = w.chantier("take", "stack", "--epoch", 1)
    w.chantier("agents", "set", "stack", "-", "--epoch", 1)
    check("a stack: independent CRs are all taken at once and start on the default branch; "
          "no CR below has a PR, so their place is the default branch too",
          fm.started == [one, two, three]
          and all(any("base origin/main" in ln for ln in base[c]) for c in (one, two, three))
          and "base origin/main" in stacked[1]
          and "base origin/main" in stacked[2]
          and "base origin/main" in stacked[3], str(base) + str(stacked))
    for i, cr in enumerate((one, two, three)):
        driver_round(w, cr, f"stack{i}.py", f"N = {i}\n")
        w.ready(cr, w.cr(cr)["pr"])

    def ship_bases(cr: str) -> list[str]:
        events = [json.loads(e) for e in (w.folder() / "events.jsonl").read_text().splitlines()]
        return [e["base"] for e in events if e["kind"] == "ship" and e["cr"] == cr]
    check("before `stack`, `ship` records the default branch for every independent CR",
          all(ship_bases(c)[-1] == "main" for c in (one, two, three)), str(ship_bases(two)))

    def trigger() -> list[str]:  # the `stack: take stack now:` lines of `status`
        return [ln for ln in w.chantier("status")[1] if ln.startswith("stack: take stack now:")]
    due = trigger()
    check("`status` prints one `stack: take stack now:` line naming the ready CRs in order when "
          "the first stack is due (CR-337)",
          due == [f"stack: take stack now: {one}, {two}, {three} ready with a PR, no stack made "
                  "yet (`take stack --epoch <n>`)"], str(due))
    w.chantier("agents", "set", "stack", "agent-stack", "--epoch", 1)
    held = trigger()
    w.chantier("agents", "set", "stack", "-", "--epoch", 1)
    check("with a stack driver recorded the line is absent; with none it is back", not held
          and len(trigger()) == 1, str(held))
    w.chantier("stack", one, two, three)
    check("after `stack` marks the CRs the trigger line is absent", not trigger(), str(trigger()))
    forge_base(w, w.cr(two)["pr"], w.cr(one)["branch"])  # the stack driver retargets the PRs
    forge_base(w, w.cr(three)["pr"], w.cr(two)["branch"])
    w.chantier("ship", three, w.cr(three)["pr"])
    w.chantier("ship", one, w.cr(one)["pr"])
    check("after `stack`, `ship` records the CR under it, the first on the default branch",
          ship_bases(three)[-1] == w.cr(two)["branch"] and ship_bases(one)[-1] == "main",
          str(ship_bases(three)))
    _, out = w.chantier("order", "add", "--note", str(joined))
    d = w.batch()
    four = d["crs"][-1]["id"]
    check("`order add` joins the open batch, on top of the stack; no batch is opened",
          len(d["crs"]) == 4 and w.cr(four)["status"] == "queued"
          and w.cr(four)["path"].startswith("4-batch/1-pending/")
          and len(list((w.state / "4-batch").glob("batch.json"))) == 1
          and any(f"base {w.cr(three)['branch']}" in ln for ln in w.chantier("handoff", four)[1]),
          str(out))
    w.chantier("order", "after", four, "--note", two)
    chained = any(f"base {w.cr(three)['branch']}" in ln for ln in w.chantier("handoff", four)[1])
    w.chantier("order", "after", four, "--note", "-")
    check("`order after` on a CR lower in the stack than the top CR with a PR leaves the base on that "
          "CR; `--note -` clears the `after` and the base is unchanged",
          chained and w.cr(four)["status"] == "queued" and "after" not in w.cr(four)
          and any(f"base {w.cr(three)['branch']}" in ln for ln in w.chantier("handoff", four)[1]))
    # a stacked CR with an `after` takes its place in the stack as base, not its dependency's branch
    w.chantier("order", "after", four, "--note", one)
    w.chantier("stack", one, two, four, three)
    _, placed = w.chantier("stack")
    check("a stacked CR with an `after` sits on the CR under it in the stack (`stack` with no CR "
          "and `take stack` print the same base), and the CR above it sits on it",
          f"base {w.cr(two)['branch']}" in next(ln for ln in placed if ln.startswith(four))
          and f"base {w.cr(four)['branch']}" in next(ln for ln in placed if ln.startswith(three)),
          str(placed))
    w.chantier("stack", one, two, three, four)
    w.chantier("order", "after", four, "--note", "-")
    fm.turn()
    check("a CR taken once two are ready with a PR starts on the nearest earlier CR with a PR "
          "(here the top of the ready part), recorded at its first take: its `handoff` prints "
          "that branch",
          w.cr(four).get("start_on") == w.cr(three)["branch"]
          and any(f"base {w.cr(three)['branch']}" in ln for ln in w.chantier("handoff", four)[1]),
          str(w.cr(four)))

    def set_status(cr: str, status: str) -> str:
        d = w.batch()
        c = next(x for x in d["crs"] if x["id"] == cr)
        was, c["status"] = c["status"], status
        (w.folder() / "batch.json").write_text(json.dumps(d, indent=2))
        return was
    was = set_status(three, "cancelled")
    on_two = any(f"base {w.cr(two)['branch']}" in ln for ln in w.chantier("handoff", four)[1])
    set_status(three, was)
    check("the recorded start base falls back to the nearest CR below with a PR while the CR that owns it is "
          "cancelled, and is back with it (recorded, not recomputed)",
          on_two and any(f"base {w.cr(three)['branch']}" in ln for ln in w.chantier("handoff", four)[1]))
    driver_round(w, four, "stack3.py", "N = 3\n")
    w.ready(four, w.cr(four)["pr"])

    def edit_batch(cr: str, **fields) -> None:
        d = w.batch()
        next(c for c in d["crs"] if c["id"] == cr).update(fields)
        (w.folder() / "batch.json").write_text(json.dumps(d, indent=2))
    edit_batch(four, after=[two])
    forge_base(w, w.cr(four)["pr"], w.cr(three)["branch"])
    w.chantier("ship", four, w.cr(four)["pr"])
    check("`ship` records the stack place as base for a stacked CR that has an `after`",
          ship_bases(four)[-1] == w.cr(three)["branch"], str(ship_bases(four)))
    edit_batch(four, after=[])
    # `ship` names the PR body lines whose SHA a restack made stale
    wt = Path(w.cr(four)["worktree"])
    body = w.at(w.cr(four)["path"]) / "work" / "pr-body.md"
    old = w.sh("git", "rev-parse", "HEAD", cwd=wt)
    def commit_id(raw: bytes) -> str:  # the id git gives a commit object, with no process
        return hashlib.sha1(b"commit %d\x00" % len(raw) + raw).hexdigest()

    def write_commit(raw: bytes) -> None:
        subprocess.run(["git", "hash-object", "-t", "commit", "-w", "--stdin"], cwd=wt, input=raw,
                       check=True, capture_output=True)

    if old[:7].isdigit():  # the old head must hold a letter a-f in its first seven characters
        raw = subprocess.run(["git", "cat-file", "commit", "HEAD"], cwd=wt, check=True,
                             capture_output=True).stdout
        headers = raw.split(b"\n\n", 1)[0]
        tries = [headers + f"\n\nfeat: stack3 try {n}\n".encode() for n in range(1, 50)]
        raw = next(r for r in tries if not commit_id(r)[:7].isdigit())
        write_commit(raw)
        w.sh("git", "update-ref", "HEAD", commit_id(raw), cwd=wt)
        old = w.sh("git", "rev-parse", "HEAD", cwd=wt)
    body.write_text(f"## Test plan\n\nTested at {old[:7]} on the gate\ncarried from {old[:7]}\n"
                    f"STALE {old[:7]}\nNo hash here: deadbeefdeadbeef0000\n"
                    f"Verified at {old[:7]} (carried from {old[:7]})\n"
                    f"![after at {old[:7]}](https://github.com/acme/demo/blob/{old}/a.png?raw=true)"
                    f" carried from {old[:7]}\n"
                    f'STALE <img src="https://raw.githubusercontent.com/acme/demo/{old}/b.png">\n')
    w.sh("git", "commit", "--quiet", "--amend", "-m", "feat: stack3, amended", cwd=wt)
    new_head = w.sh("git", "rev-parse", "HEAD", cwd=wt)
    _, out = w.chantier("ship", four, w.cr(four)["pr"])
    named = [ln for ln in out if "pr-body.md" in ln]
    check("`ship` names four PR body lines: line 3, the stale claimed SHA on a `Verified at ... "
          "(carried from ...)` line, a Markdown image and an HTML image on a `STALE` line, both "
          "linked into the old head; the SHA after `carried from`, the `STALE` text and a token "
          "that is no commit are not named",
          len(named) == 4
          and named[0].startswith("off: pr-body.md line 3 names " + old[:7])
          and named[1].startswith("off: pr-body.md line 7 names " + old[:7])
          and named[2].startswith("off: pr-body.md line 8 shows an image from " + old[:7])
          and "attach it with the forge's CLI" in named[2]
          and named[3].startswith("off: pr-body.md line 9 shows an image from " + old[:7])
          and all(f"not in {new_head[:7]}'s history" in ln for ln in named), str(out))
    body.write_text(f"## Test plan\n\nTested at {new_head[:7]} on the gate\n")
    _, out = w.chantier("ship", four, w.cr(four)["pr"])
    check("with the body fixed, `ship` names no line", not any("pr-body.md" in ln for ln in out), str(out))
    # a dangling commit whose first seven characters are digits: a token of digits is no commit
    tree = w.sh("git", "rev-parse", f"{new_head}^{{tree}}", cwd=wt)
    who = "scenario <scenario@example.com> 1700000000 +0000"
    cands = (f"tree {tree}\nauthor {who}\ncommitter {who}\n\ndigits {i}\n".encode()
             for i in range(100000))
    found = next((r for r in cands if commit_id(r)[:7].isdigit()), None)
    digits = commit_id(found) if found else ""
    if found:
        write_commit(found)
    body.write_text(f"## Test plan\n\nPR {digits[:7]} and the date\nTested at {old[:7]} again\n")
    _, out = w.chantier("ship", four, w.cr(four)["pr"])
    named = [ln for ln in out if "pr-body.md" in ln]
    check("`ship` does not take a token of digits for a commit, though it resolves outside the head; "
          "the line naming the old head with a letter is still named",
          digits != "" and len(named) == 1 and f"line 4 names {old[:7]}" in named[0], str(out))
    body.write_text(f"## Test plan\n\nTested at {new_head[:7]} on the gate\n")

    _, out = w.chantier("order", "merged", one)
    d = w.batch()
    check("the bottom merges alone: it moves to 3-done at once and the batch stays open",
          w.cr(one)["status"] == "merged" and "/3-done/" in w.cr(one)["path"]
          and (w.state / w.cr(two)["path"]).is_dir() and d["status"] == "running"
          and all(w.cr(c)["status"] == "ready" for c in (two, three, four)), str(out))
    check("after the step records a merge the trigger line stays absent: a stack was made once",
          not trigger(), str(trigger()))
    _, out = w.chantier("take", "stack", "--epoch", 1)
    check("what remains forms another stack: the first now stands on the default branch",
          out[0].endswith(f"{two} → {three} → {four}")
          and f"{two} ready" in out[1] and "base origin/main" in out[1]
          and f"base {w.cr(two)['branch']}" in out[2], str(out))
    w.chantier("agents", "set", "stack", "agent-stack", "--epoch", 1)
    code, _ = w.chantier("take", "stack", "--epoch", 1, expect=2)
    refused = w.last_stderr
    check("one stack driver at a time, and the batch does not pause under it",
          code == 2 and w.chantier("pause", "--epoch", 1, expect=2)[0] == 2
          and w.batch()["status"] == "running")
    check("`take stack` refused because a stack driver is recorded names `stack`, which changes nothing",
          "`stack`" in refused, refused)
    kept = {n: (w.folder() / n).read_bytes() for n in ("batch.json", "events.jsonl")}
    _, again = w.chantier("stack")
    check("`stack` with no CR prints the lines `take stack` printed plus a last `context:` line, "
          "and writes nothing (`batch.json`, `events.jsonl`)",
          again[:-1] == stack_take_rows(out)
          and again[-1].startswith("context:")
          and all((w.folder() / n).read_bytes() == v for n, v in kept.items()),
          str(again))
    timing = [ln for ln in out if ln.startswith("timing: ")]
    check("`take stack` prints the `timing:` lines (lines only) right after the CR rows, and "
          "`stack` prints none",
          timing and out.index(timing[0]) == len(stack_take_rows(out))
          and not any(ln.startswith("timing: ") for ln in again), str(out))
    code, _ = w.chantier("order", "after", four, "--note", two, expect=2)
    check("`order after` on a ready CR in a stack batch is refused, and the message names `stack`",
          code == 2 and "not queued" in w.last_stderr and "`stack`" in w.last_stderr, w.last_stderr)
    forge_base(w, w.cr(two)["pr"], "main")  # restacked onto the default branch
    w.chantier("ship", two, w.cr(two)["pr"])
    ships = [json.loads(e) for e in (w.folder() / "events.jsonl").read_text().splitlines()]
    last = [e for e in ships if e["kind"] == "ship" and e["cr"] == two][-1]
    check("the restacked PR is recorded on the default branch", last["base"] == "main", str(last))
    w.chantier("agents", "set", "stack", "-", "--epoch", 1)
    for cr in (two, three, four):
        w.chantier("order", "merged", cr)
    fm.turn()
    if fm.paused:
        priced_foreman(w)
    check("the stack merged piece by piece: the batch pauses, then closes",
          fm.paused and w.batch()["status"] == "paused"
          and clear_agents(w) is None
          and w.chantier("close", "--batch", w.name.removeprefix("batch-"), "--yes")[0] == 0
          and not (w.folder() / "batch.json").exists())
    w.env.pop("CHANTIER_BATCH", None)
    stack_start_base(w)


def stack_start_base(w: World) -> None:
    """The start base of a CR taken in a stack batch: the nearest earlier CR with a PR."""
    note("\n## 13-bis. A stack CR starts on the nearest earlier CR with a PR")
    w.reset()
    items = [prepare_cr(w, f"Start base {x}")[1] for x in "abcdefg"]
    w.start(*map(str, items), "--mode", "stack", "--slots", 6, *FROM_AGENTS_MD)
    w.env["CHANTIER_BATCH"] = w.name
    w.chantier("foreman", "set", "local_foreman13", "--epoch", 1)
    a, b, c, d, e, f, g = (x["id"] for x in w.batch()["crs"])

    def edit(cr: str, **fields: object) -> None:
        data = w.batch()
        next(x for x in data["crs"] if x["id"] == cr).update(fields)
        (w.folder() / "batch.json").write_text(json.dumps(data, indent=2))

    def based(cr: str, branch: str | None) -> bool:
        """The `handoff` base of `cr` is `branch` (the default branch for None)."""
        want = f"base {branch or 'origin/main'}"
        return any(want in ln for ln in w.chantier("handoff", cr)[1])

    def link(cr: str) -> str:
        return PR_LINK[ARGS.forge] + str(300 + int(cr.removeprefix("CR-")))

    edit(g, kind="release")
    edit(e, kind="fix")
    edit(f, after=[b])
    edit(d, pr=link(d), status="queued")  # a later CR with a PR: it counts for nobody before it
    w.chantier("take", a, "--epoch", 1)
    check("a CR taken while no earlier CR has a PR (a later one having one does not count) "
          "starts on the default branch, no `start_on` recorded",
          "start_on" not in w.cr(a) and based(a, None), str(w.cr(a)))
    edit(a, pr=link(a))  # a is working, a draft: its PR is open
    w.chantier("take", b, "--epoch", 1)
    check("a CR taken while an earlier CR is working with a PR, no two being ready, starts on "
          "that CR's branch (the old rule gave the default branch)",
          w.cr(b).get("start_on") == w.cr(a)["branch"] and based(b, w.cr(a)["branch"]), str(w.cr(b)))
    w.chantier("take", c, "--epoch", 1)
    check("a CR taken while the CR right before it has no PR and an earlier one has starts on "
          "the earlier one with the PR",
          w.cr(c).get("start_on") == w.cr(a)["branch"] and based(c, w.cr(a)["branch"]), str(w.cr(c)))
    edit(b, pr=link(b))
    edit(c, pr=link(c), status="cancelled")
    edit(a, status="merged")
    edit(d, pr=None)
    w.chantier("take", d, "--epoch", 1)
    check("an earlier CR with a PR that is cancelled or merged is skipped: the nearest one left "
          "with a PR is the base",
          w.cr(d).get("start_on") == w.cr(b)["branch"] and based(d, w.cr(b)["branch"]), str(w.cr(d)))
    w.chantier("take", e, "--epoch", 1)
    check("a fix CR starts on the default branch; a release starts on the top CR's branch",
          "start_on" not in w.cr(e) and based(e, None) and based(g, w.cr(f)["branch"]),
          str(w.cr(e)))
    edit(b, status="ready")
    w.chantier("take", f, "--epoch", 1)
    check("a CR with an open `after` still starts on its dependency's branch, no `start_on` "
          "recorded",
          "start_on" not in w.cr(f) and based(f, w.cr(b)["branch"]), str(w.cr(f)))
    w.reset()
    x_item, y_item = (prepare_cr(w, t)[1] for t in ("Parallel start x", "Parallel start y"))
    w.start(str(x_item), str(y_item), *FROM_AGENTS_MD)
    w.env["CHANTIER_BATCH"] = w.name
    w.chantier("foreman", "set", "local_foreman13", "--epoch", 1)
    x, y = (k["id"] for k in w.batch()["crs"])
    w.chantier("take", x, "--epoch", 1)
    edit(x, pr=link(x))
    w.chantier("take", y, "--epoch", 1)
    check("in a parallel batch a CR taken while an earlier CR has a PR still starts on the "
          "default branch", w.batch()["mode"] == "parallel" and "start_on" not in w.cr(y)
          and based(y, None), str(w.cr(y)))
    w.reset()
    w.env.pop("CHANTIER_BATCH", None)


def hub_cycle(w: World) -> None:
    """One cycle of the forge hub on this world (what its process does every 20 s): the fake forge
    is read, and a `merged@1` line is appended for a PR it shows merged and the record does not."""
    code = ("import time\n"
            "from chantier.core.repo import Repo\n"
            "from chantier.hub.cycle import Hub\n"
            "Hub(Repo.find()).cycle(time.monotonic())\n")
    p = subprocess.run([sys.executable, "-c", code], cwd=w.work, env=w.env, capture_output=True,
                       text=True, encoding="utf-8")
    check("the hub's cycle ran against the fake forge", p.returncode == 0, p.stderr[-300:])


def start_base_forge(w: World) -> None:
    """`take` and `handoff` leave out a CR whose PR the forge shows merged (a `merged@1` line of
    the journal, written by the hub), not recorded merged yet."""
    note("\n## 13-ter. A stack CR does not start on a CR whose PR the forge shows merged")
    w.reset()
    items = [prepare_cr(w, f"Forge base {x}")[1] for x in "zabcd"]
    w.start(*map(str, items), "--mode", "stack", "--slots", 6, *FROM_AGENTS_MD)
    w.env["CHANTIER_BATCH"] = w.name
    w.chantier("foreman", "set", "local_foreman13", "--epoch", 1)
    z, a, b, c, d = (x["id"] for x in w.batch()["crs"])

    def edit(cr: str, **fields: object) -> None:
        data = w.batch()
        next(x for x in data["crs"] if x["id"] == cr).update(fields)
        (w.folder() / "batch.json").write_text(json.dumps(data, indent=2))

    def link(cr: str) -> str:
        return PR_LINK[ARGS.forge] + str(400 + int(cr.removeprefix("CR-")))

    says = (f"base: not {a}'s branch: the forge shows its PR {link(a)} merged, not recorded yet "
            f"(order merged {a})")

    def on_base(out: list[str], ref: str) -> bool:
        return any(ln.startswith("worktree: ") and f" base {ref}" in ln for ln in out)

    w.chantier("take", a, "--epoch", 1)
    edit(a, pr=link(a))  # a is working with an open PR
    forge_pr(w, link(a), state="MERGED", mergedAt="2026-11-16T10:00:00Z")  # merged on the forge
    _, out = w.chantier("take", b, "--epoch", 1)
    check("4. with no journal line (the PR merged on the forge, no hub cycle yet) `take` prints "
          "a's branch as the base, no `base:` line, as today",
          w.cr(b).get("start_on") == w.cr(a)["branch"] and on_base(out, w.cr(a)["branch"])
          and not any(ln.startswith("base: ") for ln in out), str(out))
    hub_cycle(w)
    _, out = w.chantier("take", c, "--epoch", 1)
    check("1. once the hub saw the merge, `take` records no `start_on`, prints the default "
          "branch as the base and the `base:` line naming a and the order merged",
          "start_on" not in w.cr(c) and on_base(out, "origin/main") and says in out, str(out))
    _, out = w.chantier("handoff", c)
    check("1. `handoff` prints the same two lines", on_base(out, "origin/main") and says in out,
          str(out))
    _, status = w.chantier("status")
    _, rows = w.chantier("stack")
    check("5. `status` and `stack` still show the record's plan: a is listed, not merged",
          any(ln.startswith(a + " ") for ln in status + rows) and w.cr(a)["status"] != "merged",
          str((status, rows)))
    edit(z, pr=link(z))  # an earlier CR with an open PR, below a
    _, out = w.chantier("take", d, "--epoch", 1)
    check("2. with an earlier CR z that has an open PR below a, `take` records z's branch and "
          "prints it as the base, the `base:` line still naming a",
          w.cr(d).get("start_on") == w.cr(z)["branch"] and on_base(out, w.cr(z)["branch"])
          and says in out, str(out))
    edit(a, status="ready")
    w.chantier("order", "merged", a, "--epoch", 1)
    _, out = w.chantier("handoff", d)
    check("3. after `order merged a`, `handoff` prints the same base and no `base:` line",
          on_base(out, w.cr(z)["branch"]) and not any(ln.startswith("base: ") for ln in out),
          str(out))
    forge_pr(w, link(a), state="OPEN", mergedAt=None)  # PR links repeat: leave the fake forge clean
    w.reset()
    w.env.pop("CHANTIER_BATCH", None)


def base_from_pr(w: World) -> None:
    note("\n## 13b. `take` and `handoff` print a stacked CR's base, `ship` reads and records any CR's "
         "base, as its PR has it on the forge")

    def reads() -> int:
        """The PR reads the fake forge logged (a GET of one pull request or merge request)."""
        return sum(1 for x in forge_calls(w) if any(re.search(r"(pulls|merge_requests)/\d+$", a) for a in x)
                   and not {"PATCH", "PUT", "POST"} & set(x))

    def worktree_line(out: list[str]) -> str:
        return next((ln for ln in out if ln.startswith("worktree: ")), "")

    def ship_base(cr: str) -> list[str]:
        events = [json.loads(e) for e in (w.folder() / "events.jsonl").read_text().splitlines()]
        return [e["base"] for e in events if e["kind"] == "ship" and e["cr"] == cr]

    w.reset()
    items = [prepare_cr(w, t)[1] for t in ("Base one", "Base two", "Base three")]
    w.start(*map(str, items), "--mode", "stack", *FROM_AGENTS_MD)
    w.chantier("foreman", "set", "local_foreman_pb", "--epoch", 1)
    Foreman(w, epoch=1).turn()
    one, two, three = (c["id"] for c in w.batch()["crs"])
    driver_round(w, one, "base1.py", "N = 1\n")
    driver_round(w, two, "base2.py", "N = 2\n")
    w.chantier("stack", one, two, three)
    link = w.cr(two)["pr"]
    forge_base(w, link, w.cr(one)["branch"])  # the stack driver put it on the CR below
    before = reads()
    _, out = w.chantier("handoff", two)
    check("`handoff` prints a stacked CR's base as its PR has it on the forge (the CR below's branch), "
          "with one read", f"base {w.cr(one)['branch']}" in worktree_line(out) and reads() == before + 1,
          worktree_line(out))
    w.ready(two, link)
    w.chantier("agents", "set", two, "-", "--epoch", 1)
    _, out = w.chantier("take", two, "--epoch", 1, "--note", "rebase: base check")
    check("`take --note` prints the same base on its `worktree:` line",
          worktree_line(out).endswith(f"base {w.cr(one)['branch']}"), worktree_line(out))
    _, out = w.chantier("ship", two, link)
    check("`ship` prints the base of the PR it records, and the event and the CR keep it",
          f"(base {w.cr(one)['branch']}, head " in out[0] and ship_base(two)[-1] == w.cr(one)["branch"]
          and w.cr(two)["pr_base"] == w.cr(one)["branch"], str(out))
    forge_base(w, link, "main")
    _, out = w.chantier("handoff", two)
    check("a PR on the default branch is printed as the remote's default branch",
          worktree_line(out).endswith("base origin/main"), worktree_line(out))
    before = reads()
    _, out = w.chantier("handoff", three)
    check("a stacked CR with no PR prints today's line and makes no forge read",
          worktree_line(out).endswith("base origin/main") and reads() == before, worktree_line(out))
    w.gh(pull_read_refused=True)
    _, out = w.chantier("handoff", two)
    shown = f"base ? (not read from {link}: "
    check("a forge that refuses the read: `handoff` exits 0 and prints `base ? (not read from <link>: …)`",
          shown in worktree_line(out) and "403" in worktree_line(out) and "\n" not in worktree_line(out),
          worktree_line(out))
    held = w.cr(two)["pr_base"] is not None and w.cr(two)["pr_draft"] is not None
    _, out = w.chantier("ship", two, link)
    check("`ship` on a refused read exits 0, prints `base ?` and `draft not read`, keeps the event's "
          "base empty, and clears `pr_base` and `pr_draft` it held",
          shown in out[0] and "draft not read" in out[0] and ship_base(two)[-1] == "" and held
          and w.cr(two)["pr_base"] is None and w.cr(two)["pr_draft"] is None, str(out))
    _, out = w.ready(two, link)
    check("a CR handed back ready, after a failed read, reads `PR in draft`",
          out[0].startswith(f"[driver {two}→foreman] hand-back PR in draft"), str(out))
    w.gh(pull_read_refused=False)

    # a parallel batch makes no forge read
    w.chantier("agents", "set", two, "-", "--epoch", 1)
    w.chantier("order", "merged", one, "--epoch", 1)
    w.reset()
    _, item = prepare_cr(w, "Base parallel")
    w.start(str(item), *FROM_AGENTS_MD)
    w.chantier("foreman", "set", "local_foreman_pp", "--epoch", 1)
    Foreman(w, epoch=1).turn()
    (solo,) = (c["id"] for c in w.batch()["crs"])
    driver_round(w, solo, "solo.py", "N = 0\n")
    before = reads()
    _, out = w.chantier("handoff", solo)
    no_read = reads() == before and worktree_line(out).endswith("base origin/main")
    _, shipped = w.chantier("ship", solo, w.cr(solo)["pr"])
    check("a CR of a parallel batch with a PR: `handoff` makes no forge read and prints `base "
          "origin/main`; `ship` makes exactly one read, prints `(base main, head …` and records "
          "`pr_base` main", no_read and reads() == before + 1 and "(base main, head " in shipped[0]
          and w.cr(solo)["pr_base"] == "main", f"{worktree_line(out)} {shipped}")
    w.env.pop("CHANTIER_BATCH", None)

    # a parallel batch whose CR q was stacked by hand on p's branch: the record follows the forge
    w.reset()
    p_item, q_item = prepare_cr(w, "Base p")[1], prepare_cr(w, "Base q")[1]
    w.start(str(p_item), str(q_item), "--slots", 3, *FROM_AGENTS_MD)
    w.env["CHANTIER_BATCH"] = w.name
    p, q = (c["id"] for c in w.batch()["crs"])
    for x, name in ((p, "p"), (q, "q")):
        w.chantier("take", x, "--epoch", 0)
        start_driver(w, x)
        driver_round(w, x, f"hand_{name}.py", "N = 1\n")
    pb, qlink, plink = w.cr(p)["branch"], w.cr(q)["pr"], w.cr(p)["pr"]
    forge_base(w, qlink, pb)  # q's PR sits on p's branch, and is out of draft
    forge_draft(w, plink, True)  # p's PR is a draft
    w.chantier("ship", p, plink)
    _, out = w.chantier("ship", q, qlink)
    check("a PR stacked by hand: `ship` prints the forge's base and `out of draft`, records `pr_base` "
          "and `pr_draft`, and the event keeps the base",
          f"(base {pb}, head " in out[0] and out[0].endswith("out of draft)")
          and w.cr(q)["pr_base"] == pb and w.cr(q)["pr_draft"] is False and ship_base(q)[-1] == pb,
          str(out))
    _, out = w.ready(q, qlink)
    own_md = (w.state / w.cr(q)["path"] / "STATUS.md").read_text(encoding="utf-8")
    check("handed back ready over a draft, it reads `PR in draft`, not `ready to merge`: the hand-back "
          "line, its label and the `notify` text name the CR it waits for; the now line takes the "
          "ready line's wording and the next line names only what is still missing",
          out[0].startswith(f"[driver {q}→foreman] hand-back PR in draft")
          and out[1] == f"{q} PR in draft: its PR {qlink} is out of draft on the forge; "
                        f"it waits on {p} ({plink})"
          and f"waits on {pb}" not in out[1] and f"waits for {p}" in drawn(w, q)[1]["label"]
          and f"on {pb}, waits for {p}" not in own_md
          and f"**Now:** PR in draft: {out[1].split(' PR in draft: ', 1)[1]}." in own_md
          and "**Next:** Ready to merge once what is under it is." in own_md
          and "the PR is out of draft" not in own_md, str(out))
    forge_base(w, qlink, "main")
    w.chantier("ship", q, qlink)
    row = next(ln for ln in w.chantier("status")[1] if ln.startswith(q + " "))
    check("once the forge puts it on the default branch, `ship` records `main` and it reads `ready to merge`",
          w.cr(q)["pr_base"] == "main" and "ready to merge" in row, row)
    forge_draft(w, plink, False)  # PR links repeat from batch to batch: leave the fake forge clean
    w.env.pop("CHANTIER_BATCH", None)

    # `ship --draft` is gone: the forge is the only source of the draft state
    code, _ = w.chantier("ship", q, qlink, "--draft", expect=2)
    check("`ship <cr> <link> --draft` exits 2 (an unknown option) and records nothing",
          code == 2 and w.cr(q)["pr_draft"] is False and w.cr(q)["pr_base"] == "main", w.last_stderr)


def forge_stack_cli(w: World) -> None:
    note("\n## 13a. `forge-stack`: the native stack made and read back on the forge")
    w.reset()
    a_item, b_item, r_item = (prepare_cr(w, t)[1] for t in ("Forge piece a", "Forge piece b", "Forge release"))
    w.start(str(a_item), str(b_item), str(r_item), "--mode", "stack", "--release", 3, *FROM_AGENTS_MD)
    w.env["CHANTIER_BATCH"] = w.name
    a, b, r = (c["id"] for c in w.batch()["crs"])
    path_key = next(k for k in w.env if k.upper() == "PATH")
    on_path = {path_key: f"{w.fake.parent}{os.pathsep}{w.env[path_key]}"}
    links = {a: PR_LINK[ARGS.forge] + "201", b: PR_LINK[ARGS.forge] + "202", r: PR_LINK[ARGS.forge] + "203"}
    h7 = lambda cr: hashlib.sha1(cr.encode()).hexdigest()[:7]  # noqa: E731

    def record(statuses: dict[str, str] | None = None, **prs: str) -> None:
        """A PR and a head for the CRs named (`ready` unless `statuses` says otherwise), and the
        statuses named."""
        d = w.batch()
        for c in d["crs"]:
            if c["id"] in prs:
                c["pr"] = prs[c["id"]]
                c["head"] = hashlib.sha1(c["id"].encode()).hexdigest()
                c["status"] = "ready"
            c["status"] = (statuses or {}).get(c["id"], c["status"])
        (w.folder() / "batch.json").write_text(json.dumps(d, indent=2))

    def edit_cr(cr: str, **fields: object) -> None:
        d = w.batch()
        next(c for c in d["crs"] if c["id"] == cr).update(fields)
        (w.folder() / "batch.json").write_text(json.dumps(d, indent=2))

    def stack_calls() -> list[list[str]]:
        log = w.root / "gh-state.json.calls"
        rows = [json.loads(x) for x in log.read_text().splitlines()] if log.exists() else []
        return [x for x in rows if x[:1] == ["api"] and "POST" in x and any(a.endswith("/stacks") for a in x)]

    # `stack` naming only some of the open CRs: they take the bottom, the others stay above
    w.chantier("stack", b)
    got = {c["id"]: c for c in w.batch()["crs"]}
    check("`stack` naming one CR of three: it takes order 1, the others keep their relative order "
          "above it, and only the CR named is `stacked`",
          got[b]["order"] == 1 and 1 < got[a]["order"] < got[r]["order"]
          and got[b]["stacked"] and not got[a].get("stacked") and not got[r].get("stacked"),
          str({k: (v["order"], v.get("stacked")) for k, v in got.items()}))
    edit_cr(b, after=[a])
    code, _ = w.chantier("stack", b, expect=2)
    check("`stack` naming a CR whose dependency is open and not named is refused: `which is not named`",
          code == 2 and "which is not named" in w.last_stderr and w.cr(b)["order"] == 1, w.last_stderr)
    edit_cr(b, after=[])
    w.chantier("stack", a, b, r)
    w.chantier("foreman", "set", "local_foreman_fs", "--epoch", 1)

    if ARGS.forge == "gitlab":
        branch = lambda cr: w.cr(cr)["branch"]  # noqa: E731

        def put_calls() -> list[list[str]]:
            log = w.root / "gh-state.json.calls"
            rows = [json.loads(x) for x in log.read_text().splitlines()] if log.exists() else []
            return [x for x in rows if "PUT" in x and not x[1].endswith("/merge")]

        def mr(cr: str, n: int, target: str, state: str = "opened", draft: bool = False):
            return str(n), {"state": state, "draft": draft, "source_branch": branch(cr),
                            "target_branch": target, "web_url": PR_LINK["gitlab"] + str(n)}

        # 2. two ready MRs, the release with none: the chain made, read back, made again
        w.gh(mrs=dict([mr(a, 201, "main"), mr(b, 202, "main")]))
        record(**{a: links[a], b: links[b]})
        code, out = w.chantier("forge-stack", "create", env=on_path)
        puts = put_calls()
        check("GitLab: `forge-stack create` retargets the MR that is off the record's base (not the "
              "first), passes `--hostname`, prints the chain's link and its MRs bottom to top",
              code == 0 and len(puts) == 1 and "merge_requests/202" in puts[0][1]
              and f"target_branch={branch(a)}" in puts[0] and "--hostname" in puts[0]
              and "gitlab.example.com" in puts[0] and out[0] == f"chain {links[b]} (MRs bottom to top: !201 !202)",
              f"{out} {puts}")
        code, out = w.chantier("forge-stack", "show", env=on_path)
        check("GitLab: `forge-stack show` names the commit the user may merge below and the release "
              "as to come; it writes nothing (no `PUT`)",
              code == 0 and f"partial stack mergeable below {h7(b)} (!202" in out[0]
              and any(x.startswith("to come:") and r in x for x in out) and len(put_calls()) == 1,
              str(out))
        code, out = w.chantier("forge-stack", "create", env=on_path)
        check("GitLab: a second `create` on the chain in place retargets nothing and exits 0",
              code == 0 and len(put_calls()) == 1, str(out))

        # 3. a CR joins as a draft: retarget only, no unstack
        _, joined = prepare_cr(w, "Forge joined")
        w.chantier("order", "add", "--note", str(joined))
        new = w.batch()["crs"][-1]["id"]
        w.chantier("stack", a, b, new)
        record({new: "working"}, **{new: PR_LINK["gitlab"] + "204"})
        check("GitLab: a `stack` row names the MR as `(!<n>)`",
              any(x.startswith(f"{new} working, PR ") and "(!204) worktree" in x
                  for x in w.chantier("stack")[1]), str(w.chantier("stack")[1]))
        num = {a: 201, b: 202, new: 204, r: 203}
        base = {a: "main", b: branch(a), new: branch(b), r: branch(new)}

        def forge_mrs(only, draft=(), state=None, target=None, extra=None) -> None:
            mrs = dict(mr(cr, num[cr], (target or {}).get(num[cr], base[cr]),
                          (state or {}).get(num[cr], "opened"), num[cr] in draft) for cr in only)
            w.gh(mrs={**mrs, **(extra or {})}, retarget_refused=False)

        w.gh(mrs={**dict([mr(a, 201, "main"), mr(b, 202, branch(a))]), **dict([mr(new, 204, "main", draft=True)])})
        before = len(put_calls())
        code, out = w.chantier("forge-stack", "rebuild", env=on_path)
        log = (w.root / "gh-state.json.calls").read_text()
        check("GitLab: a CR joins as a draft: `rebuild` retargets the new MR onto the CR below, with "
              "no unstack, and prints the draft on top",
              code == 0 and f"!204 target main -> {branch(b)}" in out and len(put_calls()) == before + 1
              and "unstack" not in log and "/stacks" not in log
              and any("drafts on top !204" in x for x in out), str(out))
        code, out = w.chantier("forge-stack", "show", env=on_path)
        check("GitLab: `forge-stack show` of that chain: mergeable below the second MR, the draft on "
              "top, `to come:` the draft's CR and the release",
              code == 0 and f"mergeable below {h7(b)} (!202" in out[0] and "drafts on top !204" in out[0]
              and f"to come: {new} working, {r} queued" in out, str(out))

        # 4. the checks, one case each
        three = [a, b, new]
        record({new: "ready"})
        forge_mrs(three, draft=[204])
        code, out = w.chantier("forge-stack", "show", env=on_path, expect=2)
        check("GitLab: a ready CR whose MR is still a draft: `check 4: still a draft !204`",
              any(x.startswith("check 4: still a draft") and "!204" in x for x in out), str(out))
        record({new: "working"})
        forge_mrs(three)
        code, out = w.chantier("forge-stack", "show", env=on_path, expect=2)
        check("GitLab: a CR not ready whose MR is not a draft: `check 4: not a draft !204 (<cr> working)`",
              f"check 4: not a draft !204 ({new} working)" in out, str(out))
        record({new: "ready"})
        forge_mrs(three, draft=[201])
        code, out = w.chantier("forge-stack", "show", env=on_path, expect=2)
        check("GitLab: a draft under a ready MR: `check 4: a draft under a ready MR !201`",
              "check 4: a draft under a ready MR !201" in out, str(out))
        foreign = dict([("999", {"state": "opened", "draft": False, "source_branch": "elsewhere",
                                 "target_branch": branch(b), "web_url": PR_LINK["gitlab"] + "999"})])
        cases = [("an MR on the wrong target", dict(target={202: "main"}), "check 3",
                  f"!202 targets main, expected {branch(a)}"),
                 ("a foreign open MR on a stack branch", dict(extra=foreign), "check 2",
                  f"not in the batch's stack !999 (on {branch(b)})"),
                 ("a closed MR", dict(state={202: "closed"}), "check 1", "!202 is closed"),
                 ("an MR merged into the branch below",
                  dict(state={202: "merged"}, target={202: branch(a)}), "check 1",
                  f"!202 merged into {branch(a)}, not main: folded into {a}")]
        for what, kw, line, word in cases:
            forge_mrs(three, **kw)
            code, out = w.chantier("forge-stack", "show", env=on_path, expect=2)
            check(f"GitLab: `forge-stack show` on {what}: a `{line}` line naming the cause, exit 2",
                  code == 2 and any(x.startswith(line) and word in x for x in out), str(out))
        record(**{r: links[r]})
        forge_mrs([a, b, new, r])
        code, out = w.chantier("forge-stack", "show", env=on_path)
        check("GitLab: the complete chain (every CR ready, no draft, the release on top): `stack "
              "complete, mergeable below` the release's head, and no `to come:` line",
              code == 0 and len(out) == 1 and f"stack complete, mergeable below {h7(r)} (!203)" in out[0]
              and "the release on top" in out[0] and "ready to merge:" in out[0], str(out))
        edit_cr(a, pr_draft=True)
        code, out = w.chantier("forge-stack", "show", env=on_path, expect=2)
        check("GitLab: check 4 reads the draft state the CLI recorded: `recorded draft !201, the "
              "forge says out of draft`",
              "check 4: recorded draft !201, the forge says out of draft" in out, str(out))
        edit_cr(a, pr_draft=None)
        forge_mrs([a, b, new, r], extra=dict([("999", {**foreign["999"], "target_branch": branch(r)})]))
        code, out = w.chantier("forge-stack", "show", env=on_path, expect=2)
        check("GitLab: an open MR targeting the release's branch: `check 5` naming it, exit 2",
              any(x.startswith("check 5") and "!203" in x and "!999" in x for x in out), str(out))

        # 5. a forge refusal mid-way, and --stack
        forge_mrs([a, b, new, r], target={202: "elsewhere", 204: "elsewhere"})
        w.gh(retarget_refused=[204])
        w.chantier("forge-stack", "rebuild", env=on_path, expect=4)
        said = w.last_stderr
        check("GitLab: a `rebuild` stopped by the forge prints what was done before the forge's exact "
              "text (exit 4)",
              f"!202 target elsewhere -> {branch(a)}" in said and "403 Forbidden" in said
              and said.index("!202 target") < said.index("403 Forbidden"), said)
        forge_mrs([a, b, new, r])
        code, _ = w.chantier("forge-stack", "show", "--stack", 5, env=on_path, expect=2)
        check("GitLab: `show --stack 5` is refused naming `GitHub only`",
              code == 2 and "GitHub only" in w.last_stderr, w.last_stderr)
        record({new: "ready"})
    else:
        branch = lambda cr: w.cr(cr)["branch"]  # noqa: E731
        gh_state = lambda: json.loads(w.gh_state.read_text())  # noqa: E731

        def stack_on_forge(order: list[int], drafts: list[int] = (), is_open: bool = True) -> None:
            w.gh(stacks=[{"number": 100, "open": is_open, "pull_requests": order}], drafts=list(drafts))

        # 1. two ready PRs, the release with none: the stack as it stands, the release to come
        record(**{a: links[a], b: links[b]})
        # the forge refuses (HTTP 422) a stack whose PR is not on the previous PR's head
        w.gh(heads={"201": branch(a), "202": branch(b), "203": branch(r)})
        code, out = w.chantier("forge-stack", "create", env=on_path)
        posts = stack_calls()
        check("`forge-stack create` retargets the second PR onto the first's branch, then stacks the "
              "CRs that have a PR (the release has none): the stacks endpoint once, `201 202` only, "
              "the retarget line before the stack's link",
              code == 0 and len(posts) == 1 and [x for x in posts[0] if x.startswith("pull_requests[]")]
              == ["pull_requests[]=201", "pull_requests[]=202"] and "--hostname" not in posts[0]
              and "repos/acme/demo/stacks" in posts[0] and len(out) == 2
              and out[0] == f"#202 base main -> {branch(a)}" and out[1].startswith("stack #100 ")
              and links[b] in out[1], f"{out} {posts}")
        code, out = w.chantier("forge-stack", "show", env=on_path)
        check("`forge-stack show` on that stack names the commit the user may merge below, and the "
              "release as to come; it writes nothing",
              code == 0 and f"partial stack mergeable below {h7(b)} (#202" in out[0]
              and any(x.startswith("to come:") and r in x for x in out) and len(stack_calls()) == 1,
              str(out))
        w.chantier("forge-stack", "create", env=on_path, expect=4)
        check("a second `create` over PRs already stacked comes back with the forge's exact text (exit 4)",
              "already in a stack" in w.last_stderr, w.last_stderr)

        # 6. no PR at the bottom
        record(**{a: ""})
        for action in ("create", "rebuild"):
            code, _ = w.chantier("forge-stack", action, env=on_path, expect=2)
            check(f"`forge-stack {action}` with no PR at the bottom is refused (exit 2), naming the CR",
                  code == 2 and "no PR at the bottom of the stack" in w.last_stderr and a in w.last_stderr,
                  w.last_stderr)
        code, out = w.chantier("forge-stack", "show", env=on_path, expect=2)
        check("`forge-stack show` with no PR at the bottom prints `check 1: no PR at the bottom`, exit 2",
              code == 2 and any(x.startswith("check 1: no PR at the bottom") and a in x for x in out), str(out))
        record(**{a: links[a]})

        # 2. a CR joins on top as a draft: unstack, retarget, create again
        _, joined = prepare_cr(w, "Forge joined")
        w.chantier("order", "add", "--note", str(joined))
        new = w.batch()["crs"][-1]["id"]
        w.chantier("stack", a, b, new)
        record({new: "working"}, **{new: PR_LINK["github"] + "204"})
        w.gh(drafts=[204], heads={**gh_state()["heads"], "204": branch(new)})

        def patches() -> int:
            log = w.root / "gh-state.json.calls"
            rows = [json.loads(x) for x in log.read_text().splitlines()] if log.exists() else []
            return sum(1 for x in rows if "PATCH" in x and any(y.endswith("/pulls/204") for y in x))
        # Run 2's case: the working CR's PR is on main, not on its place in the stack
        edit_cr(new, pr_base="main")
        code, out = w.chantier("forge-stack", "show", env=on_path)
        _, rows = w.chantier("stack")
        row = next((ln for ln in rows if ln.startswith(new + " ")), "")
        check("a working CR whose PR is not on its place is left out of the stack as it stands: "
              "`show` has it in `to come:`, `stack` ends its row with `not on its place` and the "
              "note to send, and no PATCH touches its PR",
              code == 0 and f"to come: {new} working, {r} queued" in out
              and row.endswith(f"not on its place: its PR is on main; to come until its Driver "
                               f"rebases (note rebase: stacked on {b})") and patches() == 0,
              f"{out} {row}")
        edit_cr(a, status="working", pr_base=branch(b))
        for action in ("create", "rebuild"):
            w.chantier("forge-stack", action, env=on_path, expect=2)
            check(f"`forge-stack {action}` with the bottom CR working and its PR off its place is "
                  "refused (exit 2), naming it",
                  f"no PR placed at the bottom of the stack: {a} is working" in w.last_stderr
                  and links[a] in w.last_stderr, w.last_stderr)
        edit_cr(a, status="ready", pr_base=None)
        edit_cr(new, pr_base=branch(b))  # its Driver rebased and `ship` read the new base
        forge_base(w, PR_LINK["github"] + "204", branch(b))
        before = len(stack_calls())
        code, out = w.chantier("forge-stack", "rebuild", env=on_path)
        posts = stack_calls()[before:]
        check("a CR joins as a draft: `rebuild` unstacks the stack, stacks `201 202 204` (its PR is "
              "on its place, nothing to retarget), and prints the draft on top and what is to come",
              code == 0 and out[0] == "unstacked #100" and patches() == 0
              and len(posts) == 1 and [x for x in posts[0] if x.startswith("pull_requests[]")]
              == [f"pull_requests[]={n}" for n in (201, 202, 204)]
              and any("drafts on top #204" in x for x in out), str(out))
        code, out = w.chantier("forge-stack", "show", env=on_path)
        check("`forge-stack show` of that stack: mergeable below the second PR, the draft on top, "
              "`to come:` the draft's CR and the release",
              code == 0 and f"mergeable below {h7(b)} (#202" in out[0] and "drafts on top #204" in out[0]
              and f"to come: {new} working, {r} queued" in out, str(out))

        # a working CR with a draft PR on its place, not named in `stack`: to come, never a row
        _, late = prepare_cr(w, "Forge late")
        w.chantier("order", "add", "--note", str(late))
        extra = w.batch()["crs"][-1]["id"]
        record({extra: "working"}, **{extra: PR_LINK["github"] + "295"})
        edit_cr(extra, pr_base=branch(new))
        w.gh(drafts=[204, 295], heads={**gh_state()["heads"], "295": branch(extra)})
        code, out = w.chantier("forge-stack", "show", env=on_path)
        check("a working CR with a PR on its place that the stack driver has not placed is under "
              "`to come:`, working, and no `check 2` line names its PR",
              code == 0 and any(x.startswith("to come:") and f"{extra} working" in x for x in out)
              and not any(x.startswith("check 2") and "#295" in x for x in out), str(out))
        edit_cr(extra, status="cancelled", pr=None, pr_base=None)

        # 3. check 4 against each CR's status
        record({new: "ready"})
        code, out = w.chantier("forge-stack", "show", env=on_path, expect=2)
        check("a ready CR whose PR is still a draft: `check 4: still a draft #204`",
              any(x.startswith("check 4: still a draft") and "#204" in x for x in out), str(out))
        record({new: "working"})
        w.gh(drafts=[])
        code, out = w.chantier("forge-stack", "show", env=on_path, expect=2)
        check("a CR that is not ready whose PR is not a draft: `check 4: not a draft #204 (<cr> working)`",
              f"check 4: not a draft #204 ({new} working)" in out, str(out))
        record({new: "ready"})
        w.gh(drafts=[201])
        code, out = w.chantier("forge-stack", "show", env=on_path, expect=2)
        check("a draft under a ready PR: `check 4: a draft under a ready PR #201`",
              "check 4: a draft under a ready PR #201" in out, str(out))

        # 5. the complete stack
        record(**{r: links[r]})
        full = [201, 202, 204, 203]
        stack_on_forge(full)
        code, out = w.chantier("forge-stack", "show", env=on_path)
        check("the complete stack (every CR ready, no draft, the release on top): `stack complete, "
              "mergeable below` the release's head, and no `to come:` line",
              code == 0 and len(out) == 1 and f"stack complete, mergeable below {h7(r)} (#203)" in out[0]
              and "the release on top" in out[0], str(out))
        cases = [("a draft", dict(order=full, drafts=[202]), "check 4", "#202"),
                 ("a wrong order", dict(order=[202, 201, 204, 203]), "check 3", "#202"),
                 ("the release not on top", dict(order=[201, 202, 203, 204]), "check 5", "#203"),
                 ("a closed stack", dict(order=full, is_open=False), "check 1", "not open"),
                 ("a missing PR", dict(order=[201, 202, 203]), "check 2", "#204"),
                 ("a foreign PR", dict(order=[*full, 999]), "check 2", "#999")]
        for what, kw, line, word in cases:
            stack_on_forge(**kw)
            code, out = w.chantier("forge-stack", "show", env=on_path, expect=2)
            check(f"`forge-stack show` on {what}: a `{line}` line naming the cause, exit 2",
                  code == 2 and any(x.startswith(line) and word in x for x in out), str(out))
        stack_on_forge(full, drafts=[204, 203])
        code, out = w.chantier("forge-stack", "show", env=on_path, expect=2)
        check("`forge-stack show` prints one line per failed check", len(out) == 1 and "#204 #203" in out[0], str(out))
        w.gh(stacks=[{"number": 99, "open": False, "pull_requests": [201, 202]},
                     {"number": 100, "open": True, "pull_requests": full}], drafts=[])
        code, out = w.chantier("forge-stack", "show", env=on_path)
        check("`forge-stack show` without --stack prefers the open stack over a closed one that "
              "overlaps the batch's PRs", code == 0 and "stack #100 ready to merge:" in out[0], str(out))
        edit_cr(a, pr_draft=True)
        code, out = w.chantier("forge-stack", "show", env=on_path, expect=2)
        check("check 4 reads the draft state the CLI recorded: `recorded draft #201, the forge says "
              "out of draft`",
              "check 4: recorded draft #201, the forge says out of draft" in out, str(out))
        edit_cr(a, pr_draft=None)
        # 7. a dropped CR's PR still in the forge's stack is named apart from a foreign one
        kept = gh_state()
        stack_on_forge([*full, 999])
        code, out = w.chantier("forge-stack", "show", env=on_path, expect=2)
        check("a foreign PR is still named `not in the batch's stack #999`",
              any("not in the batch's stack #999" in x for x in out), str(out))
        stack_on_forge(full)
        record({b: "cancelled"})
        code, out = w.chantier("forge-stack", "show", env=on_path, expect=2)
        check(f"a dropped CR's PR still held by the forge's stack: `check 2: … dropped #202 ({b}): "
              "close it`, exit 2, and #202 is not called foreign",
              any(x.startswith("check 2") and f"dropped #202 ({b}): close it" in x
                  and "not in the batch's stack" not in x for x in out), str(out))
        before = len(stack_calls())
        code, out = w.chantier("forge-stack", "rebuild", env=on_path)
        posts = stack_calls()[before:]
        check(f"`rebuild` unstacks with `(it also held #202 of {b}, dropped: close it)` and posts the "
              "stack without #202",
              code == 0 and f"unstacked #100 (it also held #202 of {b}, dropped: close it)" in out
              and len(posts) == 1 and [x for x in posts[0] if x.startswith("pull_requests[]")]
              == [f"pull_requests[]={n}" for n in (201, 204, 203)], str(out))
        record({b: "ready"})
        w.gh_state.write_text(json.dumps(kept))  # the forge as it was before this step
        record(**{b: PR_LINK["gitlab"] + "202"})
        for action in ("create", "show"):
            code, _ = w.chantier("forge-stack", action, env=on_path, expect=2)
            check(f"a GitLab link in a GitHub stack: `forge-stack {action}` is refused, not all in "
                  "one repository",
                  code == 2 and "not all in one repository" in w.last_stderr, w.last_stderr)
        record(**{b: "https://example.com/acme/demo/issues/202"})
        code, _ = w.chantier("forge-stack", "show", env=on_path, expect=2)
        check("a link of neither shape is refused naming `is neither`",
              code == 2 and "is neither" in w.last_stderr, w.last_stderr)
        record(**{b: links[b]})

    _, joined = prepare_cr(w, "Forge inserted")
    record({r: "queued"})  # a ready release refuses `order add`: it is added before it started
    w.chantier("order", "add", "--note", str(joined))
    record({r: "ready"})
    ins = w.batch()["crs"][-1]["id"]
    order = [a, ins, b, new, r]
    w.chantier("stack", *order)
    _, listed = w.chantier("take", "stack", "--epoch", 1)
    w.chantier("agents", "set", "stack", "-", "--epoch", 1)
    check("insertion: a CR added to the stack batch and ordered below the release CR sits there in "
          "`take stack`, the release CR still last",
          listed and listed[0].endswith(" → ".join(order))
          and stack_take_rows(listed)[-1].startswith(f"{r} "),
          str(listed))
    check("`take stack` prints the rows with no `context:` line (its agent has not started yet)",
          not any(ln.startswith("context:") for ln in listed), str(listed))
    code, rows = w.chantier("stack")
    body = rows[1:-1]
    check("`stack` with no CR prints each row with `head <head7>` (or `head -`) and `restack: none`, "
          "then a `context:` line (`not measured` here: no transcript)",
          len(body) == len(order) and all(" head " in ln and ln.endswith("restack: none") for ln in body)
          and any(ln.startswith(f"{a} ") and f" head {h7(a)} " in ln for ln in body)
          and any(ln.startswith(f"{ins} ") and " head - " in ln for ln in body)
          and rows[-1].startswith("context: not measured"), str(rows))
    w.chantier("note", a, f"restack: on main {h7(a)}, head {h7(a)}")
    _, rows = w.chantier("stack")
    check("after `note <cr> \"restack: on … head …\"`, that CR's row shows the note and the others "
          "still say `restack: none`",
          any(ln.startswith(f"{a} ") and ln.endswith(f"restack: on main {h7(a)}, head {h7(a)}")
              for ln in rows)
          and all(ln.endswith("restack: none") for ln in rows[1:-1] if not ln.startswith(f"{a} ")),
          str(rows))
    if ARGS.forge == "github":
        code, out = w.chantier("forge-stack", "show", env=on_path, expect=2)
        check("after the insertion, `forge-stack show` reads the stack as it stands (the CR with no "
              "PR is to come): the PRs above it are not in it",
              code == 2 and any(x.startswith("check 2") and "not in the stack as it stands" in x
                                and b in x for x in out), str(out))
        record(**{ins: PR_LINK["github"] + "205"})
        check("the release's base is the CR just under it after an insertion below it, and the CR "
              "above the new one sits on it (`take stack`)",
              any(ln.startswith(r) and f"base {branch(new)}" in ln for ln in listed)
              and any(ln.startswith(b) and f"base {branch(ins)}" in ln for ln in listed), str(listed))
        # 1. an insertion: the old stack dissolved, the bases moved, one new stack bottom to top
        before = len(stack_calls())
        following = gh_state().get("next_stack", 100)
        code, out = w.chantier("forge-stack", "rebuild", env=on_path)
        posts = stack_calls()[before:]
        bases = gh_state()["bases"]
        check("`forge-stack rebuild` after an insertion: unstacks the old stack, retargets the PRs "
              "that sit on another base, creates one stack bottom to top (the release on top) and "
              "reads it back",
              code == 0 and out[0] == "unstacked #100" and f"#202 base {branch(a)} -> {branch(ins)}" in out
              and f"#203 base main -> {branch(new)}" in out and len(posts) == 1
              and [x for x in posts[0] if x.startswith("pull_requests[]")]
              == [f"pull_requests[]={n}" for n in (201, 205, 202, 204, 203)]
              and bases["205"] == branch(a) and bases["202"] == branch(ins)
              and bases["203"] == branch(new) and any(ln.startswith(f"stack #{following} ") for ln in out)
              and any(f"stack #{following} ready" in ln for ln in out), str(out))
        w.gh(drafts=[203])
        code, out = w.chantier("forge-stack", "rebuild", env=on_path)
        check("`rebuild` is idempotent, and prints a draft as a line to act on, with exit 0",
              code == 0 and any(ln.startswith("check 4") and "#203" in ln for ln in out)
              and not any("base" in ln and "->" in ln for ln in out), str(out))
        w.gh(drafts=[])
        # 2. a partial merge: the first PR left goes to the default branch, one stack made
        edit = w.batch()
        edit["crs"][0]["status"] = "merged"
        (w.folder() / "batch.json").write_text(json.dumps(edit, indent=2))
        before = len(stack_calls())
        code, out = w.chantier("forge-stack", "rebuild", env=on_path)
        posts = stack_calls()[before:]
        check("`forge-stack rebuild` after a partial merge: the first PR left is retargeted to the "
              "default branch, the merged PR is left out, one stack is created",
              code == 0 and any(ln.startswith("#205 base ") and ln.endswith("-> main") for ln in out)
              and any("also held #201" in ln for ln in out) and len(posts) == 1
              and [x for x in posts[0] if x.startswith("pull_requests[]")]
              == [f"pull_requests[]={n}" for n in (205, 202, 204, 203)]
              and gh_state()["bases"]["205"] == "main", str(out))
        # 3. a forge refusal mid-way: what was done and the forge's text, then a second run completes
        w.gh(stacks=[{"number": 150, "open": True, "pull_requests": [205, 202, 204, 203]}],
             bases={"205": "main", "202": "elsewhere", "204": branch(b), "203": branch(new)},
             patch_refused=True)
        w.chantier("forge-stack", "rebuild", env=on_path, expect=4)
        gone_line = ("stack #150 is dissolved and no stack replaces it yet: run "
                     "`forge-stack create`")
        check("a `rebuild` stopped by the forge prints what was done, the forge's exact text and, "
              "last, that the stack is dissolved and `forge-stack create` is next (exit 4)",
              "unstacked #150" in w.last_stderr and "HTTP 403" in w.last_stderr
              and w.last_stderr.strip().splitlines()[-1] == gone_line
              and gh_state()["bases"]["202"] == "elsewhere", w.last_stderr)
        w.gh(patch_refused=False)
        code, out = w.chantier("forge-stack", "rebuild", env=on_path)
        check("run again, `rebuild` finds no stack, retargets what is still off and completes",
              code == 0 and f"#202 base elsewhere -> {branch(ins)}" in out
              and not any(ln.startswith("unstacked") for ln in out)
              and gh_state()["bases"]["202"] == branch(ins)
              and any(ln.startswith("stack #") for ln in out), str(out))
        # 3b. a stack the forge keeps open after its five unstack tries: exit 4, then a rerun works
        open_now = [s["number"] for s in gh_state()["stacks"] if s["open"]]
        w.gh(unstack_ignored=True)
        w.chantier("forge-stack", "rebuild", env=on_path, expect=4)
        stuck = w.last_stderr
        check("a `rebuild` whose stack stays open after five unstack tries exits 4 and names the "
              "stack and the tries",
              len(open_now) == 1 and f"stack #{open_now[0]} is still open after 5 unstack tries"
              in stuck and "the forge reads it back with #" in stuck
              and "is dissolved" not in stuck and "state is unknown" not in stuck, stuck)
        w.gh(unstack_ignored=False, next_stack=200)  # numbers apart from the one seeded in 3.
        code, out = w.chantier("forge-stack", "rebuild", env=on_path)
        check("with the forge answering again, the next `rebuild` unstacks it and completes",
              code == 0 and f"unstacked #{open_now[0]}" in out
              and any(ln.startswith("stack #") for ln in out), str(out))
        # 3c. the forge's empty unstack reply is a success; a refusal after it says `create`
        planned_prs = {201, 202, 203, 204, 205}

        def open_holding() -> list[int]:
            return [s["number"] for s in gh_state()["stacks"]
                    if s["open"] and planned_prs & set(s["pull_requests"])]

        held_now = open_holding()
        w.gh(unstack_empty=True)
        code, out = w.chantier("forge-stack", "rebuild", env=on_path)
        made = open_holding()
        check("with the forge's unstack reply empty (2xx, no body), `rebuild` still completes: it "
              "unstacks, creates a stack and reads it back, one open stack holds the PRs",
              code == 0 and len(held_now) == 1 and f"unstacked #{held_now[0]}" in out
              and any(ln.startswith("stack #") for ln in out)
              and (any(" ready" in ln for ln in out) or any(ln.startswith("check 4") for ln in out))
              and len(made) == 1 and made != held_now, str(out))
        w.gh(stack_refused=True)
        w.chantier("forge-stack", "rebuild", env=on_path, expect=4)
        refused = w.last_stderr
        said = refused.strip().splitlines()
        cut = [refused.find(x) for x in (f"unstacked #{made[0]}", "HTTP 403: stacks are not allowed")]
        check("a `rebuild` whose create call is refused after the unstack: what was done, the "
              "forge's text, then last the dissolved line naming `forge-stack create` (exit 4)",
              len(made) == 1 and 0 <= cut[0] < cut[1]
              and said[-1] == f"stack #{made[0]} is dissolved and no stack replaces it yet: run "
              "`forge-stack create`", refused)
        w.gh(stack_refused=False)
        code, out = w.chantier("forge-stack", "create", env=on_path)
        check("`forge-stack create` after the dissolved line: exit 0 and one open stack holds the PRs",
              code == 0 and len(open_holding()) == 1, str(out))
        # 3d. a create call the forge accepted whose reply cannot be read: `show` is next
        made = open_holding()
        w.gh(create_unreadable=True)
        w.chantier("forge-stack", "rebuild", env=on_path, expect=4)
        unreadable = w.last_stderr
        cut = [unreadable.find(x) for x in (f"unstacked #{made[0]}", "not JSON")]
        check("a `rebuild` whose create reply cannot be read: what was done, `not JSON`, then last the "
              "unknown-state line naming `forge-stack show`, and no dissolved line (exit 4)",
              len(made) == 1 and 0 <= cut[0] < cut[1]
              and unreadable.strip().splitlines()[-1] == "the forge accepted the create call but "
              "its reply cannot be read, so the stack's state is unknown: run `forge-stack show`"
              and "is dissolved" not in unreadable, unreadable)
        w.gh(unstack_empty=False, create_unreadable=False)
        code, out = w.chantier("forge-stack", "show", env=on_path)
        check("`forge-stack show` after the unknown-state line: the stack the fake made is read "
              "back, one open stack holds the PRs",
              code == 0 and len(open_holding()) == 1 and open_holding() != made, str(out))
        # 4. refused on a GitLab link
        record(**{b: PR_LINK["gitlab"] + "202"})
        code, _ = w.chantier("forge-stack", "rebuild", env=on_path, expect=2)
        check("a GitLab link in a GitHub stack: `forge-stack rebuild` is refused, not all in one "
              "repository",
              code == 2 and "not all in one repository" in w.last_stderr, w.last_stderr)
        record(**{b: links[b]})
        # 5. leaving the stack: `order mode --note parallel`, then `unstack` dissolves it
        def unstack_calls() -> list[list[str]]:
            log = w.root / "gh-state.json.calls"
            rows = [json.loads(x) for x in log.read_text().splitlines()] if log.exists() else []
            return [x for x in rows if any(a.endswith("/unstack") for a in x)]

        w.chantier("forge-stack", "rebuild", env=on_path)  # one open stack holds the open PRs
        open_stack = [s["number"] for s in gh_state()["stacks"] if s["open"]]
        gone, kept_open = len(unstack_calls()), len(stack_calls())
        w.chantier("order", "mode", "--note", "parallel")
        code, out = w.chantier("forge-stack", "unstack", env=on_path)
        check("`forge-stack unstack` after `order mode --note parallel`: unstacks the open stack "
              "(the fake's unstack call logged), retargets each open PR to main, creates no stack",
              code == 0 and len(open_stack) == 1 and f"unstacked #{open_stack[0]}" in out
              and len(unstack_calls()) == gone + 1 and len(stack_calls()) == kept_open
              and any(ln.endswith("-> main") for ln in out)
              and {gh_state()["bases"][n] for n in ("202", "204", "203")} == {"main"}, str(out))
        code, out = w.chantier("forge-stack", "unstack", env=on_path)
        check("a second `unstack` finds no stack and nothing to retarget: exit 0",
              code == 0 and out == ["no stack holds the batch's PRs"]
              and len(unstack_calls()) == gone + 1, str(out))
    if ARGS.forge == "gitlab":
        # 6. leaving the stack: `unstack` only retargets, there is no stack to dissolve
        w.chantier("order", "mode", "--note", "parallel")
        forge_mrs([a, b, new, r], target={202: branch(a), 204: branch(b)})
        before = len(put_calls())
        code, out = w.chantier("forge-stack", "unstack", env=on_path)
        log = (w.root / "gh-state.json.calls").read_text()
        check("GitLab: `forge-stack unstack` after `order mode --note parallel` only retargets each "
              "MR to main (no unstack call, no stacks endpoint)",
              code == 0 and f"!202 target {branch(a)} -> main" in out
              and f"!204 target {branch(b)} -> main" in out and len(put_calls()) == before + 3
              and "unstack" not in log.replace("forge-stack", "") and "/stacks" not in log, str(out))
    w.reset()
    _, par = prepare_cr(w, "Forge parallel")
    w.start(str(par), *FROM_AGENTS_MD)
    w.env["CHANTIER_BATCH"] = w.name
    code, _ = w.chantier("forge-stack", "create", env=on_path, expect=2)
    check("`forge-stack create` is refused (exit 2) on a parallel batch",
          code == 2 and "not a stack" in w.last_stderr, w.last_stderr)
    code, _ = w.chantier("forge-stack", "rebuild", env=on_path, expect=2)
    check("`forge-stack rebuild` is refused (exit 2) on a parallel batch",
          code == 2 and "not a stack" in w.last_stderr, w.last_stderr)
    w.reset()
    w.env.pop("CHANTIER_BATCH", None)


def batch_modes(w: World) -> None:
    note("\n## 13b. The three modes: parallel by default, series, the switch to a stack")
    w.reset()
    p1, p2 = prepare_cr(w, "Mode one")[1], prepare_cr(w, "Mode two")[1]
    code, _ = w.start(str(p1), "--parallel", *FROM_AGENTS_MD, expect=2)
    check("`open --parallel` is refused as an unknown argument", code == 2 and p1.is_dir(),
          w.last_stderr)
    w.start(str(p1), str(p2), *FROM_AGENTS_MD)
    w.env["CHANTIER_BATCH"] = w.name
    one, two = (c["id"] for c in w.batch()["crs"])
    check("a batch with no mode named is parallel", w.batch()["mode"] == "parallel",
          str(w.batch()["mode"]))
    code, _ = w.chantier("take", "stack", "--epoch", 0, expect=2)
    take_stack_err = w.last_stderr
    code2, _ = w.chantier("stack", one, two, expect=2)
    check("parallel: `take stack` and `stack` are refused",
          code == 2 and code2 == 2 and w.batch()["mode"] == "parallel", w.last_stderr)
    for cr, name in ((one, "mode_one.py"), (two, "mode_two.py")):
        w.chantier("take", cr, "--epoch", 0)
        start_driver(w, cr)
        driver_round(w, cr, name, "N = 1\n")
        w.ready(cr, w.cr(cr)["pr"])
    w.chantier("order", "merged", one)
    code, out = w.chantier("take", two, "--note", f"rebase: {one} merged", "--epoch", 0)
    check("parallel: after a merge, a ready CR goes back to a Driver for its rebase, on the "
          "default branch", code == 0 and any("base origin/main" in ln for ln in out), str(out))

    w.reset()
    sa, sb, sc = (prepare_cr(w, t)[1] for t in ("Series first", "Series second", "Series third"))
    w.start(str(sa), str(sb), str(sc), "--mode", "series", *FROM_AGENTS_MD)
    w.env["CHANTIER_BATCH"] = w.name
    a, b, c = (x["id"] for x in w.batch()["crs"])
    _, out = w.chantier("status")
    check("series: `status` shows the next CR waiting for the previous one",
          w.batch()["mode"] == "series"
          and any(ln.startswith(b) and f"waits for {a} queued" in ln for ln in out)
          and any(ln.startswith(c) and f"waits for {b} queued" in ln for ln in out), str(out))
    code, _ = w.chantier("take", b, "--epoch", 0, expect=2)
    check("series: `take` refuses the next CR until the previous one is ready",
          code == 2 and f"waits for {a} queued" in w.last_stderr, w.last_stderr)
    w.chantier("take", a, "--epoch", 0)
    start_driver(w, a)
    driver_round(w, a, "series_a.py", "A = 1\n")
    code, _ = w.chantier("take", b, "--epoch", 0, expect=2)
    check("series: a working predecessor is not enough", code == 2 and f"{a} working" in w.last_stderr,
          w.last_stderr)
    w.ready(a, w.cr(a)["pr"])
    _, out = w.chantier("take", b, "--epoch", 0)
    start_driver(w, b)
    check("series: once the previous one is ready, the next starts on its branch, and the third "
          "still waits", any(f"base {w.cr(a)['branch']}" in ln for ln in out)
          and w.chantier("take", c, "--epoch", 0, expect=2)[0] == 2 and f"waits for {b} working" in w.last_stderr,
          str(out))
    driver_round(w, b, "series_b.py", "B = 1\n")
    w.ready(b, w.cr(b)["pr"])
    w.chantier("order", "merged", a)
    _, out = w.chantier("take", b, "--note", f"rebase: {a} merged", "--epoch", 0)
    check("series: once the previous one is merged, the next one is rebased on the default branch",
          any("base origin/main" in ln for ln in out), str(out))
    w.ready(b, w.cr(b)["pr"])
    _, out = w.chantier("take", c, "--epoch", 0)
    check("series: the third starts on the second's branch once that one is ready",
          any(f"base {w.cr(b)['branch']}" in ln for ln in out), str(out))
    w.chantier("handback", c, "blocked", "question: which one?")
    sd = prepare_cr(w, "Series on top")[1]
    w.chantier("order", "add", "--note", str(sd))
    d = w.batch()["crs"][-1]["id"]
    _, out = w.chantier("status")
    check("series: `order add` puts the new CR on top, waiting for the last one",
          w.cr(d)["order"] == max(x["order"] for x in w.batch()["crs"])
          and any(ln.startswith(d) and f"waits for {c} blocked" in ln for ln in out), str(out))

    w.reset()
    x1, x2 = prepare_cr(w, "Series late")[1], prepare_cr(w, "Series early")[1]
    depends_on(x1, x2.name)
    code, _ = w.start(str(x1), str(x2), "--mode", "series", *FROM_AGENTS_MD, expect=2)
    check("series: a CR placed before its dependency is refused at `open`",
          code == 2 and "cannot come before it in the series" in w.last_stderr and x1.is_dir()
          and x2.is_dir(), w.last_stderr)

    w.reset()
    y = [prepare_cr(w, t)[1] for t in ("Switch one", "Switch two", "Switch three")]
    w.start(*(str(p) for p in y), "--mode", "series", *FROM_AGENTS_MD)
    w.env["CHANTIER_BATCH"] = w.name
    a, b, c = (x["id"] for x in w.batch()["crs"])
    code, _ = w.chantier("take", c, "--epoch", 0, expect=2)
    waits_err = w.last_stderr
    _, out = w.chantier("order", "mode", "--note", "stack")
    check("`order mode --note stack` turns a series into a stack at once, and logs it",
          code == 2 and f"waits for {b} queued" in waits_err and w.batch()["mode"] == "stack" and w.batch()["orders"][-1]["kind"] == "mode"
          and w.batch()["orders"][-1]["applied"]
          and any('"kind": "mode"' in ln for ln in (w.folder() / "events.jsonl").read_text().splitlines())
          and [b["mode"] for b in json.loads((w.state / "STATUS.json").read_text(encoding="utf-8"))["batches"]
               if b["batch"] == w.name] == ["stack"],
          str(out))
    code, out = w.chantier("take", c, "--epoch", 0)
    check("after the switch, a queued CR is taken at once, on the default branch",
          code == 0 and any("base origin/main" in ln for ln in out), str(out))
    code, out = w.chantier("take", "stack", "--epoch", 0)
    check("after the switch, `take stack` works", code == 0 and out[0].startswith("the stack of batch"),
          str(out))

    # any mode to any other, live: a merged CR (m), two ready (y before x), a working one (z) and a
    # queued one (q); the merged CR's record never changes
    w.reset()
    names = ("Switch merged", "Switch x", "Switch y", "Switch z", "Switch q")
    w.start(*(str(prepare_cr(w, t)[1]) for t in names), *FROM_AGENTS_MD)
    w.env["CHANTIER_BATCH"] = w.name
    m, x, y, z, q = (c["id"] for c in w.batch()["crs"])
    for cr, name in ((m, "sw_m.py"), (y, "sw_y.py"), (x, "sw_x.py")):
        w.chantier("take", cr, "--epoch", 0)
        start_driver(w, cr)
        driver_round(w, cr, name, "N = 1\n")
        w.ready(cr, w.cr(cr)["pr"])
    w.chantier("order", "merged", m)
    w.chantier("take", z, "--epoch", 0)
    start_driver(w, z)
    kept = {k: w.cr(m).get(k) for k in ("status", "order", "pr", "branch")}

    def open_order() -> list[str]:
        crs = [c for c in w.batch()["crs"] if c["status"] not in ENDED]
        return [c["id"] for c in sorted(crs, key=lambda c: c["order"])]

    def last_mode() -> dict:
        lines = (w.folder() / "events.jsonl").read_text().splitlines()
        return [e for e in map(json.loads, lines) if e["kind"] == "mode"][-1]

    code, out = w.chantier("order", "mode", "--note", "series")
    _, status = w.chantier("status")
    check("parallel to series: the order is y, x, z, q (readiness first), the queued CR waits for its "
          "predecessor, the merged CR is unchanged",
          code == 0 and open_order() == [y, x, z, q] and last_mode()["previous"] == "parallel"
          and any(ln.startswith(q) and f"waits for {z} working" in ln for ln in status)
          and {k: w.cr(m).get(k) for k in kept} == kept, str(out) + str(status))
    code, out = w.chantier("take", x, "--note", "rebase: mode series", "--epoch", 0)
    check("parallel to series: a ready CR's rebase prints its predecessor's branch",
          code == 0 and any(f"base {w.cr(y)['branch']}" in ln for ln in out), str(out))
    w.ready(x, w.cr(x)["pr"])
    code, out = w.chantier("order", "mode", "--note", "parallel")
    code2, out2 = w.chantier("take", q, "--epoch", 0)
    check("series to parallel: a queued CR that waited for its predecessor is taken at once, on the "
          "default branch; the merged CR is unchanged",
          code == 0 and code2 == 0 and any("base origin/main" in ln for ln in out2)
          and {k: w.cr(m).get(k) for k in kept} == kept, str(out2))
    code, out = w.chantier("order", "mode", "--note", "stack")
    check("parallel to stack with two CRs ready: the order follows readiness (y before x), then the "
          "others; the event names the previous mode; the merged CR is unchanged",
          code == 0 and open_order() == [y, x, z, q] and last_mode()["previous"] == "parallel"
          and last_mode()["mode"] == "stack" and f"order: {y} → {x} → {z} → {q}" in out[-1]
          and {k: w.cr(m).get(k) for k in kept} == kept, str(out))
    code, out = w.chantier("take", "stack", "--epoch", 0)
    code2, _ = w.chantier("stack", y, x)
    check("after the switch, `take stack` works and `stack` accepts that order",
          code == 0 and out[0].startswith("the stack of batch") and code2 == 0
          and w.cr(x)["stacked"], str(out))
    d = w.batch()
    next(c for c in d["crs"] if c["id"] == x)["start_on"] = w.cr(y)["branch"]  # a recorded start base
    (w.folder() / "batch.json").write_text(json.dumps(d, indent=2))
    code, out = w.chantier("order", "mode", "--note", "parallel")
    check("stack to parallel clears every place in the stack, and says to unstack first",
          code == 0 and not any(c.get("stacked") for c in w.batch()["crs"])
          and any("forge-stack unstack" in ln for ln in out), str(out))
    code, out = w.chantier("take", x, "--note", "rebase: mode parallel", "--epoch", 0)
    _, status = w.chantier("status")
    check("stack to parallel: a CR that was stacked on another, or recorded a start base, is taken "
          "back on the default branch, no CR waits for a predecessor, the merged CR is unchanged",
          code == 0 and any("base origin/main" in ln for ln in out)
          and not any("waits for" in ln for ln in status)
          and {k: w.cr(m).get(k) for k in kept} == kept, str(out) + str(status))
    w.env.pop("CHANTIER_BATCH", None)


def early_conflict(w: World) -> None:
    note("\n## 13b. Early conflict between two ready PRs")

    def two_ready(titles: tuple[str, str], *mode: str) -> tuple[Foreman, str, str]:
        w.reset()
        w.start(*(str(prepare_cr(w, t)[1]) for t in titles), *mode, *FROM_AGENTS_MD)
        w.env["CHANTIER_BATCH"] = w.name
        w.chantier("foreman", "set", "early_foreman", "--epoch", 1)
        a_, b_ = (c["id"] for c in w.batch()["crs"])
        return Foreman(w, epoch=1), a_, b_

    def hand_back(cr: str, value: int) -> None:
        if w.cr(cr)["status"] == "queued":  # the Foreman's turn may have taken it already
            w.chantier("take", cr, "--epoch", 1)
        start_driver(w, cr)
        driver_round(w, cr, "shared.py", f"N = {value}\n")
        w.ready(cr, w.cr(cr)["pr"])

    def merge_trees(fm: Foreman) -> list[tuple[str, ...]]:
        return [g for g in fm.git_main if g[0] == "merge-tree"]

    def conflict_asks(fm: Foreman) -> list[str]:
        return [a for a in fm.asked if a.startswith("conflict ")]

    fm, first, second = two_ready(("Early first", "Early second"))
    hand_back(first, 1)
    fm.turn()
    check("the first hand-back: no other ready PR, so no merge-tree and no `conflict` ask",
          not merge_trees(fm) and not conflict_asks(fm), str(fm.git_main))
    hand_back(second, 2)
    fm.turn()
    check("the second hand-back: the ready ask goes up unchanged, then one `conflict` ask naming "
          "the file, and the second CR carries the note; merge-tree ran once, read-only",
          fm.asked[-2:] == [f"ready-to-merge {second} {w.cr(second)['pr']}",
                            f"conflict {second} with {first}: shared.py; switch to a stack?"]
          and w.cr(second)["notes"][-1] == f"early conflict: with {first}: shared.py"
          and len(merge_trees(fm)) == 1
          and merge_trees(fm)[0][:4] == ("merge-tree", "--write-tree", "--name-only",
                                         "--no-messages"), str(fm.asked) + str(fm.git_main))
    fm.turn()
    fm.early_conflicts(w.batch(), w.cr(second))
    check("a pair already noted gives no second ask and no second note",
          len(conflict_asks(fm)) == 1
          and sum(n.startswith("early conflict:") for n in w.cr(second)["notes"]) == 1
          and len(merge_trees(fm)) == 1, str(fm.asked))
    check("the check moved no mode and no order: the batch is still parallel, both CRs ready",
          w.batch()["mode"] == "parallel"
          and all(w.cr(c)["status"] == "ready" for c in (first, second)))
    code, out = w.chantier("order", "mode", "--note", "stack")
    code2, _ = w.chantier("take", "stack", "--epoch", 1)
    order = [c["id"] for c in sorted(w.batch()["crs"], key=lambda c: c["order"])]
    check("the Chief of Staff's `order mode --note stack` gives a stack with the earlier ready CR "
          "at the bottom",
          code == 0 and code2 == 0 and w.batch()["mode"] == "stack" and order == [first, second]
          and f"order: {first} → {second}" in out[-1], str(out) + str(order))

    fm, first, second = two_ready(("Early stacked first", "Early stacked second"), "--mode", "stack")
    hand_back(first, 1)
    hand_back(second, 2)
    fm.turn()
    check("a stack batch: no merge-tree runs and no `conflict` ask is sent",
          not merge_trees(fm) and not conflict_asks(fm)
          and fm.asked[-1].startswith(f"ready-to-merge {second} "), str(fm.asked))
    w.env.pop("CHANTIER_BATCH", None)


def release(w: World) -> None:
    note("\n## 14. A release: the project's procedure, approvals, a fix, a grant")
    _, change = prepare_cr(w, "Last change")
    _, version = prepare_cr(w, "Release v1.1.0")
    bad = (("--release", 3), ("--release", 2, "--grant-fixes"),
           ("--autonomous-releases", 1, "--budget", 5))
    for args in bad:
        code, _ = w.chantier("open", str(change), str(version), *FROM_AGENTS_MD, *args,
                             expect=1)
        check(f"open refuses {args}", code == 1 and change.is_dir())
    w.reset()
    w.start(str(change), str(version), "--release", 2, "--slots", 2, *FROM_AGENTS_MD)
    w.env["CHANTIER_BATCH"] = w.name
    w.chantier("foreman", "set", "local_foreman3", "--epoch", 1)
    fm = Foreman(w, epoch=1)
    work, rel = (c["id"] for c in w.batch()["crs"])
    fm.turn()
    check("the release waits for the batch's other CRs", fm.started == [work])
    code, _ = w.chantier("take", rel, "--epoch", 1, expect=2)
    check("the release CR is refused until the others are merged",
          code == 2 and "merged or cancelled" in w.last_stderr, w.last_stderr)
    driver_round(w, work, "last.py", "LAST = True\n")
    w.ready(work, w.cr(work)["pr"])
    fm.turn()
    check("an ordinary ready CR goes to the user, never to a merge",
          fm.asked[-1].startswith(f"ready-to-merge {work} "), str(fm.asked))
    w.chantier("order", "merged", work)
    fm.turn()
    check("once the other CR is merged, the release is taken at once (no confirmation), with "
          "the grant in its facts",
          fm.started[-1] == rel and "confirmation" not in " ".join(w.chantier("status")[1])
          and any(ln.startswith("grant: every irreversible action waits") for ln in fm.facts),
          str(fm.facts))

    tag = "push tag v1.1.0"
    _, out = w.chantier("release", "start", rel)
    check("an attempt is counted", out[0].startswith("attempt 1"), str(out))
    notes = w.state / w.cr(rel)["path"] / "work" / "notes-v1.1.0.md"
    notes.write_text("# v1.1.0\n")
    w.chantier("note", rel, "--draft", notes)
    _, out = w.chantier("status")
    check("status shows the draft on the release's line",
          any(ln.startswith(rel) and notes.as_posix() in ln for ln in out), str(out))
    code, out = w.chantier("release", "go", rel, "--note", tag, expect=2)
    check("an irreversible action without approval is refused",
          code == 2 and out[0].startswith("no approval"), str(out))
    w.chantier("handback", rel, "blocked", f"approval: {tag}")
    fm.turn()
    check("the Chief of Staff gets the approval to ask", fm.asked[-1].startswith(f"blocked {rel} approval:"))
    code, _ = w.chantier("order", "approve", work, "--note", tag, expect=1)
    check("only the release CR takes an approval", code == 1)
    w.chantier("order", "approve", rel, "--note", tag)
    check("an approval is recorded; the release stays blocked until the Foreman acts",
          w.cr(rel)["status"] == "blocked" and w.cr(rel)["approvals"] == [tag])
    fm.turn()
    check("the Foreman gives the approval to a new Release driver", fm.started[-1].startswith(f"{rel} approve:")
          and any("approvals unused: " + tag in ln for ln in fm.facts), str(fm.facts))
    code, out = w.chantier("release", "go", rel, "--note", tag)
    check("the approval opens that action", code == 0 and out[0].startswith(f"go: {tag}"))
    code, _ = w.chantier("release", "go", rel, "--note", "publish v1.1.0", expect=2)
    check("an approval is spent once", code == 2)

    w.chantier("handback", rel, "blocked", "fix: the heavy suite fails; work/fix-1.md")
    fm.turn()
    _, fix = prepare_cr(w, "Fix the heavy suite")
    code, _ = w.chantier("order", "grant", rel, "--note", "releases=1 fixes=on", expect=1)
    check("a grant without a budget is refused", code == 1 and "budget" in w.last_stderr)
    w.chantier("order", "grant", rel, "--note", "releases=1 fixes=on budget=5")
    started = len(fm.started)
    fm.turn()
    check("a grant leaves a release that waits for its fix alone",
          len(fm.started) == started and w.cr(rel)["status"] == "blocked")
    _, out = w.chantier("order", "add", "--note", str(fix), "--fix-for", rel)
    fm.turn()
    fix_id = w.batch()["crs"][-1]["id"]
    check("a fix becomes a CR of the batch; the release waits for it",
          fm.started[-1] == fix_id and w.cr(rel)["status"] == "blocked"
          and w.cr(fix_id)["fix_for"] == rel, str(fm.started))
    code, out = w.chantier("release", "go", rel, "--note", "publish v1.1.0", expect=2)
    check("no irreversible action while a fix of the release is not merged",
          code == 2 and out[0].startswith(f"no: fix {fix_id} is not merged"), str(out))
    code, _ = w.chantier("release", "go", fix_id, "--note", "merge the fix", expect=2)
    check("a fix that is not ready does not merge", code == 2 and "ready" in w.last_stderr)
    driver_round(w, fix_id, "heavy.py", "FIXED = True\n")
    w.gh(merge_refused=True)
    w.ready(fix_id, w.cr(fix_id)["pr"])
    w.chantier("order", "grant", rel, "--note", "fixes=off")
    code, out = w.chantier("release", "go", fix_id, "--note", "merge the fix", expect=2)
    check("without the grant, the user merges the fix",
          code == 2 and "the user merges it" in out[0], str(out))
    w.chantier("order", "grant", rel, "--note", "fixes=on")
    fm.turn()
    check("a merge the forge refuses goes to the Chief of Staff, the fix stays ready",
          fm.asked[-1].startswith(f"refused {fix_id}") and w.cr(fix_id)["status"] == "ready",
          fm.asked[-1])
    w.gh(merge_refused=False)
    fm.told.discard((fix_id, "ready", w.cr(fix_id)["pr"]))  # the user's word: try again
    fm.turn()
    check("under the grant the Foreman merges the fix with the forge's CLI and records it; "
          "the release goes on",
          w.cr(fix_id)["status"] == "merged" and "/3-done/" in w.cr(fix_id)["path"]
          and any(a.startswith(f"merged {fix_id} ") for a in fm.asked)
          and fm.started[-1].startswith(f"{rel} fix merged:"), str(fm.asked))

    _, out = w.chantier("release", "start", rel)
    check("each new attempt is counted", out[0].startswith("attempt 2"), str(out))
    state = w.folder() / "batch.json"
    data = w.batch()
    state.write_text(json.dumps({**data, "spent_usd": 6}))
    code, out = w.chantier("release", "go", rel, "--note", "publish v1.1.0", expect=5)
    check("past the budget, a grant opens nothing", code == 5 and "budget" in out[0], str(out))
    w.chantier("handback", rel, "blocked", "budget: publish v1.1.0")
    fm.turn()
    _, out = w.chantier("order", "budget", "--note", "20")
    check("a wider budget is recorded; the CR blocked on it waits for the Foreman",
          out[-1] == "budget $20" and w.cr(rel)["status"] == "blocked", str(out))
    fm.turn()
    check("the Foreman sends the blocked release on, with the budget's note",
          fm.started[-1].startswith(f"{rel} budget:") and w.cr(rel)["status"] == "working"
          and all(o["done"] for o in w.batch()["orders"]), str(fm.started))
    code, out = w.chantier("release", "go", rel, "--note", "publish v1.1.0")
    check("the grant opens the action without asking", code == 0 and "without asking" in out[0])
    w.chantier("note", rel, "release commit")
    commit(w, rel, "VERSION", "1.1.0\n", "release: v1.1.0")
    w.chantier("gate", rel, GATE)
    ship(w, rel, "release: v1.1.0")
    # the grant is lifted for a moment: the user's approval never covers the release PR's merge
    w.chantier("order", "grant", rel, "--note", "releases=0 fixes=on budget=20")
    w.chantier("handback", rel, "ready", w.cr(rel)["pr"])
    check("the release PR is prepared: `ready`, no verdict asked, and not red",
          w.cr(rel)["status"] == "ready" and "waits for its merge" in w.last_out[-1]
          and not any("🔴" in lb for lb in drawn(w, rel)[0]), str(w.last_out))
    events = [json.loads(e) for e in (w.folder() / "events.jsonl").read_text().splitlines()]
    check("the release PR, in a parallel batch, sits on the default branch",
          [e["base"] for e in events if e["kind"] == "ship" and e["cr"] == rel][-1] == "main")
    w.chantier("order", "approve", rel, "--note", f"merge the release PR {w.cr(rel)['pr']}")
    code, out = w.chantier("release", "go", rel, "--note", f"merge the release PR {w.cr(rel)['pr']}",
                           expect=2)
    check("an approval never covers the release PR's merge: `release go` answers `merge`",
          code == 2 and out[0].startswith("no: the release PR") and "user's to merge" in out[0],
          str(out))
    for o in w.batch()["orders"]:
        if not o["done"] and o["kind"] != "approve":
            w.chantier("order", "done", o["id"], "--epoch", 1)
    drivers = len(fm.started)
    fm.turn()
    check("an approval recorded while the release PR waits takes no Driver: the Foreman marks it "
          "done and the release stays `ready`",
          len(fm.started) == drivers and w.cr(rel)["status"] == "ready"
          and all(o["done"] for o in w.batch()["orders"]), str(fm.started))
    w.chantier("order", "grant", rel, "--note", "releases=1 fixes=on budget=20")
    w.chantier("order", "done", w.batch()["orders"][-1]["id"], "--epoch", 1)
    w.gh(merge_refused=True)
    fm.turn()
    check("under the grant the Foreman merges the release PR; refused by the forge, it asks",
          fm.asked[-1].startswith(f"refused {rel}") and w.cr(rel)["status"] == "ready",
          fm.asked[-1])
    w.gh(merge_refused=False)
    fm.told.discard((rel, "refused", fm.asked[-1].removeprefix(f"refused {rel} ")))
    drivers = len(fm.started)
    fm.turn()
    check("merged with the forge's CLI, `order merged --epoch` sends the release on with a new "
          "Driver, not to the archives",
          len(fm.started) == drivers + 1 and fm.started[-1].startswith(f"{rel} merged:")
          and "5-archives/" not in w.cr(rel)["path"]
          and all(o["done"] for o in w.batch()["orders"]), str(fm.started))
    check("the merged PR is not the next attempt's: `pr`, `pr_base` and `pr_draft` are cleared",
          all(w.cr(rel).get(k) is None for k in ("pr", "pr_base", "pr_draft")))
    merged_pr = w.cr(rel)["merged_pr"]
    events = [json.loads(e) for e in (w.folder() / "events.jsonl").read_text().splitlines()]
    merge_go = [e for e in events if e["kind"] == "release-go" and e["cr"] == rel
                and e.get("result") == "go" and e["action"].startswith("merge")]
    check("the Foreman's merge go under the grant spends no approval: the one recorded before "
          "the grant is still there, and the go's why is the grant's",
          len(w.cr(rel)["approvals"]) == 1
          and merge_go and "without asking" in merge_go[-1]["why"]
          and "the user approved" not in merge_go[-1]["why"], str(merge_go))
    for step in ("push tag v1.1.0", "publish v1.1.0"):
        code, out = w.chantier("release", "go", rel, "--note", step)
        check(f"the merge is the go for `{step}`, with no approval",
              code == 0 and out[0].startswith("go:") and merged_pr in out[0]
              and "approved" not in out[0], str(out))
    w.chantier("release", "published", rel, "--note", "v1.1.0 https://forge.example/v1.1.0")
    _, out = w.chantier("handback", rel, "ready", "https://forge.example/v1.1.0")
    check("a released CR moves to 3-done, and the batch can pause",
          "/3-done/" in w.cr(rel)["path"] and any(ln.startswith("paused batch-") for ln in out)
          and w.batch()["status"] == "paused", str(out))
    fm.turn()
    check("the release done, the batch pauses", fm.paused, str(fm.asked))
    calls = (w.root / "gh-state.json.calls").read_text()
    merged = ('"merge"', '/merge"')[ARGS.forge == "gitlab"]
    check("the forge saw the Foreman's merges", calls.count(merged) >= 2)


def granted_fixes(w: World) -> None:
    note("\n## 14b. The Foreman starts a release's fixes under the grant, up to three")
    _, version = prepare_cr(w, "Release v1.3.0")
    w.reset()
    w.start(str(version), "--release", 1, "--slots", 1, *FROM_AGENTS_MD)
    w.env["CHANTIER_BATCH"] = w.name
    w.chantier("foreman", "set", "local_foreman5", "--epoch", 1)
    rel = w.batch()["crs"][0]["id"]
    work = w.state / w.cr(rel)["path"] / "work"
    work.mkdir()
    files = [work / f"fix-{n}.md" for n in range(1, 5)]
    for n, path in enumerate(files, 1):
        path.write_text(f"# Fix step {n}\n\nExpected: it passes. Actual: it fails.\n")
    add = ("order", "add", "--note", files[0], "--fix-for", rel)
    code, _ = w.chantier(*add, "--epoch", 1, expect=2)
    check("without a grant, the Foreman starts no fix", code == 2 and "no grant" in w.last_stderr,
          w.last_stderr)
    w.chantier("order", "budget", "--note", 50)
    w.chantier("order", "grant", rel, "--note", "fixes=on")
    codes = [w.chantier("order", "add", "--note", path, "--fix-for", rel, "--epoch", 1,
                        expect=None)[0] for path in files]
    check("under the grant, three fixes start and a fourth is refused", codes == [0, 0, 0, 5],
          str(codes))
    fix = w.batch()["crs"][1]
    spec = w.state / fix["path"] / "03-change-spec.md"
    check("a fix file becomes a fix CR of the batch, its specification kept",
          fix["kind"] == "fix" and fix["title"] == "Fix step 1" and fix["status"] == "queued"
          and spec.read_text() == files[0].read_text(), str(fix))
    w.chantier("order", "add", "--note", files[3], "--fix-for", rel)
    check("past three, a fix is the user's go", len(w.batch()["crs"]) == 5)
    still = [c for c in w.batch()["crs"] if c["status"] != "cancelled"]  # a second drop is refused
    for c in still[:-1]:
        w.chantier("order", "drop", c["id"], "--note", "trash")
    _, out = w.chantier("status")
    check("`status` tells an order the CLI applied from one nothing has touched",
          any(ln.startswith("orders the CLI applied") and "order done" in ln and "O-" in ln
              for ln in out), str(out))
    _, out = w.chantier("order", "drop", still[-1]["id"], "--note", "trash")
    check("the drop of the last CR pauses the batch, its applied orders ended",
          w.batch()["status"] == "paused" and all(o["done"] for o in w.batch()["orders"])
          and any(ln.startswith("paused batch-") for ln in out), str(out))
    dropped = next(c for c in w.batch()["crs"] if c["status"] == "cancelled")
    count = len(w.batch()["orders"])
    code, _ = w.chantier("order", "drop", dropped["id"], "--note", "trash", expect=2)
    check("a second drop of a cancelled CR is refused and records no order",
          code == 2 and "already dropped" in w.last_stderr and len(w.batch()["orders"]) == count,
          w.last_stderr)
    code, _ = w.chantier("order", "drop", dropped["id"].removeprefix("CR-"), "--note", "trash",
                           expect=2)
    check("`101` is taken for `CR-101` in `order`", code == 2 and "already dropped" in w.last_stderr,
          w.last_stderr)
    code, _ = w.chantier("order", "note", dropped["id"], "--note", "late", expect=2)
    check("a note on a cancelled CR is refused", code == 2 and "cancelled" in w.last_stderr,
          w.last_stderr)
    code, _ = w.chantier("order", "rounds", "--note", "0", expect=1)
    check("`order rounds` with no CR shows its full usage", "--note <n>" in w.last_stderr,
          w.last_stderr)
    code, _ = w.chantier("order", "budget", "--note", "-5", expect=1)
    check("`order budget` says why a value is refused", "'-5'" in w.last_stderr
          and "dollars" in w.last_stderr, w.last_stderr)
    for o in w.batch()["orders"]:
        if not o["done"]:
            w.chantier("order", "done", o["id"], "--epoch", 1)
    w.reset()


def release_last(w: World) -> None:
    note("\n## 14c. A release added to a running batch waits for every other CR, then for the user")
    _, first = prepare_cr(w, "First change")
    _, second = prepare_cr(w, "Second change")
    _, third = prepare_cr(w, "Third change")
    _, version = prepare_cr(w, "Release v1.5.0")
    _, other = prepare_cr(w, "Release v1.6.0")
    _, fix_one = prepare_cr(w, "Fix one")
    _, fix_two = prepare_cr(w, "Fix two")
    w.reset()
    w.start(str(first), "--slots", 1, *FROM_AGENTS_MD)
    w.env["CHANTIER_BATCH"] = w.name
    w.chantier("foreman", "set", "local_foreman6", "--epoch", 1)
    fm = Foreman(w, epoch=1)
    work = w.batch()["crs"][0]["id"]
    w.chantier("order", "add", "--release", "--fix-for", work, "--note", str(version), expect=1)
    check("--release goes with no --fix-for", w.last_stderr.count("--release") >= 1, w.last_stderr)
    w.chantier("order", "add", "--release", "--note", str(version))
    rel = w.batch()["crs"][-1]["id"]
    check("order add --release adds the batch's release CR, with the default grant, after the CR",
          w.cr(rel)["kind"] == "release" and w.cr(rel)["after"] == [work]
          and w.batch()["release"] == {"autonomous": 0, "fixes": False, "published": 0, "cr": rel},
          str(w.cr(rel)))
    w.chantier("order", "add", "--note", str(second))
    late = w.batch()["crs"][-1]["id"]
    check("a CR added later is waited for too", w.cr(rel)["after"] == [work, late])
    _, out = w.chantier("status")
    check("status shows the release waiting for each CR",
          any(ln.startswith(rel) and f"waits for {work} queued, {late} queued" in ln for ln in out),
          str(out))
    w.chantier("order", "add", "--release", "--note", str(other), expect=2)
    check("a second release is refused, the next batch named", "next batch" in w.last_stderr,
          w.last_stderr)
    w.chantier("order", "after", rel, "--note", work, expect=2)
    check("order after is refused on the release", "release CR" in w.last_stderr, w.last_stderr)
    w.chantier("order", "after", late, "--note", rel, expect=2)
    check("a CR that waits for the release is a cycle, the release named",
          "cycle" in w.last_stderr and rel in w.last_stderr, w.last_stderr)
    w.chantier("order", "confirm", work, "--note", "v1.5.0", expect=1)
    check("only a release is confirmed", rel in w.last_stderr, w.last_stderr)
    w.chantier("order", "confirm", rel, "--note", "v1.5.0", expect=2)
    check("the user's word is refused while CRs are open: they are named",
          "not merged yet" in w.last_stderr and work in w.last_stderr and late in w.last_stderr,
          w.last_stderr)

    check("the first CR starts", fm.take(work) == 0)
    driver_round(w, work, "first.py", "FIRST = True\n")
    w.ready(work, w.cr(work)["pr"])
    code, _ = w.chantier("take", rel, "--epoch", 1, expect=2)
    check("a ready CR keeps the release waiting",
          code == 2 and f"{work} ready" in w.last_stderr, w.last_stderr)
    w.chantier("order", "merged", work)
    w.chantier("order", "drop", late, "--note", "trash")
    check("a merged CR and a dropped one are met",
          w.cr(work)["status"] == "merged" and w.cr(late)["status"] == "cancelled")
    _, out = w.chantier("status")
    check("status shows no confirmation for the release: the others ended, it waits for nothing",
          not any("confirmation" in ln for ln in out)
          and not any(ln.startswith(rel) and "waits for" in ln for ln in out), str(out))
    w.chantier("order", "confirm", rel, "--note", "v1.5.0, the notes settled")
    check("the user's word to run the procedure is kept on the CR and in its notes, never as "
          "`confirmed`",
          w.cr(rel)["procedure"] == "v1.5.0, the notes settled" and "confirmed" not in w.cr(rel)
          and any(n.startswith("procedure:") for n in w.cr(rel)["notes"]))
    w.chantier("order", "add", "--note", str(third))
    added = w.batch()["crs"][-1]["id"]
    check("a CR added then voids the word, which the log and a note explain",
          "procedure" not in w.cr(rel) and w.cr(rel)["after"][-1] == added
          and any("voided" in n for n in w.cr(rel)["notes"])
          and any(e["kind"] == "confirm-void" for e in map(json.loads, (w.folder() / "events.jsonl").read_text().splitlines())))
    w.chantier("order", "drop", added, "--note", "trash")
    w.chantier("order", "confirm", rel, "--note", "v1.5.0, with the third change dropped")
    check("the release starts with no confirmation asked", fm.take(rel) == 0)

    w.chantier("order", "add", "--note", str(second), expect=2)
    check("order add is refused once the release has started, with its two ways out",
          "--fix-for" in w.last_stderr and "next batch" in w.last_stderr
          and "ships the work under it" in w.last_stderr, w.last_stderr)
    w.chantier("order", "confirm", rel, "--note", "again")
    check("the user's word is accepted once the release has started, the others being merged",
          w.cr(rel)["procedure"] == "again", str(w.cr(rel)))
    w.chantier("order", "add", "--note", str(fix_one), "--fix-for", rel)
    check("a fix of the release is still added",
          w.batch()["crs"][-1]["kind"] == "fix" and "procedure" in w.cr(rel))
    w.chantier("release", "start", rel)
    w.chantier("order", "merged", rel)
    check("a merged release PR puts the release back to queued, attempts kept",
          w.cr(rel)["status"] == "queued" and w.cr(rel)["attempts"] == 1)
    w.chantier("order", "add", "--note", str(second), expect=2)
    check("order add is refused again, whatever the state, since attempts says so",
          "has started" in w.last_stderr, w.last_stderr)
    w.chantier("order", "add", "--note", str(fix_two), "--fix-for", rel)
    check("order add --fix-for still works", w.batch()["crs"][-1]["fix_for"] == rel)
    fixes = [x["id"] for x in w.batch()["crs"] if x.get("fix_for") == rel]
    own = icon_is(w, rel, "🟠", "a queued release with an open fix (`take` refuses it)")
    check("the open fixes are in the release's `waits`",
          all(any(wt.startswith(f"{i} ") for wt in own["waits"]) for i in fixes)
          and f"waits for {fixes[0]}" in own["label"], str(own))
    for i in fixes:
        w.chantier("order", "drop", i, "--note", "trash")

    w.reset()
    _, alone = prepare_cr(w, "Release v1.7.0")
    w.start(str(alone), "--release", 1, "--slots", 1, *FROM_AGENTS_MD)
    w.env["CHANTIER_BATCH"] = w.name
    w.chantier("foreman", "set", "local_foreman7", "--epoch", 1)
    only = w.batch()["crs"][0]["id"]
    w.chantier("order", "confirm", only, "--note", "v1.7.0")
    check("the user's word is accepted for a release alone, before a release PR is recorded",
          w.cr(only)["procedure"] == "v1.7.0", str(w.cr(only)))
    solo = Foreman(w, epoch=1)
    check("a release alone starts when taken, with no confirmation asked, on the default branch",
          solo.take(only) == 0 and any("base origin/main" in ln for ln in solo.facts),
          str(solo.facts))
    w.chantier("release", "start", only)
    commit(w, only, "VERSION", "1.7.0\n", "release: v1.7.0")
    w.chantier("gate", only, GATE)
    ship(w, only, "release: v1.7.0")
    w.chantier("order", "confirm", only, "--note", "again", expect=2)
    check("the user's word is refused while the release PR is not merged",
          "is not merged" in w.last_stderr, w.last_stderr)
    w.chantier("handback", only, "ready", w.cr(only)["pr"])
    w.chantier("order", "merged", only)
    code, out = w.chantier("release", "go", only, "--note", "tag v1.7.0")
    check("after `order merged`, `release go` answers `go`, naming the merged PR",
          code == 0 and out[0].startswith("go:") and "was merged" in out[0], str(out))
    w.reset()


def on_branch(w: World, cr_id: str, base: str) -> None:
    """A Driver's first step for a CR that starts on another CR's branch: the worktree its
    prompt names, on the pushed branch of the CR under it."""
    c = w.cr(cr_id)
    Path(c["worktree"]).parent.mkdir(exist_ok=True)
    w.sh("git", "fetch", "--quiet", "origin")
    w.sh("git", "worktree", "add", "--quiet", "-b", c["branch"], c["worktree"], f"origin/{base}")


def restack(w: World, cr_id: str, under: str) -> None:
    """The stack driver restacks a PR: rebase onto the CR under it, push with a lease, `ship`."""
    c = w.cr(cr_id)
    wt = Path(c["worktree"])
    w.sh("git", "fetch", "--quiet", "origin", cwd=wt)
    w.sh("git", "rebase", "--quiet", f"origin/{w.cr(under)['branch']}", cwd=wt)
    w.sh("git", "push", "--quiet", "--force-with-lease", "-u", "origin", c["branch"], cwd=wt)
    forge_base(w, c["pr"], w.cr(under)["branch"])  # the PR sits on the branch of the CR under it
    w.chantier("ship", cr_id, c["pr"])


def settle(w: World) -> None:
    """The Foreman marks each order the CLI applied as done."""
    for o in w.batch()["orders"]:
        if not o["done"]:
            w.chantier("order", "done", o["id"], "--epoch", 1)


def release_on_stack(w: World) -> None:
    note("\n## 14d. A release on top of a stack: prepared on the top CR's branch, merged last")
    w.reset()
    items = [prepare_cr(w, t)[1] for t in ("Stack piece a", "Stack piece b", "Release v1.8.0")]
    w.start(*map(str, items), "--mode", "stack", "--release", 3, *FROM_AGENTS_MD)
    w.env["CHANTIER_BATCH"] = w.name
    w.chantier("foreman", "set", "local_foreman9", "--epoch", 1)
    fm = Foreman(w, epoch=1)
    a, b, r = (c["id"] for c in w.batch()["crs"])
    fm.turn()
    code, out = w.chantier("take", r, "--epoch", 1, expect=2)
    refusal = w.last_stderr
    _, status = w.chantier("status")
    check("1. a stack's release is refused while the CRs under it are queued or working, "
          "each named; status shows no confirmation",
          fm.started == [a, b] and code == 2 and a in refusal and b in refusal
          and "ready or merged" in refusal and not any("confirmation" in ln for ln in status),
          refusal)
    for i, cr in enumerate((a, b)):
        driver_round(w, cr, f"piece{i}.py", f"N = {i}\n")
        w.ready(cr, w.cr(cr)["pr"])
    head = w.cr(a)["head"]
    code, _ = w.chantier("take", r, "--epoch", 1, expect=2)
    check("2. both CRs ready but not stacked: the release is refused, naming the head of the "
          "CR the top branch does not hold, and `take stack`",
          code == 2 and head[:7] in w.last_stderr and "take stack" in w.last_stderr
          and a in w.last_stderr, w.last_stderr)
    code, _ = w.chantier("stack", r, a, b, expect=None)
    check("4. `stack` refuses an order that puts a CR above the release",
          code != 0 and "cannot sit below" in w.last_stderr and r in w.last_stderr, w.last_stderr)
    w.chantier("stack", a, b, r)
    restack(w, b, a)
    _, listed = w.chantier("take", "stack", "--epoch", 1)
    w.chantier("agents", "set", "stack", "-", "--epoch", 1)
    top = w.cr(b)["branch"]
    rows = stack_take_rows(listed)
    check("3. once stacked, `take stack` lists the release last, with the top CR's branch "
          "as its base",
          listed[0].endswith(f"{a} → {b} → {r}") and rows[-1].startswith(f"{r} queued")
          and f"base {top}" in rows[-1], str(listed))
    on_branch(w, r, top)
    code = fm.take(r)
    check("3. the release is taken, and its facts print `base` = the top CR's branch",
          code == 0 and any(f"base {top}" in ln for ln in fm.facts), str(fm.facts))

    tag = "tag v1.8.0"
    w.chantier("order", "approve", r, "--note", tag)
    w.chantier("order", "grant", r, "--note", "releases=1 budget=5")
    code, out = w.chantier("release", "go", r, "--note", tag, expect=2)
    check("5. `release go` is refused while CRs are open, with an approval and a grant: the "
          "`merge` text names them",
          code == 2 and out[0].startswith("no: ") and a in out[0] and b in out[0]
          and "not merged" in out[0], str(out))
    w.chantier("order", "grant", r, "--note", "releases=0 fixes=off budget=5")
    settle(w)

    w.chantier("release", "start", r)
    commit(w, r, "VERSION", "1.8.0\n", "release: v1.8.0")
    w.chantier("gate", r, GATE)
    wt = Path(w.cr(r)["worktree"])
    w.sh("git", "push", "--quiet", "--force-with-lease", "-u", "origin", w.cr(r)["branch"], cwd=wt)
    (w.at(w.cr(r)["path"]) / "work").mkdir(exist_ok=True)
    (w.at(w.cr(r)["path"]) / "work" / "pr-body.md").write_text(BODY.format(title=w.cr(r)["title"], cr=r))
    pr = open_pr(w, r, "release: v1.8.0", base=top)
    OPENED[r] = pr
    _, out = w.chantier("ship", r, pr)
    code, out = w.chantier("handback", r, "ready", f"{pr} draft on {top}: waits for the merge")
    events = [json.loads(e) for e in (w.folder() / "events.jsonl").read_text().splitlines()]
    check("6. the release PR is shipped on the top CR's branch and handed back `ready`, with "
          "no verdict; its STATUS icon is not red",
          code == 0 and [e["base"] for e in events if e["kind"] == "ship" and e["cr"] == r][-1] == top
          and w.cr(r)["status"] == "ready" and "waits for its merge" in out[-1]
          and not any(e["kind"] == "verdict" and e["cr"] == r for e in events)
          and not any("🔴" in lb for lb in drawn(w, r)[0]), str(out))
    extra = prepare_cr(w, "Late piece")[1]
    fixed = prepare_cr(w, "Urgent fix")[1]
    w.chantier("order", "add", "--note", str(extra), expect=2)
    check("7. `order add` is refused once the release has started",
          "has started" in w.last_stderr and "--fix-for" in w.last_stderr, w.last_stderr)
    w.chantier("order", "add", "--note", str(fixed), "--fix-for", r)
    fix = w.batch()["crs"][-1]["id"]
    check("7. `order add --fix-for` is accepted", w.cr(fix)["kind"] == "fix" and w.cr(fix)["fix_for"] == r)
    w.chantier("order", "drop", fix, "--note", "trash")
    w.chantier("order", "merged", r, expect=2)
    check("8. `order merged` on the release is refused while a CR is open: it merges last",
          a in w.last_stderr and "merges last" in w.last_stderr, w.last_stderr)
    w.chantier("order", "confirm", r, "--note", "go", expect=2)
    check("8. the user's word is refused while the CRs are open",
          a in w.last_stderr and "not merged yet" in w.last_stderr, w.last_stderr)

    # a change of content: CR a gets a new round after the release PR is prepared
    settle(w)
    check("11. CR a goes back for a round", fm.take(a, "round: a change of content") == 0)
    w.chantier("agents", "set", r, "-", "--epoch", 1)
    code, _ = w.chantier("take", r, "--note", "redo: a changed", "--epoch", 1, expect=2)
    check("11. the release is refused while CR a is not ready", code == 2 and a in w.last_stderr,
          w.last_stderr)
    driver_round(w, a, "piece0.py", "N = 10\n")
    w.ready(a, w.cr(a)["pr"])
    code, _ = w.chantier("take", r, "--note", "redo: a changed", "--epoch", 1, expect=2)
    check("11. ready again but not restacked, it is refused still",
          code == 2 and "take stack" in w.last_stderr, w.last_stderr)
    restack(w, b, a)
    check("11. once restacked, the release is taken back with the `redo` note",
          fm.take(r, "redo: a changed") == 0 and w.cr(r)["status"] == "working")
    w.chantier("release", "start", r)
    check("11. `release start` keeps the PR recorded and counts an attempt",
          w.cr(r)["pr"] == pr and w.cr(r)["attempts"] == 2 and w.cr(r).get("head") is None,
          str(w.cr(r)))
    w.sh("git", "fetch", "--quiet", "origin", cwd=wt)
    w.sh("git", "rebase", "--quiet", f"origin/{top}", cwd=wt)
    w.chantier("gate", r, GATE)
    w.sh("git", "push", "--quiet", "--force-with-lease", "-u", "origin", w.cr(r)["branch"], cwd=wt)
    w.chantier("ship", r, pr)
    w.chantier("handback", r, "ready", f"{pr} draft on {top}: waits for the merge")
    settle(w)

    w.chantier("order", "merged", a)
    w.chantier("order", "merged", b)
    w.chantier("release", "go", r, "--note", tag, expect=2)  # the refusal is checked in `release`
    w.chantier("order", "grant", r, "--note", "releases=1 budget=5")
    code, out = w.chantier("release", "go", r, "--note", tag)
    check("9. under a grant (`releases=1 budget=5`) it answers `go` on the grant's word, and "
          "spends no approval",
          code == 0 and out[0].startswith("go:") and "without asking" in out[0]
          and w.cr(r)["approvals"] == [tag], str(out))
    w.chantier("order", "grant", r, "--note", "releases=0 fixes=off budget=5")
    settle(w)

    # the post-merge word, asked with the merge go: no grant live, the release PR waits
    publish = "publish v1.8.0"
    code, _ = w.chantier("order", "approve", r, "--note", publish, expect=None)
    check("14. a second `order approve` is accepted while the release PR waits for its merge",
          code == 0 and w.cr(r)["approvals"] == [tag, publish], str(w.cr(r)["approvals"]))
    drivers = len(fm.started)
    fm.turn()
    check("14. the Foreman starts no Driver for it: the release stays `ready`, its PR recorded, "
          "the orders done",
          len(fm.started) == drivers and w.cr(r)["status"] == "ready" and w.cr(r)["pr"] == pr
          and all(o["done"] for o in w.batch()["orders"]), str(fm.started))
    code, out = w.chantier("release", "go", r, "--note", f"merge the release PR {pr}", expect=2)
    check("14. with no grant, `release go` still answers `merge`",
          code == 2 and out[0].startswith("no: the release PR"), str(out))
    redo = fm.take(r, "redo: a check")
    w.chantier("release", "start", r)
    _, handoff = w.chantier("handoff", r)
    check("14. a redo before the merge keeps both approvals, which `handoff` still lists",
          redo == 0 and w.cr(r)["approvals"] == [tag, publish]
          and any(f"approvals unused: {tag}; {publish}" in ln for ln in handoff), str(handoff))
    w.sh("git", "fetch", "--quiet", "origin", cwd=wt)
    w.chantier("gate", r, GATE)
    w.sh("git", "push", "--quiet", "--force-with-lease", "-u", "origin", w.cr(r)["branch"], cwd=wt)
    w.chantier("ship", r, pr)
    w.chantier("handback", r, "ready", f"{pr} draft on {top}: waits for the merge")
    settle(w)

    w.chantier("order", "merged", r)
    w.chantier("order", "note", r, "--note", f"wait: {publish}: user, 2026-11-18: 'wait'")
    fm.turn()
    check("14. the Driver started at the merge gets facts that carry both approvals, and "
          "a `wait:` note recorded right after the merge leaves the take reading `merged:`",
          fm.started[-1].startswith(f"{r} merged:")
          and f"approvals unused: {tag}; {publish}" in " ".join(fm.facts)
          and [n.split(":")[0] for n in w.cr(r)["notes"] if n.startswith(("approved:", "wait:"))][-2:]
          == ["approved", "wait"]
          and all(o["done"] for o in w.batch()["orders"]), str(fm.started))
    steps = [w.chantier("release", "go", r, "--note", s)[1][0] for s in ("push the tag", "publish")]
    check("10. `order merged` puts the release back to `queued`, taken by a new Driver; "
          "`release go` answers `go` naming the merged PR for two steps, with no grant",
          fm.started[-1].startswith(f"{r} merged:") and w.cr(r)["status"] == "working"
          and all(s.startswith("go:") and pr in s for s in steps), str(steps))
    # the host refuses the publication; the user publishes by hand and says so
    attempts = w.cr(r)["attempts"]
    cmd = "gh release create v1.8.0 --title v1.8.0 --verify-tag --notes-file notes.md"
    w.chantier("note", r, "steps run: push the tag")
    w.chantier("handback", r, "blocked", f"approval: publish: {cmd}")
    check("10. a publication the host refuses is `blocked approval: publish:`, the batch running",
          w.cr(r)["status"] == "blocked"
          and (w.cr(r)["blocked_reason"] or "").startswith("approval: publish:")
          and w.batch()["status"] != "paused", str(w.cr(r)))
    word = "publication done: user, 2026-11-18: 'publié'"
    code, out = w.chantier("order", "note", r, "--note", word, expect=None)
    check("10. the user's word is accepted and says the CR is blocked until the Foreman takes "
          "it back", code == 0 and any("is blocked" in ln for ln in out), str(out))
    fm.turn()
    check("10. the Foreman took the release back with the note, with no new attempt, and "
          "every order is done",
          fm.started[-1].startswith(f"{r} note: publication done:")
          and w.cr(r)["status"] == "working" and w.cr(r)["attempts"] == attempts
          and all(o["done"] for o in w.batch()["orders"]), str(fm.started))
    w.chantier("release", "published", r, "--note", "v1.8.0 https://forge.example/v1.8.0")
    w.chantier("handback", r, "ready", "https://forge.example/v1.8.0")
    fm.turn()
    check("10. the release `3-done`, the batch pauses",
          "/3-done/" in w.cr(r)["path"] and fm.paused, str(w.cr(r)))

    # 12. a procedure with no release PR
    w.reset()
    items = [prepare_cr(w, t)[1] for t in ("Piece c", "Release v1.9.0")]
    w.start(*map(str, items), "--mode", "stack", "--release", 2, *FROM_AGENTS_MD)
    w.env["CHANTIER_BATCH"] = w.name
    w.chantier("foreman", "set", "local_foreman10", "--epoch", 1)
    fm = Foreman(w, epoch=1)
    c, r = (x["id"] for x in w.batch()["crs"])
    fm.turn()
    driver_round(w, c, "piece_c.py", "N = 0\n")
    w.ready(c, w.cr(c)["pr"])
    on_branch(w, r, w.cr(c)["branch"])
    check("12. the release starts on the only CR's branch once it is ready", fm.take(r) == 0
          and any(f"base {w.cr(c)['branch']}" in ln for ln in fm.facts), str(fm.facts))
    w.chantier("handback", r, "blocked", "waits: the other CRs' merge, then the user's word "
               "to run the release procedure")
    w.chantier("order", "confirm", r, "--note", "yes, run it", expect=2)
    check("12. the user's word is refused before the other CRs' merge", c in w.last_stderr,
          w.last_stderr)
    w.chantier("order", "merged", c)
    w.chantier("order", "confirm", r, "--note", "yes, run it")
    code, out = w.chantier("release", "go", r, "--note", "tag v1.9.0")
    check("12. accepted after: `release go` answers `go` naming the word, and no `confirmed` "
          "field is written", code == 0 and "the user's word" in out[0] and "yes, run it" in out[0]
          and "confirmed" not in w.cr(r) and w.cr(r)["procedure"] == "yes, run it", str(out))

    w.reset()

    # 13. a series
    items = [prepare_cr(w, t)[1] for t in ("Series one", "Series two", "Release v2.0.0")]
    w.start(*map(str, items), "--mode", "series", "--release", 3, *FROM_AGENTS_MD)
    w.env["CHANTIER_BATCH"] = w.name
    w.chantier("foreman", "set", "local_foreman12", "--epoch", 1)
    fm = Foreman(w, epoch=1)
    one, two, r = (x["id"] for x in w.batch()["crs"])
    fm.turn()
    driver_round(w, one, "series1.py", "S = 1\n")
    w.ready(one, w.cr(one)["pr"])
    on_branch(w, two, w.cr(one)["branch"])
    fm.turn()
    code, _ = w.chantier("take", r, "--epoch", 1, expect=2)
    refused = code == 2 and two in w.last_stderr
    driver_round(w, two, "series2.py", "S = 2\n", base=w.cr(one)["branch"])
    w.ready(two, w.cr(two)["pr"])
    on_branch(w, r, w.cr(two)["branch"])
    check("13. in a series, the release waits for the CRs, then starts on the second CR's branch",
          refused and fm.take(r) == 0
          and any(f"base {w.cr(two)['branch']}" in ln for ln in fm.facts), str(fm.facts))
    w.reset()
    w.env.pop("CHANTIER_BATCH", None)


def qa_on_head(w: World) -> None:
    note("\n## 14c. QA on the project's head, on the user's word, during the batch")
    _, item = prepare_cr(w, "Waits for its merge")
    w.reset()
    w.start(str(item), *FROM_AGENTS_MD)
    w.env["CHANTIER_BATCH"] = w.name
    w.chantier("foreman", "set", "local_foreman6", "--epoch", 1)
    fm = Foreman(w, epoch=1)
    cr = w.batch()["crs"][0]["id"]
    # the QA refusals (no request, a spent budget, a QA folder to open) are pytest's
    # (test_rail_refusals.py); the batch's budget is lifted for the QA below
    inbox = w.work / ".agents/changes/1-inbox"
    before = (sorted(p.name for p in inbox.glob("qa-*")), len(w.batch()["orders"]))
    w.chantier("order", "budget", "--note", "10")
    _, out = w.chantier("order", "qa", "--note", "try the export on a phone")
    check("a raised budget lets `order qa` through", len(w.batch()["orders"]) == before[1] + 2
          and len(list(inbox.glob("qa-*"))) == len(before[0]) + 1, str(out))
    shown = out[1].removeprefix("QA folder: ").split(";")[0]
    folder = w.work / shown
    check("`order qa` makes its work folder in the inbox, with the request, and names it",
          out[0] == f"[chief-of-staff→foreman] order O-2: qa {shown} try the export on a phone"
          and "/1-inbox/qa-" in folder.as_posix()
          and "phone" in (folder / "intake/request.md").read_text(encoding="utf-8"), str(out))
    qa_prompt = prompt_block(out, "qa-driver")
    check(
        "`order qa` prints the qa-driver prompt after its `QA folder:` line, with no `writes:` line",
        bool(qa_prompt)
        and out.index(qa_prompt[0]) > 1
        and not any(ln.startswith("  writes:") for ln in qa_prompt)
        and f"  QA folder: {shown}; order O-2" in qa_prompt,
        str(out),
    )
    fm.turn()
    check("the Foreman starts a QA driver on the folder, and the CR goes on without it",
          fm.qa == [shown] and fm.started == [cr] and w.cr(cr)["status"] == "working",
          str(fm.qa))
    code, _ = w.chantier("agents", "set", "O-2", "agent-qa", "--epoch", 1)
    check("`agents set O-<k>` maps a QA order to its agent", code == 0, w.last_stderr)
    _, out = w.chantier("status")
    check("`status` shows the QA order and its folder until it is done",
          any(ln.startswith(f"orders pending: O-2 qa {shown}") for ln in out), str(out))
    drop_then_cancel(w, cr, 1)
    code, _ = w.chantier("pause", "--epoch", 1, expect=2)
    check("a batch does not pause under a running QA", code == 2 and "O-2" in w.last_stderr,
          w.last_stderr)
    (folder / "04-result.md").write_text("# QA\n\n- The export button is hidden on mobile\n")
    w.chantier("order", "done", "O-2", "--epoch", 1)
    w.reset()
    check("its findings stay in the inbox, an ordinary item",
          (folder / "04-result.md").is_file())
    w.chantier("abandon", folder)


def changes_tree(w: World) -> None:
    note("\n## 14e. The changes tree: 3-ready, and the folder follows the status")
    w.reset()
    first = lambda out, word: w.work / out[0].removeprefix(word).split(";", 1)[0].rsplit(" (", 1)[0]  # noqa: E731
    _, spec = prepare_cr(w, "Tree with spec")
    _, out = w.chantier("file", "Tree without spec")
    bare = first(out, "filed ")
    ready_spec = first(w.chantier("triage", spec, "--ready")[1], "triaged ")
    ready_bare = first(w.chantier("triage", bare, "--ready")[1], "triaged ")
    # the triage moves and refusals are pytest's: test_triage_moves.py
    _, out = w.start(ready_spec, ready_bare, "--slots", 2, *FROM_AGENTS_MD)
    w.env["CHANTIER_BATCH"] = w.name
    d = w.batch()
    one, two = d["crs"]
    check("`open` takes both 3-ready items into 1-pending; the one with no specification records "
          "the request as its specification",
          all("4-batch/1-pending/" in c["path"] for c in d["crs"])
          and one["specification"] == "03-change-spec.md"
          and two["specification"] == "intake/request.md" and two["title"].startswith("Tree without")
          and not ready_spec.exists() and not ready_bare.exists(), str(d["crs"]))
    w.chantier("foreman", "set", "local_foreman_tree", "--epoch", 1)
    fm = Foreman(w, epoch=1)
    fm.take(two["id"])
    check("`take` moves the folder to 2-actives and shows the request as the specification",
          "4-batch/2-actives/" in w.cr(two["id"])["path"]
          and (w.state / w.cr(two["id"])["path"] / "intake/request.md").is_file()
          and any("intake/request.md" in ln for ln in fm.facts), str(fm.facts))
    fm.take(one["id"])
    driver_round(w, one["id"], "tree.py", "N = 1\n")
    w.ready(one["id"], w.cr(one["id"])["pr"])
    w.chantier("handback", two["id"], "blocked", "question: which one")
    check("the folder stays in 2-actives after `handback`, ready or blocked",
          all("4-batch/2-actives/" in w.cr(c["id"])["path"] for c in (one, two))
          and w.cr(one["id"])["status"] == "ready" and w.cr(two["id"])["status"] == "blocked")
    w.chantier("order", "merged", one["id"])
    done = w.state / w.cr(one["id"])["path"]
    check("`order merged` moves the folder to 3-done and records the merge time",
          done.parent == w.state / "4-batch" / "3-done" and done.is_dir()
          and w.cr(one["id"]).get("merged_at"), w.cr(one["id"])["path"])
    w.chantier("order", "drop", two["id"], "--note", "trash")
    dropped = w.state / w.cr(two["id"])["path"]
    check("`order drop` moves the folder to 6-trash at once",
          dropped.parent == w.state / "6-trash" and dropped.is_dir(), w.cr(two["id"])["path"])
    fm.turn()
    priced_foreman(w)
    age_sessions(w)
    clear_agents(w)
    stray = w.state / "4-batch" / "2-actives" / "stray"
    stray.mkdir()
    code, _ = w.chantier("close", "--batch", w.name, "--yes", expect=2)
    check("`close --yes` is refused while 2-actives holds a CR, and deletes nothing",
          code == 2 and "2-actives/stray" in w.last_stderr
          and (w.state / "4-batch/batch.json").is_file() and done.is_dir(), w.last_stderr)
    stray.rmdir()
    w.chantier("close", "--batch", w.name, "--yes")
    archived = [p for p in (w.state / "5-archives").iterdir() if p.name.endswith(f"-{done.name}")]
    page = (archived[0] / "STATUS.md").read_text(encoding="utf-8") if archived else ""
    check("`close` archives the 3-done CR as <merge time>-<number>-<slug>, its page saying the "
          "cost is final; the state folders stay, empty",
          len(archived) == 1 and re.fullmatch(r"\d{6}-\d{4}-" + re.escape(done.name), archived[0].name)
          and "so far" not in page and not done.exists()
          and sorted(p.name for p in (w.state / "4-batch").iterdir()) ==
          ["1-pending", "2-actives", "3-done"], str(archived))
    w.env.pop("CHANTIER_BATCH", None)


def depends_on(item: Path, *slugs: str, raw: str | None = None) -> None:
    """The Chief of Staff's `depends.json`, in the CR's folder."""
    (item / "depends.json").write_text(raw if raw is not None else json.dumps({"after": list(slugs)}),
                                       encoding="utf-8")


def drawn(w: World, cr: str) -> tuple[set[str], dict]:
    """The label of a CR in every record that lists it (the batch's STATUS.md and STATUS.json,
    the index where it is active, the CR's own pair), and the CR's own STATUS.json."""
    own_dir = w.state / w.cr(cr)["path"]
    own = json.loads((own_dir / "STATUS.json").read_text(encoding="utf-8"))
    batch = json.loads((w.folder() / "STATUS.json").read_text(encoding="utf-8"))
    index = json.loads((w.state / "STATUS.json").read_text(encoding="utf-8"))
    labels = {own["label"]} | {r["label"] for r in batch["crs"] if r["cr"] == cr}
    labels |= {r["label"] for b in index["batches"] for r in b["crs"] if r["cr"] == cr}
    texts = [(w.folder() / "STATUS.md").read_text(encoding="utf-8"),
             (own_dir / "STATUS.md").read_text(encoding="utf-8")]
    return {lb for lb in labels if all(lb in t for t in texts)} | {
        "MISSING " + lb for lb in labels if not all(lb in t for t in texts)}, own


def icon_is(w: World, cr: str, icon: str, what: str) -> dict:
    labels, own = drawn(w, cr)
    check(f"{what}: {icon} in STATUS.md and STATUS.json, at every level",
          len(labels) == 1 and next(iter(labels)).startswith(icon + " "), str(labels))
    return own


def ready_words_unplaced(w: World) -> None:
    note("\n## 13b. A ready CR the stack driver has not placed reads its word from its PR's base")

    def edit_cr(cr: str, drop: tuple[str, ...] = (), **fields: object) -> None:
        d = w.batch()
        c = next(x for x in d["crs"] if x["id"] == cr)
        c.update(fields)
        for key in drop:
            c.pop(key, None)
        (w.folder() / "batch.json").write_text(json.dumps(d, indent=2))

    def ready_of(cr: str) -> str | None:
        return drawn(w, cr)[1].get("readiness")

    def batch_readiness(cr: str) -> str | None:
        board = json.loads((w.folder() / "STATUS.json").read_text(encoding="utf-8"))
        return next(r.get("readiness") for r in board["crs"] if r["cr"] == cr)

    w.reset()
    items = [prepare_cr(w, t)[1] for t in ("Unplaced a", "Unplaced b", "Unplaced c")]
    w.start(*map(str, items), "--mode", "stack", *FROM_AGENTS_MD)
    w.env["CHANTIER_BATCH"] = w.name
    w.chantier("foreman", "set", "local_foreman_unplaced", "--epoch", 1)
    Foreman(w, epoch=1).turn()  # no `stack <cr>...` call in this batch
    a, b, c = (x["id"] for x in w.batch()["crs"])
    driver_round(w, b, "unplaced_b.py", "N = 1\n")
    driver_round(w, c, "unplaced_c.py", "N = 2\n")
    bpr, cpr = w.cr(b)["pr"], w.cr(c)["pr"]
    _, out = w.ready(b, bpr)
    check("6. a working CR with no PR before it, b shipped out of draft on the default branch and "
          "handed back: `ready to merge`, in the hand-back line, `readiness` and the label",
          out[0].startswith(f"[driver {b}→foreman] hand-back ready to merge")
          and ready_of(b) == "ready to merge" == batch_readiness(b)
          and drawn(w, b)[1]["label"].startswith("🟢 "), str(out))
    forge_draft(w, cpr, True)
    w.chantier("ship", c, cpr)
    _, out = w.ready(c, cpr)
    check("7. c shipped as a draft on the default branch: `PR in draft`, it waits for its turn "
          "out of draft, not for a CR of the order",
          out[0].startswith(f"[driver {c}→foreman] hand-back PR in draft")
          and out[1].endswith("a draft on the forge; it waits for its turn out of draft")
          and drawn(w, c)[1]["label"].endswith("waits for its turn out of draft")
          and ready_of(c) == "PR in draft", str(out))
    forge_draft(w, cpr, False)
    forge_base(w, cpr, w.cr(b)["branch"])
    w.chantier("ship", c, cpr)
    w.chantier("note", c, "redraw")
    check("8. c's PR on b's branch, out of draft, shipped: `ready to merge` while b is",
          ready_of(c) == "ready to merge", str(drawn(w, c)[1]))
    forge_draft(w, bpr, True)
    w.chantier("ship", b, bpr)
    w.chantier("note", c, "redraw")
    check("8. b turned back to a draft and shipped: c reads `PR in draft` and waits on b",
          ready_of(c) == "PR in draft" and f"waits for {b}" in drawn(w, c)[1]["label"],
          str(drawn(w, c)[1]))
    forge_draft(w, bpr, False)
    w.chantier("ship", b, bpr)
    edit_cr(c, drop=("pr_base",))  # an old record: no base recorded
    w.chantier("note", c, "redraw")
    check("9. c with `pr_base` dropped (an old record): today's rule, `PR in draft`, it waits on a",
          ready_of(c) == "PR in draft" and f"waits for {a}" in drawn(w, c)[1]["label"],
          str(drawn(w, c)[1]))
    code, out = w.chantier("stack", a, b, c, expect=None)
    check("10. `stack a b c` places the three: the chain's rule again, b and c `PR in draft` over a",
          code == 0 and ready_of(b) == "PR in draft" and ready_of(c) == "PR in draft",
          f"{code} {out} {ready_of(b)} {ready_of(c)}")
    for cr in (b, c):  # PR links repeat from batch to batch: leave the fake forge clean
        forge_draft(w, w.cr(cr)["pr"], False)
        forge_base(w, w.cr(cr)["pr"], "main")
    w.reset()
    w.env.pop("CHANTIER_BATCH", None)


def stack_hold(w: World) -> None:
    note("\n## 13b. `order hold`: a ready CR held out of the stack, on the forge and in the record")
    w.reset()
    items = [prepare_cr(w, t)[1] for t in ("Hold piece a", "Hold piece b", "Hold piece c")]
    w.start(*(str(x) for x in items), "--mode", "stack", *FROM_AGENTS_MD)
    w.env["CHANTIER_BATCH"] = w.name
    a, b, c = (x["id"] for x in w.batch()["crs"])
    path_key = next(k for k in w.env if k.upper() == "PATH")
    on_path = {path_key: f"{w.fake.parent}{os.pathsep}{w.env[path_key]}"}
    num = {a: 201, b: 202, c: 203}
    branch = lambda cr: w.cr(cr)["branch"]  # noqa: E731
    gh_state = lambda: json.loads(w.gh_state.read_text())  # noqa: E731

    def edit_cr(cr: str, **fields: object) -> None:
        d = w.batch()
        next(x for x in d["crs"] if x["id"] == cr).update(fields)
        (w.folder() / "batch.json").write_text(json.dumps(d, indent=2))

    for cr in (a, b, c):
        edit_cr(cr, pr=PR_LINK["github"] + str(num[cr]), status="ready", pr_draft=False,
                head=hashlib.sha1(cr.encode()).hexdigest())
    w.chantier("stack", a, b, c)
    w.chantier("foreman", "set", "local_foreman_hold", "--epoch", 1)
    w.gh(next_stack=200, heads={str(n): branch(cr) for cr, n in num.items()},
         stacks=[{"number": 100, "open": True, "pull_requests": [201, 202, 203]}])
    forge_base(w, PR_LINK["github"] + "202", branch(a))
    forge_base(w, PR_LINK["github"] + "203", branch(b))
    for cr, base in ((b, branch(a)), (c, branch(b))):
        edit_cr(cr, pr_base=base)

    code, out = w.chantier("order", "hold", c)
    check("`order hold` of the top ready CR is recorded at once (`applied`), prints the way back, and "
          "`stack` leaves it out of the rows and prints the `held:` line",
          code == 0 and any(x.startswith(f"{c} held out of the stack (order O-1)") for x in out)
          and w.batch()["orders"][-1]["applied"] is True
          and w.cr(c)["held"] == "O-1" and not w.cr(c)["stacked"], str(out))
    _, rows = w.chantier("stack")
    check("`stack` with no CR: the chain without the held CR, and `held: <cr> (order O-1) out of the "
          "stack, PR <link> on main`",
          rows[0].endswith(f"{a} → {b}") and not any(x.startswith(f"{c} ") for x in rows)
          and any(x.startswith(f"held: {c} (order O-1) out of the stack, PR {PR_LINK['github']}203 "
                               f"on main") for x in rows), str(rows))
    w.chantier("take", "stack", "--note", f"hold {c}", "--epoch", 1, expect=0)
    # the stack driver: the held PR to draft (`gh pr ready --undo`), the record told, then rebuild
    w.gh(drafts=[203])
    w.chantier("stack", "--draft", c)
    code, out = w.chantier("forge-stack", "rebuild", env=on_path)
    state = gh_state()
    top = next((x for x in reversed(state["stacks"]) if x["open"]), {})
    check("`forge-stack rebuild` with a held PR: unstacks, retargets the held PR to the default branch "
          "(a line naming the hold), stacks the other CRs' PRs only, and the held PR stays a draft",
          code == 0 and f"#203 base {branch(b)} -> main (held out of the stack)" in out
          and any("held out of the stack: left out" in x for x in out)
          and top.get("pull_requests") == [201, 202] and state["bases"]["203"] == "main"
          and 203 in state.get("drafts", []), f"{out} {top}")
    _, out = w.chantier("status")
    check("`status` prints the `held:` line after a rebuild", any(x.startswith(f"held: {c} ") for x in out),
          str(out))
    w.chantier("take", c, "--note", "again", "--epoch", 1, expect=2)
    check("`take` of a held CR is refused naming `order unhold`",
          f"only the user's `order unhold {c}` releases it" in w.last_stderr, w.last_stderr)

    w.chantier("order", "unhold", c)
    w.chantier("agents", "set", "stack", "-", "--epoch", 1)
    w.chantier("take", "stack", "--note", f"unhold {c}", "--epoch", 1)
    forge_base(w, PR_LINK["github"] + "203", branch(b))
    edit_cr(c, pr_base=branch(b))
    code, out = w.chantier("forge-stack", "rebuild", env=on_path)
    top = next((x for x in reversed(gh_state()["stacks"]) if x["open"]), {})
    _, rows = w.chantier("stack")
    check("`order unhold` and a take: the CR is back on top of the stack on the forge and in `stack`, "
          "with no `held:` line",
          code == 0 and top.get("pull_requests") == [201, 202, 203]
          and rows[0].endswith(f"{a} → {b} → {c}") and "held" not in w.cr(c)
          and not any(x.startswith("held:") for x in rows), f"{out} {rows}")


def park_live(w: World) -> None:
    note("\n## 13b. `park`: a working CR on an outside wait leaves the slots and the stack, and `take` brings it back")
    w.reset()
    items = [prepare_cr(w, t)[1] for t in ("Park piece a", "Park piece b", "Park piece c")]
    w.start(*(str(x) for x in items), "--mode", "stack", *FROM_AGENTS_MD)
    w.env["CHANTIER_BATCH"] = w.name
    a, b, c = (x["id"] for x in w.batch()["crs"])
    path_key = next(k for k in w.env if k.upper() == "PATH")
    on_path = {path_key: f"{w.fake.parent}{os.pathsep}{w.env[path_key]}"}
    num = {a: 211, b: 212, c: 213}
    branch = lambda cr: w.cr(cr)["branch"]  # noqa: E731
    gh_state = lambda: json.loads(w.gh_state.read_text())  # noqa: E731

    def edit_cr(cr: str, **fields: object) -> None:
        d = w.batch()
        next(x for x in d["crs"] if x["id"] == cr).update(fields)
        (w.folder() / "batch.json").write_text(json.dumps(d, indent=2))

    for cr in (a, b, c):
        edit_cr(cr, pr=PR_LINK["github"] + str(num[cr]), status="ready", pr_draft=False,
                head=hashlib.sha1(cr.encode()).hexdigest())
    w.chantier("stack", a, b, c)
    w.chantier("foreman", "set", "local_foreman_park", "--epoch", 1)
    w.gh(next_stack=200, heads={str(n): branch(cr) for cr, n in num.items()},
         stacks=[{"number": 100, "open": True, "pull_requests": [211, 212, 213]}])
    forge_base(w, PR_LINK["github"] + "212", branch(a))
    forge_base(w, PR_LINK["github"] + "213", branch(b))
    for cr, base in ((b, branch(a)), (c, branch(b))):
        edit_cr(cr, pr_base=base)
    edit_cr(b, status="working")  # its Driver says it waits on the user's trial

    code, out = w.chantier("park", b, "--wait", "answer=does the trial pass?", "--epoch", 1)
    check("`park` of a working CR on an outside wait: one `parked` line naming the wait, the stack "
          "driver's take, the CR `blocked` with `parked` set and out of the stack",
          code == 0 and out[0].startswith(f"parked {b}: waits for w1 answer")
          and any(x.startswith("stack: `take stack") for x in out)
          and w.cr(b)["status"] == "blocked" and w.cr(b).get("parked")
          and not w.cr(b)["stacked"], str(out))
    _, rows = w.chantier("stack")
    check("`stack` leaves the parked CR out of its rows",
          not any(x.startswith(f"{b} ") for x in rows), str(rows))
    _, out = w.chantier("status")
    check("`status` prints the `parked:` line with the wait and the way out of the stack",
          any(x.startswith(f"parked: {b} since ") and "the stack" in x for x in out), str(out))
    w.chantier("take", b, "--note", "back", "--epoch", 1, expect=2)
    check("`take` of a parked CR with its wait open is refused, naming `wait <cr> clear`",
          f"`wait {b} clear w1 --epoch <n>` first" in w.last_stderr, w.last_stderr)
    w.chantier("take", "stack", "--note", f"park: {b}", "--epoch", 1, expect=0)
    w.gh(drafts=[212])
    code, out = w.chantier("forge-stack", "rebuild", env=on_path)
    state = gh_state()
    top = next((x for x in reversed(state["stacks"]) if x["open"]), {})
    check("`forge-stack rebuild` leaves the parked PR out, on the default branch, and names it parked",
          code == 0 and any("parked out of the stack" in x for x in out)
          and top.get("pull_requests") == [211, 213], f"{out} {top}")

    w.chantier("wait", b, "clear", "w1", "--epoch", 1, expect=0)
    _, out = w.chantier("status")
    check("with its wait cleared, `status` says to take it back before any queued CR",
          any(x.startswith(f"parked: {b} wait cleared") for x in out), str(out))
    top_order = max(x["order"] for x in w.batch()["crs"])
    code, out = w.chantier("take", b, "--note", "wait cleared: the trial passed", "--epoch", 1)
    check("`take` of the cleared parked CR gives it a new Driver, back on top of the stack",
          code == 0 and "back on top of the stack" in out[0] and not w.cr(b).get("parked")
          and w.cr(b)["order"] == top_order + 1 and w.cr(b)["status"] == "working", str(out))


def hold_live(w: World) -> None:
    note("\n## 13c. `order hold` of a live CR: out of the slots, in the stack and in a parallel batch")
    w.reset()
    items = [prepare_cr(w, f"Live hold {t}")[1] for t in ("a", "b", "c", "release")]
    w.start(*(str(x) for x in items), "--mode", "stack", "--slots", 2, *FROM_AGENTS_MD)
    w.env["CHANTIER_BATCH"] = w.name
    a, b, c, rel = (x["id"] for x in w.batch()["crs"])
    path_key = next(k for k in w.env if k.upper() == "PATH")
    on_path = {path_key: f"{w.fake.parent}{os.pathsep}{w.env[path_key]}"}
    num = {a: 201, b: 202, c: 203}
    branch = lambda cr: w.cr(cr)["branch"]  # noqa: E731
    gh_state = lambda: json.loads(w.gh_state.read_text())  # noqa: E731

    def edit_cr(cr: str, **fields: object) -> None:
        d = w.batch()
        next(x for x in d["crs"] if x["id"] == cr).update(fields)
        (w.folder() / "batch.json").write_text(json.dumps(d, indent=2))

    edit_cr(rel, kind="release")
    w.chantier("foreman", "set", "local_foreman_hl", "--epoch", 1)
    # 1. a stack of three CRs, two slots: the first two are taken
    w.chantier("take", a, "--epoch", 1)
    w.chantier("take", b, "--epoch", 1)
    w.chantier("agents", "set", b, "agent-b", "--epoch", 1)
    old = w.leases[unit_name(b)]
    code, _ = w.chantier("take", c, "--epoch", 1, expect=None)
    check("a stack of two slots, both held: the third CR is not taken", code != 0
          and "no free slot" in w.last_stderr, w.last_stderr)

    # 2. the hold of the second, working: its slot is free, its old lease is lost
    code, out = w.chantier("order", "hold", b)
    check("`order hold` of a working CR: blocked, held, its order pending until `order done`, the line "
          "names the Foreman's steps",
          code == 0 and w.cr(b)["status"] == "blocked" and w.cr(b)["held"] == "O-1"
          and w.cr(b)["blocked_reason"] == "held: order O-1" and w.batch()["orders"][-1]["applied"] is False
          and any(x.startswith(f"{b} held (order O-1): it was live; its slot is free") for x in out), str(out))
    w.chantier("note", b, "late", "--lease", old, lease=False, expect=3)
    check("the old Driver's next leased command is `claim lost`", "claim lost" in w.last_stderr,
          w.last_stderr)
    w.chantier("agents", "set", b, "-", "--epoch", 1)
    w.chantier("order", "done", "O-1", "--epoch", 1)
    code, _ = w.chantier("take", c, "--epoch", 1, expect=None)
    check("the freed slot goes to the third CR: its `take` is accepted", code == 0 and
          w.cr(c)["status"] == "working", w.last_stderr)

    # 3. the stack driver and the rebuild: the held PR on the default branch, the stack without it
    for cr in (a, c):
        edit_cr(cr, status="ready", pr_draft=False, head=hashlib.sha1(cr.encode()).hexdigest())
    for cr in (a, b, c):
        edit_cr(cr, pr=PR_LINK["github"] + str(num[cr]))
    w.chantier("stack", a, c)
    w.gh(next_stack=200, heads={str(n): branch(cr) for cr, n in num.items()},
         stacks=[{"number": 100, "open": True, "pull_requests": [201, 202, 203]}])
    forge_base(w, PR_LINK["github"] + "202", branch(a))
    forge_base(w, PR_LINK["github"] + "203", branch(b))
    edit_cr(b, pr_base=branch(a))
    edit_cr(c, pr_base=branch(b))
    w.chantier("take", "stack", "--note", f"hold {b}", "--epoch", 1, expect=0)
    w.gh(drafts=[202])
    w.chantier("stack", "--draft", b)
    code, out = w.chantier("forge-stack", "rebuild", env=on_path)
    state = gh_state()
    top = next((x for x in reversed(state["stacks"]) if x["open"]), {})
    check("`forge-stack rebuild` with a held live CR's PR: it goes to the default branch, the stack "
          "is the others' PRs only, the base of the CR above it follows",
          code == 0 and top.get("pull_requests") == [201, 203] and state["bases"]["202"] == "main"
          and state["bases"]["203"] == branch(a), f"{out} {top}")
    w.chantier("agents", "set", "stack", "-", "--epoch", 1)

    # 4. no release over a held CR
    w.chantier("take", rel, "--epoch", 1, expect=2)
    check("`take <release>` is refused naming the held CR", f"waits for {b} held (order O-1)" in
          w.last_stderr and f"`order unhold {b}`" in w.last_stderr, w.last_stderr)

    # 5. the unhold: taken back as a working CR, then it hands back ready and the batch merges
    spent = w.cr(b).get("round", 0)
    w.chantier("order", "unhold", b)
    code, out = w.chantier("take", b, "--note", "unhold: O-2", "--epoch", 1)
    check("`take --note \"unhold: ...\"` turns the CR working again, on top, with no round counted",
          code == 0 and w.cr(b)["status"] == "working" and w.cr(b).get("round", 0) == spent
          and w.cr(b)["order"] > max(w.cr(x)["order"] for x in (a, c)), str(out))
    edit_cr(b, status="ready", pr_draft=False, head=hashlib.sha1(b.encode()).hexdigest())
    w.chantier("stack", a, c, b)
    for cr in (a, c, b):
        w.chantier("order", "merged", cr, "--epoch", 1)
    check("the CR handed back ready is merged with the others, no `held:` line left",
          all(w.cr(x)["status"] == "merged" for x in (a, b, c))
          and not any(x.startswith("held:") for x in w.chantier("status")[1]), "merged")

    # 6. a parallel batch: the same hold frees the slot, the unhold and a take bring it back
    w.reset()
    items = [prepare_cr(w, f"Live hold parallel {t}")[1] for t in ("a", "b")]
    w.start(*(str(x) for x in items), "--mode", "parallel", "--slots", 1, *FROM_AGENTS_MD)
    w.env["CHANTIER_BATCH"] = w.name
    a, b = (x["id"] for x in w.batch()["crs"])
    w.chantier("foreman", "set", "local_foreman_hlp", "--epoch", 1)
    w.chantier("take", a, "--epoch", 1)
    w.chantier("agents", "set", a, "agent-a", "--epoch", 1)
    code, _ = w.chantier("take", b, "--epoch", 1, expect=None)
    check("a parallel batch of one slot, held by the first CR: the second is not taken",
          code != 0 and "no free slot" in w.last_stderr, w.last_stderr)
    w.chantier("order", "hold", a)
    w.chantier("agents", "set", a, "-", "--epoch", 1)
    w.chantier("order", "done", "O-1", "--epoch", 1)
    code, _ = w.chantier("take", b, "--epoch", 1, expect=None)
    check("a parallel hold frees the slot: the other CR is taken", code == 0, w.last_stderr)
    w.chantier("handback", b, "blocked", "scenario stop", expect=0)
    w.chantier("order", "unhold", a)
    code, _ = w.chantier("take", a, "--note", "unhold: O-2", "--epoch", 1, expect=None)
    check("`order unhold` and a take bring the held CR back working in a parallel batch",
          code == 0 and w.cr(a)["status"] == "working" and "held" not in w.cr(a), w.last_stderr)
    w.env.pop("CHANTIER_BATCH", None)


def stack_waiver(w: World) -> None:
    note("\n## 13b. One long gate on the stack's top PR: `order waive stack`")
    w.reset()
    low, mid, top = (prepare_cr(w, t)[1] for t in ("Waive low", "Waive mid", "Waive top"))
    _, joined = prepare_cr(w, "Waive joiner")
    w.start(str(low), str(mid), str(top), "--mode", "stack", *FROM_AGENTS_MD)
    w.env["CHANTIER_BATCH"] = w.name
    w.chantier("foreman", "set", "local_foreman13b", "--epoch", 1)
    Foreman(w, epoch=1).turn()
    one, two, three = (c["id"] for c in w.batch()["crs"])

    def events(kind, cr):
        return [e for e in map(json.loads, (w.folder() / "events.jsonl").read_text("utf-8").splitlines())
                if e["kind"] == kind and e["cr"] == cr]

    def row(cr):
        rows = json.loads((w.folder() / "STATUS.json").read_text("utf-8"))["crs"]
        return next(r for r in rows if r["cr"] == cr)

    def gate_lines(cr):
        return [ln for ln in w.chantier("handoff", cr)[1] if ln.startswith("gate:")]

    for cr, name in ((one, "low.py"), (two, "mid.py"), (three, "top.py")):
        commit(w, cr, name, "CR = 1\n")
        ship(w, cr, f"feat: {name}")
        w.verified(cr)
    code, _ = w.chantier("handback", one, "ready", w.cr(one)["pr"], expect=2)
    check("with no waiver, a lower CR is refused its hand-back without a long gate",
          code == 2 and "no long gate passed" in w.last_stderr and not gate_lines(one), w.last_stderr)
    note_ = "the user: one long gate on the top PR"
    _, out = w.chantier("order", "waive", "stack", "--note", note_)
    check("`order waive stack` records the waiver on each CR of the stack, as the order's id, "
          "its scope and the user's words",
          all(w.cr(c).get("gate_waiver") == {"order": "O-1", "scope": "stack", "note": note_}
              for c in (one, two)) and w.batch()["orders"][-1]["kind"] == "waive", str(out))
    code, _ = w.chantier("order", "waive", two, "--note", "-", expect=2)
    check("the waiver of one CR of a waived stack is not withdrawn alone: the refusal names the "
          "stack's withdrawal", code == 2 and "waive stack --note -" in w.last_stderr, w.last_stderr)
    check("`handoff` prints one `gate:` line: waived and validated by the top for a lower CR, the "
          "stack's validation for the top",
          gate_lines(one) == [f"gate: waived (O-1, stack): run no long gate; validated by {three}"]
          and gate_lines(three)[0].startswith(("gate: this CR's long gate validates the stack (")),
          str(gate_lines(one) + gate_lines(three)))
    _, shown = w.chantier("status")
    status_md = (w.folder() / "STATUS.md").read_text("utf-8")
    pr3 = w.cr(three)["pr"].rsplit("/", 1)[-1]
    words = (f"waived → {three} (#{pr3})", f"validates {one}, {two}")
    check("`status`, `STATUS.md` and `STATUS.json` show `waived → CR-k` for a covered CR and "
          "`validates …` for the top",
          words[0] in "\n".join(shown) and words[1] in "\n".join(shown) and all(x in status_md for x in words)
          and row(one)["gate"]["state"] == "waived" and row(one)["gate"]["validated_by"]["cr"] == three
          and row(three)["gate"]["validates"] == [one, two] and row(three)["gate"]["state"] == "none",
          "\n".join(shown))
    _, out = w.chantier("handback", one, "ready", w.cr(one)["pr"])
    done = events("handback", one)[-1]
    check("a covered CR hands back ready with no long gate and no `--no-gate`: the line says so, "
          "the event records the order and no gate ran",
          w.cr(one)["status"] == "ready" and not events("gate", one)
          and f"long gate waived (O-1): validated by {three}'s gate" in out[0]
          and done.get("gate_waiver") == "O-1" and done.get("waiver_note") == note_,
          str(out))
    code, _ = w.chantier("handback", three, "ready", w.cr(three)["pr"], expect=2)
    check("the top of a waived stack is refused its hand-back without its own long gate",
          code == 2 and "no long gate passed" in w.last_stderr, w.last_stderr)
    w.chantier("order", "add", "--note", str(joined))
    four = w.batch()["crs"][-1]["id"]
    check("an `order add` on top moves the validation to the new CR, which is never covered",
          gate_lines(four)[0].startswith("gate: this CR's long gate validates the stack (")
          and f"validated by {four}" in gate_lines(three)[0]
          and row(four)["gate"]["state"] != "waived",
          str(gate_lines(four)) + str(gate_lines(three)))
    check("the hand-back event of a covered CR keeps working through the move: its gate stays waived",
          row(one)["gate"]["state"] == "waived" and row(one)["gate"]["validated_by"]["cr"] == four,
          str(row(one)["gate"]))
    w.chantier("order", "waive", "stack", "--note", "-")
    code, _ = w.chantier("handback", two, "ready", w.cr(two)["pr"], expect=2)
    check("`order waive stack --note -` makes a lower CR need its long gate again; a CR already "
          "handed back keeps the waiver it was handed back under, with the user's words",
          code == 2 and "no long gate passed" in w.last_stderr and "gate_waiver" not in w.cr(two)
          and not gate_lines(two) and row(one)["gate"]["state"] == "waived"
          and row(one)["gate"]["waiver"] == note_, w.last_stderr)


def ready_words(w: World) -> None:
    note("\n## 13b. Ready locally, PR in draft, ready to merge: a ready CR reads its state")

    def edit_cr(cr: str, drop: tuple[str, ...] = (), **fields: object) -> None:
        d = w.batch()
        c = next(x for x in d["crs"] if x["id"] == cr)
        c.update(fields)
        if fields.get("status") == "working":
            c.pop("lease", None)  # a Driver handed back again holds no lease of the old one
        for key in drop:
            c.pop(key, None)
        (w.folder() / "batch.json").write_text(json.dumps(d, indent=2))

    def ready_of(cr: str) -> str | None:
        return drawn(w, cr)[1].get("readiness")

    def batch_readiness(cr: str) -> str | None:
        board = json.loads((w.folder() / "STATUS.json").read_text(encoding="utf-8"))
        return next(r.get("readiness") for r in board["crs"] if r["cr"] == cr)

    def row(cr: str) -> str:
        return next(ln for ln in w.chantier("status")[1] if ln.startswith(cr + " "))

    # a stack: a out of draft, b in draft, c out of draft above a draft
    w.reset()
    a_item, b_item, c_item = (prepare_cr(w, t)[1] for t in ("Words a", "Words b", "Words c"))
    w.start(str(a_item), str(b_item), str(c_item), "--mode", "stack", *FROM_AGENTS_MD)
    w.env["CHANTIER_BATCH"] = w.name
    w.chantier("foreman", "set", "local_foreman_words", "--epoch", 1)
    fm = Foreman(w, epoch=1)
    a, b, c = (x["id"] for x in w.batch()["crs"])
    fm.turn()
    w.chantier("stack", a, b, c)
    for i, cr in enumerate((a, b, c)):
        driver_round(w, cr, f"words{i}.py", f"N = {i}\n")
    forge_base(w, w.cr(b)["pr"], w.cr(a)["branch"])  # the stack driver put each PR on the one below
    forge_base(w, w.cr(c)["pr"], w.cr(b)["branch"])
    forge_draft(w, w.cr(b)["pr"], True)  # the forge holds b's PR as a draft
    _, out = w.chantier("ship", b, w.cr(b)["pr"])
    check("1. `ship` records the draft state the forge holds: b's draft, a's and c's out of draft",
          "draft)" in out[0] and "out of draft" not in out[0] and w.cr(b)["pr_draft"] is True
          and w.cr(a)["pr_draft"] is False and w.cr(c)["pr_draft"] is False,
          f"{out} {[x.get('pr_draft') for x in w.batch()['crs']]}")
    forge_draft(w, w.cr(b)["pr"], False)
    _, out = w.chantier("ship", b, w.cr(b)["pr"])
    turned_ready = "out of draft" in out[0] and w.cr(b)["pr_draft"] is False
    forge_draft(w, w.cr(b)["pr"], True)
    _, out = w.chantier("ship", b, w.cr(b)["pr"])
    check("1. the forge turns b ready: `ship` records out of draft; back to a draft: it records a draft",
          turned_ready and "out of draft" not in out[0] and w.cr(b)["pr_draft"] is True, str(out))

    _, out = w.ready(a, w.cr(a)["pr"])
    check("2. a CR out of draft at the bottom is handed back `ready to merge`, in the line to the "
          "Foreman and in the state's own line",
          out[0].startswith(f"[driver {a}→foreman] hand-back ready to merge")
          and out[1].startswith(f"{a} ready to merge"), str(out))
    icon_is(w, a, "🟢", "a ready CR out of draft at the bottom")
    check("2. its STATUS files and `status` read `ready to merge`",
          ready_of(a) == "ready to merge" == batch_readiness(a) and "ready to merge" in row(a)
          and "ready to merge" in w.chantier("handoff", a)[1][0], row(a))
    _, out = w.ready(b, w.cr(b)["pr"])
    check("3. a PR in draft is handed back `PR in draft`, naming its draft state and the CR it waits on",
          out[0].startswith(f"[driver {b}→foreman] hand-back PR in draft")
          and out[1].startswith(f"{b} PR in draft: its PR {w.cr(b)['pr']} is a draft on the forge; "
                                f"it waits on {a} ({w.cr(a)['pr']})"), str(out))
    own = icon_is(w, b, "🟤", "a ready CR whose PR is a draft")
    check("3. its label and `readiness` read `PR in draft`, held by the CR it sits on",
          own["readiness"] == "PR in draft" == batch_readiness(b)
          and f"PR in draft, waits for {a}" in own["label"], str(own))
    _, out = w.ready(c, w.cr(c)["pr"])
    check("4. a PR out of draft over a draft reads `PR in draft` too, and waits for the CR under it",
          out[0].startswith(f"[driver {c}→foreman] hand-back PR in draft")
          and f"its PR {w.cr(c)['pr']} is out of draft on the forge; it waits on {b} ({w.cr(b)['pr']})"
          in out[1] and f"waits for {b}" in drawn(w, c)[1]["label"], str(out))
    icon_is(w, c, "🟤", "a PR out of draft over a draft")
    # run 1: c out of draft, the forge's base still `main`, b not out of draft: the line names b
    cpr, bpr = w.cr(c)["pr"], w.cr(b)["pr"]
    forge_base(w, cpr, "main")
    w.chantier("ship", c, cpr)
    edit_cr(c, status="working")  # handed back again, the record as a Driver leaves it
    _, out = w.ready(c, cpr)
    check("4. a stacked PR out of draft with the forge's base `main` waits on the CR under it, "
          "never on `main`",
          out[1].endswith(f"out of draft on the forge; it waits on {b} ({bpr})")
          and "waits on main" not in out[1], str(out))
    edit_cr(b, drop=("pr",))
    check("4. a CR handed back ready with no PR reads `ready` alone in the `stack` rows",
          any(ln.startswith(f"{b} ready worktree") for ln in w.chantier("stack")[1]),
          str(w.chantier("stack")[1]))
    edit_cr(c, status="working")  # handed back again, the record as a Driver leaves it
    _, out = w.ready(c, cpr)
    check("4. a CR waited on with no PR recorded reads `(no PR yet)`",
          out[1].endswith(f"it waits on {b} (no PR yet)"), str(out))
    edit_cr(b, pr=bpr)
    forge_base(w, cpr, w.cr(b)["branch"])
    w.chantier("ship", c, cpr)
    edit_cr(c, drop=("pr_draft",))
    edit_cr(c, status="working")  # handed back again, the record as a Driver leaves it
    _, out = w.ready(c, cpr)
    check("4. a PR with no recorded draft state reads `of unknown draft state` and stays `PR in draft`",
          out[0].startswith(f"[driver {c}→foreman] hand-back PR in draft")
          and f"its PR {cpr} is of unknown draft state (draft not read: ship {c} {cpr}); "
              f"it waits on {b} ({bpr})" in out[1], str(out))
    w.chantier("ship", c, cpr)
    def pr_n(cr: str) -> str:
        return "#" + re.search(r"(\d+)/?$", w.cr(cr)["pr"])[1]

    edit_cr(c, pr_draft=False)  # c is out of draft over b's draft
    stack_rows = w.chantier("stack")[1]
    check("4. `status` reads the derived word; the `stack` rows read the hand-back state and the "
          "PR's draft flag",
          "PR in draft" in row(c)
          and any(ln.startswith(f"{c} ready, PR out of draft ({pr_n(c)}) worktree") for ln in stack_rows)
          and any(ln.startswith(f"{b} ready, PR draft ({pr_n(b)}) worktree") for ln in stack_rows),
          f"{row(c)} {stack_rows}")

    kept = {n: (w.folder() / n).read_bytes() for n in ("batch.json", "events.jsonl")}
    code, _ = w.chantier("stack", "--out-of-draft", c, expect=2)
    check("5. `stack --out-of-draft` over a draft is refused, naming it; nothing is written",
          code == 2 and f"under it is a draft: {b}" in w.last_stderr
          and all((w.folder() / n).read_bytes() == v for n, v in kept.items()), w.last_stderr)
    code, out = w.chantier("stack", "--out-of-draft", a, b, c)
    check("5. `stack --out-of-draft a b c` records the three and each reads `ready to merge`",
          code == 0 and out == [f"{x} ready to merge" for x in (a, b, c)]
          and all(w.cr(x)["pr_draft"] is False for x in (a, b, c))
          and all(ready_of(x) == "ready to merge" for x in (a, b, c)), str(out))
    for x in (a, b, c):
        icon_is(w, x, "🟢", "a stack ready to merge")
    forge_draft(w, w.cr(b)["pr"], False)  # the stack driver turned them ready on the forge
    code, _ = w.chantier("stack", "--out-of-draft", "--draft", a, expect=1)
    check("5. `--out-of-draft` and `--draft` together are refused",
          code == 1 and "not both" in w.last_stderr, w.last_stderr)

    check("6. a CR taken back for a round: the PR above it falls back to `PR in draft`",
          fm.take(b, "round: a change") == 0 and w.cr(b)["status"] == "working", str(w.cr(b)))
    icon_is(w, c, "🟤", "the CR above a CR taken back")

    def cr_rows(lines: list[str]) -> list[str]:
        ids = tuple(x["id"] + " " for x in w.batch()["crs"])
        return [ln for ln in lines if ln.startswith(ids) and " worktree " in ln]

    rows = cr_rows(w.chantier("stack")[1])
    check("6. the `stack` row of a CR taken back reads `working, PR …`, and `take stack` prints "
          "the same CR rows",
          any(ln.startswith(f"{b} working, PR ") for ln in rows)
          and rows == cr_rows(w.chantier("take", "stack", "--epoch", 1)[1]), str(rows))
    check("6. `readiness` of the CR above follows, and it waits for the CR taken back",
          ready_of(c) == "PR in draft" and ready_of(a) == "ready to merge"
          and f"waits for {b}" in drawn(w, c)[1]["label"], str(drawn(w, c)[1]))
    code, _ = w.chantier("stack", "--out-of-draft", b, expect=2)
    check("6. `--out-of-draft` on a CR that is working is refused: only a CR handed back ready",
          code == 2 and "only a CR handed back ready" in w.last_stderr, w.last_stderr)
    driver_round(w, b, "words1.py", "N = 11\n")
    w.ready(b, w.cr(b)["pr"])
    w.chantier("stack", "--draft", c)
    check("7. `stack --draft` records a PR turned back to a draft; the CR reads `PR in draft`",
          w.cr(c)["pr_draft"] is True and ready_of(c) == "PR in draft"
          and ready_of(b) == "ready to merge", str(w.cr(c)))
    w.chantier("stack", "--out-of-draft", c)

    # an old record, a hand-edited record
    edit_cr(c, drop=("pr_draft",))
    w.chantier("note", c, "record edited by hand")  # any write draws the STATUS files again
    check("8. an old record with no draft state reads `PR in draft`, never ahead of the forge",
          ready_of(c) == "PR in draft" and "🟤" in drawn(w, c)[1]["label"], str(drawn(w, c)[1]))
    edit_cr(c, pr_draft=False)
    edit_cr(a, drop=("pr",))
    w.chantier("note", a, "record edited by hand")
    own = icon_is(w, a, "🟣", "a ready CR with no PR recorded")
    check("8. a hand-edited ready CR with no `pr` reads `ready locally`",
          own["readiness"] == "ready locally" and "ready locally" in own["label"]
          and "ready locally" in row(a), str(own))
    edit_cr(a, pr=OPENED[a])

    stray = [str(p.relative_to(w.state)) for p in w.state.rglob("STATUS.*")
             if "\U0001f535" in p.read_text(encoding="utf-8")]
    check("no STATUS file draws the retired blue icon", stray == [], str(stray))

    for cr in (b, c):  # PR links repeat from batch to batch: leave the fake forge clean
        forge_base(w, w.cr(cr)["pr"], "main")

    # a stack whose top PR the forge puts on a, not on b (the chain's neighbour)
    w.reset()
    items = [prepare_cr(w, t)[1] for t in ("Forge a", "Forge b", "Forge c")]
    w.start(*map(str, items), "--mode", "stack", *FROM_AGENTS_MD)
    w.env["CHANTIER_BATCH"] = w.name
    w.chantier("foreman", "set", "local_foreman_words5", "--epoch", 1)
    Foreman(w, epoch=1).turn()
    a, b, c = (x["id"] for x in w.batch()["crs"])
    w.chantier("stack", a, b, c)
    for i, cr in enumerate((a, b, c)):
        driver_round(w, cr, f"forge{i}.py", f"N = {i}\n")
    for cr in (a, b):
        forge_draft(w, w.cr(cr)["pr"], True)
        w.chantier("ship", cr, w.cr(cr)["pr"])
    forge_base(w, w.cr(c)["pr"], w.cr(a)["branch"])
    w.chantier("ship", c, w.cr(c)["pr"])
    w.ready(c, w.cr(c)["pr"])
    check("11. a stack's PR the forge puts on a, not b: with a and b drafts it waits for a, the CR its "
          "forge base is on", f"waits for {a}" in drawn(w, c)[1]["label"]
          and w.cr(c)["pr_base"] == w.cr(a)["branch"], str(drawn(w, c)[1]))
    forge_draft(w, w.cr(a)["pr"], False)
    w.chantier("ship", a, w.cr(a)["pr"])
    w.ready(a, w.cr(a)["pr"])
    check("11. with a out of draft and b a draft it waits for b (the chain's rule) and reads `PR in draft`",
          f"waits for {b}" in drawn(w, c)[1]["label"] and ready_of(c) == "PR in draft", str(drawn(w, c)[1]))
    for cr in (a, b):  # PR links repeat from batch to batch: leave the fake forge clean
        forge_draft(w, w.cr(cr)["pr"], False)
    forge_base(w, w.cr(c)["pr"], "main")

    # a release prepared on the stack's top CR reads its state like any CR
    w.reset()
    items = [prepare_cr(w, t)[1] for t in ("Words top", "Words release")]
    w.start(*map(str, items), "--mode", "stack", "--release", 2, *FROM_AGENTS_MD)
    w.env["CHANTIER_BATCH"] = w.name
    w.chantier("foreman", "set", "local_foreman_words2", "--epoch", 1)
    fm = Foreman(w, epoch=1)
    top, rel = (x["id"] for x in w.batch()["crs"])
    fm.turn()
    driver_round(w, top, "words_top.py", "N = 1\n")
    w.ready(top, w.cr(top)["pr"])
    w.chantier("stack", top, rel)
    on_branch(w, rel, w.cr(top)["branch"])
    check("9. the release is taken", fm.take(rel) == 0, str(fm.facts))
    w.chantier("order", "approve", rel, "--note", "tag v1.9.0")
    w.chantier("release", "start", rel)
    commit(w, rel, "VERSION", "1.9.0\n", "release: v1.9.0")
    w.chantier("gate", rel, GATE)
    wt = Path(w.cr(rel)["worktree"])
    w.sh("git", "push", "--quiet", "--force-with-lease", "-u", "origin", w.cr(rel)["branch"], cwd=wt)
    (w.at(w.cr(rel)["path"]) / "work").mkdir(exist_ok=True)
    (w.at(w.cr(rel)["path"]) / "work" / "pr-body.md").write_text(
        BODY.format(title=w.cr(rel)["title"], cr=rel))
    pr = open_pr(w, rel, "release: v1.9.0", base=w.cr(top)["branch"])
    forge_draft(w, pr, True)  # the forge holds the release PR as a draft
    w.chantier("ship", rel, pr)
    _, out = w.chantier("handback", rel, "ready", f"{pr} waits for the merge")
    check("9. a prepared release whose PR is a draft is handed back `PR in draft`, naming the PR "
          "and what it waits on",
          out[0].startswith(f"[driver {rel}→foreman] hand-back PR in draft")
          and f"the release PR {pr} is a draft on the forge; it waits on {top} ({w.cr(top)['pr']})"
          in out[1], str(out))
    icon_is(w, rel, "🟤", "a prepared release whose PR is a draft")
    w.chantier("stack", "--out-of-draft", top, rel)
    _, out = w.chantier("handoff", rel)
    check("9. out of draft with the CR under it, the prepared release reads `ready to merge`",
          ready_of(rel) == "ready to merge" and "ready to merge" in out[0], str(out))
    icon_is(w, rel, "🟢", "a prepared release out of draft")
    forge_draft(w, pr, False)  # PR links repeat from batch to batch: leave the fake forge clean
    forge_base(w, pr, "main")

    # a parallel batch: a CR on another CR's branch is a PR in draft until that CR is merged
    w.reset()
    w.env.pop("CHANTIER_BATCH", None)
    base_, next_ = prepare_cr(w, "Words base")[1], prepare_cr(w, "Words next")[1]
    depends_on(next_, base_.name)
    w.start(str(base_), str(next_), "--slots", 3, *FROM_AGENTS_MD)
    w.env["CHANTIER_BATCH"] = w.name
    p, q = (x["id"] for x in w.batch()["crs"])
    w.chantier("take", p, "--epoch", 0)
    start_driver(w, p)
    driver_round(w, p, "words_p.py", "P = 1\n")
    w.ready(p, w.cr(p)["pr"])
    icon_is(w, p, "🟢", "a parallel CR on the default branch, out of draft")
    w.chantier("take", q, "--epoch", 0)
    start_driver(w, q)
    driver_round(w, q, "words_q.py", "Q = 1\n")
    forge_base(w, w.cr(q)["pr"], w.cr(p)["branch"])  # its PR sits on p's branch, as it starts
    w.chantier("ship", q, w.cr(q)["pr"])
    _, out = w.ready(q, w.cr(q)["pr"])
    check("10. a CR on an open CR's branch, shipped out of draft, is still `PR in draft`: its base "
          "is not the default branch",
          out[0].startswith(f"[driver {q}→foreman] hand-back PR in draft")
          and f"waits for {p}" in drawn(w, q)[1]["label"], str(out))
    icon_is(w, q, "🟤", "a CR on an open CR's branch")
    w.chantier("order", "merged", p)
    forge_base(w, w.cr(q)["pr"], "main")  # the forge retargets it; the Driver ships again
    w.chantier("ship", q, w.cr(q)["pr"])
    check("10. once the CR under it is merged, it reads `ready to merge`",
          ready_of(q) == "ready to merge" and "ready to merge" in w.chantier("handoff", q)[1][0],
          str(drawn(w, q)[1]))
    icon_is(w, q, "🟢", "that CR once its base merged")
    w.env.pop("CHANTIER_BATCH", None)


def dependencies(w: World) -> None:
    note("\n## 14d. A CR declares what it depends on; a slot is a running Driver")
    one, two = prepare_cr(w, "Cycle one")[1], prepare_cr(w, "Cycle two")[1]
    depends_on(one, two.name)
    depends_on(two, one.name)
    w.reset()
    code, _ = w.start(str(one), str(two), expect=2)
    check("a cycle is refused at `open`, naming it; nothing is opened or moved",
          code == 2 and "cycle" in w.last_stderr and one.is_dir() and two.is_dir()
          and not list((w.state / "4-batch").glob("batch.json")), w.last_stderr)
    depends_on(two, "no-such-cr")
    code, _ = w.start(str(two), expect=2)
    check("an unknown slug is refused, named", code == 2 and "no-such-cr" in w.last_stderr
          and two.is_dir(), w.last_stderr)
    depends_on(two, raw="{not json")
    code, _ = w.start(str(two), expect=2)
    check("a malformed `depends.json` is refused", code == 2 and "depends.json" in w.last_stderr
          and two.is_dir(), w.last_stderr)

    base_, next_ = prepare_cr(w, "Dep base")[1], prepare_cr(w, "Dep next")[1]
    depends_on(next_, base_.name)
    w.start(str(base_), str(next_), "--slots", 3, *FROM_AGENTS_MD)
    w.env["CHANTIER_BATCH"] = w.name
    a, b = (c["id"] for c in w.batch()["crs"])
    check("`open` records `after` as CR ids", w.cr(b).get("after") == [a] and "after" not in w.cr(a),
          str(w.batch()["crs"]))
    icon_is(w, a, "⚪", "a queued CR with a free slot")
    icon_is(w, b, "🟠", "a queued CR with `waits`")
    _, out = w.chantier("status")
    check("`status` shows what a queued CR waits for",
          any(ln.startswith(b) and f"waits for {a} queued" in ln for ln in out), str(out))
    board = json.loads((w.state / "4-batch" / "STATUS.json").read_text(encoding="utf-8"))
    check("the STATUS files name what a queued CR waits for, as `status` does",
          any(r["cr"] == b and r["waits"] == [f"{a} queued"] and f"waits for {a} queued" in r["label"]
              for r in board["crs"]), str(board["crs"]))
    code, _ = w.chantier("take", b, "--epoch", 0, expect=2)
    check("a CR is refused until its dependency is ready, and the refusal names it",
          code == 2 and f"waits for {a} queued" in w.last_stderr and w.cr(b)["status"] == "queued",
          w.last_stderr)
    w.chantier("take", a, "--epoch", 0)
    start_driver(w, a)
    code, _ = w.chantier("take", b, "--epoch", 0, expect=2)
    check("a working dependency is not enough", code == 2 and f"{a} working" in w.last_stderr,
          w.last_stderr)
    driver_round(w, a, "dep_a.py", "A = 1\n")
    w.ready(a, w.cr(a)["pr"])
    _, out = w.chantier("take", b, "--epoch", 0)
    check("once it is ready, the dependent starts on its branch (even in a parallel batch)",
          any(f"base {w.cr(a)['branch']}" in ln for ln in out), str(out))
    w.chantier("order", "merged", a)
    _, out = w.chantier("handoff", b)
    check("when the dependency is merged, the base is the default branch",
          any("base origin/main" in ln for ln in out), str(out))
    after_archive = prepare_cr(w, "Dep late")[1]
    depends_on(after_archive, base_.name)
    _, out = w.chantier("order", "add", "--note", str(after_archive))
    late = w.batch()["crs"][-1]
    check("a dependency already archived as merged is met and not recorded",
          "after" not in late and late["status"] == "queued"
          and w.chantier("take", late["id"], "--epoch", 0)[0] == 0, str(out))
    cancelled = prepare_cr(w, "Dep dropped")[1]
    w.chantier("order", "add", "--note", str(cancelled))
    dropped = w.batch()["crs"][-1]["id"]
    w.chantier("order", "drop", dropped, "--note", "trash")
    icon_is(w, dropped, "⚪", "a dropped CR")
    waiting = prepare_cr(w, "Dep waiting")[1]
    depends_on(waiting, cancelled.name)
    w.chantier("order", "add", "--note", str(waiting))
    code, _ = w.chantier("take", w.batch()["crs"][-1]["id"], "--epoch", 0, expect=2)
    check("a cancelled dependency stays unmet", code == 2 and f"{dropped} cancelled" in w.last_stderr,
          w.last_stderr)

    w.reset()
    s1, s2 = prepare_cr(w, "Stack first")[1], prepare_cr(w, "Stack second")[1]
    depends_on(s2, s1.name)
    w.start(str(s1), str(s2), "--mode", "stack", *FROM_AGENTS_MD)
    w.env["CHANTIER_BATCH"] = w.name
    x, y = (c["id"] for c in w.batch()["crs"])
    code, _ = w.chantier("stack", y, x, expect=2)
    check("a stack order that puts a CR below its dependency is refused",
          code == 2 and x in w.last_stderr and w.batch()["crs"][0]["order"] == 1, w.last_stderr)
    code, _ = w.chantier("stack", x, y)
    check("the order that respects it is taken", code == 0)
    _, out = w.chantier("order", "after", y, "--note", "-")
    check("`order after` with `-` frees a queued CR; it is logged and printed for the Foreman",
          "after" not in w.cr(y) and out[0].startswith("[chief-of-staff→foreman] order O-1: after")
          and w.batch()["orders"][-1]["kind"] == "after" and len(w.batch()["crs"]) == 2
          and any("base origin/main" in ln for ln in w.chantier("handoff", y)[1]), str(out))
    _, out = w.chantier("order", "after", y, "--note", x)
    check("`order after` replaces the dependencies of a queued CR, with no new number",
          w.cr(y).get("after") == [x] and len(w.batch()["crs"]) == 2
          and w.chantier("take", y, "--epoch", 0, expect=2)[0] == 2 and f"waits for {x} queued" in w.last_stderr,
          str(out))
    code, _ = w.chantier("order", "after", x, "--note", y, expect=2)
    check("`order after` refuses a cycle and changes nothing", code == 2 and "cycle" in w.last_stderr
          and "after" not in w.cr(x) and w.cr(y).get("after") == [x], w.last_stderr)
    code, _ = w.chantier("order", "after", "CR-999", "--note", x, expect=2)
    check("`order after` refuses an unknown CR", code == 2 and "CR-999" in w.last_stderr, w.last_stderr)
    code, _ = w.chantier("order", "after", y, "--note", "CR-999", expect=2)
    check("`order after` refuses an unknown dependency, and keeps the old one",
          code == 2 and "CR-999" in w.last_stderr and w.cr(y).get("after") == [x], w.last_stderr)
    w.chantier("take", x, "--epoch", 0)
    code, _ = w.chantier("order", "after", x, "--note", "-", expect=2)
    check("`order after` refuses a CR that is not queued", code == 2 and "queued" in w.last_stderr,
          w.last_stderr)

    w.reset()
    q1, q2 = prepare_cr(w, "Slot one")[1], prepare_cr(w, "Slot two")[1]
    w.start(str(q1), str(q2), "--slots", 2, *FROM_AGENTS_MD)
    w.env["CHANTIER_BATCH"] = w.name
    c1, c2 = (c["id"] for c in w.batch()["crs"])
    w.chantier("take", c1, "--epoch", 0)
    w.chantier("order", "qa", "--note", "try it")
    check("an open QA order holds a slot: `status` counts it",
          w.chantier("status")[1][0].split(" live ")[1].startswith("2/2"), str(w.last_out))
    code, _ = w.chantier("take", c2, "--epoch", 0, expect=2)
    check("with the QA driver and a CR, no slot is free for the next", code == 2
          and "no free slot" in w.last_stderr and "O-1 qa" in w.last_stderr, w.last_stderr)
    icon_is(w, c1, "🟡", "a working CR")
    icon_is(w, c2, "🟠", "a queued CR with no free slot (a QA order holds the last one)")
    code, _ = w.chantier("order", "qa", "--note", "again", expect=2)
    check("a second QA order is refused too: its driver would have no slot",
          code == 2 and "no free slot" in w.last_stderr, w.last_stderr)
    w.chantier("order", "done", "O-1", "--epoch", 0)
    icon_is(w, c2, "⚪", "a queued CR once `order done` frees the slot")
    state = w.folder() / "batch.json"
    w.chantier("order", "budget", "--note", "10")
    state.write_text(json.dumps({**w.batch(), "spent_usd": 2}))
    w.chantier("order", "budget", "--note", "1")
    icon_is(w, c2, "🟠", "a queued CR on a spent budget (`take` refuses it)")
    w.chantier("order", "budget", "--note", "10")
    icon_is(w, c2, "⚪", "a queued CR once the budget is raised")
    code, _ = w.chantier("take", c2, "--epoch", 0)
    check("the QA driver's end frees its slot", code == 0)
    start_driver(w, c2)
    w.chantier("handback", c2, "blocked", "waits: the stack driver")
    own = icon_is(w, c2, "🟠", "a CR blocked with `waits:`")
    check("`waits:` keeps severity red and its Next names the thing, not the user's answer",
          own["severity"] == "red" and own["label"] == "🟠 blocked Waits 1/3"
          and "the stack driver" in own["next"] and "user's answer" not in own["next"], str(own))
    w.chantier("take", c2, "--note", "the stack driver landed", "--epoch", 0)
    w.chantier("handback", c2, "blocked", "question: which one?")
    icon_is(w, c2, "🔴", "a CR blocked for any other reason")
    start_driver(w, c1)
    driver_round(w, c1, "icons_one.py", "ONE = 1\n")
    w.ready(c1, w.cr(c1)["pr"])
    icon_is(w, c1, "🟢", "a ready CR out of draft")
    w.chantier("order", "merged", c1)
    icon_is(w, c1, "✅", "a merged CR")
    w.env.pop("CHANTIER_BATCH", None)


def release_merge_on_approval(w: World) -> None:
    note("\n## 15. A release PR is the user's to merge: no approval covers it")
    _, version = prepare_cr(w, "Release v1.2.0")
    w.reset()
    w.start(str(version), "--release", 1, *FROM_AGENTS_MD)
    w.env["CHANTIER_BATCH"] = w.name
    w.chantier("foreman", "set", "local_foreman4", "--epoch", 1)
    fm = Foreman(w, epoch=1)
    fm.turn()
    rel = w.batch()["crs"][0]["id"]
    w.chantier("release", "start", rel)
    commit(w, rel, "VERSION", "1.2.0\n", "release: v1.2.0")
    w.chantier("gate", rel, GATE)
    ship(w, rel, "release: v1.2.0")
    pr = w.cr(rel)["pr"]
    w.chantier("handback", rel, "ready", pr)
    fm.turn()
    check("without a grant, the prepared release PR goes to the user, never to a merge",
          fm.asked[-1] == f"ready-to-merge {rel} {pr}" and w.cr(rel)["status"] == "ready", str(fm.asked))
    drivers = len(fm.started)
    w.chantier("order", "approve", rel, "--note", f"merge the release PR {pr}")
    for o in w.batch()["orders"]:
        if not o["done"]:
            w.chantier("order", "done", o["id"], "--epoch", 1)
    w.chantier("release", "go", rel, "--note", f"merge the release PR {pr}", expect=2)
    check(
        "an approval never starts a Driver or merges: the Foreman started and merged nothing",
        len(fm.started) == drivers and not any(a.startswith(f"merged {rel} ") for a in fm.asked),
        str(fm.started),
    )
    w.chantier("order", "merged", rel)
    fm.turn()
    check("the user's merge starts the next Driver, which goes on",
          len(fm.started) == drivers + 1 and w.cr(rel)["status"] == "working", str(fm.started))
    w.chantier("handback", rel, "ready", "v1.2.0")
    fm.turn()
    check("the batch pauses", fm.paused)
    last = w.folder()
    priced_foreman(w)
    clear_agents(w)
    if sys.platform == "win32":  # elsewhere a file in use does not stop a rename
        with open(last / "STATUS.md", encoding="utf-8"):
            code, _ = w.chantier("close", "--batch", w.name, "--yes", expect=None)
        check("`close` on a folder in use deletes nothing and can run again",
              code != 0 and "in use" in w.last_stderr and (last / "batch.json").is_file(),
              w.last_stderr)
    w.chantier("close", "--batch", w.name, "--yes")


def lost_messages(w: World) -> None:
    note("\n## 16. Lost messages: the wake catches up, and nothing is left unsaid")
    titles = ("Lost one", "Lost two", "Lost three")
    prepared = [prepare_cr(w, title)[1] for title in titles]
    w.reset()
    # seeded here, not left by an earlier case: batch 7 was the last, its folder is gone, and the
    # trash holds a dated CR
    (w.state / ".batch-number").write_text("7\n")
    (w.state / "6-trash" / "261103-1100-111-dropped").mkdir(parents=True)
    w.start(*(str(p) for p in prepared), "--slots", 3, *FROM_AGENTS_MD)
    w.env["CHANTIER_BATCH"] = w.name
    check(
        "batch numbers go on rising after the last batch's folder is deleted",
        w.name == "batch-08",
        w.name,
    )
    w.chantier("foreman", "set", "local_foreman5", "--epoch", 1)
    fm = Foreman(w, epoch=1)
    fm.turn()
    one, two, three = (c["id"] for c in w.batch()["crs"])
    check("a date in the trash is not a CR number", len(one) == len("CR-101"), one)

    _, out = w.chantier("order", "note", three, "--note", "first")  # its line never reaches the Foreman
    order = out[0].split()[2].rstrip(":")
    _, out = w.chantier("status", "--refresh", "--epoch", 1, expect=None)
    check("a wake shows the order whose line never came, and records the heartbeat",
          any(ln.startswith(f"orders pending: {order} note {three} first") for ln in out)
          and "live 3/3" in out[0] and w.batch()["heartbeat"], str(out))
    fm.turn()
    check("the Foreman tells the Driver and marks the order done",
          all(o["done"] for o in w.batch()["orders"])
          and any(m == f"{three} first" for m in fm.messages), str(fm.messages))
    check("the line that arrives late changes nothing",
          w.chantier("order", "done", order, "--epoch", 1)[1] == [f"{order} already done"])

    driver_round(w, one, "lost.py", f"WHO = '{one}'\n")
    w.ready(one, w.cr(one)["pr"])
    fm.turn()
    check("a ready CR is told", fm.asked[-1].startswith(f"ready-to-merge {one} "))
    driver_round(w, two, "lost.py", f"WHO = '{two}'\n")
    w.sh("git", "push", "--quiet", "origin", f"{w.cr(one)['branch']}:main")  # the user merges
    _, out = w.ready(two, w.cr(two)["pr"])
    check("a hand-back records what the Driver says; whether the PR still merges is the "
          "Foreman's to notice with the forge's CLI", w.cr(two)["status"] == "ready", str(out))
    _, out = w.chantier("status", "--refresh", "--epoch", 1, expect=None)
    check("a wake names the activity of each working CR and says what it knows of the spend",
          any(ln.startswith(f"activity {three} ") for ln in out)
          and not any("longest silent" in ln for ln in out)
          and any(ln.startswith(("spent $", "spend not updated")) for ln in out), str(out))
    driver_round(w, three, "other.py", "OTHER = True\n")
    w.ready(three, w.cr(three)["pr"])
    fm.turn()

    _, out = w.chantier("status")
    check("status counts the asks unread", any("asks unread" in ln for ln in out), str(out))
    _, out = w.chantier("asks", "refused", one, "the", "host", "said", "no")
    check("the Foreman's own ask is recorded and printed, with its id",
          re.fullmatch(rf"\[foreman→chief-of-staff\] ask A-\d+: refused {one} the host said no",
                       out[0]), str(out))
    _, out = w.chantier("asks")
    check("`asks` gives every ask still unread, sent or not",
          out[0].startswith(f"A-1: ready-to-merge {one} ")
          and out[-1].endswith(f"refused {one} the host said no"), str(out))
    first_id = out[0].split(":")[0]
    _, out = w.chantier("asks", "--read", first_id)
    check("one ask is marked heard", out == ["read 1"], str(out))
    _, out = w.chantier("asks")
    check("the others stay", out and not out[0].startswith("A-1:"), str(out))
    w.chantier("asks", "--read", "all")
    _, out = w.chantier("asks")
    check("an ask is read once", out == ["no unread ask"], str(out))
    ask_supersedes(w, one, three)


def ask_supersedes(w: World, one: str, three: str) -> None:
    """CR-272: a readiness ask marks the earlier unread one of the same CR (of the stack) read."""
    def unread() -> list[str]:
        return [ln.split(":")[0] for ln in w.chantier("asks")[1] if ln.startswith("A-")]

    def ask_id(out: list[str]) -> str:
        return out[0].split("ask ")[1].split(":")[0]

    _, out = w.chantier("asks", "ready-to-merge", one, "https://x/pr/1", "gaps:", "a")
    first = ask_id(out)
    _, out = w.chantier("asks", "ready-to-merge", one, "https://x/pr/1", "gaps:", "b")
    second = ask_id(out)
    check("a second readiness ask prints its line first, then the superseded one",
          re.fullmatch(r"\[foreman→chief-of-staff\] ask A-\d+: ready-to-merge .*", out[0])
          and out[1:] == [f"{first} superseded by {second} (marked read)"], str(out))
    check("`asks` lists the second readiness ask and not the first", unread() == [second], str(unread()))
    events = [json.loads(ln) for ln in (w.folder() / "events.jsonl").read_text("utf-8").splitlines()]
    check("the `asks-read` event names the superseded ask and its successor",
          any(e.get("kind") == "asks-read" and e.get("asks") == [first]
              and e.get("superseded_by") == second for e in events)
          and any(e.get("kind") == "ask" and e.get("ask") == second and e.get("cr") == one
                  for e in events), str(events[-3:]))
    _, out = w.chantier("asks", "pr-in-draft", one, "https://x/pr/1", "on", "main:", "waits", "for", "x")
    third = ask_id(out)
    check("a `pr-in-draft` supersedes a `ready-to-merge` of the same CR",
          out[1:] == [f"{second} superseded by {third} (marked read)"] and unread() == [third], str(out))
    w.chantier("asks", "--read", "all")
    q = ask_id(w.chantier("asks", "question", one, "which?")[1])
    bl = ask_id(w.chantier("asks", "blocked", one, "waits:", "x")[1])
    w.chantier("asks", "ready-to-merge", one, "https://x/pr/1")
    check("`question` and `blocked` stay unread under a readiness ask",
          unread()[:2] == [q, bl], str(unread()))
    rd = unread()[-1]
    _, out = w.chantier("asks", "question", one, "again?")
    check("a `question` supersedes nothing", len(out) == 1 and rd in unread(), str(out))
    w.chantier("asks", "--read", "all")
    a_one = ask_id(w.chantier("asks", "ready-to-merge", one, "https://x/pr/1")[1])
    a_three = ask_id(w.chantier("asks", "ready-to-merge", three, "https://x/pr/3")[1])
    check("a readiness ask for another CR leaves the first unread", unread() == [a_one, a_three], str(unread()))
    w.chantier("asks", "ready-to-merge", one, "https://x/pr/1", "gaps:", "c")
    check("the new ask for one CR leaves the other's unread", a_three in unread() and a_one not in unread(),
          str(unread()))
    w.chantier("asks", "--read", a_three)
    before = {a["id"]: a["read"] for a in w.batch()["asks"]}
    w.chantier("asks", "ready-to-merge", three, "https://x/pr/3", "gaps:", "d")
    after = {a["id"]: a["read"] for a in w.batch()["asks"]}
    check("an ask already read is not touched again", after[a_three] == before[a_three], str(after[a_three]))
    w.chantier("asks", "--read", "all")
    s1 = ask_id(w.chantier("asks", "stack-ready-to-merge", "https://x/pr/9", "one=https://x/pr/1")[1])
    _, out = w.chantier("asks", "stack-ready-to-merge", "https://x/pr/9", "one=https://x/pr/1", "gaps:", "z")
    check("a second `stack-ready-to-merge` supersedes the first",
          out[1:] == [f"{s1} superseded by {ask_id(out)} (marked read)"], str(out))


def fake_transcripts(w: World, d: dict) -> None:
    from_root = str(w.work.resolve())
    slug = "".join(ch if ch.isalnum() else "-" for ch in from_root)
    main = w.root / "claude-projects" / slug / "uuid-foreman.jsonl"
    sub = main.with_suffix("") / "subagents"
    sub.mkdir(parents=True)

    def msg(mid, model, out, **fields):
        return json.dumps({"type": "assistant", **fields, "message": {
            "id": mid, "stop_reason": "end_turn", "model": model, "usage": {
                "input_tokens": 10, "output_tokens": out, "cache_read_input_tokens": 20_000,
                "cache_creation": {"ephemeral_1h_input_tokens": 2_000}}}}) + "\n"

    def user(content):
        return json.dumps({"type": "user", "message": {"content": content}}) + "\n"

    result = [{"type": "tool_result", "content": "ok"}]  # the same turn goes on: not a wake
    earlier = msg("old", "claude-sonnet-5-5", 900_000, timestamp="2000-01-01T00:00:00.000Z")
    # a call in the opening second, with a fraction: a text comparison drops it
    opening = d["created"].removesuffix("Z") + ".250Z"
    synthetic = json.dumps({"type": "assistant", "message": {  # an API error: no tokens
        "id": "syn", "model": "<synthetic>", "usage": {
            "input_tokens": 0, "output_tokens": 0, "cache_read_input_tokens": 0}}}) + "\n"
    main.write_text(earlier + synthetic + "".join(
        (user("a wake") if i % 3 == 0 else user(result))
        + msg(f"f{i}", "claude-sonnet-5-5", 300, **({"timestamp": opening} if i == 0 else {}))
        for i in range(30)))
    chief = main.with_name("uuid-chief.jsonl")  # the Chief of Staff: an earlier subject, then now
    chief.write_text(earlier + msg("c1", "claude-sonnet-5-5", 300))
    (sub / "agent-earlier.jsonl").write_text(earlier)  # the session's earlier batch costs nothing
    for c in d["crs"]:
        if c.get("agent") and c["status"] != "cancelled":
            f = sub / f"agent-{c['agent']}.jsonl"
            f.write_text("".join(msg(f"{c['id']}{i}", "claude-sonnet-5-5", 900) for i in range(12)))
            f.with_suffix("").with_suffix(".meta.json").write_text(
                json.dumps({"agentType": "cr-driver"}))
            worker = sub / f"agent-worker-{c['agent']}.jsonl"  # started by the Driver
            worker.write_text("".join(msg(f"w{c['id']}{i}", "claude-sonnet-5-5", 900)
                                      for i in range(4)))
            worker.with_suffix("").with_suffix(".meta.json").write_text(
                json.dumps({"agentType": "coder", "parentAgentId": c["agent"]}))


class SurfaceWorld(World):
    """A planning surface (its own git repository) with two projects, each with its clone and
    worktrees outside the surface. `state` is the demo project's planning folder."""

    def __init__(self, root: Path):
        super().__init__(root)
        self.work = root / "code"  # the demo project's clone: the code repository
        self.surface = root / "surface"
        self.project = self.surface / "projects" / "demo"
        self.state = self.project / "changes"
        # a board's writer of a unit that does not test it commits only at its final cycle or on
        # a `sync now`: its quiet and its longest wait are an hour
        self.env["CHANTIER_WRITER_TEST_TIMES"] = "30:3600:3600:3600:7200"
        self.writerless = False  # True where a unit tests the refusal of a write with no writer

    def writer_up(self) -> None:
        """Stand for the surface's writer where no board runs: a `writer` entry of `server.json`
        for this process, which is alive. A real board's writer, a live `server` entry (a board of
        another version, a board starting) and a unit that tests the refusal leave it alone."""
        file = self.surface / ".git" / "chantier" / "server.json"
        try:
            data = json.loads(file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
        if self.writerless or not isinstance(data, dict):
            return
        for key in ("server", "writer"):  # a live entry stays; a killed board's is replaced
            entry = data.get(key)
            if isinstance(entry, dict) and int(entry.get("pid") or 0) > 0 and psutil.pid_exists(int(entry["pid"])):
                return
        data.pop("server", None)
        data["writer"] = {"pid": os.getpid(), "version": "0", "started": stamp_now(),
                          "state": "synced", "reason": "", "text": "", "since": stamp_now(),
                          "last_cycle": stamp_now(), "pending": 0, "pending_since": None,
                          "ahead": 0, "unpushed_since": None, "last_commit": None,
                          "last_push": None, "last_fetch": None, "conflict": None, "failure": None}
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(json.dumps(data), encoding="utf-8")

    def chantier(self, *args, project="demo", cwd=None, **kw):
        head = ("--project", project) if project else ()
        self.writer_up()
        return super().chantier(*head, *args, cwd=cwd or self.surface, **kw)

    def build(self) -> None:
        super().build()
        self.sh("git", "clone", "--quiet", str(self.root / "origin.git"), str(self.root / "code2"),
                cwd=self.root)
        self.sh("git", "init", "--quiet", "-b", "main", str(self.surface), cwd=self.root)
        self.sh("git", "config", "user.name", "scenario", cwd=self.surface)
        self.sh("git", "config", "user.email", "scenario@example.com", cwd=self.surface)
        (self.surface / "AGENTS.md").write_text("# Surface rules\n\nPlan on the default branch.\n")
        for name, suffix, archive in (("demo", "", "- Archive in the PR: yes\n"), ("other", "2", "")):
            folder = self.surface / "projects" / name
            folder.mkdir(parents=True)
            (folder / "checkout.yml").write_text(
                f"repo: ../../../code{suffix}\nworktrees: ../../../wt{suffix}\n")
            (folder / "project.md").write_text(
                f"# {name}\n\n- Remote: {self.root / 'origin.git'}\n{archive}")
        self.sh("git", "add", ".", cwd=self.surface)
        self.sh("git", "commit", "--quiet", "-m", "init", cwd=self.surface)
        # the surface's origin: the writer's upstream
        origin = self.root / "surface-origin.git"
        self.sh("git", "init", "--quiet", "--bare", "-b", "main", str(origin), cwd=self.root)
        self.sh("git", "remote", "add", "origin", str(origin), cwd=self.surface)
        self.sh("git", "push", "--quiet", "-u", "origin", "main", cwd=self.surface)
        self.sh("git", "remote", "set-head", "origin", "main", cwd=self.surface)

    def prepare(self, title: str, project="demo") -> Path:
        _, out = self.chantier("file", title, project=project)
        inbox = self.surface / out[0].removeprefix("filed ").split(";", 1)[0]
        (inbox / "01-intent.md").write_text(f"# {title}\n\nThe original request is in intake.\n")
        (inbox / "02-answers.md").write_text("# Decisions\n\nNo open questions.\n")
        (inbox / "03-change-spec.md").write_text(f"# {title}\n\nImplement {title}.\n")
        _, out = self.chantier("triage", inbox, "--priority", "P1", project=project)
        return self.surface / out[0].removeprefix("triaged ").rsplit(" (", 1)[0]

    def surface_files(self) -> list[str]:
        p = subprocess.run(["git", "status", "--porcelain", "-uall"], cwd=self.surface,
                           capture_output=True, text=True, encoding="utf-8", check=True)
        return [ln.split(maxsplit=1)[1].strip('"') for ln in p.stdout.splitlines()]


LOCAL_FILES = {"STATUS.md", "STATUS.json", ".lock", ".lifecycle.lock", ".long-gate.lock",
               ".long-gate.2.lock", ".long-gate.2.run", ".long-gate.2.stop", ".batch-number", "seat.json", "batch.json", "events.jsonl", "brief.md"}


def surface_publishes(w: SurfaceWorld, label: str) -> None:
    """The surface's git sees the CR documents and evidence, never a running batch's local files."""
    files = w.surface_files()
    local = [f for f in files if Path(f).name in LOCAL_FILES or Path(f).name.startswith(".closing-")
             or "/work/gates/" in f or f.endswith((".log", ".tmp"))]
    check(f"{label}: the surface's git lists no local file", not local, str(local))
    check(f"{label}: and still lists the CR's documents",
          any(f.endswith("03-change-spec.md") for f in files), str(files))


def surface_writer(tmp: Path) -> None:
    note("\n## 20b. The surface's writer: a real `board --seat` commits and pushes the plan")
    tmp.mkdir()
    w = SurfaceWorld(tmp)
    w.build()
    w.env["CHANTIER_WRITER_TEST_TIMES"] = "1:1:3:2:60"  # a short quiet, so a cycle is quick
    origin = w.root / "surface-origin.git"
    journal = w.state / "forge-journal.jsonl"

    def origin_files() -> str:
        return w.sh("git", "--git-dir", str(origin), "log", "--name-only", "--format=", "main")

    def until(then, timeout: float = 40) -> bool:
        end = time.monotonic() + timeout
        while not (found := then()) and time.monotonic() < end:
            time.sleep(0.5)
        return bool(found)

    def writer_line(command: str) -> str:
        _, out = w.chantier(command, expect=None)
        return next((x for x in out if x.startswith("writer:")), "")

    def head() -> str:
        return w.sh("git", "rev-parse", "HEAD", cwd=w.surface)

    def pushed() -> str:
        return w.sh("git", "--git-dir", str(origin), "rev-parse", "main")

    def events() -> list[str]:
        if not journal.is_file():
            return []
        return [json.loads(x)["type"] for x in journal.read_text(encoding="utf-8").splitlines()]

    w.chantier("init")
    w.chantier("seat", "take", "sess-w", "--env", "remote", "--title", "[remote] writer", "--link", "l")
    bp = BoardProc(w, "board", "--project", "demo", "--host", "127.0.0.1", "--port", 0, "--seat",
                   "sess-w", cwd=w.surface)
    try:
        link = Link(bp.line())
        first = bp.line() or ""
        check("a board started with `--seat` on the surface prints its `writer:` line",
              link.ok and first.startswith("writer: "), f"{link.over} {first}")
        item = w.prepare("Writer plan")  # `file`, then `triage`
        check("`file` then `triage` reach the bare origin within the shortened bound",
              until(lambda: "03-change-spec.md" in origin_files() and "2-backlog/P1" in origin_files()),
              origin_files())
        check("`seat` prints `writer: synced`",
              until(lambda: writer_line("seat").startswith("writer: synced")),
              writer_line("seat"))
        # a commit pushed from a second clone of the surface is integrated
        clone = w.root / "surface-clone"
        w.sh("git", "clone", "--quiet", str(origin), str(clone), cwd=w.root)
        for key, value in (("user.name", "second"), ("user.email", "second@example.com")):
            w.sh("git", "config", key, value, cwd=clone)
        (clone / "projects" / "other" / "from-clone.md").write_text("from the second clone\n")
        w.sh("git", "add", "-A", cwd=clone)
        w.sh("git", "commit", "--quiet", "-m", "from the second clone", cwd=clone)
        w.sh("git", "push", "--quiet", "origin", "main", cwd=clone)
        check("a commit pushed from a second clone of the surface is integrated",
              until(lambda: (w.surface / "projects" / "other" / "from-clone.md").is_file()),
              w.sh("git", "log", "--oneline", "-3", cwd=w.surface))
        # a conflicting change on both sides: the conflict line, the journal, the resolution
        target = Path(item) / "01-intent.md"
        rel = target.relative_to(w.surface).as_posix()
        until(lambda: pushed() == head())
        (clone / rel).write_text("# the second clone's version\n")
        w.sh("git", "commit", "--quiet", "-am", "same file, other side", cwd=clone)
        w.sh("git", "pull", "--quiet", "--rebase", cwd=clone)
        w.sh("git", "push", "--quiet", "origin", "main", cwd=clone)
        target.write_text("# the surface's version\n")
        check("a conflicting change on both sides yields the conflict line in `seat` and the journal",
              until(lambda: writer_line("seat").startswith("writer: conflict")
                    and "sync-conflict@1" in events()),
              f"{writer_line('seat')} {events()}")
        # the scripted Chief of Staff's resolution: a resolved file, then the rebase continues
        w.sh("git", "fetch", "--quiet", "origin", cwd=w.surface)
        subprocess.run(["git", "rebase", "origin/main"], cwd=w.surface, capture_output=True)  # stops
        target.write_text("# resolved by the Chief of Staff\n")
        w.sh("git", "add", rel, cwd=w.surface)
        subprocess.run(["git", "-c", "core.editor=true", "rebase", "--continue"], cwd=w.surface,
                       check=True, capture_output=True, env={**os.environ, "GIT_EDITOR": "true"})
        check("the Chief of Staff's resolution is pushed by the writer, `seat` is `synced`",
              until(lambda: pushed() == head() and writer_line("seat").startswith("writer: synced"), 60)
              and "sync-resumed@1" in events(), f"{pushed()} {head()} {writer_line('seat')} {events()}")
    finally:
        w.writerless = True  # the board is stopped: no writer, whatever entry a kill leaves
        bp.stop()
    before = {str(f.relative_to(w.state)): f.read_bytes() for f in w.state.rglob("*") if f.is_file()}
    code, _ = w.chantier("file", "No writer", expect=2)
    after = {str(f.relative_to(w.state)): f.read_bytes() for f in w.state.rglob("*") if f.is_file()}
    check("the board stopped, `file` is refused with the writer's text and the folder is unchanged",
          "the surface's writer is not running: nothing written" in w.last_stderr and before == after,
          w.last_stderr)


def surface_config_page(w: SurfaceWorld, coder_line: Callable[..., str], frozen: str) -> None:
    """The board's Configuration page with a batch open: `config.put` writes the project folder's
    file and says it applies at the next batch; the running batch keeps its frozen value; the board
    commits nothing itself: the surface server's writer does."""
    target = w.project / "chantier.yaml"
    head = w.sh("git", "rev-parse", "HEAD", cwd=w.surface)
    bp = BoardProc(w, "board", "--project", "demo", "--host", "127.0.0.1", "--port", 0, cwd=w.surface)
    try:
        link = Link(bp.line())
        code, _, view = op(link.port, link, "config.get", {"project": "demo"})
        check("the board's `config.get` at a surface answers the view: writable, no file yet, "
              "a batch open",
              code == 200 and view.get("writable") is True and view.get("sha256") is None
              and view.get("batch") == w.name, f"{code} {str(view)[:200]}")
        change = {"host": "claude", "role": "coder", "key": "model", "value": "opus"}
        code, _, answer = op(link.port, link, "config.put",
                             {"project": "demo", "changes": [change], "base_sha256": None})
        check("`config.put` with a batch open writes the project folder's file and answers "
              "`applies at the next batch`",
              code == 200 and answer.get("ok") is True and "applies at the next batch" in answer.get("lines", [])
              and target.is_file(), f"{code} {answer.get('lines')} {answer.get('error')}")
        lines = [json.loads(x) for x in (w.project / "changes" / "forge-journal.jsonl")
                 .read_text(encoding="utf-8").splitlines()]
        check("that save of a role's model appends one `config@1` line, by the board, keyed on the role",
              [(e["seq"], e["source"], e["type"], e["key"]) for e in lines]
              == [(1, "board", "config@1", "hosts.claude.roles.coder.model")], str(lines))
        check("the board's code committed nothing: the surface's HEAD did not move and the file waits "
              "for its writer",
              w.sh("git", "rev-parse", "HEAD", cwd=w.surface) == head
              and "projects/demo/chantier.yaml" in w.surface_files(), str(w.surface_files()))
        # the two limits: a save moves one `config@1` line of the forge journal; a running watcher ends
        # on it, `status` carries the slots one until an `order slots` follows
        held = w.batch()["slots"]
        quick = {"CHANTIER_HUB_TEST_TIMES": "1:4"}  # the watcher ends 4 s after the last event

        def save(limit: list, sha: str) -> tuple[int, dict]:
            code, _, got = op(link.port, link, "config.put",
                              {"project": "demo", "changes": limit, "base_sha256": sha})
            return code, got

        def ended(proc: BoardProc) -> list[str]:
            try:
                proc.p.wait(timeout=60)
            except subprocess.TimeoutExpired:
                return ["(still running)"]
            got = []
            while (x := proc.line(2)) is not None:
                got.append(x)
            return got

        cli_form = (f'uv run --no-sync --project "{SKILL.parents[1].resolve().as_posix()}" chantier '
                    f'--project "{(w.surface / "projects" / "demo").resolve().as_posix()}"')

        def cursor(n: int) -> str:
            return (f"watch: {w.name} still running: for the Chief of Staff, start again in the "
                    f"background now: {cli_form} watch --after {n}")

        watch = BoardProc(w, "--project", "demo", "watch", cwd=w.surface, env=quick)
        try:
            watch.line()  # its start line
            code, saved = save([{"key": "batch.slots", "value": 6}], answer["sha256"])
            kept = f"{w.name} keeps {held} until an order slots"
            check("`config.put` of `batch.slots` says what happens to the batch, with no "
                  "`applies at the next batch` line",
                  code == 200 and f"slots 4 -> 6: {kept}" in saved.get("lines", [])
                  and "applies at the next batch" not in saved.get("lines", []),
                  f"{code} {saved.get('lines')} {saved.get('error')}")
            told = f"config changed on the board: batch.slots 4 -> 6; {w.name} keeps 4 until an order slots"
            got = ended(watch)
            check("a running `chantier watch` ends with the `config changed on the board` line and its cursor",
                  got == [told, cursor(2)], str(got))
        finally:
            watch.stop()
        # the specifying limit at 1 with a `work/specifying` marker present
        (w.project / "changes" / "1-inbox" / "marker-cr" / "work").mkdir(parents=True)
        (w.project / "changes" / "1-inbox" / "marker-cr" / "work" / "specifying").write_text("", "utf-8")
        watch = BoardProc(w, "--project", "demo", "watch", "--after", 2, cwd=w.surface, env=quick)
        try:
            watch.line()
            code, saved = save([{"key": "specifying.parallel", "value": 1}], saved["sha256"])
            check("`config.put` of `specifying.parallel` says it applies from the next start",
                  code == 200 and "specifying 4 -> 1: from the next start" in saved.get("lines", []),
                  f"{code} {saved.get('lines')} {saved.get('error')}")
            got = ended(watch)
            check("the watcher ends with the `specifying.parallel 4 -> 1` line",
                  got == ["config changed on the board: specifying.parallel 4 -> 1", cursor(3)], str(got))
        finally:
            watch.stop()
    finally:
        bp.stop()
    check("`status` prints the slots change once, the specifying one never",
          told in w.chantier("status")[1] and not any("specifying.parallel" in x for x in w.chantier("status")[1]),
          str(w.chantier("status")[1]))
    time.sleep(1.1)  # the stamps are whole seconds: the order is sent after the save
    w.chantier("order", "slots", "--note", "6")
    check("after an `order slots`, `status` no longer prints the line",
          told not in w.chantier("status")[1], str(w.chantier("status")[1]))
    play = " ".join(w.chantier("playbook")[1])
    check("`playbook` prints the limits with the project folder's label, the marker and `at the limit`",
          "batch slots 6 [surface project]" in play
          and "specifying 1 [surface project], markers 1 (marker-cr)" in play
          and "specifying at the limit" in play, play)
    events_line = next(x for x in w.chantier("playbook")[1] if x.startswith("events:"))
    held_file = target.read_bytes()
    target.write_bytes(held_file + b"\nevents:\n  wake_every: 2m\n")
    try:
        mine = next(x for x in w.chantier("playbook")[1] if x.startswith("events:"))
    finally:
        target.write_bytes(held_file)
    check("`playbook` prints the wake rule after the limits: the shipped 20s with no label, then "
          "the project folder's 2m with its label",
          (events_line, mine) == ("events: wake every 20s", "events: wake every 2m [surface project]"),
          f"{events_line} / {mine}")
    check("the running batch keeps the value it froze, and `playbook` prints the new one",
          coder_line("--batch", w.name) == frozen
          and "opus (claude-opus-5-5, Claude Opus 5.5) [surface project]" in coder_line(),
          f"{coder_line()} / {coder_line('--batch', w.name)}")
    # the writer commits and pushes the file when asked (a fresh board, its writer's `sync now`)
    bw = BoardProc(w, "board", "--project", "demo", "--host", "127.0.0.1", "--port", 0, cwd=w.surface)
    try:
        Link(bw.line())
        bw.line()  # its `writer:` line
        w.chantier("sync", "now")
        end = time.monotonic() + 60
        while time.monotonic() < end and not (
                w.sh("git", "rev-parse", "HEAD", cwd=w.surface) != head
                and w.sh("git", "ls-remote", "origin", "main", cwd=w.surface).split()[0]
                == w.sh("git", "rev-parse", "HEAD", cwd=w.surface)):
            time.sleep(0.5)
    finally:
        bw.stop()
    pushed = w.sh("git", "ls-remote", "origin", "main", cwd=w.surface).split()[0]
    check("the surface server's writer commits the file and pushes it",
          w.sh("git", "rev-parse", "HEAD", cwd=w.surface) != head
          and "projects/demo/chantier.yaml" not in w.surface_files()
          and pushed == w.sh("git", "rev-parse", "HEAD", cwd=w.surface), str(w.surface_files()))
    target.unlink()
    w.sh("git", "commit", "--quiet", "-am", "drop the configuration", cwd=w.surface)


def external_surface(tmp: Path) -> None:
    note("\n## 20. A planning surface: the project's plans in a repository of their own")
    OPENED.clear()
    tmp.mkdir()
    w = SurfaceWorld(tmp)
    w.build()
    # at the surface's root, with two projects: a command names the project
    code, out = w.chantier("preflight", project=None)
    check("preflight at a surface lists its projects and passes",
          code == 0 and any("demo" in ln and "other" in ln for ln in out), str(out))
    code, _ = w.chantier("status", project=None, expect=2)
    check("a command at a surface with two projects exits 2 naming both",
          "demo" in w.last_stderr and "other" in w.last_stderr and "--project" in w.last_stderr,
          w.last_stderr)
    away = w.root / "code.away"
    (w.root / "code").rename(away)
    code, out = w.chantier("preflight", expect=2)
    check("a missing clone fails preflight and names the path and the remote",
          any("P8" in ln and "code" in ln and "origin.git" in ln for ln in out), str(out))
    away.rename(w.root / "code")
    w.chantier("init")
    ignore = (w.state / ".gitignore").read_text(encoding="utf-8")
    check("`init` makes the planning folder and its .gitignore of local files",
          (w.state / "1-inbox").is_dir() and "seat.json" in ignore and "/4-batch/batch.json" in ignore
          and "**/work/gates/" in ignore.splitlines() and not (w.work / ".agents").exists(), ignore)
    gate_dir = w.state / "2-backlog" / "P1" / "any-cr" / "work" / "gates"
    gate_dir.mkdir(parents=True)
    (gate_dir / "out.txt").write_text("x", encoding="utf-8")
    gated = subprocess.run(["git", "check-ignore", "-q", "--no-index", "--", str(gate_dir / "out.txt")],
                           cwd=w.surface, check=False)
    check("a CR's work/gates/ is ignored at any depth of the planning folder",
          gated.returncode == 0, str(gated.returncode))
    shutil.rmtree(w.state / "2-backlog" / "P1" / "any-cr")
    code, out = w.chantier("preflight")
    check("preflight passes in the surface's main checkout", code == 0, str(out))
    item = w.prepare("Surface work")
    item2 = w.prepare("Surface second")
    w.chantier("summary", "set", item, "--title", "Surface work", "--summary", "A surface CR.")
    code, out = w.chantier("summary", "lint", expect=None)
    ignored = subprocess.run(["git", "check-ignore", "-q", "--", str(item / "summary.json")],
                             cwd=w.surface).returncode
    check("`summary set` and `lint` with --project write and read the surface's project, and its "
          ".gitignore does not ignore summary.json",
          (item / "summary.json").is_file() and code == 2 and out[0] == "1 gap(s) in 2 CRs"
          and ignored == 1, str(out))
    # (the Coder's shipped default is sonnet: a configured sonnet is dropped, so the surface's
    # sonnet is no setting; the project folder's opus is the value that shows once the repository's goes)
    layers = [(w.surface / "chantier.yaml", "sonnet"), (w.project / "chantier.yaml", "opus"),
              (w.work / "chantier.yaml", "haiku")]
    timing = "    timing:\n      session:\n        steering_wake: 20m\n        cache_ttl: 1h\n"
    for path, model in layers:  # the three user layers: surface root, project folder, code repository
        extra = timing if path.parent == w.project else ""  # the timing settings: the project folder's
        path.write_text(f"hosts:\n  claude:\n    roles:\n      coder:\n        model: {model}\n{extra}",
                        encoding="utf-8")
    w.start(item, "--direct", "--slots", 1, *FROM_AGENTS_MD)
    w.env["CHANTIER_BATCH"] = w.name
    check("the batch opens in the project's planning folder, the CR path is relative to it",
          w.batch()["crs"][0]["path"].startswith("4-batch/") and (w.state / "4-batch" / "batch.json").is_file()
          and not (w.work / ".agents").exists(), str(w.batch()["crs"][0]))
    # the configuration in layers: the strongest value with its label, frozen at `open`, a reset, a removal
    def coder_line(*args) -> str:
        _, found = w.chantier("playbook", *args)
        return next((ln for ln in found if ln.startswith("coder:")), "")
    frozen = coder_line("--batch", w.name)
    session = ("timing: Claude Code session: steering wake 20 min [surface project], "
               "cache TTL 60 min [surface project]")
    check("the project folder's timing prints `[surface project]`, the brief and `playbook --batch` carry it",
          session in w.chantier("playbook")[1] and session in w.chantier("playbook", "--batch", w.name)[1]
          and "- Timing: Claude Code subagent: cache TTL 5 min, CI re-runs 1; " + session[len("timing: "):]
          in (w.folder() / "brief.md").read_text(encoding="utf-8"), "")
    check("a surface root, a project folder and a code repository each set the Coder's model: `playbook` "
          "prints the repository's with its label, and `open` froze it",
          "haiku (claude-haiku-5-5, Claude Haiku 5.5) [repository]" in coder_line()
          and "[repository]" in frozen and "claude-haiku-5-5" in frozen, f"{coder_line()} / {frozen}")
    layers[2][0].write_text("hosts:\n  claude:\n    roles:\n      coder:\n        model: default\n",
                            encoding="utf-8")
    check("the repository's `model: default` takes the model back to its file's, `[reset in repository]`",
          coder_line().startswith("coder: agent=chantier:coder model=(its file's) [reset in repository]")
          and coder_line("--batch", w.name) == frozen, f"{coder_line()} / {coder_line('--batch', w.name)}")
    layers[2][0].unlink()
    check("with the repository's file removed, `playbook` prints the project folder's value "
          "`[surface project]`; the batch still prints the frozen one",
          "opus (claude-opus-5-5, Claude Opus 5.5) [surface project]" in coder_line()
          and coder_line("--batch", w.name) == frozen, f"{coder_line()} / {coder_line('--batch', w.name)}")
    for path, _ in layers:
        path.unlink(missing_ok=True)
    surface_config_page(w, coder_line, frozen)
    code, _ = w.chantier("open", item2, "--direct", *FROM_AGENTS_MD, expect=None)
    check("a second open on the same project is refused", code != 0, w.last_stderr)
    # another project of the surface opens its own batch at once; the seat is one per project
    other = w.prepare("Other work", project="other")
    w.chantier("init", project="other")
    # a model per role on each host: Copilot cannot start a named agent with a model
    copilot = {"CHANTIER_HOST": "copilot", "COPILOT_AGENT_SESSION_ID": "uuid-chief"}
    other_yaml = w.surface / "projects" / "other" / "chantier.yaml"
    head = "hosts:\n  copilot:\n    roles:\n      coder:\n"
    other_yaml.write_text(head + "        agent: my-coder\n        model: gpt-6.1-terra\n", encoding="utf-8")
    code, out = w.chantier("open", other, "--direct", *FROM_AGENTS_MD, project="other", env=copilot,
                           expect=None)
    check("on Copilot, the user's own agent with a model is refused by `open` (exit 2, the line "
          "named, the cause given) and nothing moved",
          code == 2 and "cannot start a named agent with a model" in w.last_stderr + " ".join(out)
          and "chantier.yaml:" in w.last_stderr + " ".join(out)
          and not (w.surface / "projects" / "other" / "changes" / "4-batch" / "batch.json").exists(),
          f"{code} {out} {w.last_stderr}")
    other_yaml.write_text("batch:\n  slots: 1\n" + head + "        model: gpt-6.1-terra\n", encoding="utf-8")
    _, out = w.chantier("playbook", project="other", env=copilot)
    check("on Copilot, a model with no agent starts a generic agent: `playbook` prints "
          "`agent=(generic)` and the tools line",
          any(ln.startswith("coder: agent=(generic) model=gpt-6.1-terra") and "tools=(the caller's, not "
              "restricted)" in ln for ln in out), str(out))
    _, out = w.chantier("open", other, "--direct", *FROM_AGENTS_MD, project="other", env=copilot)
    other_batch = out[0].split()[1]
    check("`open` with no `--slots` takes `batch.slots` from the project folder's file and names its "
          "layer", ", 1 slots [surface project]," in out[0], str(out))
    w.chantier("seat", "take", "sess-a", "--env", "remote", "--title", "[remote] surface", "--link", "l")
    _, out = w.chantier("seat", "get", project="other")
    check("two projects of one surface each run a batch, and the seat is one per project",
          out[:1] == ["seat none"] and (w.project / "changes" / "seat.json").is_file(), str(out))
    w.chantier("seat", "leave", "sess-a")
    # the other batches of the surface: each session sees the other project's batch, no cap
    _, out = w.chantier("status", project="demo")
    check("`status --project demo` holds the other batch of the surface: project, batch, state, "
          "steering and its Drivers",
          f"other batches on this surface: other {other_batch} running, steering direct (the Chief of "
          "Staff), 0 Drivers" in out, str(out))
    code, out = w.chantier("preflight", project="other")
    check("`preflight --project other` holds a P14 line naming demo's batch and still passes",
          code == 0 and any(ln.startswith("P14 ok") and f"demo {w.name} running" in ln for ln in out)
          and out[-1] == "preflight passed", str(out))
    w.chantier("foreman", "set", "uuid-chief", "--epoch", 1, "--batch", other_batch, project="other")
    code, out = w.chantier("take", "CR-101", "--epoch", 1, "--batch", other_batch, project="other",
                           env=copilot)
    heading = next((i for i, ln in enumerate(out) if ln.startswith("cr-driver prompt (")), 0)
    writes = next((ln for ln in out[heading:] if ln.startswith("  writes: ")), "")
    check("a project that does not ask for its archive in the PR gets `archive: not in the PR` in the "
          "facts, and its CR Driver writes only the CR folder",
          "archive: not in the PR" in out and any(ln.startswith("clone: ") and "code2" in ln for ln in out)
          and writes != "" and "; " not in writes, str(out))
    check("`take` prints the generic Coder's contract after its opening lines, and the team line says "
          "`agent=(generic)`",
          any(ln.startswith("coder contract (a generic agent: copy it unchanged") for ln in out)
          and any(ln.startswith("team: coder agent=(generic)") for ln in out), str(out))
    other_yaml.unlink()
    shutil.rmtree(w.surface / "projects" / "other" / "changes" / "4-batch")
    # the demo batch, as a Driver of the project lives it
    w.chantier("foreman", "set", "uuid-chief", "--epoch", 1)
    w.chantier("foreman", "transcript", "uuid-chief", "--epoch", 1)
    fm = Foreman(w, epoch=1)
    fm.turn()
    cr = w.batch()["crs"][0]["id"]
    c = w.cr(cr)
    facts = fm.facts
    check("`take` prints the timing the batch opened with, though the project's file is gone",
          session in facts and not (w.project / "chantier.yaml").exists(), str(facts))
    cli_line = next((ln for ln in facts if ln.startswith("cli:")), "")
    archive_line = next((ln for ln in facts if ln.startswith("archive: ")), "")
    check("the facts carry `cli:` with --project, the clone and the archive path",
          f'--project "{w.project.as_posix()}"' in cli_line.replace("\\", "/")
          and any(ln.startswith("clone: ") and "/code" in ln.replace("\\", "/") for ln in facts)
          and re.search(r"in the PR at \.agents/changes/5-archives/\d{6}-\d{4}-101-", archive_line),
          str(facts))
    check("the worktree is created under the project's `worktrees` folder, outside the surface",
          Path(c["worktree"]).is_dir() and Path(c["worktree"]).resolve().is_relative_to(
              (w.root / "wt").resolve()), c["worktree"])
    _, out = w.chantier("rules")
    text = "\n".join(out).replace("\\", "/")
    check("`rules` lists the project's instructions, then the surface's",
          out[0] == "project:" and "surface:" in out and "/code/AGENTS.md" in text
          and "/surface/AGENTS.md" in text
          and text.index("/code/AGENTS.md") < text.index("surface:") < text.index("/surface/AGENTS.md"),
          text)
    surface_publishes(w, "after the take")
    # E7. a second slot's files and a move-up marker stay local, as the first slot's
    slot_files = [w.state / n for n in (".long-gate.2.lock", ".long-gate.2.run", ".long-gate.2.stop")]
    (w.state / ".long-gate.queue").mkdir(exist_ok=True)
    slot_files.append(w.state / ".long-gate.queue" / f"first-{time.time_ns():020d}-1")
    for p in slot_files:
        p.write_text("x", encoding="utf-8")
    check("E7: the files of a second long-gate slot and a move-up marker are not published by the surface",
          not [f for f in w.surface_files() if ".long-gate" in f], str(w.surface_files()))
    for p in slot_files:
        p.unlink()
    # the web board at a surface: every project of the surface, each confined to its own folder
    bp = BoardProc(w, "board", "--project", "demo", "--host", "127.0.0.1", "--port", 0, cwd=w.surface)
    try:
        link = Link(bp.line())
        check("`board` at a surface starts with the link and its key", link.ok, str(link.over))
        w.chantier("seat", "take", "sess-b", "--env", "remote", "--title", "[remote] other", "--link",
                   "l", project="other")
        p = subprocess.run([sys.executable, "-m", "chantier", "board", "--project", "other", "--host",
                            "127.0.0.1", "--port", "0", "--seat", "sess-b"], cwd=w.surface, env=w.env,
                           capture_output=True, text=True, encoding="utf-8", timeout=30)
        check("a second session's `board --project other --port 0 --seat <id>` prints `board already "
              "running at` the same link, exit 0, and `/api/board` answers its PID",
              p.returncode == 0 and p.stdout.strip() == f"board already running at http://127.0.0.1:{link.port}/?k={link.key}"
              and isinstance(jget(link.port, link, "/api/board")[2].get("pid"), int),
              p.stdout + p.stderr)
        code, _, api = op(link.port, link, "board.get")
        names = sorted(p["id"] for p in api.get("projects", []))
        check("the surface's board serves both projects (`surface: true`, two lines)",
              code == 200 and api.get("surface") is True and names == ["demo", "other"], str(api))
        code, _, own = op(link.port, link, "project.state", {"project": "demo"})
        check("the project's state lists its CR", code == 200 and "Surface work" in json.dumps(own), str(own)[:200])
        code, _, other = op(link.port, link, "project.tree", {"project": "other", "path": ""})
        check("the other project's folder is reached through its own id", code == 200 and other.get("files"),
              str(other)[:200])
        for label, rel in (("the other project's folder", "../../other/changes/1-inbox"),
                           ("the code clone", "../../../../code/app.py")):
            code, _, _ = op(link.port, link, "project.file", {"project": "demo", "path": rel})
            check(f"the surface's board refuses {label} through a `..` path", code == 404, str(code))
    finally:
        bp.stop()
        w.chantier("seat", "leave", "sess-b", project="other", expect=None)
    # the Driver's round: a change, the long gate, a PR without the archive, then with it
    w.chantier("round", cr, "--note", "edit surface.py")
    commit(w, cr, "surface.py", "SURFACE = True\n")
    w.chantier("gate", cr, GATE)
    ship(w, cr, "feat: surface")
    check("`ship` says the archive is missing from the PR, at its path",
          "archive missing from the PR at .agents/changes/5-archives/" in "\n".join(w.last_out),
          str(w.last_out))
    wt = Path(c["worktree"])
    where = archive_line.split(" at ", 1)[1].strip()
    folder = w.at(c["path"])
    target = wt / where
    shutil.copytree(folder, target, ignore=shutil.ignore_patterns("work", "*.log"))
    (target / "evidence").mkdir(exist_ok=True)
    (target / "evidence" / "check.txt").write_text("ok\n")
    msg = w.root / "commit-msg.txt"
    msg.write_text(f"{cr}: archive\n\n{TRAILER}\n")
    w.sh("git", "add", "-f", "--", ".agents", cwd=wt)
    w.sh("git", "commit", "--quiet", "-F", str(msg), cwd=wt)
    ship(w, cr, "feat: surface")
    check("with the archive in the PR, `ship` raises nothing about it",
          "archive missing" not in "\n".join(w.last_out), str(w.last_out))
    tree = w.sh("git", "ls-tree", "-r", "--name-only", "HEAD", where, cwd=wt).splitlines()
    check("the PR's archive holds the documents and the evidence, and no work folder",
          any(f.endswith("03-change-spec.md") for f in tree) and any(f.endswith("evidence/check.txt") for f in tree)
          and not any("/work/" in f for f in tree), str(tree))
    surface_publishes(w, "after the PR")
    check("the project's clone stays clean: its worktrees hold the Driver's commits",
          w.sh("git", "status", "--porcelain", cwd=w.work) == "", w.sh("git", "status", "--porcelain", cwd=w.work))
    w.ready(cr, w.cr(cr)["pr"])
    fm.turn()
    merge_pr(w, w.cr(cr)["pr"])
    w.chantier("order", "merged", cr)
    delivery = w.at(w.cr(cr)["path"]) / "delivery.md"
    page = delivery.read_text(encoding="utf-8") if delivery.is_file() else ""
    check("`order merged` writes delivery.md: the PR, the merge time, where the archive is",
          w.cr(cr)["pr"] in page and re.search(r"Merged: \d{4}-\d\d-\d\dT", page)
          and f"Archive in the PR: yes, at {where}" in page, page)
    fm.turn()
    check("the batch pauses once its CR is merged", fm.paused, str(w.batch()["status"]))
    slug = "".join(ch if ch.isalnum() else "-" for ch in str(w.surface.resolve()))
    chief = w.root / "claude-projects" / slug / "uuid-chief.jsonl"  # the session's own transcript
    chief.parent.mkdir(parents=True, exist_ok=True)
    chief.write_text(json.dumps({"type": "assistant", "timestamp": datetime.now(timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%S.000Z"), "message": {"id": "c1", "stop_reason": "end_turn", "model": "claude-sonnet-5-5", "usage": {
            "input_tokens": 10, "output_tokens": 100, "cache_read_input_tokens": 0}}}) + "\n")
    (w.folder() / "retro.md").write_text("# Retro\n\n## Pause 1\n\n- one, fix one\n", encoding="utf-8")
    before_close = (w.at(w.cr(cr)["path"]) / "summary.json").read_text(encoding="utf-8")
    clear_agents(w)
    w.chantier("close", "--batch", w.name, "--yes")
    archives = list((w.state / "5-archives").glob("*-101-*"))
    check("`close` puts the merged CR in 5-archives with its delivery.md, the gate log staying off the surface's git",
          len(archives) == 1 and (archives[0] / "delivery.md").is_file(), str(archives))
    batches = w.state / "5-archives" / "batches"
    check("`close` writes the batch's record and its retro in the surface's planning folder, and "
          "the CR's archive in its PR holds no retro.md and no record",
          (batches / f"{w.name}.json").is_file() and (batches / f"{w.name}.md").is_file()
          and "one, fix one" in (batches / f"{w.name}.md").read_text(encoding="utf-8")
          and not (archives[0] / "retro.md").exists()
          and not any(f.endswith("retro.md") or "/batches/" in f for f in tree), str(archives))
    surface_publishes(w, "after the close")
    code, out = w.chantier("validate", expect=None)
    check("`validate` on a closed batch's planning folder exits 0 with no `error` line: archives with their "
          "delivery.md and the batches' records read clean",
          code == 0 and not any(ln.startswith("error ") for ln in out), str(out))
    kept = (archives[0] / "summary.json").is_file() and (archives[0] / "summary.json").read_text(
        encoding="utf-8") == before_close
    code, out = w.chantier("summary", "lint", archives[0], expect=None)
    check("the summary travelled through take, order merged and close, and the archive's new "
          "delivery.md makes it late", kept and code == 2 and "delivery.md new" in out[1], str(out))
    w.env.pop("CHANTIER_BATCH", None)


def filed(w: World, title: str) -> Path:
    _, out = w.chantier("file", title)
    return w.work / out[0].removeprefix("filed ").split(";", 1)[0]


def summary_of(folder: Path) -> dict:
    return json.loads((folder / "summary.json").read_text(encoding="utf-8"))


def summary_basics(w: World, a: Path) -> None:
    """E2 items 1 to 4: no summary, set, what is not a gap, late, `--unchanged`."""
    code, out = w.chantier("summary", "lint", expect=None)
    check("`summary lint` on a filed item exits 2: the count first, then the `no summary` line "
          "with its command", code == 2 and out[0] == "1 gap(s) in 1 CRs" and "no summary" in out[1]
          and "summary set" in out[1], str(out))
    code, out = w.chantier("summary", "set", a, "--title", "Alpha", "--summary", "Alpha is filed.")
    s = summary_of(a)
    check("`summary set` writes summary.json: schema 1, a verbal origin, one source",
          s["schema"] == 1 and s["origin"]["kind"] == "verbal"
          and list(s["sources"]) == ["intake/request.md"] and s["title"] == "Alpha", str(s))
    code, out = w.chantier("summary", "lint", expect=None)
    check("`lint` then says no gap", code == 0 and out == ["no gap (1 CRs)"], str(out))
    (a / "work").mkdir()
    (a / "work" / "notes.md").write_text("notes\n")
    (a / "evidence").mkdir()
    (a / "evidence" / "shot.txt").write_text("ok\n")
    (a / "STATUS.md").write_text("status\n")
    request = a / "intake" / "request.md"
    request.write_bytes(b"\xef\xbb\xbf" + request.read_bytes().replace(b"\r\n", b"\n")
                        .replace(b"\n", b"\r\n"))
    code, out = w.chantier("summary", "lint", expect=None)
    check("a change in work/, evidence/ or STATUS.md, and a request rewritten with CRLF and a "
          "byte-order mark, make no gap", code == 0, str(out))
    (a / "02-answers.md").write_text("# Decisions\n\nOne.\n")
    (a / "intake" / "02-more.md").write_text("More.\n")
    code, out = w.chantier("summary", "lint", expect=None)
    check("a new `02-answers.md` and a new intake file make the summary late, naming both",
          code == 2 and "02-answers.md new" in out[1] and "intake/02-more.md new" in out[1], str(out))
    before = summary_of(a)
    w.chantier("summary", "set", a, "--title", "Alpha again")
    code, out = w.chantier("summary", "lint", expect=None)
    check("`--title` alone leaves the summary late", code == 2 and "late" in out[1], str(out))
    w.chantier("summary", "set", a, "--unchanged")
    after = summary_of(a)
    code, out = w.chantier("summary", "lint", expect=None)
    check("`--unchanged` closes the gap and leaves the summary as it was",
          code == 0 and after["summary"] == before["summary"] and "02-answers.md" in after["sources"],
          str(out))


def summary_origins(w: World, a: Path) -> Path:
    """E2 item 5: the origin comes from the `issue:` line."""
    b = filed(w, "Summary beta")
    intent = b / "01-intent.md"

    def origin(url: str, *more: str) -> tuple[int, dict | None]:
        intent.write_text(f"# Beta\n\nissue: {url}\n", encoding="utf-8")
        code, _ = w.chantier("summary", "set", b, "--title", "Beta", "--summary", "Beta.", *more,
                             expect=None)
        return code, (summary_of(b)["origin"] if code == 0 else None)

    for url, kind, ref in (("https://github.com/o/r/issues/41", "github", "#41"),
                           ("https://gitlab.com/o/r/-/issues/12", "gitlab", "#12"),
                           ("https://example.atlassian.net/browse/CHT-118", "jira", "CHT-118")):
        code, found = origin(url)
        check(f"an `issue:` line {url} gives the origin {kind} {ref}",
              code == 0 and found is not None and found["kind"] == kind and found["ref"] == ref
              and found["url"] == url, str(found))
    kept = (b / "summary.json").read_bytes()
    code, _ = origin("https://tracker.example.org/t/7")
    check("an unplaced URL is refused (exit 1), and summary.json is not touched", code == 1
          and "--tracker" in w.last_stderr and (b / "summary.json").read_bytes() == kept,
          w.last_stderr)
    code, found = origin("https://tracker.example.org/t/7", "--tracker", "gitlab")
    check("`--tracker gitlab` places it: gitlab #7",
          code == 0 and found is not None and found["kind"] == "gitlab" and found["ref"] == "#7",
          str(found))
    state = tree_bytes(w.state)
    code, _ = w.chantier("summary", "set", a, "--unchanged", "--tracker", "gitlab", expect=None)
    check("`--tracker` with no `issue:` line is refused (exit 1), nothing written",
          code == 1 and tree_bytes(w.state) == state, w.last_stderr)
    return b


def summary_labels(w: World, a: Path, b: Path) -> Path:
    """E2 items 6 and 7: labels and groups."""
    sources = summary_of(a)["sources"]
    w.chantier("summary", "label", a, b, "--add", "Board,cli")
    check("`label --add Board,cli` lowercases and stores both labels on both CRs",
          summary_of(a)["labels"] == ["board", "cli"] and summary_of(b)["labels"] == ["board", "cli"])
    w.chantier("summary", "label", a, b, "--remove", "cli")
    check("`label --remove cli` leaves `board`", summary_of(a)["labels"] == ["board"])
    state = tree_bytes(w.state)
    code, _ = w.chantier("summary", "label", a, b, "--add", "no way", expect=None)
    check("a label with a space is refused (exit 1), nothing written",
          code == 1 and tree_bytes(w.state) == state, w.last_stderr)
    w.chantier("summary", "group", a, b, "--name", "board v1")
    check("`group --name` puts both CRs in the group",
          summary_of(a)["group"] == "board v1" and summary_of(b)["group"] == "board v1")
    w.chantier("summary", "group", b, "--clear")
    check("`group --clear` takes one out of its group, and labels and groups leave `sources` alone",
          not summary_of(b).get("group") and summary_of(a)["group"] == "board v1"
          and summary_of(a)["sources"] == sources)
    d = filed(w, "Summary delta")
    w.chantier("summary", "label", d, "--add", "board")
    code, out = w.chantier("summary", "lint", d, expect=None)
    check("a label on an item with no summary creates the file, and `lint` still says no summary",
          (d / "summary.json").is_file() and code == 2 and "no summary" in out[1], str(out))
    return d


def summary_refusals(w: World, a: Path, d: Path) -> None:
    """E2 items 8 and 9: refused writes, an unreadable file."""
    gone = filed(w, "Summary dropped")
    _, out = w.chantier("abandon", gone)
    trashed = w.work / out[0].removeprefix("abandoned ")
    cases = (
        ("a newline in the summary", (a, "--summary", "one\ntwo")),
        ("a summary of 301 characters", (a, "--summary", "x" * 301)),
        ("a folder of 6-trash", (trashed, "--title", "T", "--summary", "S")),
        ("a path that is not a CR folder", (w.state / "STATUS.md", "--title", "T", "--summary", "S")),
        ("`--unchanged` on a new item", (d, "--unchanged")),
    )
    for label, args in cases:
        state = tree_bytes(w.state)
        code, _ = w.chantier("summary", "set", *args, expect=None)
        check(f"{label} is refused (exit 1), nothing written",
              code == 1 and tree_bytes(w.state) == state, f"{code} {w.last_stderr}")
    original = (a / "summary.json").read_bytes()
    (a / "summary.json").write_text("{not json", encoding="utf-8")
    code, out = w.chantier("summary", "lint", a, expect=None)
    check("`lint` names an unreadable summary.json", code == 2 and "unreadable" in out[1], str(out))
    code, _ = w.chantier("summary", "set", a, "--title", "T", "--summary", "S", expect=None)
    check("`set` on it exits 2 and leaves it as it was",
          code == 2 and (a / "summary.json").read_text(encoding="utf-8") == "{not json", w.last_stderr)
    (a / "summary.json").write_bytes(original)


def summary_moves(w: World, a: Path) -> Path:
    """E2 item 10 in the main checkout: the file moves with its folder; archives are not walked by
    default but are checked when named."""
    _, out = w.chantier("triage", a, "--priority", "P2")
    p2 = w.state / "2-backlog" / "P2" / a.name
    check("`triage --priority P2` keeps summary.json with the folder",
          (p2 / "summary.json").is_file() and not a.exists(), str(out))
    w.chantier("triage", p2, "--ready")
    ready = w.state / "3-ready" / a.name
    check("`triage --ready` keeps it too", (ready / "summary.json").is_file(), str(ready))
    old = w.state / "5-archives" / "261101-1200-901-old-cr"
    old.mkdir(parents=True)
    (old / "01-intent.md").write_text("# Old\n", encoding="utf-8")
    code, out = w.chantier("summary", "lint", expect=None)
    check("an archived CR is not walked by default", "old-cr" not in "\n".join(out), str(out))
    code, out = w.chantier("summary", "lint", old, expect=None)
    check("but is checked when named", code == 2 and "no summary" in out[1], str(out))
    shutil.rmtree(old)
    return ready


def summary_status_bytes(w: World, ready: Path) -> None:
    """E2 items 10 (open) and 11: the STATUS files read the same with or without summary.json."""
    w.start(ready, "--direct", "--slots", 1, *FROM_AGENTS_MD)
    cr = w.at(w.batch()["crs"][0]["path"])
    s = summary_of(cr)
    check("`open` keeps summary.json with the folder", s["title"] == "Alpha again", str(s))
    spare = filed(w, "Summary spare")
    twin = w.root / "proj2"
    shutil.copytree(w.work, twin)
    for p in (twin / ".agents" / "changes").rglob("summary.json"):
        p.unlink()
    rel = f"1-inbox/{spare.name}"
    w.chantier("triage", rel, "--priority", "P3")
    w.chantier("triage", rel, "--priority", "P3", cwd=twin)
    names = sorted(p.relative_to(w.state).as_posix() for p in w.state.rglob("STATUS.*"))

    def read(root: Path, name: str) -> str:  # the minute of each rewrite is the one thing that differs
        return re.sub(r"\d{4}-\d\d-\d\dT[\d:.+Z-]+", "T", (root / name).read_text(encoding="utf-8"))

    same = [n for n in names if read(w.state, n) == read(twin / ".agents" / "changes", n)]
    check("the STATUS files (index, batch, CR) are byte-identical with and without summary.json",
          names and same == names and any(n.startswith("4-batch/2-actives") or n.startswith("4-batch/1-pending")
                                          for n in names), str([n for n in names if n not in same]))


def summary_walk(w: World) -> None:
    """E2 item 12: more than ten gaps print the count first and cut the rest."""
    for i in range(11):
        filed(w, f"Summary many {i}")
    code, out = w.chantier("summary", "lint", expect=None)
    check("more than ten gaps: the count is the first line and the output ends with `… N more lines`",
          code == 2 and re.fullmatch(r"\d+ gap\(s\) in \d+ CRs", out[0]) and len(out) == 10
          and re.fullmatch(r"… \d+ more lines", out[-1]), str(out))


def validate_walk(w: World) -> None:
    """`validate` over the filed items with no summary: every gap printed, each `no summary` line
    the `summary lint` line behind `gap `."""
    _, lint = w.chantier("summary", "lint", expect=2)
    code, out = w.chantier("validate", expect=None)
    check("`validate` exits 0 on gaps only, its count first and every gap printed, never cut at ten",
          code == 0 and re.fullmatch(r"\d+ gap\(s\) in \d+ CRs", out[0]) and len(out) > 10
          and not any("more lines" in ln for ln in out), str(out))
    shown = [ln for ln in lint[1:] if ": no summary" in ln]
    check("each `no summary` line of `validate` is `gap ` and the matching `summary lint` line",
          shown and all(f"gap {ln}" in out for ln in shown), str(out[:3]))


def cr_summary(tmp: Path) -> None:
    note("\n## 21. A CR's summary: the linter and its commands")
    tmp.mkdir()
    w = World(tmp)
    w.build()
    w.chantier("init")
    a = filed(w, "Summary alpha")
    summary_basics(w, a)
    b = summary_origins(w, a)
    d = summary_labels(w, a, b)
    summary_refusals(w, a, d)
    ready = summary_moves(w, a)
    summary_status_bytes(w, ready)
    summary_walk(w)
    validate_walk(w)


def gitlab_ship_merge(w: World) -> None:
    """The slim GitLab path: a Driver opens its merge request through the forge's API and hands
    back, the user's merge reaches the origin, and the forge's own merge call has its shape."""
    note("\n## 22. The GitLab path: open, ship, hand back, merge")
    _, item = prepare_cr(w, "Gitlab path")
    w.start(str(item), "--slots", 1, *FROM_AGENTS_MD)
    w.env["CHANTIER_BATCH"] = w.name
    w.chantier("foreman", "set", "local_foreman_gl", "--epoch", 1)
    fm = Foreman(w, epoch=1)
    fm.turn()
    cr = w.batch()["crs"][0]["id"]
    driver_round(w, cr, "gl.py", "GL = 1\n")
    pr = w.cr(cr)["pr"]
    check(
        "the Driver's PR is a merge request of the GitLab project",
        bool(pr) and pr.startswith(PR_LINK["gitlab"]),
        str(pr),
    )
    w.ready(cr, pr)
    fm.turn()
    check(
        "the Chief of Staff is told the CR is ready, with its merge request",
        bool(fm.asked) and fm.asked[-1] == f"ready-to-merge {cr} {pr}",
        str(fm.asked),
    )
    w.chantier("wait", cr, "add", "approval", "--note", "a review", "--epoch", 1)
    _, shown = w.chantier("wait", cr)
    check(
        "a GitLab approval wait is recorded and named as cleared by hand until proved",
        any("(GitLab approval: cleared by hand until proved)" in x for x in shown),
        str(shown),
    )
    w.chantier("wait", cr, "clear", "w1", "--epoch", 1)
    land(w, w.cr(cr)["branch"])
    w.chantier("order", "merged", cr)
    fm.turn()
    remote = w.sh("git", "ls-remote", "origin", "refs/heads/main").split()[0]
    check(
        "the user's merge ends the CR and the main checkout fast-forwards",
        w.cr(cr)["status"] == "merged"
        and w.sh("git", "rev-parse", "HEAD") == remote
        and (w.work / "gl.py").is_file(),
        str(w.cr(cr)["status"]),
    )
    calls = Path(str(w.gh_state) + ".calls").read_text()
    check(
        "only the Driver called the forge, to create the merge request: nobody merged or edited it",
        '"POST"' in calls and '/merge"' not in calls and '"PUT"' not in calls,
        calls[-300:],
    )
    code, err = merge_pr(w, pr)
    calls = Path(str(w.gh_state) + ".calls").read_text()
    check(
        "the forge's merge call is a PUT on the merge request's merge path, and it answers",
        code == 0 and '"PUT"' in calls and f"merge_requests/{pr.rsplit('/', 1)[-1]}/merge" in calls,
        err or calls[-300:],
    )
    w.env.pop("CHANTIER_BATCH", None)
    w.reset()


CASES = {
    "scenario": scenario,
    "close_batch": close_batch,
    "retro_cases": retro_cases,
    "stack_batch": stack_batch,
    "start_base_forge": start_base_forge,
    "base_from_pr": base_from_pr,
    "stack_waiver": stack_waiver,
    "ready_words": ready_words,
    "ready_words_unplaced": ready_words_unplaced,
    "forge_stack_cli": forge_stack_cli,
    "stack_hold": stack_hold,
    "park_live": park_live,
    "hold_live": hold_live,
    "release": release,
    "granted_fixes": granted_fixes,
    "release_last": release_last,
    "release_on_stack": release_on_stack,
    "release_merge_on_approval": release_merge_on_approval,
    "rails": rails,
    "gate_parallel": gate_parallel,
    "cancel_during_gate": cancel_during_gate,
    "stop_own_gate": stop_own_gate,
    "handback_proofs": handback_proofs,
    "gate_proof": gate_proof,
    "gate_next_merge": gate_next_merge,
    "gate_carry": gate_carry,
    "gate_carry_stack": gate_carry_stack,
    "batch_modes": batch_modes,
    "dependencies": dependencies,
    "early_conflict": early_conflict,
    "changes_tree": changes_tree,
    "direct_batch": direct_batch,
    "seat_handover": seat_handover,
    "foreman_in_a_worktree": foreman_in_a_worktree,
    "remote_board": remote_board,
    "forge_hub": forge_hub,
    "outside_poller": outside_poller,
    "typed_waits": typed_waits,
    "surface_server": surface_server,
    "external_surface": lambda w: external_surface(w.root / "external"),
    "surface_writer": lambda w: surface_writer(w.root / "writer"),
    "cr_summary": lambda w: cr_summary(w.root / "summary"),
    "lost_messages": lost_messages,
    "qa_on_head": qa_on_head,
    "driver_liveness": driver_liveness,
    "restore_cr": restore_cr,
    "empty_batch": empty_batch,
    "running_batch": running_batch,
    "gitlab_ship_merge": gitlab_ship_merge,
}


def remove_tree(path: Path) -> str:
    """Remove a unit's workspace. A file Defender or an indexer holds is retried; what stays is
    named in the returned warning, and never fails the run."""
    left: list[str] = []

    def retry(func, name, *_):
        for attempt in range(5):
            if attempt:  # the first try is at once: a read-only file needs no wait
                time.sleep(0.5)
            try:
                os.chmod(name, 0o700)
                func(name)
                return
            except FileNotFoundError:
                return
            except OSError:
                continue
        left.append(str(name))

    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=retry)
    else:
        shutil.rmtree(path, onerror=retry)
    if path.exists() and not left:
        left.append(str(path))
    if not left:
        return ""
    print(f"warning: could not remove {path}: {left[0]}", file=sys.stderr)
    return f"left {left[0]}" + (f" and {len(left) - 1} more" if len(left) > 1 else "")


def write_scope(w: World) -> None:
    """The end of every unit: git sees nothing outside the planning folder."""
    lines = w.sh("git", "status", "--porcelain", "-uall").splitlines()
    outside = [ln for ln in lines if not ln[3:].startswith(".agents/changes/")]
    check(
        "chantier wrote nothing outside the planning folder (`git status` shows only "
        ".agents/changes/)",
        not outside,
        str(outside[:5]),
    )


def run_unit(unit: str, forge: str, out: Path) -> int:
    """The child process of one unit: its own world, its checks, its transcript and its JSON."""
    ARGS.forge = forge
    count_commands()
    tmp = Path(tempfile.mkdtemp(prefix=f"cs-{unit}-"))
    config = tmp / "gitconfig"  # the identity only: no hook, template or helper of the machine
    config.write_text(
        "[user]\n\tname = scenario\n\temail = scenario@example.com\n", encoding="utf-8"
    )
    os.environ["GIT_CONFIG_GLOBAL"] = str(config)
    w = World(tmp)
    started = time.monotonic()
    left = ""
    scoped = False  # the write-scope check runs once, even after an exception
    try:
        with timed("build"):
            w.build()
        for name in UNITS[unit][2]:
            with timed(name):
                try:
                    CASES[name](w)
                except Exception as e:  # a crash is a failed check with its reason
                    check(f"{name} ran to the end", False, f"{type(e).__name__}: {e}")
                    note(traceback.format_exc())
                    w.env.pop("CHANTIER_BATCH", None)
                    try:
                        w.reset()
                    except OSError:
                        pass
        section_end()
        scoped = True
        write_scope(w)
    except Exception as e:
        check("the unit ran to the end", False, f"{type(e).__name__}: {e}")
        note(traceback.format_exc())
        if not scoped:
            try:
                write_scope(w)
            except Exception as e2:
                check("chantier wrote nothing outside the planning folder", False, str(e2))
    finally:
        section_end()
        if not ARGS.keep:
            subprocess.run(["git", "worktree", "prune"], cwd=w.work, capture_output=True)
            left = remove_tree(tmp)
    elapsed = time.monotonic() - started
    table = timing_table()
    table.append(f"| whole unit | {elapsed:.1f} | {COMMANDS[0]} |")
    LOG.extend(["", "## Timing", "", *table])
    total = CHECKS["pass"] + CHECKS["fail"]
    where = " (kept)" if ARGS.keep else f" ({left})" if left else " (removed)"
    head = [
        f"# chantier scenario, unit {unit} on {forge}: {CHECKS['pass']}/{total} checks passed",
        "",
        f"- Run: {time.strftime('%Y-%m-%d %H:%M:%S')}, {elapsed:.1f} s",
        f"- Workspace: `{tmp}`{where}",
        "",
    ]
    (out / f"{unit}-{forge}.md").write_text("\n".join(head + LOG) + "\n", encoding="utf-8")
    (out / f"{unit}-{forge}.json").write_text(
        json.dumps(
            {
                "unit": unit,
                "forge": forge,
                "checks": total,
                "passed": CHECKS["pass"],
                "failed": FAILED,
                "commands": COMMANDS[0],
                "seconds": round(elapsed, 1),
                "left": left,
            }
        ),
        encoding="utf-8",
    )
    return 0 if not FAILED else 1


def kill_tree(proc: subprocess.Popen) -> None:
    """A unit's process and everything it started: no gate or sleeper outlives the run."""
    import psutil

    try:
        root = psutil.Process(proc.pid)
        procs = root.children(recursive=True) + [root]
    except psutil.NoSuchProcess:
        return
    for p in procs:
        try:
            p.kill()
        except psutil.NoSuchProcess:
            pass
    psutil.wait_procs(procs, timeout=10)


class Running:
    def __init__(self, unit: str, forge: str, run_dir: Path, live: bool):
        self.unit, self.forge = unit, forge
        self.hang = max(HANG_FLOOR_S, 4 * UNITS[unit][0])  # counted from the unit's own start
        self.log = None if live else open(run_dir / f"{unit}-{forge}.out", "w", encoding="utf-8")
        flags = (
            {"start_new_session": True}
            if sys.platform != "win32"
            else {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
        )
        cmd = [sys.executable, __file__, "--child", unit, "--forge", forge, "--out", str(run_dir)]
        cmd += [f"--{k}" for k in ("keep", "verbose") if getattr(ARGS, k)]
        self.t0 = time.monotonic()
        self.proc = subprocess.Popen(cmd, stdout=self.log, stderr=subprocess.STDOUT, **flags)
        self.seconds = 0.0
        self.timed_out = False

    def close(self) -> None:
        if self.log:
            self.log.close()


def unit_row(r: Running, run_dir: Path) -> dict:
    """What a finished unit reports: its JSON, or what a crash left."""
    file = run_dir / f"{r.unit}-{r.forge}.json"
    d = json.loads(file.read_text(encoding="utf-8")) if file.is_file() else {}
    if r.timed_out or not d:
        tail = ""
        out = run_dir / f"{r.unit}-{r.forge}.out"
        if not r.timed_out and out.is_file():
            tail = " ".join(out.read_text(encoding="utf-8", errors="replace").split()[-60:])
        d = {
            "checks": 0,
            "passed": 0,
            "commands": 0,
            "left": "",
            "failed": [] if r.timed_out else [f"the unit crashed with no result: {tail}"],
            **d,
        }
    if not r.timed_out and r.proc.returncode and not d["failed"]:
        d["failed"] = [f"the unit exited with code {r.proc.returncode}"]
    status = (
        "timed out"
        if r.timed_out
        else "FAIL"
        if d["failed"]
        else "over budget"
        if r.seconds > UNITS[r.unit][0]
        else "ok"
    )
    return {
        **d,
        "unit": r.unit,
        "forge": r.forge,
        "seconds": r.seconds,
        "status": status,
        "budget": UNITS[r.unit][0],
    }


def run_all(plan: list[tuple[str, str]]) -> int:
    stamp = f"{time.strftime('%Y%m%d-%H%M%S')}-{os.getpid()}"
    results = HERE / "results"
    run_dir = results / stamp
    run_dir.mkdir(parents=True)
    queue_ = sorted(plan, key=lambda uf: -UNITS[uf[0]][0])  # the longest budget first
    live: dict[tuple[str, str], Running] = {}
    rows: dict[tuple[str, str], dict] = {}
    started = time.monotonic()
    try:
        while queue_ or live:
            while queue_ and len(live) < ARGS.jobs:
                unit, forge = queue_.pop(0)
                live[unit, forge] = Running(unit, forge, run_dir, ARGS.verbose and len(plan) == 1)
            time.sleep(0.2)
            for key, r in list(live.items()):
                r.seconds = time.monotonic() - r.t0
                if r.proc.poll() is None and r.seconds > r.hang:
                    r.timed_out = True
                    kill_tree(r.proc)
                    r.proc.wait()
                if r.proc.poll() is not None:
                    r.close()
                    rows[key] = unit_row(r, run_dir)
                    del live[key]
                    d = rows[key]
                    print(
                        f"{d['status']:>11}  {key[0]} ({key[1]}): {d['passed']}/{d['checks']} "
                        f"checks, {r.seconds:.1f} s",
                        flush=True,
                    )
    finally:
        for r in live.values():  # an exit or a Ctrl-C leaves no gate or sleeper behind
            kill_tree(r.proc)
            r.close()
    wall = time.monotonic() - started
    order = [uf for u in UNITS for uf in plan if uf[0] == u]
    table = [
        "| unit | forge | checks | commands | seconds | budget | status |",
        "| --- | --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for key in order:
        d = rows[key]
        table.append(
            f"| {d['unit']} | {d['forge']} | {d['passed']}/{d['checks']} | {d['commands']} "
            f"| {d['seconds']:.1f} | {d['budget']} | {d['status']} |"
        )
    total = sum(d["seconds"] for d in rows.values())
    summary = [f"wall time: {wall:.1f} s", f"sum of the units' seconds: {total:.1f} s"]
    print("\n" + "\n".join(table) + "\n\n" + "\n".join(summary))
    ds = [rows[k] for k in order]
    warns = [
        f"WARN {d['unit']} ({d['forge']}) over its budget: {d['seconds']:.1f} s > {d['budget']} s"
        for d in ds
        if d["seconds"] > d["budget"] and d["status"] != "timed out"
    ]
    notes = [f"warning: {d['unit']} ({d['forge']}) {d['left']}" for d in ds if d.get("left")]
    hung = [
        f"TIMED OUT {d['unit']} ({d['forge']}): killed with its processes after "
        f"{max(HANG_FLOOR_S, 4 * d['budget'])} s"
        for d in ds
        if d["status"] == "timed out"
    ]
    fails = [f"FAIL {d['unit']} ({d['forge']}): {label}" for d in ds for label in d["failed"]]
    for line in warns + notes + hung + fails:
        print(line)
    transcript = [
        f"# chantier scenario: {len(plan)} unit runs, {wall:.1f} s",
        "",
        *table,
        "",
        *summary,
        "",
        *warns,
        *notes,
        *hung,
        "",
    ]
    for unit, forge in order:
        md = run_dir / f"{unit}-{forge}.md"
        transcript += [
            md.read_text(encoding="utf-8")
            if md.is_file()
            else f"# unit {unit} on {forge}: no transcript ({rows[unit, forge]['status']})",
            "",
        ]
    out = results / f"scenario-{stamp}.md"
    out.write_text("\n".join(transcript), encoding="utf-8")
    print(f"transcript {out}\nunit files {run_dir}")
    return 1 if any(d["status"] in ("FAIL", "timed out") for d in ds) else 0


def main() -> int:
    if ARGS.child:
        return run_unit(ARGS.child, ARGS.forge, Path(ARGS.out))
    plan = [
        (u, f)
        for u, (_, forges, _) in UNITS.items()
        if not ARGS.unit or u in ARGS.unit
        for f in forges
        if not ARGS.forge or f == ARGS.forge
    ]
    if not plan:
        print("no unit runs for this --unit and --forge", file=sys.stderr)
        return 2
    return run_all(plan)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--unit",
        action="append",
        choices=sorted(UNITS),
        help="run this unit only (repeatable); with none, every unit runs",
    )
    parser.add_argument(
        "--forge",
        choices=sorted(FAKE),
        help="restrict the forge; with none, each unit runs on its own forges",
    )
    parser.add_argument("--jobs", type=int, default=JOBS, help="how many units run at once")
    parser.add_argument("--keep", action="store_true", help="keep the temporary workspaces")
    parser.add_argument(
        "--verbose", action="store_true", help="print the transcript live (with one unit)"
    )
    parser.add_argument("--child", choices=sorted(UNITS), help=argparse.SUPPRESS)
    parser.add_argument("--out", help=argparse.SUPPRESS)
    ARGS = parser.parse_args()
    sys.exit(main())
