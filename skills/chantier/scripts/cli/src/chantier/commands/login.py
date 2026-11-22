"""`chantier login` and `chantier logout`: the profiles file's only writers. A login probes the
server's `board.get` with the link's key, then stores the address, the key and the projects."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from chantier.clients import profiles as store
from chantier.clients import remote
from chantier.clients.profiles import Profile, Profiles
from chantier.commands.live import from_link
from chantier.core import clock
from chantier.core.errors import EXIT_EXTERNAL, EXIT_USAGE, ChantierError

PROBE_S = 10.0
DEFAULT_NAME = "default"
KINDS = {"write": "private", "read": "read-only"}


def _kind(profile: Profile) -> str:
    return KINDS[profile.access]


def _listing(profiles: Profiles) -> list[str]:
    if not profiles.items:
        return ["no profile: commands run here"]
    return [
        f"{n} → {p.url} ({_kind(p)}, for {', '.join(p.projects)})"
        + (" (default)" if n == profiles.default else "")
        for n, p in sorted(profiles.items.items())
    ]


def _probe(base: str, key: str) -> tuple[dict[str, Any], str | None]:
    """The server's `board.get` and the access its answer says the key has."""
    try:
        reply = remote.post(base, key, "board.get", {}, PROBE_S)
    except remote.Unreachable as e:
        raise ChantierError(
            f"login: no chantier server answers at {base}: {e}", EXIT_EXTERNAL
        ) from e
    if reply.status == remote.UNAUTHORIZED:
        raise ChantierError(
            "login: the server refused the key: give the link it printed (chantier webui "
            "prints it)",
            EXIT_EXTERNAL,
        )
    if reply.status != remote.OK or reply.data is None:
        raise ChantierError(
            f"login: the server at {base} answered {reply.status}: {reply.error}", EXIT_EXTERNAL
        )
    return reply.data, reply.access


def _projects(asked: list[str], data: dict[str, Any]) -> list[str]:
    served = [str(p["id"]) for p in data.get("projects") or []]
    names = [Path(a.replace("\\", "/").rstrip("/")).name for a in asked]
    for name in names:
        if name not in served:
            raise ChantierError(
                f"login: --project {name}: the server serves {', '.join(served) or 'none'}",
                EXIT_USAGE,
            )
    home = data.get("home") or (served[0] if len(served) == 1 else None)
    if not names and not home:
        raise ChantierError(
            f"login: the server serves {', '.join(served) or 'no project'}: name one with "
            "--project <id>",
            EXIT_USAGE,
        )
    return list(dict.fromkeys(names or [str(home)]))


def login(args: argparse.Namespace) -> list[str]:
    profiles = store.load()
    if not args.link:
        return _listing(profiles)
    name = args.profile or DEFAULT_NAME
    if name == store.LOCAL:
        raise ChantierError("login: `local` is not a profile name: it means no profile", EXIT_USAGE)
    base, key = from_link(args.link)
    data, access = _probe(base, key)
    version = str(data.get("version") or "unknown")
    if access not in KINDS:
        raise ChantierError(
            f"login: the server at {base} runs an older chantier ({version}): stop it and "
            "start it again (chantier serve) from this version",
            EXIT_EXTERNAL,
        )
    ids = _projects(list(args.projects), data)
    profiles.items[name] = Profile(
        url=base,
        key=key,
        access=access,
        projects=ids,
        origin=data.get("origin") or None,
        served=str(data.get("served") or ""),
        version=version,
        saved=clock.now(),
    )
    if not args.no_default:
        profiles.default = name
    store.save(profiles)
    default = profiles.default == name
    head = (
        f"logged in: profile {name} → {base} (chantier {version} over "
        f"{profiles.items[name].served}) for {', '.join(ids)}, {KINDS[access]}, "
        f"{'the default' if default else 'not the default'}"
    )
    if access == "read":
        return [
            head,
            "read-only: live and webui use it; every other command needs the private link",
        ]
    if not default:
        return [head, f"--profile {name} runs a command there"]
    return [
        head,
        f"every chantier command for {', '.join(ids)} now runs on that server; other projects "
        "run here; --profile local runs one here, chantier logout ends it",
    ]


def logout(args: argparse.Namespace) -> list[str]:
    profiles = store.load()
    name = args.profile or profiles.default
    if name is None or name not in profiles.items:
        return [f"logout: no profile {name}" if name else "logout: no profile"]
    del profiles.items[name]
    if profiles.default == name:
        profiles.default = None
    store.save(profiles)
    stays = (
        f"the default stays {profiles.default}" if profiles.default else "commands run here again"
    )
    return [f"logged out: profile {name}; {stays}"]
