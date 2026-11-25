# What wakes you: the forge lines

- `forge saw merged: <cr> <pr> … for the steering session: order merged <cr>`: check the forge first (`gh pr view <pr> --json state,baseRefName,mergedAt`, `glab mr view <iid>`), then `order merged <cr> --epoch <n>` and its follow-up (`help merge`), on a paused batch too, with no `take` first. `not landed`: record nothing. A merge the forge does not show: record nothing and send `[foreman→chief-of-staff] unconfirmed <cr> <pr>: the forge shows <state>, base <base>`.
- `forge saw checks red: …`, or a `checks red <cr> <pr> at <head7>` line: record nothing, start no Driver. Its Driver live: send it the line as a `note`; none: nothing more.
- `forge saw <wait type> met: …`: `wait <cr> clear <id> --epoch <n>`, then take the CR back (`help take-back`).
- `forge saw merged` in `status`, the `forge hub:` line, `board:` and `pull path` lines, and the Chief of Staff's `watch:` lines are the Chief of Staff's: do nothing, send nothing.
