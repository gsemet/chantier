# Foreman: a hold, a park, a mode switch

## A held CR

- **A held CR** (the Chief of Staff's `order hold <cr>` or `order unhold <cr>` on the user's word,
  in `status`): a held CR is out of the slots and the order, in every batch mode.
  - Held while ready (a stack): take the stack driver, `take stack --note "hold <cr>"` (or
    `"unhold <cr>"`), then `order done <O-n>`.
  - Held while working: its Driver is still running. Send it `[foreman→driver <cr>] stop hold:
    <O-n>`; it answers `stopped: held; worktree clean|dirty: <files>`. Then `agents set <cr> -
    --epoch <n>`, in a stack `take stack --note "hold <cr>"`, and `order done <O-n>`; its slot is
    free only then: fill it (a queued CR's take) after the hold's `order done`, never before.
    Its worktree and branch stay as they are. Direct mode does this part itself.
  - Dependents (the open CRs whose `after` names it, and in a series those started on it) wait
    with it: no take for them, no release, until `order unhold <cr>` or `order drop <cr>`.
  - On the user's `order unhold <cr>` of a CR held while working, it comes back `blocked`: take
    it before any queued CR (`take <cr> --note "unhold: <O-n>" --epoch <n>`), with a new Driver;
    it resumes as a `resume:` does, with no round counted. In a stack it joins as a working CR
    (the next `take stack` prints it `not on its place`; send its Driver `note rebase: stacked
    on <cr below>`): no `take stack --note "unhold <cr>"` for it (a ready CR unheld in a stack
    keeps that take). If no slot is free, the take is refused: wait for one.
  - A release already working when a CR is held: let it hand back, `note` it stale, then `take
    <release> --note "redo: <cr> held"`.
  - Never take a held CR for a round. A held CR does not count in the final-order take, and
    neither the final-order take nor `take <release>` starts while a CR is held: send one ask
    `the release waits: <cr> is held (order O-n)`. The same for a parked CR: `the release waits:
    <cr> is parked (<what it waits for>)`; a CR parked while the release is working or ready: once
    it is back and handed back ready, `take <release> --note "redo: <cr> back from park"`. A parked
    CR and its dependents count as a held CR does (out of the final-order take), and a queued CR
    whose dependency is parked is one "whose dependency is blocked".

## Parking a CR on an outside wait

- **Parking a CR on an outside wait** (no question to anyone, once the wait is recorded). A CR
  whose work waits on an outside step (the user's trial or answer, an approval, an outside
  pipeline or merge) is parked at once:
  - a working CR whose Driver says it waits on such a step: `park <cr> --wait ... --epoch <n>`,
    its Driver stopped, `agents set <cr> - --epoch <n>`;
  - a CR handed back `blocked` with such a wait (`question:`, `approval:`, `waits:` with a typed
    `--wait`): `park <cr> --epoch <n>`, then, when `park` prints the `agents set` line (an agent
    still recorded), `agents set <cr> - --epoch <n>` once its Driver has ended.
  Then, in a stack, `take stack --note "park: <cr>"`. Send the Chief of Staff the line `park`
  printed: `[foreman→chief-of-staff] parked <cr>: ...`. A CR blocked on trouble in the work
  (`fix:`, `infra:`, `rounds:`, `context:`, `refused`) is not parked.
  - **The CRs that wait with it:** a working dependent, a series successor already started on
    it included, keeps its Driver; its PR stays a draft and it is not merged before the parked
    CR comes back.
  - **Coming back:** on an order line `note <cr> wait cleared: ...`, or when `status` shows
    `parked: <cr> wait cleared`: `take <cr> --note "wait cleared: <what>" --epoch <n>`, then a
    new CR Driver, before any queued CR. In a stack it joins as a working CR. No round is
    counted.
  - **Dropping a parked or held CR that has dependents:** the line `order drop` prints names
    them. In a stack, `take stack --note "drop: <cr> to <destination>"`. In a series or parallel
    batch, send each dependent with a Driver or a branch the note `rebase: <cr> dropped`, by the
    usual path (read `status` first: `working`, `[foreman→driver <dep>] note rebase: <cr>
    dropped`; `ready` or `blocked`, `take <dep> --note "rebase: <cr> dropped"`); a queued one
    needs none.
  - **The heartbeat's end:** a batch with only parked or blocked CRs left is blocked and not
    finished: the heartbeat ends as today, and the order line of a cleared wait wakes the
    Foreman.

## A mode switch

- **A mode switch** (the Chief of Staff's `order mode --note <mode>`, any mode to any other; the
  record is already changed, the order is in `status`): no CR already started is stopped, a merged
  CR is never touched, a fix CR stays outside every shape. Read the new order from `status`, then
  by target:
  - *to a stack:* read [foreman-stack](foreman-stack.md) before the first `take stack`; with two CRs or more handed back `ready` with a PR, the first `take stack` (the same `status` line names it; the
    stack driver orders the CRs from the record's order, rebases and pushes each PR on the one
    below, puts each PR it moves to draft, `forge-stack create`, turns the mergeable part ready); a
    `working` CR's Driver gets `[foreman→driver <cr>] note rebase: stacked on <cr below>`; the
    CRs not started join on top as they get their PR;
  - *to parallel:* from a stack, first `$CHANTIER forge-stack unstack` (a refusal is an
    `anomaly` / ask with the forge's exact text, no other means). Then each open CR with a PR gets
    its rebase: a `ready` or `blocked` CR `take <cr> --note "rebase: mode parallel"`, a `working`
    CR's Driver `[foreman→driver <cr>] note rebase: mode parallel`; queued CRs start as slots
    free, on the default branch;
  - *to a series:* from a stack, first `forge-stack unstack`. Then the same rebase notes with `rebase:
    mode series`, bottom CR first: the bottom one is rebased on the default branch, each one above
    on the one below, and a PR above the bottom is a draft (a stack's mergeable part shrinks to the
    bottom PR);
  - a stack driver running when the batch leaves a stack: `[foreman→stack] note mode: <mode>`; it
    stops after the branch it is pushing (no further rebase, no `rebuild`) and hands back; then
    `forge-stack unstack` and the rebase notes;
  - a release CR already started when an ordered batch goes parallel: `take <release> --note
    "redo: mode parallel"` once the others are merged (its PR closed meanwhile, branch kept).
  Then `order done`.
