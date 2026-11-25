# Driver and steering shells

The shell calls of a Driver, a steering session, a Griller and a specification or retro agent.

- No `sleep`, no polling loop (`until grep …; do sleep …; done` is one). A wait is the forge's own watch or the gate, in a background task. Two bounded waits, each once: before a second CI look (`help ci-no-check`), and one `sleep` of at most 30 s after a `pending` asynchronous merge on GitHub.
- A background task is a background shell or a host monitor. Stop yours by its id (`$CHANTIER host stop-own-background-task`) once its result is read or no longer counts; a `$CHANTIER gate` shell is the gate, stopped only with `gate <cr> --stop`. The board and the watcher have their own rules (`help board`, `help watcher`).
- No shell call changes its folder (`cd`, `Set-Location`, `pushd`, alone or chained) into a CR folder, any stage; a steering session never into a worktree. A Driver's shells run from its start folder. Name the target: `git -C <worktree>`, absolute paths, `gh --repo`, `glab -R`. On Windows a process inside a folder keeps it from being moved.
- One command per call when you can; no leading assignment (`X=1 cmd`).
- Read a file before you overwrite it, and edit rather than rewrite a part. UTF-8, no BOM.
- A multi-line forge text (PR body, comment, notes) is a file written with the host's Write tool, passed as `--body-file` or `--notes-file`: never typed, built or written by a shell command.
