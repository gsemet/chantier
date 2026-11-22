"""A repository's identity on the forge: its `origin` remote's URL, normalized, so the same
repository reached by https, by ssh or as `git@host:path` is one value (a profile tells the
surfaces of one machine apart by it)."""

from __future__ import annotations

import re
from pathlib import Path

from chantier.core.git import git

_URL = re.compile(r"^[a-z][a-z0-9+.-]*://(?:[^@/]*@)?([^/:]+)(?::\d+)?/(.*)$", re.I)
_SCP = re.compile(r"^(?:[^@/:\\]+@)?([^/:\\]{2,}):(?!//)(.*)$")


def normalize_origin(url: str | None) -> str | None:
    """`host/path` in lower-case host, with no scheme, user, port, `.git` or trailing `/`; None
    for an empty value. A local path is kept as it is, with `/`."""
    text = (url or "").strip()
    if not text:
        return None
    found = _URL.match(text) or _SCP.match(text)
    host, path = (found[1].lower(), found[2]) if found else ("", text.replace("\\", "/"))
    path = path.strip("/").removesuffix(".git").rstrip("/")
    return f"{host}/{path}" if host else path


def origin_of_folder(folder: Path) -> str | None:
    """The normalized `origin` of the repository that holds `folder`; None with no such remote or
    no such folder. Nothing is fetched."""
    if not folder.is_dir():
        return None
    return normalize_origin(git("remote", "get-url", "origin", cwd=folder, check=False))
