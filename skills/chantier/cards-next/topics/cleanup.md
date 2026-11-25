# Kept worktrees

At the last CR the CLI removes the merged CRs' worktrees and branches (`cleanup:` lines). A CR whose agent is still held, or whose worktree git refused to remove, is kept (`kept:` or `not removed:`). Remove it once its Driver has ended: `git worktree remove <path>`, then `git branch -D <branch>` (`-d` refuses after a rebase or squash merge), from the main checkout, or `git -C <clone>` (the clone `take` names) with a planning surface; or leave it to the user's word at `close`, which names it.
A trashed CR's worktree and branch stay for the user's word at `close`. Those of a CR moved to the backlog or to `3-ready` stay too, and are not offered for removal.
