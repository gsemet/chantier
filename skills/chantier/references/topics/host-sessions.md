# Claude Code: classes of session

| Class | Known by | Fit for a Foreman |
| --- | --- | --- |
| Desktop, typed | no Remote Control notice | yes, it starts it alone |
| Desktop, Remote Control | the host's Remote Control notice | yes, on a main checkout: a new Foreman in its own folder, or the last one reused |
| Main checkout | `git rev-parse --git-dir` equals `--git-common-dir` | yes |
| Worktree | they differ | no: Write refuses the main checkout, `change_directory` is refused, `request_directory` does not help |
| Remote or app session | often starts in a linked worktree `.claude/worktrees/<name>`: the row above | no |
| Cloud | the host's environment | no: no main checkout (unproved) |
| Planning surface | its folder is the surface's checkout, or the project's clone with the surface as a working directory; P6 and P7 accept both, refuse a linked worktree of either | yes: it writes the planning folder by absolute paths; a session started with no `cwd` lands there |

With no argument the Chief of Staff's batches are direct in the Remote Control row and wherever
the Foreman-mode P1 fails (terminal, VS Code), Foreman in the "Desktop, typed" row. A session in a
worktree cannot move to the main checkout: the user starts a new session there (`help
host-for-you`). Whether a surface session may write the project's clone and worktrees outside its
folder is **unproved**.

[Trials](../../../../docs/proofs/claude-code.md#other-classes-of-session)
