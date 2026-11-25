# The lease

Your lease on your unit (the CR, `stack`, or a QA order `O-k`) is 10 minutes, renewed by every command that carries `--lease <n>`, the number `take` or the order printed. Times in its texts are UTC.
- Renew at each wake: the next command carries `--lease <n>`, or run `lease <unit> renew --lease <n>`. Before a wait over 3 minutes (a worker's run, a test, CI), run `lease <unit> hold --lease <n> [--minutes N]` (45 minutes by default, 90 at most), and again at a wake when the wait goes on. `hold` runs nothing.
- A long gate of yours, running or queued, keeps the lease live with no `hold`.
- `not confirmed`: the lease ran out while you waited, a hold included. It is no failure and not "gone": your next command with the current number is accepted (the log notes `lease-late`) while nobody took the unit again; read it with `lease <unit>`. A running gate is never stopped for it.
- `claim lost`: the steering session took the unit again or ended your lease (`cancel`, `order drop`, `order hold`, `agents set <cr> -`). Stop at once, record nothing more, tell the steering session.
- `take --reclaim` is the steering session's, after it checked with the host that the Driver ended, or on the user's word for a live lease. A Driver never reclaims.
- A refusal you do not understand (a write, a `take`, a push): `access <unit> --lease <n>` explains it and changes nothing.
