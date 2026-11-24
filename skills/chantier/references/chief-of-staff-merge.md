# Chief of Staff: a PR ready to merge, a merge, a stack

## While it runs: merging

- **The words to the user** (the CLI's, in the user's language): "ready to merge" / "prête à
  merger" only for a PR the user can merge now; "PR in draft" / "PR en draft" for a draft, with
  what it waits for; "ready locally" / "prête localement" for done work with no PR yet. "Ready" /
  "prête" alone is never said of a CR or a PR, and "mergeable" never of a draft, whatever the
  forge's `mergeable` field says. An icon you write beside a CR is copied from `label` (🟢 ready to
  merge, 🟤 PR in draft, 🟣 ready locally), never judged.
  `status` prints a `handed back:` line for each CR handed back; the words you say to the user
  are that line in the user's language: its icon, its full PR link (never a named link), each
  gap next to the link, its `do not merge: waits for` text on a draft, and its `owed before the
  merge` clauses (what is still owed; the user may merge anyway, recorded as any merge). The
  prefix `handed back:` is never said to the user. Its `long gate` clause is what the record
  holds; the local run the project's rules owe comes from the Foreman's ask (`local gate <cr> at
  <sha7>: …`), which you add. When the ask and the line differ, the ask wins. Nothing in the
  line is judged.
- **The icon is the present:** the icon beside a PR or a CR is its state at the time of writing,
  never the state it is expected to reach; the future is said in words. Wrong: "the next PR ready
  to merge will be 🟢 #171 CR-237" while #171 is a draft. Right: "🟤 #171 CR-237, do not merge: it
  waits for its gate; it will be the next ready to merge". A draft's icon is its CR's state from
  the refreshed `STATUS.md`: 🟤 only when the CR has nothing left to do; a draft whose CR is
  rebasing or running CI or a Verifier is 🟡, one waiting for another CR's work (not its merge) 🟠,
  a blocked one 🔴.
- **A draft says "do not merge":** every PR in draft you name to the user carries, in the user's
  language, "do not merge" / "ne pas merger" and what blocks it: "🟤 #174 CR-222: ne pas merger,
  base = branche de CR-237". A PR in draft based on another CR's branch is never called "prête",
  even of its own work: merging it lands it in that branch, not in the default branch.
- **"You can merge it"** / "tu peux la merger": only for a PR ready to merge (🟢: out of draft, CI
  green, no conflict, on the default branch or with everything under it ready to merge).
- **A plain `ready-to-merge <cr> <link> gaps: …` ask (or `pr-in-draft <cr> <link> on <base>: waits
  for <what> gaps: …`):** when you tell the user the PR is ready to merge, quote each
  gap of the ask next to the PR's link, in the user's language (the `handed back:` line carries
  the same gaps from the hand-back); with none, say nothing about gaps.
  In a project whose rules ask a local run, the ask of each CR that owes the run, in a parallel
  or series batch, carries `local gate <cr> at <sha7>: …`: quote it in the user's language before you say the
  PR can be merged. `passed`: say the local gate ran and passed at that head. `not run` or
  `failed` (a `deliver by` time): say the project's rule asks that gate at that head before the
  merge and it has not passed there; merging anyway is the user's choice, recorded as any merge
  (`order merged`), never questioned or refused.
  Where the project's rules ask for a screenshot of the board pane for a change to it and
  the gaps name it as missing, ask the user for one screenshot of the pane from a session
  running the PR's branch, with made-up paths: no username and no home folder in it. When the
  Driver's report says the user's screenshot was not uploaded because it showed one, say so and ask
  for a new one the same way. When a Driver's `note` or hand-back report (relayed with the ask) says
  an image that showed the username or home folder was uploaded and replaced, tell the user: the
  PR, the image, and that the old attachment may stay reachable on the forge. Do nothing more. On the user's file, `order note <cr> --note "evidence: <path of the
  image>"`: the Foreman turns it into `take <cr> --epoch <n> --note "evidence: <path>"`, and a Driver
  attaches the image in Deliverables, removes the gap, runs the description pass and hands back
  ready again. In every mode, a `ready-to-merge` ask is offered to the
  user as mergeable now, on its own, with its gaps as above (for the release PR, the same message asks the post-merge word, Releases); a `pr-in-draft … on <base>: waits for
  <cr>` ask is not: say it is a PR in draft, do not merge, and what it waits for. Say "you can merge" (or any equivalent) about a PR only
  after its `ready-to-merge` line (or the `stack-ready-to-merge` line for a stack) has reached you, never on a
  Driver's progress, a green CI or the PR's look on the forge. When the user merges a PR before
  its `ready-to-merge` line, record it as any merge (`order merged <cr>`: the user's merge is a fact) and
  tell the Foreman in the same message; no reproach, no question. A `forge saw merged: <cr> …`
  line, in `status` or in a watcher's notification or end, is a merge the user made: record it like any merge, at
  the `status` that shows it or at the watcher's notification or end, once the forge confirms it ([The
  watcher](session-start-chief-of-staff.md#the-watcher)): `order merged <cr>`, then, in Foreman mode, send its line to the
  Foreman as for any order. A line that says `landed with <other cr>` is a merge to record, like
  the `into <branch>` one: the hub (or the board) read the PR merged into `<other cr>`'s branch and that CR's PR on the default branch
  at the same time or later, or the PR's own merge on the default branch (a native stack merged in one go) (`order merged <cr>`, then the Foreman's line in Foreman mode). Only
  a line that ends `not landed …` is not one to record: do not run `order merged`; tell the user
  where the PR went (into `<other cr>`'s PR, not the default branch) and wait until the PR under
  it lands (the hub or the board then writes a second line, `landed with`); the line keeps printing until
  the CR is recorded merged. When the user merges several PRs of a batch with no stack in one action (or several `forge saw merged` lines come at one `status` or one watcher's notification or end), record `order merged` for each.
  A CR taken out of a batch whose PR the user merges later, outside any batch (its folder is in the
  backlog or the next batch, `3-ready`, with `formerly.json`), has a route of its own: on "I
  merged #n" for it, run `order add --note <folder>`, which brings back its number and its PR,
  then `order merged <cr>` at once (Foreman mode: both lines to the Foreman in one message, the add first). With no batch
  open, tell the user the merge is recorded the same way in the next batch, and leave the folder
  as it is. A Driver's `blocked question: its PR <link> is already merged` is recorded the same
  way, with `order merged <cr>`.
  One exception, on GitLab: a fold (`forge-stack show` prints `folded
  into <cr below>`) is recorded at once by the fold rule below, whatever the line says.
- **A series batch:** the CRs merge one by one, in order. On each `ready-to-merge` ask, tell the user which
  PR is next to merge (the bottom one, ready to merge on the default branch) and that the others are drafts
  waiting on it; quote each gap of the ask as above; when the user says it is merged,
  `order merged <cr>`, then say what comes next. The user may merge the bottom PR as soon as it
  is ready to merge, which is what the series already does; nothing waits for a "go" of the user to merge.
  Never merge for the user. On the user's word to switch to another mode (parallel, series or a
  stack, from any of the three), `order mode --note <mode>`; the same in a parallel or a stack
  batch. Tell the user what the switch does at once, from the line `order mode` printed: to a
  stack or a series, the PRs above the bottom go to draft while the batch is rebuilt, and
  "do not merge them meanwhile" (name them); from a stack to a series, the PRs that were ready to
  merge above the bottom stop being mergeable (name them); to parallel, each open PR is rebased
  on the default branch, its long gate and CI run again, and it leaves draft once ready. A merge
  the user makes anyway is recorded as any merge (`order merged`). Merged CRs never change.
- **A stack batch:** the one-action stack merge is not the only path. Before the stack is made on
  the forge, each CR handed back `ready` on the default branch is an ordinary `ready-to-merge` ask, offered
  as mergeable now, while that CR is the only open PR of the stack's chain (the shape line's `alone asks`)
  (the bullet above); a CR above it, a draft on another CR's branch, waits.
  Each Foreman ask is checked against the batch's shape, not only for being rebased and green. In a
  stack batch, read `status --refresh`'s shape line. A per-CR `ready-to-merge` for a CR of the
  stack's chain (`stack` lists it; not a fix or held CR), while that line's `alone asks` is
  `refused` or `allowed for <another cr> only` (another CR of the stack has an open PR, or a
  stacked CR is open), is mismatched unless it carries `outside the stack: O-<k>: …` where `O-<k>`
  is your own order on that CR, carrying the user's word (the Foreman may have marked it done by
  then: check that the order is yours and on that CR, not that it is open). A mismatched ask is not
  offered: send it back with `$CHANTIER order note <cr> --note "shape: through the stack"` and tell
  the user in one line: `<cr> asked alone in a stack batch: sent back through the stack`. When a
  Foreman ask about a blocked CR names a ready CR waiting behind it, offer the user two ways out
  with the blocked CR's question: `order hold <blocked cr>` (the held CR leaves the chain, and the
  ready CR may then ask alone), or an order on the ready CR that carries the user's word, for the
  Foreman's `--outside-stack "O-<k>: …"`. A stack's readiness is offered as a
  `stack-ready-to-merge`, after the native stack is read on the forge (`forge-stack show`, the five
  checks). In direct mode the steering session checks its own asks the same way (the CLI already
  refuses such an ask; the check catches one recorded before it or forced without a fitting order).
  On a
  `stack-ready-to-merge <stack link> … <cr>=<link>…` ask (with or without `to come: …`), read the stack on
  the forge yourself before you tell the user: the five checks of the stack ([foreman-stack](foreman-stack.md),
  "The five checks"; `$CHANTIER forge-stack show` prints the failing ones, exit 0 when all hold).
  On any such ask, partial or complete, before you tell the user the stack is mergeable, apply the
  plain ask's gap rule (the bullet above) to each CR of the mergeable part: quote its gaps next to
  its link, in the user's language; where the project's rules ask for a screenshot of the board
  pane and a gap names it as missing, ask the user for that screenshot (with made-up paths, and tell of an uploaded leak, as in the
  bullet above) in the same message, naming
  the PR and which PRs are below and above it, before the sentence that says the stack can be
  merged. The user decides; the evidence route stays (`order note <cr> --note "evidence: <path>"`).
  On a partial ask, in a project whose rules ask the stack's top for a local run, quote its
  `local gate <cr> at <sha7>: passed|failed|not run` clause in the user's language before the
  sentence that says the stack can be merged. `passed`: say the local gate ran and passed at that
  head. `not run` or `failed` (a `deliver by` time), or no clause: say the project's rule asks that
  gate at that head before the merge and it has not passed there; merging anyway is the user's
  choice, recorded as any merge (`order merged`), never questioned or refused. The record holds it:
  the last `gate` events of that CR at that full head in the batch's `events.jsonl` (`status`'s
  "Long gate" column keeps `exempt: <rule>` for a CR handed back with `--no-gate`).
  All hold: first tell the user the one PR to merge, by the ask's `merge <cr> <link>` (its number
  and link): on GitHub, merging that PR merges those under it in one action; one PR at a time from
  the bottom stays their choice. Tell them that no other PR of the batch is to be merged while the
  stack stands, except the PR of a CR that is not in the stack order (a fix CR) whose latest
  readiness ask names it; a PR of a draft on top, of a CR to come, or of a CR in the stack order
  handed back on its own is not to be merged; a merge they make anyway is recorded as any merge.
  Then, with `to come: …`, tell the user the stack is mergeable up to its last PR ready to merge (in one
  action from that PR, or one PR at a time from the bottom, per the paragraph above), the drafts on
  top and the CRs still to come named (number and slug), and that the top goes on while they
  merge: it grows silently, and its state is in each report. The `stack-ready-to-merge` with no `to come:`
  says the stack is complete (when its top is the release PR, the same message asks the post-merge word, Releases): it can be merged in one action from its top PR (the link), or one PR
  at a time from the bottom, as they like, with the release commit last, quoting each CR's gaps of
  the ask in the user's language (none: say nothing about gaps). Both name the commit, in the
  user's language ("partial stack mergeable below <sha7>", "stack partielle mergeable en dessous
  du commit <sha7>"). A CR of the stack that turns ready to merge reaches the user through the next
  report's partial-stack line, never as an ask; its gaps are quoted with the next
  `stack-ready-to-merge`, partial or complete. After each merge action of the user (one PR or several), record `order
  merged` for every CR it merged, bottom first, all before telling the Foreman, in one message
  (one action leads to
  one restack at most, silently: no ask follows it, and none when the whole stack merged; the release CR's merge starts the
  release procedure, as today). An `anomaly` of the stack driver or the Foreman on a refused
  `$CHANTIER forge-stack rebuild` reaches the user as an ask with the exact text; on the user's
  yes, run yourself the command the refusal's last line names (`$CHANTIER forge-stack create`
  after the line `… is dissolved and no stack replaces it yet`, `$CHANTIER forge-stack show` after
  the line `… the stack's state is unknown`), or `$CHANTIER forge-stack rebuild` when it names none
  (no raw `gh api`). On GitLab (unproved; trial: one run
  on a GitLab project), `forge-stack show` reads the same checks on the chain and names the commit
  the same way; tell the user the stack is mergeable one MR at a time from the bottom up to the MR
  of the commit named (the same MR as the ask's `merge` part), never "in one action from that MR"; that each next MR is mergeable once
  GitLab shows it so (retargeted to the default branch and its pipeline green; when GitLab says it
  needs a rebase, chantier's restack brings it); and that an MR merged directly in the middle
  folds into the MR below it, its change reaching the default branch when that MR merges. To bring
  the MRs up to MR k onto the default branch, merge them one at a time from the bottom up to k. When
  the user merges a middle MR anyway (or `show` prints `check 1: !<iid> merged into <target> …
  folded into <cr below>`), record `order merged <k>` at once, with `order note <k-1> --note
  "folded: <k> into <k-1>"`, tell the Foreman in the same message, and tell the user that CR k's
  change now rides in CR k-1's MR. An MR added to a merge train or set to auto-merge is not merged:
  on the user's "merged", read the MR (`glab mr view <iid>`) and record `order merged` only once it
  reads merged, else say it is recorded once the train (or the pipeline) merges it, and read it
  again at the next report; only the bottom MR (on the default branch) can join the train, the next
  once it is retargeted after that merge (unproved; trial: one run on a GitLab project with merge
  trains). A check
  that fails: no "ready to merge" to the user; send it back through the Foreman. The user always merges a
  stack themselves: no grant lets a steering session merge a stack that holds the release PR.
  Under a stack waiver (`order waive stack`), the merge offer names the CR whose gate validates
  the lower PRs (`status` shows it: `waived → CR-k`) and whether that gate passed at its head:
  merging a lower PR before it passes leaves main with the failure if it fails.
  When you tell the user about a `stack-ready-to-merge` ask (partial or complete), add one clause in their
  language: heavy CI ran at the top PR's head only; merging a PR below it without heavy CI at its
  own head is their choice; heavy CI can be run on that head if they ask (the partial-stack line of
  a report does not repeat it). A merge in the middle is recorded as above, never questioned or
  refused. On their word to run it: `order note <cr> "heavy CI: at its head"`; the Foreman passes
  it on, and its `heavy-ci <cr> <head7> green|red <checks>` ask is told to the user (a red result
  changes nothing by itself: the user decides).
- **Dropping a CR from a stack:** on the user's word, `order drop <cr> --note <destination>` (the
  destination as "Where a dropped CR goes" says; the Foreman then removes it from the stack with
  `take stack --epoch <n> --note "drop: <cr> to <destination>"`), then tell the user that the CR's
  commits come out of the PRs above it, and the PRs above it are PRs in draft (do not merge) until
  the next report's partial-stack line shows them ready to merge again. The rest depends on the
  destination. Trash: its PR is closed and its branch stays until `close`. Backlog or next batch (`3-ready`): its PR
  goes to draft and, by the rebuild, onto the default branch; its branch and worktree stay and are
  not offered for removal at `close`; its folder is at `<destination>/<number>-<slug>` and keeps
  its number. A held CR: nothing to rebuild (it is already a draft on the default branch). Nothing
  more is asked of the user.
- **Holding a CR:** on the user's word to keep a live CR (working, or ready in a stack) out for now
  (not the batch: ask when it is unclear whether the user means held or out of the batch), `order
  hold <cr>`, in every batch mode; to put it back, `order unhold <cr>` (it returns on top; a CR
  held while working comes back `blocked`, to be taken back). The Foreman then stops its Driver
  (`stop hold: <O-n>`) and, in a stack, takes the stack driver (`take stack --note "hold <cr>"`),
  which rebuilds the stack on the forge without it. The CRs that wait with it (an `after`, or in a
  series a start on it) wait too: name them to the user. Name each held CR in the batch reports.
  At a batch's end, tell the user that the batch stays open while a CR is held. No release starts while a CR is held: when the release is
  blocked by a held CR, say so, name it, and offer the user `order unhold <cr>`, or `order drop
  <cr>` with the destination the user names; act on the user's answer only. Name each parked CR
  in the batch reports too, with what it waits for, and no release starts while a CR is parked
  either: its way back is its wait cleared, then `take`. At a batch's end, at `close` and when
  the release waits, a parked or blocked CR is named with what it waits for and its way back as
  the CLI's line gives it (`close` refuses with it, the last ending command prints `the batch
  stays open`); offer the user to wait for it or to send it out (`order drop <cr> --note
  <destination>`: the trash, `P1` to `P4`, or `3-ready`). Act on the user's answer only. Drop a
  held CR only after the hold's `order done` (the Foreman's, once its Driver has stopped). In direct mode the
  Chief of Staff does the Foreman's part: the stop, `agents set <cr> -`, `order done`, and the
  freed slot filled only after it. A release working at the hold is let hand back, then taken
  again (`redo: <cr> held`) by the Foreman.
- **Inserting a CR into a stack ready to merge:** on the user's word, first and at once put to draft every
  PR that will sit above the new one (`gh pr ready --undo`, `glab mr update --draft`): the stack
  is changing under them. A CR in the middle of a stack ready to merge that goes back to its Driver for a
  new round gets the same: every PR above it goes to draft first. Then `order add --note
  <folder>` and an `order note` naming the place (`insert: <new cr> below <cr>`). Tell the user
  that the stack is not mergeable until the Foreman's next `stack-ready-to-merge`, and that the release
  notes will name the change (the release CR, once started, goes back to `redo:` and updates its
  notes). The steps are the stack driver's ([driver](driver.md), "Stack driver").
