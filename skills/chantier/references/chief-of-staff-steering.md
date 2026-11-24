# Chief of Staff: steering a running batch

## While it runs

- **Status:** `$CHANTIER status [--notes]`, with PR links, and the planning folder's
  `STATUS.md` for the user. Before a report, run `$CHANTIER status --refresh` with no epoch (`status-layout.md`).
  A 🔴 CR is a question for the user. Never read the Foreman's transcript.
- **The Foreman's turn end:** your host may tell you each time the Foreman ends a turn (Claude
  Code: [the Foreman's turn-end notice](hosts/claude-code.md)). It is not a line and needs nothing
  from you: end that turn at once, with no tool call, no message and no report, and restate nothing
  of it to the user. You act on the Foreman's lines (`ready`, an ask, `pong`, `final`, `push`,
  `chain`), the user's words and your reports, never on the notice. One exception: a notice that
  shows the Foreman stopped on an error (a usage limit, an API error), with no line from it, gets
  one line to the user saying so, still with no tool call (unproved; see the host's reference).
- **Reports:** every Progress report and Completion report, with its icons, columns and cost table, is written as `status-layout.md` says: read it whole before each one. It holds the shape, the cost table, the Tips line, "MR" or "PR", and how a CR is named.
  What you say or write to the user never uses the word epoch: a Foreman's number is `Foreman n°<k>` ([concepts](concepts.md), "Steering session"), and a stale-Foreman refusal or a relay is reported as "batch-18, Foreman n°2 is stale: Foreman n°3 runs it".
  Every Progress report gives the remaining floor and the updated delivery time ([The
  floor](chief-of-staff-batch-start.md#the-floor), counted again on the state `status --refresh` has just written: the CRs not
  yet past their long gate at their current head, the depth of what remains, the gate's and the CI
  run's times from their latest passed runs), in its **Notes** (`status-layout.md`), and beside
  it the mergeable partial stack as it stands, `partial stack mergeable below <commit>`. When the
  updated delivery time is an hour or more later than the last one told to the user, the report
  says the slip and its cause in one line, in the user's language (for instance "delivery not
  before 09:40, was 07:30: CR-221 took 8 rounds"). A slip is reported only: no new cut is
  proposed, and the batch's CRs stay as they are.
  Before each report, in both modes, run `git status --porcelain` on the main checkout (with a
  planning surface, the clone `take` names) and name every path outside the planning folder that
  you have not named yet: a write the worker guard cannot see, a shell's included. Revert
  nothing and hold no CR back: another Driver or the user may be its cause. The report also gives
  the latest `main checkout:` note of a CR merged since the last report (`status --notes`, `log
  <cr>`; `status-layout.md`): a fast-forward leaves `git status` clean, so it is no trace there.
  In a stack batch, before each Progress report, read `$CHANTIER forge-stack show` (read
  only) and take the line for **Notes** from its `partial stack mergeable below …` or failing
  checks: while a check fails (a take is changing the stack), the line says `stack changing: last
  mergeable below <sha7>` with the commit of the last report, or `stack changing` when none was
  told. In direct mode the same, you steering.
- **When the delivery time passes the time the user gave** (the batch will not finish by it):
  record `$CHANTIER order note - --note "deliver by <time>"` (it prints the line to send to the
  Foreman, and a restarted Foreman finds it). In direct mode you apply the Foreman's "Deliver by a
  time" bullet ([foreman-stack](foreman-stack.md)) yourself. Tell the user nothing beyond what the
  report says.
- **Steering:** each order is one `$CHANTIER order`, applied to the state at once and printed as
  the line to send the Foreman (by your host's means), who does what needs its hands
  and marks it done; `status` shows the orders still open, those the CLI applied apart from
  those nothing has touched. For `order qa`, send the order's line and the `qa-driver prompt`
  block it printed, together, as printed. A CR is named `CR-104` or `104`; a second drop of a dropped CR, and
  a note on a cancelled one, are refused (exit 2).

  **Where a dropped CR goes.** The user's word that takes a CR out of a batch ("drop", "take it
  out", "postpone", "remove from the batch") names where it goes. When it does not, ask once, in
  the user's language, before the order: the trash (cancelled), the next batch (`ready`,
  `3-ready`) or the backlog P1..P4 (postponed or handed off; the usual case for delegated work).
  The inbox is not one of them, for any CR: a CR already planned has no reason to go back to the
  inbox (`order drop --note inbox` is refused); a later move of its folder, the inbox included, is
  `triage` or the board on the user's word. Never choose for
  the user: `order drop` is refused with no `--note`. A word that already says it needs no
  question ("cancel it" is the trash; "postpone it, P2" is `P2`). A word that only keeps a CR out of
  the order for now (a ready CR of a stack, or a live CR in any mode) is `order hold`, not a drop.
  Whatever the destination, the CR keeps its work (worktree, branch, PR); only the trash closes its
  PR; the backlog and the next batch keep it as a draft. A CR moved to the backlog or the next
  batch (`3-ready`) keeps its number (`formerly.json` in its folder).
  In direct mode, a drop line ending `close its PR <link>` (a trash drop, outside a stack) is
  yours: close it (`gh pr close <n>`, `glab mr close <n>`, no `--delete-branch`, no comment), then
  `order done`. A drop line ending `turn its PR to draft <link>` is the Foreman's in Foreman mode
  and yours in direct mode (`gh pr ready <n> --undo`, `glab mr update <n> --draft`, no comment),
  then `order done`. `cancel` of a live CR prints the same clauses.

  ```bash
  $CHANTIER order add --note "<prepared-folder or a release's fix file>" [--fix-for <release-cr> | --release]
  $CHANTIER order after CR-104 --note "CR-102,CR-103"   # what a queued CR waits for; "-" for none (not a release's)
  $CHANTIER order drop CR-104 --note trash|ready|P1..P4   # where it goes, with its work; never the inbox; a release or fix CR: trash only
  $CHANTIER order note CR-102 --note "<one line: a change, an answer, a priority>"
  $CHANTIER order merged CR-101               # the user merged its PR: to 3-done
  $CHANTIER order slots --note 0              # 0 holds; a number resumes
  $CHANTIER order rounds CR-102 --note 5      # on the user's word, or under the rounds exception (below)
  $CHANTIER order budget --note 40
  $CHANTIER order mode --note parallel|series|stack   # any mode to any other, on the user's word
  $CHANTIER order qa --note "<what to test>"  # a QA driver on the project's head; takes a slot
  $CHANTIER order waive stack --note "<the user's words>"   # a stack: one long gate on the top PR only
  $CHANTIER order waive CR-102 --note "<the user's words>" --follow-up <backlog folder>
  $CHANTIER order waive stack --note -        # withdraws it (`waive CR-102 --note -` for a CR's own)
  $CHANTIER order approve <release-cr> --note "<the action>"
  $CHANTIER order grant <release-cr> --note "releases=<n> fixes=on|off budget=<usd>"
  $CHANTIER order confirm <release-cr> --note "<the user's word to run the release procedure>"   # once the other CRs are merged
  ```

  In Foreman mode the Foreman fast-forwards the main checkout when it handles an `order merged`
  order; you do not. In the direct mode you do it yourself, and note `HEAD` before it: when `git
  diff --quiet <before> HEAD -- uv.lock` says `uv.lock` changed, the note is `main checkout:
  fast-forwarded to <sha7>; uv.lock changed: sync pending`. On that note (yours or the Foreman's),
  in chantier's own checkout, when the session's project is chantier (the dev mode), sync as your
  skill's `$CHANTIER` paragraph says, at this turn and each next one until it is done;
  `$CHANTIER status` is not enough, it sees only this surface's batch; until then say `sync
  pending: held by ...` in your report's Notes; after 3 minutes, it is a For you item
  (`status-layout.md`). Never stop or kill a holder to sync, nor ask a Foreman or a Driver to; the
  one exception is your own board and watcher, on the user's yes, as the skill's paragraph says.

  The rounds exception: a CR handed back `blocked rounds:` whose last round failed on a red the
  batch caused (a restack or rebase onto another CR's branch, a CR merged or moved below it; judge
  it from the hand-back, `log <cr>` and `diagnosis.md`; in doubt, the user's word) gets its next
  round from you. The cap is the batch's own `settings.max_rounds`, never the CR's limit that
  `status` shows: +1 per grant, each on its own cause, never above `max_rounds` + 2 (default 3:
  the 4th, then the 5th). Send the Foreman two orders in one message, `order rounds <cr> --note
  <limit + 1>` and `order note <cr> --note "rounds exception: <the event>; <the failing check>"`,
  and tell the user in the same message, with no wait: `CR-<n>: round <k> granted under the rounds
  exception: <cause>`. The Foreman takes the CR with that note and no escalation; you alone answer
  for the exception. Every other grant of rounds stays the user's.

  A Driver's question (`ask … blocked <cr> question: …`): record the user's answer in the CR's
  `02-answers.md`, then `order note <cr> --note "answer: …"`. A `fix:` from a release: under the
  grant the Foreman starts it alone; else show the user its `fix-<n>.md`, and on their go `order
  add --note <that file> --fix-for <cr>`, or file and grill a CR when it needs more. A `refused
  <cr> <text>`: show the exact text, record it at once with `$CHANTIER note <cr> "refused: <the
  exact command> -> <the host's exact text>"`; the user types one line in the Foreman's session
  allowing that action. A `qa <folder> <n> findings`: its inbox folder is an ordinary item;
  triage it with the user, split into CRs as needed.
  A typed wait (`$CHANTIER wait <cr>` lists a blocked CR's waits; `status` shows `| waits:`) is
  cleared by you on the user's answer, or on a `wait-cleared@1` line that your watcher carries (the
  forge showed it met): `wait <cr> clear <id> --epoch <n>`, then the take-back path as for any
  blocked CR (`take <cr> --epoch <n> --note "<why>"`; direct mode: take it yourself). For a parked
  CR: `wait <cr> clear <id> --epoch <n>`, then, in Foreman mode, `order note <cr> --note "wait
  cleared: <what>"`, whose order line wakes the Foreman; in direct mode, take the CR yourself
  (`take <cr> --note "wait cleared: <what>" --epoch <n>`), before any queued CR. On `[foreman→chief-of-staff]
  parked <cr>: ...`, tell the user in one line, in their language: the CR's name, what it waits
  for, that its slot is free and that the batch goes on. Ask nothing.
- **A chain:** on `[foreman→chief-of-staff] chain <cr> after <cr>: <reason>`, record it at once,
  without waiting for the user: `order after <cr> --note "<cr>"`, then `order note <cr> --note
  "chain: <reason>"`. The same covers a chain the plan proposed and the go approved, recorded at
  `open`. Your next report says the chain and its reason (`status-layout.md`). The user turns
  it off with a word while the CR is queued: `order after <cr> --note -`. Once the CR has
  started, the chain stands until the stack driver restacks.
- **An early conflict:** on `[foreman→chief-of-staff] conflict <cr> with <cr>…: <paths>; switch
  to a stack?`, tell the user, in their language: the PRs, by link and CR name; the paths they
  both change; that each PR stays ready to merge on its own, but merging one makes the others
  conflict, and those go back to their Drivers for a rebase after that merge (the parallel rule);
  and the offer: switch the batch to a stack, so the later CR is rebased once onto the earlier
  one. On the user's yes, run `order mode --note stack` and tell the user what the switch does, as
  "A series batch" says for `order mode` (the PRs above the bottom go to draft, "do not merge
  them meanwhile", named). On a no, record nothing and send the Foreman nothing; the batch stays
  parallel. In direct mode the steering session runs the check itself (it reads `foreman-conflict.md`) and
  puts the same question to the user; the ask is still recorded with `$CHANTIER asks`, as
  `routing.md` says. The ask counts like any other ask in the report.
- **A refused force push:** on `[foreman→chief-of-staff] push <branch> <expected remote sha>
  <local sha>` (in direct mode, the Driver's `push` line), the push climbs to you: the second step
  of a ladder, the one exception to "do no Driver's work". A push of a covered branch (any
  `chantier/*` branch that is not the default branch, `--force-with-lease`) is **never a question
  for the user**: you judge it and run it, with no ask and no wait for a word. The user is told,
  as information (the report's shape, no question, no tip), of a push of a branch that is not
  chantier's or of the default branch (nothing is pushed) and of a forge's protected-branch
  rejection (`push failed`), and asked only on a doubt of the judgement or when the host refuses
  your own push (the push then runs once on the user's yes). The
  check and the judgement are those of [foreman](foreman-refused.md#a-drivers-refused-force-push), "A
  Driver's refused force push", and the route form of that section is the push.
  - **Who checks what:** in Foreman mode the gate check and its three skips are the Foreman's, run
    inside its judgement; your own judgement on its `push` line runs them again. In direct mode
    they are yours, once.
  - **On `[foreman→chief-of-staff] push <branch> <expected> <local>`** (the Foreman judged it
    legitimate, then the host refused the Foreman or the Foreman did not try): read in `handoff
    <cr>` the Foreman's `push judged legitimate` note and its `refused:` or `push not tried: route
    rule missing` note; then run the full check and judgement of `foreman-refused.md` yourself, whatever
    the Foreman's note says, at the shas of the line.
    - Legitimate: `$CHANTIER note <cr> "push judged legitimate at <local sha7> for <branch>: <one
      line>"` (your own note), then the route form, at once, no ask.
    - A hard check that fails (a covered branch that `handoff` ties to no CR of this batch, or no
      long gate passed at the local head outside the skips): push nothing; record `$CHANTIER note
      <cr> "push refused <branch>: <the reason>"`; answer `push refused <branch>: <the reason>` to
      the Foreman; no user question (the user's yes must not push such a branch, and the Driver
      already knows what to do with each answer).
    - A branch that is not a `chantier/*` branch, or the default branch: push nothing, ever;
      record `push refused <branch>: not a chantier branch`, answer it to the Foreman, and tell
      the user as information (the branch asked and the CR that asked it; no question, nothing to
      answer). A yes of the user does not push it.
    - Not legitimate (the checks pass, your judgement disagrees with the Foreman's): push nothing;
      tell the user at once, in the report's shape (the **For you:** line, no tip), naming both
      judgements: the Foreman's (its note) and yours (what you found); the CR (number and slug),
      the branch, the expected and local shas. On the user's go, first `$CHANTIER note <cr> "push
      on the user's go at <local sha7> for <branch>"`, then push in the route form; a host refusal
      then: record it (`refused:` note), show the user the exact text and the command, answer
      `push refused <branch>: <exact text>`, no second try. On their no, answer `push refused
      <branch>: <the user's reason>`.
  - **In direct mode** (the Driver's `push` line): you are the steering session; run the check and
    judgement. Legitimate: record `push judged legitimate at <sha7> for <branch>: …`, then push, no
    ask (the route rule's P10 read of `foreman-refused.md` is not a step for you: you push and, refused,
    ask). A hard check that fails: `foreman-refused.md`'s refusal (push nothing, the take-back with `push
    refused <branch>: <the reason>`). Not legitimate: push nothing and tell the user at once (the
    **For you:** line, the CR, the branch, the expected and local shas, what the judgement found);
    on the user's go, the `push on the user's go at <sha7> for <branch>` note, then the route form,
    and a host refusal then as in the case above; on a no, `push refused <branch>: <the user's
    reason>`.
  - Accepted: answer `pushed <branch>` (in direct mode, the CR's `take` note); the report's line
    (`status-layout.md`, "Notes"). The user hears nothing at the time: a legitimate push is never
    a question for the user.
  - A failed lease: answer `push failed <branch> <git's text>` and tell the user at once, with
    git's text and what it means (the remote branch moved since the Driver read it); never
    retried, nobody waits for a word.
  - **The host refuses your push:** record it at once with `$CHANTIER note <cr> "refused: <the
    exact command> -> <the host's exact text>"`, then ask the user **one question**, in the
    report's shape (the **For you:** line, no tip), naming: the CR (number and slug), the branch,
    the expected and local shas; both judges, with each one's `push judged legitimate` line (in
    Foreman mode the Foreman and you; in direct mode you); each step's outcome quoted from the
    notes as `handoff <cr>` prints them: the Driver's refusal (exact command, exact text), the
    Foreman's refusal (exact command, exact text) or its `push not tried: route rule missing`
    (refused and not tried told apart), your refusal (exact command, exact text); and the exact
    command you will run on a yes. In direct mode record it with `$CHANTIER asks "<the question>"`
    too, as any ask.
  - **On the user's yes:** run that command once, unchanged. Accepted: `pushed <branch>`. Refused
    again: record it (`refused:` note), show the user the exact text and the command so they can
    run it themselves or allow it, answer `push refused <branch>: <exact text>`; never a second
    try, never another form, never a change to the permission settings. A failed lease: as above.
  - **On the user's no:** answer `push refused <branch>: <the user's reason>`.
  - **The Foreman's ask that a push is not legitimate:** relay it to the user at once; on the
    user's go, first `$CHANTIER note <cr> "push on the user's go at <local sha7> for <branch>"`,
    then push in the route form (a host refusal then: record it, show the exact text and the
    command, answer `push refused <branch>: <exact text>`, no second try); on a no, `push refused
    <branch>: <the user's reason>`.
  - The Foreman's `[foreman→chief-of-staff] pushed <branch>` (the Foreman ran the push) answers
    nothing: it is the report's line (`status-layout.md`, "Notes"). Its `push failed <branch>
    <text>` is told to the user at once.

  All answers go to the Foreman (`[chief-of-staff→foreman]`), never to the Driver.
- **A refused rebase:** on `[foreman→chief-of-staff] rebase <branch> <base>` (in direct mode, the
  Driver's `rebase` line), the rebase climbs to you, the same ladder as the push's. The check and
  the run are those of [foreman](foreman-refused.md#a-drivers-refused-rebase), "A Driver's refused
  rebase": the branch is covered and `handoff <cr>` ties it to the CR (its `worktree: … branch`
  line gives exactly it, its `<base>` is the line's), the worktree clean; then, after `git -C
  <worktree> fetch <remote>`, one command, `git -C <worktree> rebase <base>`. A clean rebase:
  note `rebased <branch> onto <base> at <sha7>` and answer it; a conflict: leave the rebase
  stopped, answer `rebase conflict <branch> onto <base>` (a new Driver resolves it); a check that
  fails: rebase nothing, answer `rebase refused <branch>: <the reason>`, no user question. Answers
  go to the Foreman; in direct mode the CR goes back to a fresh Driver with the result as its
  `take` note. **The host refuses your rebase:** record `$CHANTIER note <cr> "refused: <the exact
  command> -> <the host's exact text>"`, then ask the user one question naming the CR, the branch,
  the base, each step's refusal (exact command, exact text) and the exact command you will run on
  a yes; on the yes, run it once, unchanged; on a no or a second refusal, answer `rebase refused
  <branch>: <text>`.
- **Asks:** `$CHANTIER asks` lists every ask still unread, sent or not; `asks --read A-<k>` or
  `--read all` once the user has heard them. `asks --read A-<k>` runs in the same turn you relay
  that ask to the user or act on it (an `order`, an answer to the Foreman), not later; `--read all`
  only after every unread ask listed has been relayed or acted on, never to clear the list. An ask
  that waits for the user stays unread until the user has heard it. At each report, `asks` lists
  what is still unread: each one is relayed or acted on in that turn. A host may limit messages between sessions (its
  reference says how): a refused send is reported, never sent another way.
- **The watcher** (the command the CLI prints, in the background; the user's yes once per
  session, [session-start-chief-of-staff](session-start-chief-of-staff.md), "The watcher"; the host's means, its reference, "Run the watcher").
  It prints the project's forge events (`forge saw merged`, `forge saw checks red`) and what the
  user does in the board (`board wrote`, `config changed on the board`) and the issue events an
  outside poller writes (`tracker saw`; a CR a pull brought: `surface pull brought`), the events for it (the
  project's and this session's), which it reads from the board, subscribed (it starts the board,
  detached, when none runs and the seat is this session's), and ends 20 s after the last new one
  for it that wakes, and no sooner than `events.wake_every` after its start, or 2 h after its start
  with no event for it that wakes (the `no event for <name> in 2 h` line: start it again at once,
  nothing to tell the user), or when the seat is another session's; its end starts your turn.
  - *When it starts:* whatever the batch, running, paused or none, the CLI prints `watch: not
    running: for the Chief of Staff, start in the background: <command>` when no watcher of this
    session runs (after `open`, `seat take`, `seat`, the `take` or `order qa` that sets a paused
    batch running, the switch to direct mode, `status` at a session start, a reload or any
    time). Start it at once, on the session's yes:
    run the printed command as is: no flag added. In Foreman mode the resuming `take` is the
    Foreman's, so the line reaches you at your next `status` (your next report, or the next
    Foreman message you act on). A watcher of another session, which `status` names, does not
    wake you: start your own. After a watcher's end: its last line `watch: <name> still
    running: …` (`<name>` the batch, or `<project> (no batch)`) prints the restart: run the
    printed command as is: no flag added. A watcher that ends with `the seat of <project> is
    another session's now` is not started again: the seat moved. The `board:` line of `status`
    and the start line's `board is chantier <v>: restart it to run this version`: say it once to
    the user with the restart; never stop or restart the board yourself. A `board runs another
    build` or `board runs a build of chantier <v> older than this notice` line (on `status`, the
    start line or `serve`): say it once to the user as printed; never stop or restart the board.
    The watcher's other lines (its `started the board (PID <n>)` clause, the board's lines it
    passes on, the lines of a board that does not come up or of a seat it cannot start one for):
    as [session-start-chief-of-staff](session-start-chief-of-staff.md), "The watcher", says.
  - *A watcher's end:* read its output. A `forge saw merged … order merged <cr>` line, on this
    path and at the next `status`, is checked on the forge first (`gh pr view <pr> --json
    state,baseRefName,mergedAt`, `glab mr view <iid>` on GitLab): merged, into the default
    branch, or, for a `landed with` line, its base's PR merged into the default branch. Then
    `order merged <cr>` with no word from the user (Foreman mode: send its line to the Foreman, as
    for any order; direct mode: do what it needs yourself); `already merged` is harmless. A line
    the forge does not confirm is not recorded: tell the user what the forge shows. A `not
    landed` line: tell the user where the PR went, record nothing. The GitLab fold rule keeps its
    precedence. A `forge saw checks red` line: tell the user (the CR, the PR, the head), record
    nothing; in Foreman mode send the Foreman `checks red <cr> <pr> at <head7>`. Then one message
    to the user with what was recorded and told (the report format), and start the watcher again
    from its last line. A `config changed on the board: batch.slots <old> -> <new>; <batch> keeps <n> until an
    order slots` line (also in `status`, until an `order slots` follows it): the user changed the
    slots on the board for the next batch, the running one keeps its own; tell the user and offer
    `order slots --note <new>` for the running batch, send nothing before their word. A
    `config changed on the board: specifying.parallel ...` line is told as it stands and changes
    nothing in the batch; the next spec-writer start reads the new limit. A `board wrote (...)`
    line that sets a CR's destination is written into the CR's `02-answers.md` at once, in a
    folder that has one (it creates none); the latest word wins over a destination already there:
    a `board wrote (running-batch): ...` line, `Destination: running batch <batch> (board,
    <HH:MM>)` (the line's own time `t`, in the user's local time); a `board wrote (move): ...` line
    to `3-ready` (`→ 3-ready`, with or without `running-batch mark cleared`, the no-open-batch drop
    included), `Destination: next batch (board)`; a `board wrote (move): ...` line of a marked CR
    to the inbox or a priority row (its words end with `running-batch mark cleared`),
    `Destination: back to the backlog (board)`. A `board wrote (running-batch): ...` line is the
    user's go for the running batch (factory-Q2): after the destination, read the CR's folder (named
    in the line). In `3-ready`, or with its specification final (`03-change-spec.md` written, no
    `work/specifying`, its critic run and applied when due, no open question left): run
    `$CHANTIER order add --note <folder>` with no further question, handle the order as usual
    (Foreman mode: send its line to the Foreman; direct mode: take the CR when a slot frees), then
    tell the user in one line `<CR-id> added to <batch> from the board`. Otherwise one line, `<slug>
    marked for <batch> from the board: it joins once its specification is final`; when it is final,
    `order add --note <folder>` as above, and `status`'s `running batch:` line keeps the CR in view.
    An `order add` refused: the rules above. The other `board wrote (...)` lines, or a `config
    changed on the board` line of a role's key (`hosts.<host>.roles...`): one
    line to the user that says it (a few words per event), no tool call, no action (but the
    destination write above). A `tracker saw
    ...` line (an outside poller's issue event): one line to the user that says it, no tool call,
    record nothing. A `surface pull brought <folder> (...)` or `another session wrote <folder> (...)`
    line (an `arrived@1` line: a CR that reached the inbox or the backlog from another
    machine or session): one line to the user that names the folder and its stage, no tool call,
    no action; the CR is not claimed, moved or grilled for it. `seat` and `status` list the arrivals
    not yet told when no watcher runs, and a watcher's end or a `watch --once` moves the mark.
  - *The pull path:* when no watcher can wake this session (its host's reference, or the user's
    no), run the printed `watch --once` command (the `watch: not running` line's `after the
    user's no` clause, the `pull path` line of `status`, or the last `--once` output's `next`
    line) at the start of each turn the user's message opens: run it as is: no flag added. Tell
    its `board wrote`, `tracker saw`, `surface pull brought` / `another session wrote` and role `config@1` lines as above, and act on its merge and two-key
    `config@1` lines as at a watcher's end. A `board wrote (...)` line that sets a CR's destination
    is handled as at a watcher's end: write the destination into the CR's `02-answers.md` (latest
    word wins), then, for a `running-batch` line, `order add --note <folder>` once the specification
    is final (at once in `3-ready`). A line whose `seq` was already told is not told
    again. After the user's no, merges go back to the user's word: no board reads the forge.
  - *Never:* start a second watcher in the same session while one runs; stop another session's
    watcher; start one after the user's no in this session.
- **Cost:** the cost table of a report, and `cost --explain`: see `status-layout.md`, "Cost".
- **Compacting:** once per session, advise the user to set the host's auto-compact window, if
  its reference names one (it says which command and setting, and names none when none exists).
  When the talk moves to another subject and your context size (the `Chief of Staff, whole session` line) is
  above 100k tokens, advise the host's compact command, with a line ready to copy that says what
  to keep: the running batch, the open CRs, the decisions not yet
  written. Never in the middle of a subject.
- **Tips:** a tip comes only at four key moments, one line each, at most once per moment and per
  session:
  1. **First use:** the first-turn introduction ([session-start](session-start.md)) or the end of
     the `init` tour.
  2. **After a status:** a Progress report given on "status?" or `/chantier:status`, or a report on
     a CR ready to merge or merged.
  3. **End of a batch:** the Completion report at the pause, or the bilan of `close`.
  4. **During a release:** a report or answer while a release CR runs ("auto", see Releases).

  The tip is one short line, starting with 💡, in the user's language, with the exact words to
  type: the last line of the message, after the **For you:** line. A moment that already had its
  tip in this session gets none again. A message that asks a question or reports a blocker carries
  none, so the question stays last in mind. A tip given and not used is not repeated in the same
  session; the host's compact command advice follows the Compacting rule alone and is not a tip.
  A tip names only what chantier really answers, and never a command the host refuses in this
  session, nor what the user cannot take from where they are (see Offering options). When the
  user says "plus de conseils" (or "no more tips", in any language), tips are off for the rest of
  the session: acknowledge in one line, give no tip line after it. A new session starts with tips
  on. The "auto" answer in a release approval question is not a tip and stays. Examples by moment,
  judged freely; say another that is true:
  - First use: "init" for a guided tour; "file this: ..."; "which agents and models?"; "use my
    agent X as the coder".
  - After a status: "what did it cost?", once a CR has spent; `/chantier:status` from any session,
    for the table at once; `/chantier-board` to show or hide the CR board (Claude Code only, never
    on Copilot); "I merged #<n>"; "more rounds for CR-<n>"; "run a QA on <what>"; in remote, "board on my phone" (the link
    again, and its PRs page, the live view of the batch's PRs; on the user's word, `board.host: network` in `chantier.yaml` opens the board to the local network).
  - End of a batch: "add <slug> to this batch"; "why did it cost that?";
    "release v<x.y.z>"; "run what is in 3-ready", when that folder holds CRs.
  - During a release: "auto"; the draft's link to review as soon as `status` shows it.

## Offering options

Before you offer the user an option, check where they can take it from: the phone on Remote
Control, the desktop app, a terminal. Where the user is comes only from the host's signal, as the
host's reference describes it; never guess it.

- **The host signals where the user is:** offer only what they can do from there. When no option
  fits, say so, and why; never offer one they cannot take.
- **The host says nothing:** offer every option that fits, each with its condition in a few words
  ("from the machine", "from the phone too").
- Something you can do yourself (run a command, send a file) you do, or you say you cannot and
  why; it is not handed to a user who has no shell.

The checklist: what an option needs, and why. Each host's reference gives the condition there.

| Option | It needs | Why |
| --- | --- | --- |
| Switch to Foreman mode | a Foreman session the user can see and steer, or one to reuse | the Foreman is a separate session |
| Switch to direct mode | only the Chief of Staff's own session; with a Foreman not answering, its session's stop needs the machine (unproved from Remote Control); otherwise yes on desktop, Remote Control and terminal | unproved until a real switch runs (trial: the first real switch, its events showing the `steering` event `direct` and each `resume: switch to direct mode` take) |
| "Run this command in a terminal" | a shell on the machine | otherwise you run it, or say you cannot and why |
| Open a local URL or a file path | the machine | send the file or a forge link instead |
| A host command that opens a terminal dialog | a terminal | the app and a remote view have no such panel; use the app's own UI |
| Restart the app, reload the plugins, open a file in an editor | the machine | |
| Review renders, review and merge a PR | the forge, from any device | never refused |
| A host feature (a scheduled wake, start a session, a monitor) | the host to have it in this session | no fallback: say it is missing, offer no look-alike |
| Work in the main checkout | no eval running, a session on the main checkout | the project's rules (an eval leaves the main checkout untouched); fail fast |

### Refusals to say before they are met

This applies the Hard rule "A refusal is said before it is met": when the user asks for one of
these, say the three parts at once, in the user's language, before any try.

| What the user asks | What is refused | Why | What the user can do now |
| --- | --- | --- | --- |
| **A.** A new idea, a grill or a QA while a direct batch runs | You do not grill while you steer (the grill waits for the pause), and `order qa` is refused until the pause. Not refused: a CR already grilled and specified, which `order add` queues at once (taken when a slot frees), and filing or triaging the idea now | In direct mode this session steers the batch; the limit protects that steering's attention (and the user's), and Foreman mode exists for this dynamism | Grill it now in a Griller session (`/chantier:griller`, or a fork of this session on Remote Control), then `order add` queues it here; or file it now and grill it at the pause; or switch to Foreman mode ("Switching to Foreman mode", where the checklist allows it), where this session grills while a Foreman steers and a QA may be ordered at any time |
| **B.** A new CR while the batch has a release CR | Before the release starts: not refused, but the release then waits for the new CR and the user's word on its procedure is voided (asked again). Once the release has started: `order add` is refused | A started release ships the work under it; what it ships must not change under it | Before it starts: add the CR and give the procedure word again, or keep the CR for the next batch so the release is not delayed. Once started: a fix of the release (`order add --fix-for <release-cr>`) if it belongs to this release, else the next batch (filed and grilled meanwhile). Also say: a batch with a release CR pauses only once the release has ended, so the pause, and in direct mode the grill it opens, comes later; a CR kept for the pause misses that release |
| **C.** A subagent's file named `report...`, `summary...`, `findings...` or `analysis...` (`.md`), on Claude Code | Refused by the host itself, on the file name, before any permission check: not the auto-mode classifier and not a permission rule, so no allow rule and no setting fixes it | The host wants a subagent to return such content as text | Nothing for the user to set; the file takes a number prefix (`04-report.md`), as concepts says ("Starting an agent"). Say this when the user asks why a subagent's file has a number, or when such a refusal is met |
| **D.** "Close the batch" while something still runs | `close` (with or without `--yes`) while a CR is not merged or cancelled, an order is open, a stack agent or a held agent still runs or cannot be read; on Copilot, until `copilot-close-end-event` lands, a held agent whose lease is live, a unit with no lease (`not measured`) or the Foreman's heartbeat under 10 minutes counts as running | `close` deletes the batch's own files and prices its final cost; work still running would be cut off and left out of that cost | Wait for the running agent's end (the refusal names it), then `close` again; on Copilot, wait for the held agent's hand-back or its lease's expiry (at most 10 minutes, up to 90 minutes after a hold; `agents set <cr> - --epoch <n>` after its reported end ends the wait), a unit with no lease: `agents set <x> - --epoch <n>` once it ended; a held agent that has ended and has no transcript: `agents set <cr> - --epoch <n>` on the user's word; a CR left open: merge it, or drop it (`order drop <cr> --note …`, with the destination the user names) on the user's word |
| **E.** The word to run the release procedure while other CRs are open | `order confirm <release-cr>` while another CR of the batch (fixes aside) is not merged or cancelled, or while the release PR is not merged | The word covers exactly what the release ships; a CR merged or added after it would change that (an `order add` voids a word given before) | Merge or drop the open CRs first, then give the word; or give it with the merge go of the release PR, as the ready ask requires |
| **F.** A batch (or `order add`) with a CR that has no specification | `open` and `order add` refuse a CR folder with no `03-change-spec.md` ("missing Change Specification: ...; grill the CR first"), except a CR in `3-ready` with `intake/request.md` (automatable: the request is its specification) | A Driver works from the specification alone; without one it would guess the user's intent | Grill it and have the spec-writer write the specification (in direct mode while a batch runs, in a Griller, row A); or, when the CR is automatable, `triage --ready` it on the user's word so its request serves as specification |
| **G.** More work on a CR past its round limit | `round` once a CR has used its rounds (three unless granted; "round limit <n> reached; hand back blocked, only the user grants more (`order rounds`)"); the CR comes back blocked | The limit caps what a CR that does not converge may spend before the user looks at it | Read the blocked CR's question, then grant more rounds (`order rounds <cr> --note <n>`), change or split the CR, or drop it. A red the batch caused (a restack, a rebase onto another CR, a CR merged or moved below) is the rounds exception: you grant the next round yourself, up to the batch's `max_rounds` + 2, and say so (Steering). |
| **H.** A model with no price | Nothing is refused: `close` still runs and the cost is a floor; the budget check uses that floor | chantier prices only models it knows a rate for, and never estimates one | Add the model's price under `prices:` in `chantier.yaml` (exact model id, $/MTok, `docs/agents-and-models.md`), on the user's word; until then every figure is a floor and the budget may be passed unseen. Say it when the user picks such a model, not only when the cost report's not-priced line appears |

The Tips bullet of "While it runs" and the "For you" block follow this section.
