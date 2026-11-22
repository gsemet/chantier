# Foreman: a stack batch

Read it whole if you are the Foreman of a stack batch (a batch whose `status` line shows `shape
stack`, by `--mode stack` or by `order mode --note stack`), or the Chief of Staff steering one in
direct mode: at the batch's start, again after each compaction (the heartbeat's `shape stack: …`
line names this card's path in its `rules:` part, so a compacted Foreman finds it there), and at a
mode switch to a stack. The rest of the Foreman's rules are in [foreman](foreman.md).

Until the first stack is made, a stack batch runs like a parallel batch with chains, with one limit:
a CR handed back `ready` on the default branch asks `ready-to-merge` alone only while no other CR
of the stack's chain has an open PR and no stacked CR is open (the shape line's `alone asks`);
otherwise it waits for the stack (see "The stack's asks"). The CLI reads such a CR `ready to
merge`, with no remark on the record. A merge is handled by the rebase notes ("After a merge"),
not by a restack; a CR based on another CR's branch hands back `PR in draft`.

Once nothing of a stack remains open (each of its CRs merged or cancelled), the batch is again as
before its first stack: the next stack forms by "The first take" (two CRs ready with a PR), which
the shape line's `next take stack` reminds; the `stack: take stack now` line does not (it is
printed only while no CR of the batch was ever stacked).

## The stack's asks

- While another CR of the stack has an open PR, or a stacked CR is open (`alone asks: refused` or
  `allowed for <other cr> only` on the shape line), a CR's readiness reaches the Chief of Staff
  only through the stack: no per-CR `ready-to-merge` for a CR that is not a fix or held (the CLI
  refuses it), but the next `take stack` and, at the stack driver's hand-back, the
  `stack-ready-to-merge` ask. A CR truly alone may still ask alone, and a fix or held CR asks
  alone with no `--outside-stack` (a held CR's hold order already carries the user's word).
- `--outside-stack "<reason>"` is used only on an open order of the Chief of Staff on that CR that
  carries the user's word for that CR alone (not a `shape:` note). The reason starts with that
  order's id (`O-<k>: <words>`). Ask with the flag first, then mark the order done (`order done
  O-<k>`): the CLI accepts only an open order. Never use it to get past a refusal on your own
  judgement.
- A ready CR refused behind a working or blocked CR's draft PR waits (`next: parallel until 2 ready
  with a PR`). When the CR in front is blocked, your ask about it also names the ready CR waiting
  behind it (`…; <ready cr> waits behind it`), so the Chief of Staff can offer the user a way out.
  The final-order take ends the wait at the latest: once no CR of the stack is working or able to
  start, `take stack --note "final order"` stacks what is ready, and `take stack` asks for no count
  of ready CRs.
- An order note `shape: through the stack` on a CR (the Chief of Staff's) follows the shape line's
  `next`: with `take stack` or `take stack at the next ready CR or merge`, it is taken like any
  later take, `take stack --epoch <n>` (or `[foreman→stack] note shape: <cr>` to a running stack
  driver), then `order done`; with `parallel until 2 ready with a PR`, `order done` and wait.
- The heartbeat's `shape stack: …` line is the stack's reminder, not its rule: its `next` names the
  step for any stack event read at that wake, and "The first take" and "Each later take" stay the
  reference.
- The shape line's `rules:` part names this card's path: when this card is not in context (after a
  compaction, or a session that has not read it in this batch), read it whole before the next act
  on the stack.

## The stack grows

- **The first take,** the moment the stack can form: as soon as two CRs are handed back `ready`
  with a PR (and neither depends on an open CR not ready). `take` starts every new CR with no open
  dependency on the nearest earlier CR with a PR once that CR is handed back `ready`, else on the default branch, and a CR with an open dependency on its highest open dependency's branch (the CLI computes it; you choose nothing), recorded at its first take;
  it leaves out a CR the journal shows merged (`forge saw merged`, not recorded yet) and prints a
  `base:` line naming it: pass that base unchanged, never correct a base by a take note; the `order merged` the
  line names stays the Chief of Staff's. While it is due, `status` prints `stack: take stack now: <crs> ...`; that line
  is the trigger: take it in the same turn you read it (this rule stays the reference; the line only
  reminds it, and only for the batch's first stack).
- **Each later take,** one for everything that happened while no stack driver ran: a CR got its
  first PR (`status` shows it; it joins), a working CR rebased onto its place (its `ship` reads
  the new base; it joins like a CR that got its first PR), a CR of the stack was handed back `ready` (it turns
  ready to merge once the stack driver turns its PR out of draft), a CR the stack driver's hand-back named
  `to come: <cr below> not shipped at <tip7>` (once `<cr below>`'s `ship` records a new head), a merge was recorded (a restack). Events while a stack driver runs wait for its end,
  except a merge (below). None when nothing of the stack remains open.
- **A merge** recorded while a stack driver runs: send it `[foreman→stack] note merged: <cr>…`
  (all the CRs one message of the Chief of Staff recorded) instead of a new `take stack`; while
  none runs: one `take stack` for what remains (a restack, below).
- **A working CR placed on another:** in the same turn as each `take stack`, for each row it
  printed `not on its place`, send that CR's Driver `[foreman→driver <cr>] note rebase: stacked
  on <cr below>` (the CR the row's `base` names; [driver](driver.md), "Stack driver"). Never hold
  the take for it: the CR joins at a later take.
- **The final-order take:** once every non-release CR of the stack has handed back (`ready` or
  `blocked`), none `working`, and none `queued` that could start (a queued CR whose dependency is
  blocked or cancelled does not count: it stays out of the stack), and before `take <release>`:
  `take stack --note "final order" --epoch <n>` (a running stack driver gets `[foreman→stack] note
  final order` instead, after its current work). The release's take then follows as today (`take
  stack` first, then `take <release>`). The ask that follows the end run's hand-back names each
  such queued CR left out (with its unmet dependency), beside the one-time ask for a cancelled
  dependency. A CR that goes back to a Driver after the final-order take (a new round, a
  `rebase:`) makes it due again once that CR hands back.
- **A parked CR** ([foreman](foreman.md), "Parking a CR on an outside wait"): out of the stack as a held CR is.
  On `parked <cr>` or when `status` shows `parked: <cr> ...`: `take stack --note "park: <cr>"`.
- **Deliver by a time:** on the order note `deliver by <time>`, until the time, free slots go
  first to the CRs that can join the mergeable part by then: those closest to being handed back `ready` whose
  dependencies are already in it or ready to merge, short chains before long ones; a CR that cannot be
  ready by then is not started over one that can. You judge which, from each CR's state and chain
  (no estimate tool). No CR already started is stopped. Name the time in the stack driver's take
  (`take stack --note "deliver by <time>"`). At the time, the stack on the forge is what the user
  gets: send the `stack-ready-to-merge … to come: …` ask of the stack as it stands if it is not complete
  and none was sent for it, with the local-gate clause as the hand-back gives it (`not run` or
  `failed` included: the time overrides the condition above). Then the batch goes on toward the complete stack.
  In a batch with no stack, the same order note sends the batch's top's ask as it stands at the
  time, with its local-gate clause (`not run` or `failed` included), as [foreman](foreman.md), "The user's boundaries"
  says.

## The stack driver

You run `take
stack`, never the stack driver: its output goes in the stack driver's prompt, you start it, then
`agents set stack <id> --epoch <n>`; the stack driver reads the stack again with `$CHANTIER stack` (no CR,
it changes nothing). `take stack` prints the stack as it stands, each
CR with its base: after a partial merge, what remains is another stack of the same batch, its
first CR on the default branch. A fix CR is outside it; the release CR is its top. A CR added by `order
add` goes on top. The stack driver ends with each hand-back: `agents set stack - --epoch <n>`
before the next `take stack`. Its end is one native stack on the forge that the user merges in
one action from the top PR, or one PR at a time from the bottom: made at two PRs handed back ready, grown on
top as each CR gets its PR, drafts on top; on GitLab, the chain of MRs checked by
`forge-stack`, merged one MR at a time from the bottom (unproved; trial: one run on a GitLab
project), the `<stack link>` of the asks being the top MR's link, the first take, each later take
and the `stack-ready-to-merge` asks (with the commit and the `to come:` tail) the same. On its `hand-back ready to merge <stack link>
<cr>=<link>…`, read the stack on the forge before anything else, the five checks (below), then:
- the first stack made: `$CHANTIER asks "stack-ready-to-merge <stack link> partial stack mergeable below
  <sha7> merge <cr> <link> <cr>=<link> gaps: …… local gate <cr> at <sha7>: passed to come: <cr> <cr>…"` (`merge <cr> <link>`: the highest PR of the mergeable part, the PR whose head is `<sha7>`; the `<cr>=<link>` pairs: the mergeable part,
  each CR's gaps after its link as in the complete form below; to
  come: the drafts on top (the rows not ready to merge) and the CRs of
  `forge-stack show`'s `to come:` line (no PR yet, or working and not placed yet); `<sha7>` as `forge-stack show` printed it).
  Under a project rule that asks the stack's top for a local run, the clause is copied from the
  stack driver's hand-back and is a condition of every partial ask: send it only when it says
  `passed`, for the `<sha7>` the ask names. A hand-back with no clause under the rule is a failed
  check: `take stack --note "local gate at the mergeable top"`. With no such rule, no clause;
- the stack complete: `$CHANTIER asks "stack-ready-to-merge <stack link> mergeable below <sha7>
  merge <cr> <link> <cr>=<link>…"`, each CR's gaps after its link (`<cr>=<link> gaps: …`);
- any other hand-back (a CR joined, a draft turned ready, a restack after a merge): no ask;
- `hand-back blocked context: …` (or an end with no hand-back and no `activity`): neither an
  anomaly nor an ask: `agents set stack - --epoch <n>`, `take stack --note "resume: <its text>" --epoch <n>`, a new stack
  driver on the batch's model; a failed restack is the stack driver's `conflict-resolver` on the
  escalation model, the stack driver keeping the batch's model;
- `anomaly <cr> local gate failed at <head7>: <log path>`: no ask for that top; `take <cr> --epoch
  <n> --note "local gate failed at <head7>: <log path>"` sends that CR to a Driver for a round; it
  joins the mergeable part at a later take, once its gate passes;
- `anomaly <cr> conflict: stacked on <cr>: <files>`: before the five checks,
  `take <cr> --note "rebase: stacked on <cr below>: conflict in <files>"` (the CR is `working`,
  its draft no check 4 failure; its Driver rebases, the CR turns ready to merge at a later take);
- **A drop in the stack:** `take stack --note "drop: <cr> to <destination>"` (the destination
  the order's line carries: `6-trash`, `3-ready` or `2-backlog/P<n>`) right after the drop is
  applied, or `[foreman→stack] note drop: <cr> to <destination>` to a running stack driver. A
  held CR's drop needs no `take stack`: `order done` at once. A CR that waited with the dropped
  held CR (an `after`, or in a series a start on it) gets `rebase: <cr> dropped` by the usual
  path (`working`: a `note` to its Driver; `ready` or `blocked`: `take <dep> --note "rebase: <cr>
  dropped"`), to take the dropped CR's commits out of its branch. A working CR above gets
  `[foreman→driver <cr>] note rebase: stacked on <cr below>, without <dropped cr>` (a plain
  `status` just before). An open CR whose `after` names the dropped CR: ask the Chief of Staff
  once, and hold the take until the answer. A release above: after the hand-back, `take <release>
  --note "redo: <cr> dropped"`, then `take stack`. Then `order done`; the user is asked nothing;
- **Heavy CI on a head** (the Chief of Staff's `order note <cr> "heavy CI: at its head"`):
  `[foreman→stack] note heavy CI: <cr>`, or `take stack --note "heavy CI: <cr>"`; a working
  CR's own Driver CI covers it (tell the Chief of Staff). Its hand-back
  `heavy CI <cr> at <head7>: green|red <checks>` goes up as `$CHANTIER asks "heavy-ci <cr>
  <head7> green|red <checks>"`.

## The five checks

When one check fails, no
ask: `take stack --note "<the check that failed>"` sends it back to a stack driver. A CR of the
stack handed back, ready to merge or PR in draft: no ask. Record its gaps with `$CHANTIER note <cr> "gaps: …"` (`none`
when it has none, no `gaps:` text) and quote them after its link in the `stack-ready-to-merge`, partial or complete; the next report's
partial-stack line shows it once its PR is in the mergeable part. The Chief
of Staff's order that inserts a CR into a stack ready to merge (`order note` `insert: <new cr> below
<cr>`) makes this sequence, the steps of the stack driver's card ([driver](driver.md), "Stack
driver"): the PRs above the new place go to draft first (the Chief of Staff already did it:
check it on the forge), the new CR's Driver, `take stack --note "insert: <new cr> below
<cr>"` (the stack driver's rebuild of the stack on the forge is `$CHANTIER forge-stack
rebuild`), the release redone (`take <release> --note "redo: <new cr> inserted"`) so its notes
name the change, `take stack` again, the check, then `stack-ready-to-merge`. You edit no PR yourself.
A PR ready to merge that stopped merging is yours to notice (`gh pr
view --json mergeable`, `glab mr view`) and send back with `--note "rebase: …"`.
- **The five checks of a stack ready to merge,** read on the forge with `$CHANTIER forge-stack show`
  (it prints one line per failed check and exits 0 when all hold; on GitLab, read on the chain of
  MRs: unproved; trial: one run on a GitLab project): the stack is
  open; it holds every PR of the stack as it stands (the bottom CRs with a PR), and no other;
  in the record's order, bottom first; no PR of a CR ready to merge is a draft and every draft sits above
  the PRs ready to merge; the release PR, when it is in the stack, on top.

## After a merge

- **Stack:** a choice you make per recorded merge (or per group of merges recorded in one
  message), never fixed at the go:
  - **A restack** (once every CR that one action of the user merged is recorded, one `take
    stack` for what remains and one stack driver, or the note `merged:` to the one that runs)
    whenever a native stack of the batch is on the forge (on GitLab, a chain made by
    `forge-stack create` or `rebuild` and read back by `show`).
  - **A folded CR** (GitLab): on the Chief of Staff's `order merged <k>` with the note `folded:
    <k> into <k-1>`, the CR below goes back to a Driver first, `take <k-1> --note "folded: <k>
    merged into its branch"` (a slot, or it waits like a queued CR); the restack of what remains
    (`take stack`) comes after its hand-back. Unproved; trial: one run on a GitLab project.
  - **Rebase notes** only before the first stack is made: the parallel rules apply, scoped to the CRs whose base the merge changed. A
    `working` CR based on the merged CR's branch or on the default branch gets `[foreman→driver
    <cr>] note rebase: <merged cr> merged`; a CR handed back `ready` or `blocked` with a PR that no longer
    merges (`gh pr view --json mergeable`, `glab mr view`) or whose base was the merged CR's
    branch goes back with `take <cr> --note "rebase: <merged cr> merged"`. A PR ready to merge on the
    default branch that still merges cleanly is left alone.
  - Nothing of the stack left open: neither.

  Say in your next line to the Chief of Staff which one you chose and why, in one clause.
