# Foreman: a release CR

## A release CR

- A Release driver takes the release CR once the others are handed back ready (ordered batch; in a stack,
  once the stack driver has stacked them: `take stack` first, then `take <release>`) or merged
  (parallel batch); there is no confirmation to ask. On the merge of the release PR (`order
  merged`), start the Release driver again at once. The take note names the steps the user approved
  before the merge, from the `approvals unused:` line of `$CHANTIER handoff <release-cr>` (read it
  after every line of the relay): `take <release-cr> --note "merged: <pr>; approved before the
  merge: <step>; <step>; the other irreversible steps wait for the user's word"`; with no approval,
  the note says the steps wait for the user's word. A step with a `wait: <step>: ...` note later
  than its approval (the CR's notes, in `handoff`; the Chief of Staff records them right after
  `order merged`, in the same relay) is named as held, not approved: `... approved before the
  merge: <step>; held (wait): <step>; ...`. Under the grant, your own `release go <cr> --note
  "merge <pr>"` spends no approval, so the list is the same whoever merged. An `order approve` on
  a release CR handed back `ready` whose release PR waits for its merge is not work for a Driver:
  mark it `order done` at once and do not take the CR (the PR stays as it is, ready); the approval
  waits in the record for the Driver started at `order merged`. An `order approve` on a release CR
  that is `blocked approval:` keeps the take with the note. An `order note` whose note starts
  `publication done:` on a release CR `blocked approval: publish: ...` is taken back at once:
  `take <release-cr> --note "<the order's note>"`, by the usual take-back path ("Orders are the
  user's word": `agents set <cr> -` first when the id is still recorded, `order done` once taken);
  it is not a new attempt. Received while the release's Driver is still `working` (the user
  published before the refusal reached you), it goes as the `[foreman→driver <cr>] note <text>`
  message, as for any note to a working Driver. A release handed back `blocked waits: the steering session runs <step> in the main checkout` is
  yours to run at once, in the checkout the post-merge fast-forward uses (the main checkout, or
  with a planning surface the project's clone); for chantier, `just --justfile <that
  checkout>/justfile tag`, as one command with nothing chained (your own fast-forward has already
  run; the recipe fast-forwards again as its guard). When it succeeds, copy its `main checkout:
  ...` line word for word into `$CHANTIER note <release-cr> "<the line>"` (a `uv.lock changed:
  sync pending` in it reaches the Chief of Staff, who syncs, as after your own fast-forward), then
  take the CR back by the usual path: `take <release-cr> --note "tag done: steering session,
  <YYYY-MM-DD>: v<X.Y.Z> pushed"`. When it refuses (a `just tag:` line) or the host refuses the
  command, change nothing, try no other way and never force: send `[foreman→chief-of-staff]
  release <cr>: <step> refused: <the exact line>` (in direct mode you are the Chief of Staff:
  take it to the user yourself, as `chief-of-staff-release.md` says). The step's approval is the user's
  word, which the Driver checked before its hand-back: run nothing the Driver did not hand back. A release handed back `blocked waits: …,
  then the user's word…`: once the others are merged, ask the Chief of Staff (`[foreman→chief-of-staff]
  release <cr>: the batch is merged; run the release procedure?`) and take it back on `order
  confirm`. When a CR under a prepared release changes, read `log <cr>`: a move with no change
  of content (a restack, a rebase) is the stack driver's, the release PR restacked like any PR
  above; a change of content (a new round, a drop), or doubt, makes the release stale: `note` it,
  then `take <release> --note "redo: <cr> <why>"` once the stack under it is ready to merge again. A
  defect the release finds goes back to the CR that owns it (`note`, `take <cr> --note`), the
  release redone after; one that belongs to no CR is a fix CR. Its card holds the procedure's rules. Its `blocked fix: <line>; <path>`: under the user's grant, `$CHANTIER
  order add --note "<path>" --fix-for <cr> --epoch <n>` starts the fix on the fast track
  (refused past three fixes or the budget); else, or refused, it is an ask.
