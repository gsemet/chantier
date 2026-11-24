"""The `watch` command's handler: its arguments checked, then the watcher (`watch.py`) run, or
the pull path (`watch --once --after SEQ`)."""

from __future__ import annotations

import argparse

from chantier.core.errors import EXIT_PRECONDITION, ChantierError
from chantier.core.repo import Repo
from chantier.hub import times as hub_times
from chantier.hub.watch import Watch, run
from chantier.hub.watch_reads import Rules, checked, once
from chantier.plugin_files import read_wake_rules


def watch(args: argparse.Namespace) -> list[str] | tuple[list[str], int]:
    repo = Repo.find()
    last = checked(repo, args)
    if args.once:
        return once(repo, args.after, args.audience or [])
    rules = read_wake_rules(repo)
    if rules["events_problems"]:
        raise ChantierError(
            f"watch: {rules['events_problems'][0]}: fix it, then start the watcher again",
            EXIT_PRECONDITION,
        )
    return run(
        Watch(
            repo,
            last if args.after is None else args.after,
            rules=Rules(
                args.audience or [],
                hub_times.wake_every_s(rules["seconds"]),
                rules["other"],
                args.stream,
            ),
        )
    )
