# The QA result and its images

- Work in a detached worktree of your own under the same worktrees folder: `git -C <main checkout> fetch <remote> <default branch>`, `git -C <main checkout> worktree add --detach <repo>.worktrees/<folder name> <remote>/<default branch>`; remove it at your end (`git -C <main checkout> worktree remove`).
- `04-result.md`: one finding per bullet (steps, expected, actual); `No findings.` with no bullets when none. Proof in `evidence/` (commands, output, screenshots), long tests and whatever else helps, all in your folder.
- Each screenshot kept shows made-up paths and passes the look (`help pr-images`); one that fails is captured again, and one that cannot be is not kept: `04-result.md` says so in the finding it belonged to.
- Report only what you reproduced.
- Your order's lease: `lease O-k renew --lease <n>` at each wake, and `lease O-k hold --lease <n> [--minutes N]` before a long test (`help lease`).
