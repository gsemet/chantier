# Drivers: hand-backs out of the ordinary

## Means: hand-backs out of the ordinary

- When the host asks for your hand-back while the CR's work remains, record
  your state with `$CHANTIER note <cr> "…"`, then `handback <cr> blocked context: host asked the
  hand-back at <n> tokens while waiting for <what>: <where it stopped, what is next>` (`<n>` is the
  last `context:` figure; `<what>` is what the turn waited for: a worker's reply, the gate, CI; a
  turn that ended to wait for a worker's reply had broken "a worker is never resumed by a message"),
  then the host's hand-back.
- For PR in draft the `handback ready` line says the PR's draft state and the CR (and PR) it waits on, and
  asks for no change on the forge: turn nothing draft or ready, retarget nothing, do not stop; the
  hand-back is done.
- The steering session checks the rule `--no-gate` quotes, and sends the CR back with a note if it does not
  hold: run the long gate, then hand back again without `--no-gate`.
- `handback <cr> blocked <reason>` takes `question:`, `approval:`, `merge:`, `fix:`, `infra:`, `budget:`,
  `rounds:`, `refused`, `waits: <what>`, `context: <where it stopped, what is next>` or `context:
  closing: <where it stopped>; next: <what is left>` (the CR driver's closing hand-off). A Driver whose context is ending records its state with `$CHANTIER note <cr> "…"`,
  then hands back `blocked context:`; the steering session restarts a fresh Driver from it. A decision
  only the user can take is `blocked question: <text>`. A Driver that handed back ready may be resumed
  later by a `taken back:` note.
- A release PR is a draft while its base is not the default branch, and turns ready when the stack driver
  retargets it and it is green. A project that shows it otherwise (a label, a title prefix, no draft at
  all) is followed as written, on the opening and on turning ready. A forge or plan that refuses a draft
  stops that step: `handback blocked refused <exact text>` (the stack driver: its `anomaly` line).
- a CR whose `take` or `handoff` prints
  `gate: waived (O-<k>, …)` runs no long gate and hands back with no `--no-gate`: the CLI
  reads the recorded waiver and prints `long gate waived (O-<k>): validated by CR-<top>'s gate`
  (or `follow-up <folder>`) in the line to send;
  under a rule that asks a local run, a waived CR that owes the local run (the long-gate bullet's
  "by shape") still runs `$CHANTIER gate` at its pushed head
  before it takes its PR out of draft for its ready hand-back, unless the waiver's words name that
  gate: read them in `$CHANTIER status`'s order list (`O-<k> waive <cr> <note>`), or, when the
  order is no longer listed or its note is cut, in your CR's `STATUS.json` (`gate.waiver`); it
  still hands back with no `--no-gate`;
  the stack's top, whose `gate:` line says `this
  CR's long gate validates the stack`, runs its gate as any CR does, and a fix its gate finds
  goes on the top PR or a PR above it;
- `blocked waits: <what>` is for a thing already on its way (the stack driver, another CR) that no one
  decides: the CR shows 🟠, and the steering session takes it back when that thing lands.
- A Driver still recorded on a CR it handed back `blocked` (a `waits:` that landed, a `question:`
  answered to it, an `infra:` that cleared) hands back `ready <link>` directly once its checks
  hold (the same ones as for any ready hand-back); the CLI records `ready after blocked: <reason>`
  and prints `it was blocked: <reason>`. A release keeps the `take --note` route.
  A hand-back refused with `<cr> is ready` or `<cr> is blocked` (a refusal naming `take <cr>
  --note`) means the CR was not taken back after its earlier hand-back. Keep the commits, the gate and the verdict, which bind to the
  head. Pass the refused line, as printed, to the steering session (`[driver <cr>→foreman] …`,
  by the host's means) and wait for its `taken back:` note, then hand back again. A hand-back
  refused with `the worktree's head … is not the head ship recorded`: `ship` at this head, then
  the long gate and a new `verifier` given the move (unless the move was a clean rebase, whose
  pass and verdict carry), then hand back again. A hand-back refused
  with `<cr> is merged: no Driver to hand it back` means the user merged the PR while you were
  finishing. Do not push, edit the PR, retarget it or turn it ready or draft any more. Record
  what you left undone in one line, `$CHANTIER note <cr> "merged before the hand-back; left
  undone: <what>"` (`none` when nothing), pass the refused line as printed to the steering
  session (`[driver <cr>→foreman] …`, by the host's means), and end.
- A block that is a wait of a known type (`answer`, `approval`, `pipeline`, `merge`) is recorded
  with `handback <cr> blocked <reason> --wait <type>[=<ref>]`, repeatable: `answer="<the
  question>"`, `approval` (the recorded PR), `pipeline[=<sha>]` (the recorded head), `merge[=<link>]`
  (the recorded PR); the hand-back line ends `; waits: w1 approval`, and `$CHANTIER wait <cr>` lists
  them. A wait that does not end you: `wait <cr> add <type> [--ref <ref>] --note "<text>"`. The
  steering session clears a wait (`wait <cr> clear <id> --epoch <n>`) and takes the CR back; a
  `--wait` the CLI refuses is not worked around: hand back without it, the refusal named in the
  reason.
- `budget:` follows only a CLI refusal on the budget (`take` or `round`, exit 5: `round` is
  refused once the budget is spent, and the budget is checked before the round limit, so with
  both spent you hand back `budget:`, not `rounds:`); never skip a proof pass to save budget:
  `gate`, `verdict`, `ship`, `note` and `handback` are never refused for it.
