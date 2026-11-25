# Claude Code: the write guard

The plugin's mod reads one line of a spawn's prompt, `writes: <absolute folder>; <absolute
folder>` (a worker's: the worktree first, the CR folder second; a CR Driver's: its CR folder, then
the archive path when `take` prints one). It knows no role. A spawn whose prompt holds the line
starts in the first folder, except one with a `worktree:` line (a CR Driver's: in that worktree,
or, before it exists, in the root its first line names); with neither, in its parent's folder,
still guarded, with a note on the board. The mod rewrites `cwd` except on a resume.

That agent's Write, Edit or NotebookEdit outside every folder is refused with `refused: <path> is
outside the folders this agent may write in (<folders>); write there`. An entry is a bare absolute
path (anything after it is part of the name: every write is refused). A Git Bash drive path
(`/c/Users/...`) is read as its drive form.

The shell calls and what is not guarded: `help host-write-guard-shell`.
