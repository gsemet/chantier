# The main checkout after a merge

A convenience, never a gate: a skip costs nothing, asks nothing, has no workaround. Yours alone. Run it right after you handle `order merged <cr>` (before its `order done`) or your own; several merges in one turn get one attempt after the last. With a planning surface: `git -C <clone>` (the clone `take` names), never the surface's checkout. `<remote>`, `<default>`: the project's. Stop at the first no, with its `<why>`:
1. The project's rules forbid it: `the project's rules forbid it: <rule, short>`.
2. `git symbolic-ref --quiet --short HEAD` is not `<default>`: `on <branch>, not <default>` (or `detached HEAD`).
3. `git status --porcelain --untracked-files=no` not empty: `tracked changes: <up to three paths>`. Untracked files are never listed, moved or deleted.
4. `git fetch <remote> <default>` fails: `fetch failed: <git's text>`.
5. Note `git rev-parse HEAD` as `<before>`, then only `git merge --ff-only --no-overwrite-ignore <remote>/<default>`: never pull, reset, rebase, stash, clean, checkout, switch, nor a merge without both flags. Git refuses: retry nothing; `<why>` is its reason. The host refuses: try no other way, `refused by the host: <exact text>`.
Then `$CHANTIER note <cr> "main checkout: fast-forwarded to <sha7>"` (or `already at <sha7>`, or `not fast-forwarded: <why>`) on the last merge handled, no `--epoch`, no ask. If `git diff --quiet <before> HEAD -- uv.lock` exits 1, add `; uv.lock changed: sync pending`: you never sync.
