"""The plugin's launcher (`skills/chantier/scripts/chantier.py`, run as `uv run --script`): it
picks the mode (dev or plugin) by the one rule, then runs the CLI by the one method AGENTS.md
describes, the argument list unchanged (`--skill` added in the plugin mode when absent). With
`--print` first it prints that launch form and runs nothing; with `--sync` first it runs the dev
mode's checked sync (`references/sync-checkout.md`, steps 1 to 4) and never stops a process.
Standard library only: it runs in uv's own script environment, never the checkout's `.venv`."""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

from chantier.launch import (
    dev_launch,
    plugin_launch,
    session_project,
    sync_check_line,
    sync_line,
)

ROOT_OPTIONS = ("--project", "--profile", "--skill")  # the CLI's root options that take a value
IN_SYNC = "in sync"
SYNCED = "synced"
PENDING = "sync pending: held by "
UNLISTED = "an unlisted process"
PLUGIN_NO_SYNC = "plugin mode: no sync (only chantier's own checkout syncs)"
MISSING_UV = "chantier launcher: uv is not on PATH (uv is the one tool chantier needs)"
OUTDATED = "The environment is outdated"
HELD = "os error 32"
MISSING_CODE = 127  # the shell's code for a command not found
PS_FIELDS = 3  # `ps -eo pid,ppid,args`


class Runner:
    """How the launcher starts processes; the tests pass a fake that records the commands."""

    def capture(self, cmd: list[str]) -> tuple[int, str, str]:
        """Run `cmd` to its end, its output read: (exit code, standard output, standard error)."""
        done = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False
        )
        return done.returncode, done.stdout, done.stderr

    def run(self, cmd: list[str]) -> int:
        """Run the CLI with the launcher's standard streams and return its exit code. On POSIX the
        launcher replaces itself (`os.execvp`): no process of its own is left between the host and
        the CLI. On Windows it waits for the child; on Ctrl-C it keeps waiting, as the child gets
        the same console signal."""
        env = child_env()
        if os.name != "nt":
            sys.stdout.flush()
            os.execvpe(cmd[0], cmd, env)
        child = subprocess.Popen(cmd, env=env)
        while True:
            try:
                return child.wait()
            except KeyboardInterrupt:
                continue


def child_env() -> dict[str, str]:
    """The CLI's environment: the launcher's, without the `VIRTUAL_ENV` that `uv run --script`
    set to the launcher's own environment (else the dev form's `uv run` warns on each call)."""
    env = dict(os.environ)
    venv = env.get("VIRTUAL_ENV")
    if venv and os.path.normcase(os.path.realpath(venv)) == os.path.normcase(
        os.path.realpath(sys.prefix)
    ):
        env.pop("VIRTUAL_ENV")
    return env


class ListingFailed(Exception):
    """The holders of `.venv` could not be listed."""


def root_options(argv: list[str]) -> dict[str, str]:
    """The CLI's root options that take a value (`--project`, `--profile`, `--skill`, either
    `--name value` or `--name=value`), read before the first word that is not an option; the list
    itself is left unchanged."""
    found: dict[str, str] = {}
    i = 0
    while i < len(argv) and argv[i].startswith("-"):
        name, eq, value = argv[i].partition("=")
        if name in ROOT_OPTIONS:
            if eq:
                found[name] = value
            elif i + 1 < len(argv):
                found[name] = argv[i + 1]
                i += 1
        i += 1
    return found


def skill_of(root: Path) -> Path:
    return root / "skills" / "chantier"


def mode(root: Path, cwd: Path, project: str | None) -> str:
    """`dev` when the plugin root holds `.git` (a folder or a worktree's file: chantier's own
    checkout) and the session's project is chantier; `plugin` in every other case."""
    return _mode(root, session_project(cwd, project)[0])


def _mode(root: Path, chantier: bool) -> str:
    return "dev" if (root / ".git").exists() and chantier else "plugin"


def launch_form(which: str, root: Path, folder: Path | None) -> str:
    """The launch form the run uses, as `plugin_files.cli_command` writes it: `--project
    "<folder>"` added for a project in a planning surface."""
    base = dev_launch(root) if which == "dev" else plugin_launch(root, skill_of(root))
    return base + (f' --project "{folder.as_posix()}"' if folder else "")


def command(which: str, root: Path, argv: list[str]) -> list[str]:
    """The command the launcher runs, as a list (no shell): the dev form or the plugin form, then
    the argument list unchanged; `--skill <skill folder>` only when `argv` carries none."""
    if which == "dev":
        return [*shlex.split(dev_launch(root)), *argv]
    prefix = shlex.split(plugin_launch(root, skill_of(root)))
    if "--skill" in root_options(argv):
        prefix = prefix[:-2]  # the user's own `--skill`
    return [*prefix, *argv]


def _tokens(line: str) -> list[str]:
    return [t.strip('"') for t in shlex.split(line, posix=False)]


def _holder(pid: int, line: str) -> str:
    """`PID <n> <subcommand> <project>` from a holder's command line (the project's folder name,
    from `--project`, left out when absent); a `serve` with `--stop-idle` and no `--seat` adds
    `(started by webui)`."""
    words = _tokens(line)
    names = [w.replace("\\", "/").rsplit("/", 1)[-1].lower().removesuffix(".exe") for w in words]
    if "chantier" not in names:  # not a chantier command (a test run, a shell): its program
        return f"PID {pid} {names[0] if names else '?'}"
    rest = words[names.index("chantier") + 1 :]  # after the `chantier` executable, or `-m chantier`
    opts = root_options(rest)
    sub = next(
        (
            w
            for i, w in enumerate(rest)
            if not w.startswith("-") and not (i > 0 and rest[i - 1] in ROOT_OPTIONS)
        ),
        "?",
    )
    text = f"PID {pid} {sub}"
    project = opts.get("--project", "").replace("\\", "/").rstrip("/").rsplit("/", 1)[-1]
    if project:
        text += f" {project}"
    seat = any(w == "--seat" or w.startswith("--seat=") for w in rest)
    if sub == "serve" and "--stop-idle" in rest and not seat:
        text += " (started by webui)"
    return text


def _ps_literal(text: str) -> str:
    """`text` in a PowerShell single-quoted `-like` pattern: quotes doubled, brackets escaped."""
    return text.replace("'", "''").replace("[", "`[").replace("]", "`]")


def listing_command(root: Path) -> list[str]:
    """The host row's read-only listing of the processes that run from `<root>/.venv`."""
    if os.name == "nt":
        venv = _ps_literal(str(root).replace("/", "\\") + "\\.venv\\*")
        script = (
            "ConvertTo-Json -Compress -InputObject @(Get-CimInstance Win32_Process | "
            f"Where-Object {{ $_.ExecutablePath -like '{venv}' }} | "
            "Select-Object ProcessId, ParentProcessId, CommandLine)"
        )
        return ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script]
    return ["ps", "-eo", "pid,ppid,args"]


def _rows(root: Path, out: str) -> list[tuple[int, int, str]]:
    """(pid, parent pid, command line) of each process the listing printed for `<root>/.venv`."""
    if os.name == "nt":
        text = out.strip()
        data = json.loads(text) if text else []
        items = data if isinstance(data, list) else [data]
        return [
            (int(d["ProcessId"]), int(d["ParentProcessId"]), d.get("CommandLine") or "")
            for d in items
            if isinstance(d, dict)
        ]
    mark = f"{root.as_posix()}/.venv/"
    rows = []
    for line in out.splitlines()[1:]:
        parts = line.split(None, PS_FIELDS - 1)
        if (
            len(parts) == PS_FIELDS
            and mark in parts[2]
            and parts[0].isdigit()
            and parts[1].isdigit()
        ):
            rows.append((int(parts[0]), int(parts[1]), parts[2]))
    return rows


def holders(root: Path, runner: Runner) -> list[str]:
    """The holders of `<root>/.venv`, read-only: a process and its child under `.venv` are one
    holder, named by the top process."""
    cmd = listing_command(root)
    try:
        code, out, err = runner.capture(cmd)
    except OSError as e:
        raise ListingFailed(f"{cmd[0]}: {e}") from e
    if code != 0:
        raise ListingFailed((err or out).strip() or f"{cmd[0]} exited {code}")
    try:
        rows = _rows(root, out)
    except (ValueError, KeyError, TypeError) as e:
        raise ListingFailed(f"unreadable listing: {e}") from e
    pids = {pid for pid, _, _ in rows}
    return [_holder(pid, line) for pid, parent, line in rows if parent not in pids]


def _said(out: str, err: str) -> str:
    return "\n".join(t for t in (out.strip(), err.strip()) if t)


def _failed(code: int, text: str) -> int:
    """uv's failure, passed on: its text on standard error, its exit code."""
    if text:
        print(text, file=sys.stderr)
    return code


def sync(which: str, root: Path, runner: Runner) -> int:
    """The dev mode's checked sync: the check (step 1), then `_sync_held`. The plugin mode syncs
    nothing."""
    if which != "dev":
        print(PLUGIN_NO_SYNC)
        return 0
    code, out, err = runner.capture(shlex.split(sync_check_line(root)))
    if code == 0:
        print(IN_SYNC)
        return 0
    text = _said(out, err)
    if code != 1 or OUTDATED not in text:  # an ordinary failure, never `sync pending`
        return _failed(code, text)
    return _sync_held(root, runner)


def _sync_held(root: Path, runner: Runner) -> int:
    """Steps 2 to 4: the holders named, the sync when there are none, else `sync pending: held
    by …` (exit 0: the session goes on unsynced). It stops no process."""
    try:
        held = holders(root, runner)
    except ListingFailed as e:
        where = f"{root.as_posix()}/.venv"
        return _failed(1, f"chantier launcher: cannot list the holders of {where}: {e}")
    if not held:
        code, out, err = runner.capture(shlex.split(sync_line(root)))
        if code == 0:
            print(SYNCED)
            return 0
        text = _said(out, err)
        if HELD not in text:
            return _failed(code, text)
        held = [UNLISTED]
    print(PENDING + ", ".join(held))
    return 0


def main(
    argv: list[str],
    root: Path | None = None,
    cwd: Path | None = None,
    runner: Runner | None = None,
) -> int:
    """The launcher: `[--print | --sync] [root options] [<command> ...]`. `root` is the plugin
    root (the folder that holds `skills/chantier`), `cwd` the working folder."""
    root = (root or Path(__file__).resolve().parents[6]).resolve()
    runner = runner or Runner()
    first = argv[0] if argv else ""
    rest = argv[1:] if first in ("--print", "--sync") else argv
    chantier, folder = session_project(cwd or Path.cwd(), root_options(rest).get("--project"))
    which = _mode(root, chantier)
    try:
        if first == "--print":
            print(launch_form(which, root, folder))
            return 0
        if first == "--sync":
            return sync(which, root, runner)
        return runner.run(command(which, root, rest))
    except FileNotFoundError:
        print(MISSING_UV, file=sys.stderr)
        return MISSING_CODE
