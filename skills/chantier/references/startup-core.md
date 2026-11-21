# Chantier startup core

`$CHANTIER` is the CLI, prepared only as your skill or prompt gives it. Write `$CHANTIER` out in
full, as given, in each shell call, never in a shell variable. If it cannot run (the launch
fails: uv or uvx cannot set it up or start it, or the CLI crashes on start), in either mode, at
any call, report the exact error and stop: no work as the role, no seat, nothing written in the
planning folder, never "without it". Do not upgrade, reinstall, repair, relaunch another way, or
choose another source or tool; retry once only on a transient network error. A steering session
tells the user; a started agent ends its turn with the error as plain text. A CLI refusal, a
command's own error exit and a host's permission denial keep their handling. The CLI is never a
tool a role works without. One named exception: in the dev mode, a `uv sync` that chantier's own
processes block (holding the checkout's `.venv`; os error 32 on Windows) is not a launch failure:
the session goes on unsynced with `sync pending`, as its skill's `$CHANTIER` paragraph says,
and stops nothing that paragraph does not name.

No fallback: a tool, a model, an agent or a `$CHANTIER` command not available exactly as named is
a stop, reported with its error; never a look-alike, a workaround or an estimate. A skill or tool
the playbook names and the session lacks is not a stop: your card says how.

Other checks are read-only and block only the actions whose prerequisite failed. Permissions are
scoped to this session, project and effect; a started agent inherits only its role's, never merge
or publication permission. Report role, project, checked state, blocked actions and causes,
pending permissions, authorized effects and evidence limits: failed, unavailable or not
performed; available, documented, exercised, server-announced, not tested or skipped. Never
invent capacity: a host path not exercised is labelled untested.

Before an action, read every reading the manifest lists for it; one that cannot be read blocks
that action only.

No shell call changes its folder (`cd`, `Set-Location`, `pushd`, alone or chained before a
command) into a CR folder (any stage), whatever your role: name the target with absolute paths.
On Windows a process whose current folder is inside a folder keeps that folder from being moved
(WinError 32), so the CR's next move fails.
