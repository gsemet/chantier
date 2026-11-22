"""The `cli.run` op: one chantier command of a client logged in with `chantier login`, run as a
child process of this build in the served planning folder, on this machine. The server judges the
arguments itself (never trusting the client's), and gives back the command's output, its exit code
and its launch form. The command edits what it edits when run locally; the server adds nothing."""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Mapping
from typing import Any

from chantier import plugin_files
from chantier.board.api.result import Result, fail
from chantier.board.context import Context
from chantier.board.projects import Project
from chantier.board.reads import found
from chantier.core import remote_wire as wire

TIMEOUT_S = 600.0
NOT_FOUND = "not found"
NUL = "\x00"


def child_env(server: Mapping[str, str], client: Mapping[str, str]) -> dict[str, str]:
    """The child's environment: the server's without any name a client may send (a command never
    speaks for the session that started the server), then the client's, then the mark that tells
    the command it runs for a client."""
    kept = {k: v for k, v in server.items() if k not in wire.FORWARDED_ENV}
    return {**kept, **client, wire.VIA_SERVER: "1"}


def _nul(a: Any) -> bool:
    texts = [*a.argv, *a.env, *a.env.values(), a.project or "", a.stdin or ""]
    return any(NUL in t for t in texts)


def judge(a: Any) -> tuple[str, str | None]:
    """The command's name and why its arguments are refused (a 400), or None."""
    from chantier.cli import Usage, _parser  # noqa: PLC0415 - the CLI imports every command

    if _nul(a):
        return "", "cli.run: a NUL character in the arguments"
    if outside := sorted(set(a.env) - set(wire.FORWARDED_ENV)):
        return "", f"cli.run: env {outside[0]} is not one a client may send"
    parser = _parser(quiet=True)
    try:
        cmd = str(parser.parse_args(a.argv).cmd)
    except Usage as e:
        return "", f"cli.run: {e}"
    if cmd in wire.NEVER_REMOTE:
        return cmd, f"cli.run: {cmd} does not run through the server"
    if opt := wire.holds_taken_over(a.argv, parser, cmd):
        return cmd, f'cli.run: argv holds {opt}: the server names the project from "project"'
    return cmd, None


def command(project: Project, argv: list[str]) -> list[str]:
    """The child's command line: this interpreter, the chantier package, this build's skill, and
    the project's folder when it is in an external surface."""
    option = ["--project", str(project.repo.project_folder)] if project.repo.external else []
    skill = str(plugin_files.skill_dir())
    return [
        sys.executable,
        "-m",
        "chantier",
        "--profile",
        "local",
        "--skill",
        skill,
        *option,
        *argv,
    ]


def _text(raw: bytes) -> str:
    return raw.decode("utf-8", "replace").replace("\r\n", "\n")


def run(ctx: Context, a: Any) -> Result:
    cmd, why = judge(a)
    if why is not None:
        return fail(400, why)
    project = found(ctx, a.project or ctx.projects.home_id)
    if project is None:
        return fail(404, NOT_FOUND)
    repo = project.repo
    ctx.runs.begin()
    try:
        done = subprocess.run(
            command(project, a.argv),
            cwd=repo.surface_root if repo.external else repo.root,
            input=(a.stdin or "").encode("utf-8"),
            capture_output=True,
            timeout=TIMEOUT_S,
            env=child_env(os.environ, a.env),
            check=False,
        )
    except subprocess.TimeoutExpired:
        return fail(504, f"cli.run: {cmd} ran past {TIMEOUT_S:g} s; stopped")
    finally:
        ctx.runs.end()
    ctx.settle(project)
    return Result(
        200,
        {
            "code": done.returncode,
            "stdout": _text(done.stdout),
            "stderr": _text(done.stderr),
            "version": ctx.version,
            "launch": plugin_files.cli_command(repo),
        },
    )
