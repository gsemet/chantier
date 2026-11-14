"""The `chantier` commands. Each returns the lines to print; errors raise ChantierError with an
exit code.

The CLI is the frame the agents work in: the CR lifecycle in `.agents/changes/` (the stages,
the batch folders, the record and the STATUS files), the batch's limits (slots, budget, rounds,
the user's word on an irreversible action), the means to synchronise (orders, asks, notes, the
long gate's lock) and a few tools (the project's rules, the cost). The agents do the work, git
and the forge included; the CLI names what they create (branches, worktrees), keeps the record,
and runs no git command that changes anything: it reads the head, the remote and the status to
say what is off, and no forge command at all. One named exception, in `board/`: `chantier
board`, the web board's server, for the user in remote; it writes only its key file in the git
folder, takes its dependencies (starlette, uvicorn) from the root pyproject.toml, and knows no
role.
"""
