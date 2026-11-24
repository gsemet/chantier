# Drivers: the steering session, the lease, checkpoints

## Means: checkpoint commits

- Before the branch's first push, a checkpoint that is your head may
  be folded into the next round's commit: stage that round's files by name, then `git commit
  --amend -m "<a message for both>"`, and note it (`note <cr> "r<n> folded into <sha>"`). Once
  the branch is pushed, or when the checkpoint is not your head, it stays as it is, with its
  real message: never a rewrite for a message alone (a rebase onto the base is still the
  ordinary rule).

## Means: the steering session's messages

- `[foreman→driver <cr>] note <text>`: decide what it does (next round, restart, after the PR),
  `note` the decision. A `note taken back: <why>` received after your own `handback ready`
  means the steering session took the CR back for you: the CR is yours again, `handoff <cr>`
  for where it stands, then go on from `<why>` as from a prompt's `Note:` (a `rebase:` as `driver-retake.md` "CR driver:
  re-takes" says). Any other note received after your hand-back, with no `taken
  back:`, is not work to start: pass it to the steering session as the refused line above.
  `ping`: `[driver <cr>→foreman] pong <step>`. When the `Steering:` line says nothing reaches the steering session before your end, a `ping` gets no answer: go on. `stop`: stop a long gate of yours that
  is running (`gate <cr> --stop`) and every other background task of yours, then `handback blocked stopped`; when the steering session's
  stop comes with a switch of mode (to Foreman or to direct mode), the note says so.

## Means: the lease

Read when you wait, or when a lease is refused. Your lease is 10 minutes, renewed by every command
that carries `--lease <n>` (the number `take` printed); times in its texts are UTC.

- Renew at each wake: the next command carries `--lease <n>`, or run `lease <cr> renew --lease
  <n>`; with `driver-wake`, at its wake. A wait over 3 minutes (a worker's run,
  a test) runs `lease <cr> hold --lease <n> [--minutes N]` before the wait (45 by
  default, 90 at most), and again at a wake when the wait goes on; `hold` runs nothing.
- A long gate of yours, running or waiting in the queue, keeps the lease live with no `hold`.
- Not confirmed: the lease ran out while you waited (past a hold too; a running gate is never stopped), which is not a failure and not "gone". Your next
  command with the current number is accepted (the log notes `lease-late`) while nobody took the CR
  again; read it with `lease <cr>`.
- `claim lost`: the steering session took the CR again, or ended your lease (`cancel`, `order
  drop`, `order hold`, `agents set <cr> -`). Stop at once, record nothing more, tell the Foreman.
- Reclaim is the steering session's: `take --reclaim` after it checked with the host that the
  Driver ended, or on the user's word for a live lease. A Driver never reclaims.
- A refusal you do not understand (a write, a `take`, a push): run `$CHANTIER access <cr> --lease
  <n>` before you ask; it explains and changes nothing.
