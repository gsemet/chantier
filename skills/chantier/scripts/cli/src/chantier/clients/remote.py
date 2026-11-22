"""The client of a profile's server: which command goes there (`active`), the HTTP call (`post`),
and `forward`, which sends one command to the server's `cli.run` and prints what comes back. The
profiles file is read here and nowhere else on the way (`profiles`)."""

from __future__ import annotations

import argparse
import http.client
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from chantier import __version__
from chantier.clients import profiles as store
from chantier.clients.profiles import Profile, Profiles
from chantier.clients.tui.link import HEADER
from chantier.core.errors import EXIT_EXTERNAL, EXIT_USAGE, ChantierError
from chantier.core.origin import origin_of_folder
from chantier.core.remote_wire import FORWARDED_ENV, NEVER_REMOTE, strip
from chantier.core.repo import Repo, SurfaceChoice
from chantier.plugin_files import cli_command

ACCESS = "X-Chantier-Access"
CLIENT = f"chantier-remote/{__version__}"
OK, UNAUTHORIZED, FORBIDDEN, NOT_FOUND = 200, 401, 403, 404
RUN_TIMEOUT_S = 630.0  # above the server's 600 s
READ_ONLY = (
    "remote: profile {name} holds the read-only key: commands need the private link "
    "(chantier login <private link>)"
)
GATE = (
    "gate runs on the server's machine, not through a profile: run it there, or here with "
    "--profile local"
)


class Unreachable(Exception):
    """No answer from the server: the reason."""


@dataclass
class Reply:
    status: int
    access: str | None
    data: dict[str, Any] | None
    error: str | None


def post(base: str, key: str, op: str, body: dict[str, Any], timeout: float) -> Reply:
    """`POST <base>api/v1/call/<op>` with the key in its header (proxies as the environment says:
    a profile's address is a link the user gave). `Unreachable` when nothing answers."""
    request = urllib.request.Request(
        urllib.parse.urljoin(base, f"api/v1/call/{op}"),
        json.dumps(body).encode("utf-8"),
        {HEADER: key, "Content-Type": "application/json", "User-Agent": CLIENT},
        method="POST",
    )
    try:
        with urllib.request.build_opener().open(request, timeout=timeout) as r:
            status, raw, headers = r.status, r.read(), r.headers
    except urllib.error.HTTPError as e:
        status, raw, headers = e.code, e.read(), e.headers
    except (OSError, ValueError, http.client.HTTPException) as e:
        raise Unreachable(str(getattr(e, "reason", None) or e)) from e
    text = raw.decode("utf-8", "replace")
    try:
        found = json.loads(text)
    except ValueError:
        found = None
    data = found.get("data") if isinstance(found, dict) else None
    said = found.get("error") if isinstance(found, dict) else None
    error = str(said) if said else " ".join(text.split()) or f"HTTP {status}"
    return Reply(status, headers.get(ACCESS), data if isinstance(data, dict) else None, error)


@dataclass
class Picked:
    """The command's project: its id, and the planning folder chantier would open for it on this
    machine (`surface`: its repository's normalized `origin`, or None; `local`: whether one
    exists), with the local repository found."""

    id: str
    local: bool = False
    origin: str | None = None
    repo: Repo | None = None


def picked(project: str | None) -> Picked | None:
    """The project the CLI's own resolution names, read-only: `--project`, else the working
    folder's. None when neither names one (the command then runs here, as today)."""
    try:
        repo = Repo.find(project=project, readonly=True)
    except SurfaceChoice:
        return None
    except ChantierError:
        if project:  # names no local folder: its last component is its id
            return Picked(Path(project.replace("\\", "/").rstrip("/")).name)
        return None
    pid = (repo.project_dir or repo.root).name
    where = repo.surface if repo.external else repo.root
    local = bool(where and repo.changes.is_dir())
    return Picked(pid, local, origin_of_folder(where) if local and where else None, repo)


def active(
    profiles: Profiles, named: str | None, found: Picked | None
) -> tuple[str, Profile] | None:
    """The profile that takes this command, or None: `--profile local` none; `--profile <name>`
    that profile, for a project in its list; else the default, for a project in its list whose
    local surface, if any, has the profile's `origin`. No project picked: none."""
    if named == store.LOCAL or found is None:
        return None
    if named:
        profile = profiles.items.get(named)
        if profile is None:
            raise ChantierError(
                f"--profile {named}: no such profile ({profiles.names()}, or local)", EXIT_USAGE
            )
        if found.id not in profile.projects:
            raise ChantierError(
                f"--profile {named}: logged in for {', '.join(profile.projects)}, not "
                f"{found.id}: chantier login <link> --profile {named} --project {found.id}",
                EXIT_USAGE,
            )
        return named, profile
    profile = profiles.items.get(profiles.default or "")
    if profile is None or profiles.default is None or found.id not in profile.projects:
        return None
    if found.local and found.origin != profile.origin:
        return None
    return profiles.default, profile


def _choose(args: argparse.Namespace) -> tuple[str, Profile, Picked] | None:
    """The profile that takes this command, with its project; None when it runs here. The file
    is not read for `--profile local` (the server's child never reads it)."""
    if args.profile == store.LOCAL:
        return None
    profiles = store.load()
    if args.profile is None and profiles.default is None:
        return None
    found = picked(args.project)
    chosen = active(profiles, args.profile, found)
    return None if chosen is None or found is None else (chosen[0], chosen[1], found)


def profile_for(args: argparse.Namespace) -> tuple[str, Profile] | None:
    """The profile `live` and `webui` use for their link, by the same rule as a command's."""
    taken = _choose(args)
    return None if taken is None else (taken[0], taken[1])


def _refused(status: int, said: str, name: str, base: str) -> str:
    if status == UNAUTHORIZED:
        return (
            f"the server at {base} refused the key of profile {name}: log in again with the "
            "link it prints (chantier webui)"
        )
    if status == FORBIDDEN:
        return (
            f"the server at {base} takes profile {name}'s key as read-only: log in with the "
            "private link"
        )
    if status == NOT_FOUND and said.startswith("unknown op"):
        return (
            f"the server at {base} runs an older chantier with no remote commands: stop it and "
            "start it again (chantier serve) from this version"
        )
    return said


def _own_form(args: argparse.Namespace, local: Repo | None) -> str:
    """This machine's launch form, as a Driver block's `cli:` line should hold it."""
    form = cli_command(local if local is not None and not local.external else None)
    if args.profile:
        form += f' --profile "{args.profile}"'
    if args.project:
        form += f' --project "{args.project}"'
    return form


def _stdin(args: argparse.Namespace) -> str | None:
    """The client's stdin, for `journal add --json -` only."""
    if args.cmd == "journal" and getattr(args, "action", None) == "add" and args.json == "-":
        return sys.stdin.buffer.read().decode("utf-8-sig")
    return None


def forward(
    args: argparse.Namespace, argv: list[str], parser: argparse.ArgumentParser
) -> int | None:
    """Send the command to the profile's server and print its answer; its exit code. None when
    the command runs here: no profile takes it, or it is one that never runs remotely."""
    if args.cmd in NEVER_REMOTE and args.cmd != "gate":
        return None
    taken = _choose(args)
    if taken is None:
        return None
    name, profile, found = taken
    if args.cmd == "gate":
        raise ChantierError(GATE, EXIT_USAGE)
    if profile.access != "write":
        raise ChantierError(READ_ONLY.format(name=name), EXIT_USAGE)
    body = {
        "argv": strip(argv, parser, args.cmd),
        "project": found.id,
        "env": {k: os.environ[k] for k in FORWARDED_ENV if k in os.environ},
        "stdin": _stdin(args),
    }
    try:
        reply = post(profile.url, profile.key, "cli.run", body, RUN_TIMEOUT_S)
    except Unreachable as e:
        raise ChantierError(
            f"remote: profile {name}: no chantier server answers at {profile.url}: {e}; run it "
            "here with --profile local, or chantier logout",
            EXIT_EXTERNAL,
        ) from e
    data = reply.data or {}
    if reply.status != OK or "code" not in data:
        said = reply.error or f"HTTP {reply.status}"
        raise ChantierError(
            f"remote: {_refused(reply.status, said, name, profile.url)}", EXIT_EXTERNAL
        )
    own, theirs = _own_form(args, found.repo), str(data.get("launch") or "")
    out, err = (str(data.get(k) or "") for k in ("stdout", "stderr"))
    if theirs:
        out, err = out.replace(theirs, own), err.replace(theirs, own)
    sys.stdout.write(out)
    sys.stderr.write(err)
    return int(data["code"])
