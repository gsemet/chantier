# Driver and steering shells (part 2 of 2)

- No shell call changes its folder (`cd`, `Set-Location`, `pushd`, alone or chained) into a CR folder, any stage; a steering session never into a worktree. A Driver's shells run from its start folder. Name the target: `git -C <worktree>`, absolute paths, `gh --repo`, `glab -R`. On Windows a process inside a folder keeps it from being moved.
- A steering session opened outside the repository sets `CHANTIER_ROOT` to it.
- One command per call when you can; no leading assignment (`X=1 cmd`).
- Read a file before you overwrite it, and edit rather than rewrite a part. UTF-8, no BOM.
- A multi-line forge text (PR body, comment, notes) is a file written with the host's Write tool, in `work/` or where your card or the project keeps it, passed as `--body-file` or `--notes-file`: never typed, built or written by a shell command. A one-line plain text (a title, a `--note`) and a commit message are not covered.
