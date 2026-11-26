# The main checkout after a merge (part 2 of 2)

The first step that says no stops the whole attempt, nothing more done, with its `<why>`:
1. The project's rules (`$CHANTIER rules`) forbid changing it now: `the project's rules forbid it: <rule, quoted short>`.
2. `git symbolic-ref --quiet --short HEAD` is not `<default>`: `on <branch>, not <default>` (or `detached HEAD`).
3. `git status --porcelain --untracked-files=no` not empty: `tracked changes: <up to three paths>`. Untracked files are never listed, read, moved or deleted.
4. `git fetch <remote> <default>` fails: `fetch failed: <git's text>`.
5. Note `git rev-parse HEAD` as `<before>`, then only `git merge --ff-only --no-overwrite-ignore <remote>/<default>`: never pull, reset, rebase, stash, clean, checkout, switch, nor a merge without both flags. Git refuses: retry nothing; `<why>` is its reason in a few words (`diverged from <remote>/<default>`, `untracked file in the way: <path>`, or git's text). The host refuses: try no other way, `refused by the host: <exact text>`.
Then `$CHANTIER note <cr> "main checkout: fast-forwarded to <sha7>"` (or `already at <sha7>`, or `not fast-forwarded: <why>`) on the last merge handled, no `--epoch`, no ask. If `git diff --quiet <before> HEAD -- uv.lock` exits 1, add `; uv.lock changed: sync pending`: only the Chief of Staff syncs.
