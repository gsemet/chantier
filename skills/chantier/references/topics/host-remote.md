# Claude Code: starting a session from Remote Control

From a session driven by Remote Control, every session start (a Foreman, a
Griller) is `mcp__ccd_session__start_session` with **no `cwd` and no `preset`** and
`use_worktree: false`. A start with a `cwd` (the planning surface, the eval root) or a saved
`preset` is refused ("The user is working over Remote Control, and this turn can't start that
session"). With neither, the new session lands in the steering session's own folder, which must be
a main checkout (the surface's, or the project's with the surface as a working directory). What
lies outside reaches it by absolute paths in its prompt; no card names a `cwd`.

A Chief of Staff for remote is started locally (desktop, no worktree), then put in Remote Control;
from there it starts a Foreman or, on the user's word, a Griller in its own folder. Chantier explains the user's steps and never does them. A session the
user creates from the remote client's own "Remote Control" entry lands in a worktree, which blocks
planning on the default branch. Unproved: a session the user creates from the remote client on a
chosen folder.

Documented, unproved here: Worktree is off by default in the desktop app
(<https://code.claude.com/docs/en/desktop>); `claude remote-control --spawn same-dir` keeps the
folder (<https://code.claude.com/docs/en/remote-control>).

[Trials](../../../../docs/proofs/claude-code.md#other-classes-of-session)
