"""The surface's writer: the surface server's thread that commits, rebases and pushes the planning
surface's published paths (`projects/` and the root `chantier.yaml`, never the surface's other
files), and pushes with them every local commit of the surface's branch. One writer per surface
and machine, elected by `chantier/writer.lock` in the git folder; its record is the `writer` entry
of `server.json`; its `sync-*@1` lines go through the journal's one append function.

`times.py` holds the cycle's times and their test seam, `record.py` the entry, `paths.py` the
writer's pathspec, `git_ops.py` the git commands (English messages, nothing forced, hooks never
skipped), `cycle.py` the cycle (commit, fetch, integrate, push), `loop.py` the election and the
thread, `lines.py` the texts the CLI and the board print."""
