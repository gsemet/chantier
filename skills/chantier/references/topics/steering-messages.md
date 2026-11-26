# Messages with the steering session

Send a line with `$CHANTIER msg steering anomaly|blocked|note "<text>" --cr <unit> --lease <n>`: `anomaly` and `blocked` wake the steering session, a `note` waits for its next wake. With no watcher it prints `not delivered` and exits non-zero: then use your host's means (`$CHANTIER host driver-messages-steering-direct`) or the hand-back. `inbox` lists what reached you.

A message to you:
- `[foreman→driver <cr>] note <text>`: decide what it does (next round, restart, after the PR) and `note` the decision.
- `note taken back: <why>`, received after your own `handback ready`: the CR is yours again; `handoff <cr>`, then go on from `<why>` as from a prompt's `Note:` (a `rebase:` is `help retake`). Any other note after your hand-back is not work to start: pass it to the steering session as the refused line.
- `ping`: `[driver <cr>→foreman] pong <step>`. When the `Steering:` line says nothing reaches the steering session before your end, a ping gets no answer: go on.
- `stop`: `gate <cr> --stop` for a long gate of yours, stop every other background task of yours, then `handback <cr> blocked stopped`. A stop that comes with a switch of mode says so in the note.
- A prompt with no `Steering:` line is a gap: `note` it and use the host's row.
