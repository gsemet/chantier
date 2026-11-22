"""`chantier webui`: the web board's link with its key; the surface server started, detached,
when none runs. It asks nothing, takes no seat and opens no browser: typing it is the yes."""

from __future__ import annotations

import argparse
import shlex
from typing import Any

from chantier.board import running
from chantier.board.address import is_loopback, local_url, url
from chantier.board.command import BEYOND, _running_lines
from chantier.board.projects import open_projects
from chantier.core.errors import EXIT_EXTERNAL, ChantierError
from chantier.hub.feed import Board
from chantier.hub.watch import START_S, STEP_S
from chantier.plugin_files import cli_command

STOPS_IDLE = "board: stops by itself after 30 min with no client (webui started it)"
NOT_STARTED = "webui: the server did not start within 20 s: run {cli} serve and read its error"


def _answering(board: Board, found: tuple[dict[str, Any], str] | None) -> bool:
    return found is not None and isinstance(
        board.probe(found[0]["host"], found[0]["port"], found[1]), dict
    )


def webui(args: argparse.Namespace, board: Board | None = None) -> list[str]:
    board = board or Board()
    projects = open_projects()
    repo = projects.home
    found = board.recorded(repo.git_dir)
    if found is not None:
        if not _answering(board, found):
            raise ChantierError(f"webui: {running.silent_text(found[0])}", EXIT_EXTERNAL)
        entry, key = found
        return _running_lines((entry["host"], entry["port"]), key, False, entry)
    cli = cli_command(repo)
    board.spawn([*shlex.split(cli), "serve", "--stop-idle"], projects.surface or repo.root)
    deadline = board.clock() + START_S
    while True:
        found = board.recorded(repo.git_dir)
        if _answering(board, found):
            break
        if board.clock() >= deadline:
            raise ChantierError(NOT_STARTED.format(cli=cli), EXIT_EXTERNAL)
        board.sleep(STEP_S)
    assert found is not None
    entry, key = found
    host, port = entry["host"], entry["port"]
    lines = [f"board on {url(host, port, key)} over {entry.get('served')}"]
    if local := local_url(host, port, key):
        lines.append(f"on this machine: {local}")
    if not is_loopback(host):
        lines.append(BEYOND.format(host=host))
    lines.append(STOPS_IDLE)
    return lines
