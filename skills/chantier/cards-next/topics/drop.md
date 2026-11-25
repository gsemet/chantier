# A dropped CR's PR

- A drop order whose line ends `close its PR <link>` (a trash drop outside a stack; after `cancel` for a live CR): close it before its `order done`, with `gh pr close <n>` or `glab mr close <n>`, no `--delete-branch`, no comment.
- One that ends `turn its PR to draft <link>` (a drop to the backlog or `3-ready` outside a stack, the PR out of draft; after `cancel` for a live CR): `gh pr ready <n> --undo` or `glab mr update <n> --draft` (unproved), no comment.
- In a stack: `help stack-drop`. A dropped held or parked CR with dependents: `help park`.
- The worktree and branch of a trashed CR, or of one moved to the backlog or `3-ready`, are never removed by you (`help cleanup`).
