# Recording merges

- A `forge saw merged: <cr> ...` line (in `status` or a watcher) is a merge the user made: record it once the forge confirms it (`help watcher-events`): `order merged <cr>`, then Foreman mode sends its line to the Foreman; with `foreman watch: running` tell the user, record nothing. `landed with <other cr>` is a merge to record; only `not landed ...` is not: tell where the PR went and wait for the PR under it. Several PRs merged in one action: `order merged` for each.
- A CR taken out and whose PR the user merges later (its folder in the backlog or `3-ready`, with `formerly.json`): on "I merged #n", `order add --note <folder>` (brings back its number and PR), then `order merged <cr>` at once (Foreman mode: both lines in one message, the add first). With no batch open say it is recorded the same way in the next batch and leave the folder. A Driver's `blocked question: its PR <link> is already merged`: `order merged <cr>`.
- A Foreman's `merged early <cr>: left undone: <note>`: offer it to the user as an inbox item.
- Parallel batch: the first CR ready to merge wins; the user merges in the order they become ready unless told otherwise.
- GitLab: a fold (`forge-stack show` prints `folded into <cr below>`) is recorded at once, a rule that keeps its precedence over the forge check (`help merge-stack-gitlab`).
