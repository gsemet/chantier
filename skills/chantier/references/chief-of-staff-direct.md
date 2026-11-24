# Chief of Staff: steering a batch yourself

## Steering a batch yourself

In direct mode no Foreman session is started: you steer the batch from your own session. The CR
lifecycle, the batch's frame (`open`, slots, rounds, budget, orders, `pause`, `close`), the folders,
`STATUS.md`, the reports and the user's boundaries are the same in both modes. Read
[foreman](foreman.md) (and, for a stack batch, [foreman-stack](foreman-stack.md)) and your host's reference ([Claude Code](hosts/claude-code.md) or
[Copilot](hosts/copilot.md)) and do what they say of the Foreman, until the batch completes, with
these differences.

- **Leases.** The Foreman's rule is yours: `take` is refused while a unit's lease is live
  (`--reclaim` only on the user's word) or not confirmed (a `lease not confirmed since …` mark in
  `status` is not a Driver gone; check with the host that it ended, then `take <cr> --reclaim --note
  "resume: lease not confirmed"`; a QA order: `agents set O-k <id> --reclaim`; the stack: `take stack
  --reclaim`), and `agents set <cr>|O-k|stack -` after an agent's reported end ends its live lease. A `lease hold` keeps a lease live up to 90 minutes with no process behind it; once the host shows its holder ended, that `agents set ... -` ends it with no word of the user; `--reclaim` on a live lease stays the user's word, for a holder the host cannot show ended.

- **A refusal you do not understand.** A Griller's or a Driver's: `$CHANTIER access <cr> --epoch
  <n>` before you ask; it explains and changes nothing.

- **Escalation.** The Foreman's escalation triggers ([concepts](concepts.md), "Escalation") are
  yours: the escalation model is the `escalate:` line of `$CHANTIER playbook`. The two rounds
  routes are yours too (`escalate: rounds` after the user's grant of more rounds; a grant under
  the rounds exception is taken with `rounds exception:` and no escalation,
  `escalate: blocked twice`), once per CR, then the user; a CR with no rounds blocked twice goes
  straight to the user's question. A restack that fails runs the stack driver's
  `conflict-resolver` on the escalation model, the stack driver keeping the batch's model.

- **Your title.** At `open --direct`, rename yourself `[<code>] 💬 Project · CoS (Batch <nn>)`;
  after `close --yes`, back to `[<code>] 💬 Project · CoS`
  ([titles](titles.md), the Foreman row).
- **Your number as Foreman.** Claim it as a Foreman does: `$CHANTIER foreman set <your session id> --epoch
  <n>` (`1` for a new batch), then `$CHANTIER foreman transcript <your transcript id> --epoch
  <n>`. On a batch opened empty, claim it just before your first `take`, not at `open`, so the
  wait costs the batch nothing. Right after each claim, every batch you steer, a resumed or taken-over one too: run
  `$CHANTIER rules` and read the rule files it lists, as a Foreman does at its start. A reading
  before this batch's `open` is not this batch's; skip only the re-read of a file this session
  has read since this batch's `open` and since its last compaction. The command runs every time,
  after the claim, whatever ran before it. Carry `--epoch <n>` on exactly these commands and on no other: the claim (`foreman set`,
  `foreman transcript`), the loop's wakes (`status --refresh --epoch <n>`) and the recorded stop
  of your loop (`status --stop-heartbeat`), `take`, `agents set`, `order done`, `order merged`,
  `order add --fix-for`, `gate <cr> --first`, `cancel` and `pause`. Each of them refuses a call
  without `--epoch` (exit 2), except `order merged` and `order add --fix-for`, whose form
  without it is the Chief of Staff's order, and the refresh before a report. Any other command,
  or any other `order` kind (`order add` without `--fix-for`, `order note`, `order after`...),
  refuses `--epoch` (exit 2), except `access`, which reads `--epoch` as an option and renews and
  records nothing. Never
  on the refresh before a report, which stays `status --refresh` with no epoch and records no
  heartbeat; arm the
  same heartbeat, as your host's reference says. Your own "heartbeat N min" is the minutes since
  your loop's last wake, and "heartbeat stopped" is a loop you ended on purpose (the host's
  reference says how it is recorded). The CLI prices your transcript from that claim, as one `Chief of
  Staff, steering the batch` row, which counts in the spend and the budget as a Foreman's does;
  the turns that grill with the user or write specifications (a turn that writes a CR's
  `01-intent.md`, `02-answers.md`, `03-change-spec.md` or `work/specifying`, or starts a
  spec-writer or a spec critic; a turn that only names or reads them, in a Driver's prompt or a command, stays on
  the row; a turn is attributed whole) leave that row for the `grill and specifications with the
  user` line, outside the budget. Write those four files with the host's Write (or Edit) tool,
  never with a shell command: the CLI recognises grill work only by that write. A `steering the batch (outside the budget)` line also shows what you spent since the
  batch opened outside your claim window (before the claim, after a Foreman took over); the `Chief of Staff, whole session` line prices the whole session, steering window included, and names in a
  parenthesis the part that is in the batch's spend; it counts the
  compactions since the batch opened.
- **The Drivers.** You start them, several in parallel on the free slots, in the background, and
  hear their hand-backs, as the Foreman's card says, including its check of a `no long gate`
  hand-back. "Never message a Driver" does not hold for the Drivers of a batch you steer. Start each
  Driver from the skeleton `take` (or `take stack`) printed, copied whole, each `<…>` filled in (the
  `Steering:` means from the host's reference); add no `writes:` line the skeleton does not print,
  and drop none it prints ([concepts](concepts.md), "A Driver's prompt"). Start a QA driver from the
  skeleton `order qa` printed, as the Foreman's card says, and record its agent id with `agents set
  O-<k> <id> --epoch <n>`.
- **A stack batch.** The Foreman's check of the five checks of a stack ready to merge
  ([foreman-stack](foreman-stack.md), "The five checks") is yours; one check, read on the forge
  (`$CHANTIER forge-stack show`), is enough before you tell the user the stack is ready to merge. Inserting
  a CR into a stack ready to merge is as in "Inserting a CR into a stack ready to merge", the stack driver and the
  release redone by you.
- **A dependent draft PR.** The Foreman's rule after an `order merged` (a draft handed back ready, waiting
  for that dependency goes back to a Driver with `rebase: <dependency> merged`) applies to you.
- **A note that carries work to a Driver.** The Foreman's rule applies to you: just before you
  send one (a `rebase:` first of all), read a plain `$CHANTIER status` and choose from the state
  it shows now: handed back `ready` or `blocked`, `take <cr> --note` and the take-back path; `working`, the
  message.
- **The main checkout after a merge.** The Foreman card's procedure ([foreman](foreman.md), "The
  main checkout after a merge": its steps, commands and `<why>` words) is yours, after each
  `order merged <cr> --epoch <n>` you record, with its `main checkout:` note on that CR
  (`note` carries no `--epoch`). It is on by default unless the project's rules forbid it; for an
  eval and a worktree session see "Work in the main checkout" in Offering options.
- **Nothing is sent to yourself.** No `ready <batch>`, no `[foreman→chief-of-staff]` line. An
  ask is still recorded with `$CHANTIER asks "<text>"` (so a resume loses nothing) and told to the
  user at once, in the report's shape. A Driver's refused rebase or force push is judged and run by
  you, as above, without asking the user, and asked to the user only when the host refuses you too;
  a push of a branch that is not chantier's is never run, the user is told of it; the CR goes back to a fresh Driver with the result as its `take`
  note (`push: <the result>`, as `foreman-refused.md` says): `pushed <branch>`, `push failed <branch>
  <text>` or `push refused <branch>: <text>`.
- **A CR added while the batch runs is queued.** `order add` queues it, with no pause needed, and
  you take it when a slot frees; `order qa` is refused by the CLI (exit 2). `order add --release`
  and `order add --fix-for <release-cr>` are accepted as ever, a release CR needing no real grill.
  Once the batch is paused it takes any number of CRs before its first `take` (below).
- **What you accept while you steer:**
  - "status?" and "what did it cost?"; answers to a blocked CR of this batch; orders on the batch
    itself ("I merged #42", "drop CR-140", "stop the batch", more rounds, slots or budget).
  - **Backlog work.** Any work on the backlog's files: file (`file`), triage (`triage`, on the
    user's word as always, directly or on a Griller's request), reorganise, merge items, drop
    (`abandon`, on the user's explicit word), and record answers and decisions in a CR's
    `02-answers.md` (the "Record at once" rule holds), and keep each CR's summary fresh
    (`summary lint`, `summary set`; `summary label` and `summary group` on the user's word
    only). `triage --ready` never joins the running batch: a CR joins it only by `order add`, from
    a destination the user chose ("Where the CR goes").
  - **The spec-writer and the spec critic.** On the user's word that a CR already grilled (by a
    Griller, or before the batch) is grilled enough, start the spec-writer as "Backlog and grill"
    says; the spec critic stays open too, on a CR grilled before, and its questions wait for the
    pause, like any grill question.
  - **Not while the batch runs:** grill a CR (ask its questions, write its `01-intent.md` from a
    discussion with the user); touch the running batch from backlog work (`triage --ready` joins no CR to it; the CLI
    refuses `order qa`; nothing starts that the user did not order on the batch);
    the demo.
  - Any other request is noted word for word and handed back when the batch completes; an idea
    that arrives while the batch runs is filed in the inbox at once (`file`, no grill). A request
    to grill, or to order a QA, gets at once, besides being noted, the three-part answer of row A
    in [Refusals to say before they are met](chief-of-staff-steering.md#refusals-to-say-before-they-are-met): what is
    refused, why, and the ways (a Griller session, or a fork of this one, is the user's step:
    explain it, never do it).
  - A paused batch is not running: all of this lifts at the pause. When the CLI paused the batch,
    your retro and its retro critic still run after the pause and before the close offer; what
    lifts at the pause does not lift them.
- **The pause.** The end of the last CR (your `order merged <cr> --epoch <n>`, `cancel`,
  `order drop`, a release Driver's `handback released`) removes the merged CRs' worktrees and
  branches whose Driver has ended and pauses the batch (`paused <batch>`). When it prints
  `every CR is merged or cancelled, not paused: <causes>`, do what blocks it, then the cleanup
  and `$CHANTIER pause --epoch <n>` as before. Then, in the same turn: cancel the armed wake (as
  the host's reference says), run the fast-forward of the main checkout, and write the batch's retro in `4-batch/retro.md`
  (a section headed with the date and the CRs it covers: one line per problem met with its
  long-term fix, `- [<tag>] <problem>: <long-term fix>`, the tag `project` or `chantier` as
  `foreman.md` defines it, a cause on both sides being two lines; what went wrong or slowly, from
  `status --notes`, `events.jsonl`, the CRs' `work/` notes and `cost --explain`; one untagged line
  saying so when there was none; one line per distinct refused command, `- [chantier] refused
  `<command>` (<capability>): <the table row or rule to fix>`; never rewrite an earlier section;
  a release's retro is named by reference, not copied), after running the `retro-critic` exactly
  as `foreman-pause.md` ("The retro critic") says (the section holds the kept points only, the dropped
  ones go to `4-batch/retro-dropped.md`). Give the
  Completion report, with its Retro offered as the Foreman-mode pause says (each point numbered,
  by route, on the user's word, before any `close`), then, once your retro critic has handed
  back, offer the close at once, unprompted: run `$CHANTIER close --batch <batch>` (the check, no
  `--yes`), show the bilan, the final cost, what goes, and its line of worktrees and branches to
  remove, which names the merged CRs' leftovers beside the trashed CRs' (with why each was kept,
  from the `cleanup:` lines when the session still has them), and its `kept, moved out with their
  work` line (show it, remove nothing on it), and ask "close the batch?" (until the user's
  `close`, the paused batch is still the running batch: a CR placed in `1-pending` by `order add`
  starts it again at the next `take`);
  `close --yes` only on the user's yes, as the Closing bullet says, and on the same yes remove
  every entry of that line, merged and trashed alike (`git worktree prune` for a folder git no
  longer knows). Grill the inbox ideas with the user and, on their word,
  `order add --note <folder>` for each CR: the batch stays paused; your first `take` sets it
  running again, and the batch pauses again at its end. `close` stays the
  user's word, and follows the Closing bullet: in direct mode it counts only your Drivers as something that
  runs (their transcripts on Claude Code, their live leases on Copilot until
  `copilot-close-end-event` lands), not your own session.
- **Switching to Foreman mode.** On the user's word, and only where a Foreman can start:
  preflight in Foreman mode passes first (P1, P2); under Remote Control the switch starts a new
  Foreman or reuses one, as at the desk. Start no new Driver. Before the Foreman starts,
  stop each live Driver you own (CR, stack, QA, release) by the host's stop, after `$CHANTIER note
  <cr> "switch to Foreman mode: Driver stopped; the Foreman restarts it"`; then start the Foreman
  with the next epoch, as in Starting a batch, and add to its prompt "Resume: restart every CR the
  switch stopped by the restart path, `resume: switch to Foreman mode`". No Driver of yours runs
  once the Foreman claims (two Drivers on one CR is what this prevents). Your epoch is then stale
  and the CLI refuses your steering
  commands (exit 3); the batch's steering becomes Foreman. The switch can be undone by the
  switch to direct mode (next bullet).
- **Switching to direct mode.** In order:
  1. **Trigger.** The user's word only ("switch the batch to direct mode", "take over the
     batch"), on a running or paused Foreman batch, its Foreman alive or not. It needs nothing a
     Foreman needs (no preflight P1 or P2): it works under Remote Control, in a terminal, on both
     hosts.
  2. **Pre-check, before anything is stopped.** Compare this session's own transcript id (the
     host's reference says where it is) with the batch record's `chief_transcript` (in
     `batch.json`). If they differ, run `$CHANTIER seat take <your session id>` (it records this
     session's transcript on the batch) and compare again. If they still differ, or the
     transcript is unknown, the CLI could not tell your claim from a Foreman's: stop, and tell
     the user why; no workaround.
  3. **Is the Foreman answering?** `$CHANTIER foreman get`, `$CHANTIER status --refresh` (no
     epoch) for `heartbeat N min`, then `[chief-of-staff→foreman] ping`. It is not answering
     when its heartbeat is late by the board's test (older than the batch's steering wake plus 5
     minutes) and no `pong` came within 5 minutes; or when the user said so (no wait). When its
     heartbeat is "stopped" (a loop it ended on purpose, or the batch's pause), the time in
     `heartbeat_stopped` counts as its last heartbeat.
  4. **A live Foreman.** Send `[chief-of-staff→foreman] switch to direct mode`, and start nothing
     until its `switched to direct mode <batch>: stopped <what>` line comes. A Foreman that
     answered the ping but sends no such line: keep waiting; only the user's word moves it to the
     "not answering" path. This path works under Remote Control too.
  5. **A Foreman not answering.** Its session is stopped by the user, or by you on the user's yes
     where your host's reference names the means (Claude Desktop:
     `mcp__ccd_session_mgmt__stop_session`; Copilot: none recorded, so the user stops it). Under
     Remote Control, say the stop needs the machine (stopping a session from the phone is
     unproved), name the session and wait. In every case name the session to the user (its title
     and the id `foreman get` prints) and wait until it is stopped.
  6. **Has each old Driver ended?** Before any restart, run `$CHANTIER close --batch <batch>`
     (the check, never `--yes`): it lists each held agent's transcript state. Restart only the
     CRs (and the stack driver, QA orders) whose old Driver is shown ended; for any shown running
     or unreadable, ask the user, and restart it only once the user says it is stopped. Never
     assume that stopping a session ended its Agent children. On the live-Foreman path the
     Foreman's `switched` line names what it stopped; the same check confirms them.
  7. **Claim.** `$CHANTIER foreman set <your session id> --epoch <n+1>` (`n` from `foreman get`),
     then `$CHANTIER foreman transcript <your transcript id> --epoch <n+1>`; the output's
     steering line confirms the switch. No such line: stop and tell the user (the batch is still
     a Foreman batch at Foreman n°<n+1>). If the output ends with `watch: not running: …`, start
     the watcher now (run the printed command as is: no flag added). Then, as after any claim of yours: `$CHANTIER rules`
     and the rule files, your title `[<code>] 💬 Project · CoS (Batch <nn>)`, and your heartbeat,
     as this section says. The old Foreman's number is stale: any command it still sends is
     refused (exit 3) and it stops.
  8. **Resume.** At once, by the restart path with `resume: switch to direct mode`, for each
     Driver step 6 showed ended: every `working` CR, the recorded stack driver and every open QA
     order with an agent id (`agents set <cr> - --epoch <n+1>`, `handoff <cr>`, `take <cr> [--reclaim after the host check, when
     the lease is only not confirmed] --note "resume: switch to direct mode" --epoch <n+1>`, a new Driver from the printed skeleton,
     `agents set <cr> <id> --epoch <n+1>`; the stack driver by `take stack --note ...`). A Driver
     of a Foreman stopped from outside counts as stopped from outside: no question to the user,
     counting toward nothing. A CR the old Driver handed back `blocked stopped` with the switch's
     note is taken back the same way and counts toward nothing. No round is counted, no second
     slot taken, the budget applies (exit 5 is a `budget` ask). Queued CRs stay queued; CRs
     handed back `ready` or `blocked` stay as they are; PRs, branches and worktrees are kept.
  9. **Said to the user.** One line: the batch is direct from now on, which CRs restarted (and
     which wait for the user's word that their old Driver is stopped), and that the old Foreman's
     spend stays in the batch's cost. Never the word "epoch" ("Foreman n°3 is stale: the Chief of
     Staff steers batch-06").
  The switch to Foreman mode undoes it.
