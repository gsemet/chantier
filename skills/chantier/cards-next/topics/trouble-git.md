# A git command in the wrong place

- A Driver and its workers write nothing in the repository's git folder (`.git/info/exclude`, `.git/config`, `.git/hooks`), by any tool or shell command; git's own commands write there as git does. A file to ignore is ignored by the worktree's own files (a `.gitignore` change goes through a `coder`, as any project file) or not at all; a file that should not be committed is simply not staged (staging is by name).
- The main checkout moves only by the steering session's post-merge fast-forward, never by a Driver's command.
- A git command run in the wrong place by mistake: stop, undo only what is safe to undo (`git -C <main checkout> rebase --abort`, `merge --abort`), and `note` it. Anything else left in the main checkout goes to the steering session as it is, by `msg steering anomaly` (stack driver) or a `blocked question:` hand-back, never cleaned by force.
