"""The profiles file: where `chantier login` keeps a server's address and key for the projects it
was logged in for. One file, `profiles.json`, in the user's config folder, outside any project;
nothing else is read or written here. The same folder also holds `live.json`, the column widths of
`chantier live`, which `clients/tui/widths.py` reads and writes with the path `commands/live.py`
passes it."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from chantier.core.errors import EXIT_PRECONDITION, ChantierError

FILE = "profiles.json"
LOCAL = "local"  # `--profile local`: no profile, the command runs here
HOME_ENV = "CHANTIER_CONFIG_HOME"


@dataclass
class Profile:
    url: str
    key: str
    access: str  # "write" (the private key) or "read"
    projects: list[str]
    origin: str | None
    served: str
    version: str
    saved: str


@dataclass
class Profiles:
    default: str | None = None
    items: dict[str, Profile] = field(default_factory=dict[str, Profile])

    def names(self) -> str:
        return ", ".join(sorted(self.items)) or "none"


def config_dir() -> Path:
    """The folder of the user's chantier configuration: `$CHANTIER_CONFIG_HOME` as it is, else
    `platformdirs`' roaming user configuration folder. On Windows that is `chantier` in the
    roaming application data folder (`%APPDATA%`, asked of Windows itself, not read from the
    variable). On macOS it is `~/Library/Application Support/chantier`, elsewhere
    `~/.config/chantier`; on both, an absolute `XDG_CONFIG_HOME` gives
    `$XDG_CONFIG_HOME/chantier` instead, and a relative one is ignored."""
    if home := os.environ.get(HOME_ENV):
        return Path(home)
    import platformdirs

    return Path(platformdirs.user_config_dir("chantier", appauthor=False, roaming=True))


def path() -> Path:
    return config_dir() / FILE


def _bad(where: Path, reason: str) -> ChantierError:
    return ChantierError(f"profiles: {where}: {reason}: fix or delete it", EXIT_PRECONDITION)


def _profile(where: Path, name: str, raw: Any) -> Profile:
    try:
        found = Profile(**raw)
        shaped = (
            isinstance(found.url, str)
            and isinstance(found.key, str)
            and found.access in ("write", "read")
            and isinstance(found.projects, list)
            and all(isinstance(p, str) for p in found.projects)
            and (found.origin is None or isinstance(found.origin, str))
        )
    except TypeError as e:
        raise _bad(where, f"profile {name}: {e}") from e
    if not shaped:
        raise _bad(where, f"profile {name} is malformed")
    return found


def load() -> Profiles:
    """The profiles; none when the file is not there. A file that does not parse is an error
    (exit 2), never a silent local run."""
    where = path()
    if not where.is_file():
        return Profiles()
    try:
        data = json.loads(where.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as e:
        raise _bad(where, str(e).splitlines()[0] if str(e) else "unreadable") from e
    if not isinstance(data, dict) or not isinstance(data.get("profiles"), dict):
        raise _bad(where, "no `profiles` object")
    default = data.get("default")
    if default is not None and (not isinstance(default, str) or default not in data["profiles"]):
        raise _bad(where, f"the default {default!r} is no profile")
    items = {n: _profile(where, n, v) for n, v in data["profiles"].items()}
    return Profiles(default, items)


def save(profiles: Profiles) -> None:
    """Write the file atomically (a temporary file in the folder, then `os.replace`), mode 0600
    on POSIX; the folder is made when it is not there."""
    where = path()
    where.parent.mkdir(parents=True, exist_ok=True)
    body = {
        "default": profiles.default,
        "profiles": {n: asdict(p) for n, p in sorted(profiles.items.items())},
    }
    fd, name = tempfile.mkstemp(dir=where.parent, prefix=".profiles-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as out:
            out.write(json.dumps(body, indent=2, ensure_ascii=False) + "\n")
        if sys.platform != "win32":
            os.chmod(name, 0o600)
        os.replace(name, where)
    except BaseException:
        Path(name).unlink(missing_ok=True)
        raise
