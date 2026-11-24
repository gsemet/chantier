"""The start lines of `chantier serve`: the links, the exposure and the file watch's mode, and
the lines of a board that already runs."""

from __future__ import annotations

from typing import Any

from chantier.board.address import is_loopback, local_url, url
from chantier.board.watch_files import NOTIFY

NOT_APPLIED = (
    "--ui not applied: a board already serves this surface; stop it to change what it serves"
)
BEYOND = (
    "board: listens on the local network ({host}); the private link acts: give it to the user "
    "only, plain HTTP"
)
READ_ONLY = "read-only: {link} (it shows the board and acts on nothing; it can be shared)"
LOCAL_READ_ONLY = "on this machine, read-only: {link}"
NO_NETWORK = "board: no local network address found; on this machine only"
WATCHES = "board: watches the planning files"
CHECKS = "board: no file notifications here; checks every 5 s"
STOPS_IDLE = "board: stops by itself after 30 min with no client (a watcher started it)"
FORGE_WHEN_OBSERVED = (
    "board: the running board reads the forge only while a client is subscribed (a watcher "
    "started it); the pull path gets no forge event until one is"
)


def read_only_lines(host: str, port: int, read_key: str) -> list[str]:
    """The public read-only link, and its 127.0.0.1 form when it differs; none for a file with
    no read-only key."""
    if not read_key:
        return []
    lines = [READ_ONLY.format(link=url(host, port, read_key))]
    if local := local_url(host, port, read_key):
        lines.append(LOCAL_READ_ONLY.format(link=local))
    return lines


def files_line(mode: object) -> str | None:
    """The start line of the file watch's mode (`server.json`'s `files`); None for none."""
    return WATCHES if mode == NOTIFY else CHECKS if mode else None


def running_lines(  # noqa: PLR0913, PLR0917 - the address, the keys and the running entry
    there: tuple[str, int],
    key: str,
    ui_given: bool,
    entry: dict[str, Any] | None = None,
    forge_always: bool = False,
    read_key: str = "",
) -> list[str]:
    """The lines of a board already running: its link, its exposure, its file watch (from its
    `server` entry), what this start could not apply, and last its idle stop."""
    entry = entry or {}
    lines = [f"board already running at {url(*there, key)}"]
    if local := local_url(*there, key):
        lines.append(f"on this machine: {local}")
    lines.extend(read_only_lines(*there, read_key))
    if not is_loopback(there[0]):
        lines.append(BEYOND.format(host=there[0]))
    if found := files_line(entry.get("files")):
        lines.append(found)
    if ui_given:
        lines.append(NOT_APPLIED)
    if forge_always and entry.get("forge") != "always":
        lines.append(FORGE_WHEN_OBSERVED)
    if entry.get("stop_idle"):
        lines.append(STOPS_IDLE)
    return lines
