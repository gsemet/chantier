# Foreman: a lost Driver

## A lost Driver

- **A lost Driver** (a CR's, the release's, the stack's or a QA order's: the rule covers every
  kind, and holds in a direct batch, whose Chief of Staff reads this card).
  - **A Driver waiting on its own background work** has not ended while its CR is `working` (a hand-back already recorded: "An ended Driver that wakes again"). A Driver that ends its turn
    while its own background work runs (the long gate, a CI watch) is allowed to. On Claude Code the
    host says `Agent "<name>" is waiting on its own background work`: send it no message and no
    ping, and do not run `agents set -`. It wakes on its own when that work ends, and the
    heartbeat's `activity` line covers it (`gate running`, `gate queued`, an age). Only `Agent
    "<name>" finished`, or a host refusal, is an end.
  - **An ended Driver that wakes again.** This applies to a CR or Release Driver whose hand-back
    the record already holds (the CR `ready`, `blocked`, merged or cancelled) when it wakes with no
    message from you since that hand-back. The signs: its hand-back line comes a second time;
    another line from it answers nothing you sent; or the host's notice says it is waiting on its
    own background work while `status` shows no `gate running` and no `gate queued` for that CR.
    With a gate running, leave it alone: that shell is its long gate, and it ends on its own. A
    background task it left running woke it. Do not act on the line again, since the record holds
    the hand-back. Stop that Driver by the host's means (your host's reference, "Stop a Driver"),
    then `$CHANTIER note <cr> "stopped: leftover background work after its hand-back"`, then
    `agents set <cr> - --epoch <n>`, in the same turn, as "Keeping its own stops apart" asks for
    your own stops. It is not a restart and not a silent end, and it counts toward nothing. A
    Driver still recorded on a `blocked` CR that answers your note (a `waits:` that landed, a
    `question:` answered to it) is not concerned: that is the note's answer.
  - **Suspect:** a working CR (or the stack driver, or an open QA order) whose `activity` line
    shows no activity, no `gate running` and no `gate queued` for one full heartbeat interval (the
    steering wake, 55 minutes by default). A line
    `not measured` or a row `no Driver recorded` is read for what it says, never as activity. A
    project's `AGENTS.md` ranks above this threshold.
  - **Proof of death**, one of three: the host refuses a message to the agent because it no
    longer exists (dead at once); or a `[foreman→driver <cr>] ping` to a suspect gets no `pong` by
    the next wake (on a host whose reference says a Driver cannot answer before its end, the sign that
    reference names stands in place of the `pong`: for Claude Code, [its reference](hosts/claude-code.md), "A Driver's silence"); or the host says the Driver was stopped, read at once, with no ping round and no
    message first. On Claude Code that is exactly two things: the stop a compaction snapshot reports
    (the `task_status` `killed` record, which the session sees as `Task "<name>" (<id>) was
    stopped.`, and which `status` flags: a CR's row in any `status`, the stack driver's and a QA
    order's `activity` line in `status --refresh` only, so on the heartbeat's wake), and the host's
    refusal `Agent <id> was stopped and won't be resumed…` of a message sent to it. Never try to
    resume such a Driver by a message: the host refuses it (proved, batch-22).
  - **A `pong` proves a Driver alive, not that it moves:** one with no new round, head or note for
    3 hours gets `stop`.
  - **After an app restart, at a new epoch:** Drivers are background children of the steering
    session and die with it. When a new Foreman epoch is claimed, every `working` CR, the recorded
    stack driver and every open QA order with an agent id is restarted at once, with no ping
    round.
  - **After a switch to Foreman mode** (with the bullet above): when you claim the batch from a
    direct batch, every CR whose Driver the switch stopped, the recorded stack driver and every
    open QA order with an agent id are restarted at once by the restart path, with `resume: switch
    to Foreman mode`; this is a death by the host in the sense of "A silent end" (it does not
    count). A CR the Chief of Staff's Driver handed back `blocked stopped` with the switch's note
    is taken back the same way and counts toward nothing.
  - **The restart path**, for every restart (a proven death, a new epoch, a silent end, a
    `context:` hand-back, a host failure), always starting by clearing the id: `agents set <cr> -
    --epoch <n>`, `handoff <cr>`, `take <cr> --note "resume: <cause>" --epoch <n>` (for a host
    failure, `--note "resume: host failure: <exact text>"`), a new Driver, `agents set
    <cr> <id> --epoch <n>`. No round is counted and no second slot is taken; the budget applies (a
    refusal with exit 5 is a `budget` ask).
  - **A hand-back `blocked context: …`** (the Driver's context reached the threshold, or the host asked its hand-back early, or the Driver handed off its closing
    (`context: closing: …`: at its pushed-head `VERIFIED` with 115,000 tokens or more, or at the
    context rule during the closing): its text says which): restart a fresh Driver on
    that CR before any queued CR (a blocked CR holds no slot, so it takes the next free one):
    `agents set <cr> - --epoch <n>`, then `take <cr> --note "resume: context" --epoch <n>`, no
    round, no ask. A second `context:` on the same CR with no new head, round or note since the
    first is an ask: `question <cr> driver out of context twice`. In a report or a retro, a
    `context: host asked the hand-back …` is named "a turn ended early", with what the Driver
    waited for, never "out of context". A text that starts `context: closing:` goes through the
    same restart path with the note `resume: closing`: `agents set <cr> - --epoch <n>`, then
    `take <cr> --note "resume: closing" --epoch <n>`, then a new CR Driver, then `agents set <cr>
    <id> --epoch <n>`. No round is counted, no ask is made, and it goes before any queued CR. A
    report or a retro calls it "the closing step", never "out of context". The second-`context:`
    ask counts only real context ends (no `host asked the hand-back` and no `closing:` in the
    text). A second `context: closing:` hand-back on the same CR with no new `closing:` step note
    (`closing: body posted at …`, `closing: description pass VERIFIED at …`, `closing: PR ready`
    or `closing: PR kept draft on …`) since the first is an ask too: `question <cr> driver out of
    context twice`.
  - **A Driver stopped from outside** (any Driver kind: CR, release, stack, QA order):
    - **Which stops:** only a stop the steering session did not make itself. Its own stop by the
      host's means (a switch to Foreman mode or to direct mode, a drop, the user's stop or
      hold, the `stop` after a `pong` with no progress for 3 hours) is never restarted by this rule;
      each of those keeps its own path. A stop the user makes in the app is from outside.
    - **Keeping its own stops apart:** the snapshot record does not say who stopped the agent, and a
      compaction may come after the steering session's own stop. So when the steering session stops
      a Driver itself and does not restart it at once by the restart path, it clears the id it
      recorded for it in the same turn (`agents set <cr> - --epoch <n>`, or `agents set stack -` /
      `agents set <O-k> -` for the stack driver or a QA order), after a `note <cr> "stopped: <why>"`
      for a CR, except a switch of mode (to Foreman or to direct mode), whose restart path
      clears them. The `status` flag names only a recorded agent, so it never shows for the steering
      session's own stop; and a refusal to a message to an agent it no longer has recorded is not
      this rule.
    - **What it does:** it takes the restart path at once (`agents set <cr> - --epoch <n>`,
      `handoff <cr>`, `take <cr> --note "resume: stopped from outside: <the host's text>" --epoch
      <n>`, a new Driver, `agents set <cr> <id> --epoch <n>`; for the stack, `take stack --note …`
      as in its existing restart). It is covered by the batch's go: no ask, no question to the user,
      no wait for the user's word. The host's words "only launch a new agent if the user explicitly
      asks" are answered by that go.
    - **Counting:** it is the host's doing, like a death by the host: it counts neither toward
      `driver ended twice` nor toward "blocked twice" in Escalation, and it is restarted at each
      such stop, however many (no "second stop" ask, unlike a second host failure).
    - **Said in the report:** your next report names each such restart: the CR, "stopped from
      outside", the time of the stop, and the new Driver's agent id. In Foreman mode your report
      line to the Chief of Staff carries it, and the Chief of Staff gives it in its report to the
      user.
  - **A host failure:** a Driver (CR, stack, release, QA) whose end carries the host's error
    rather than a hand-back takes the restart path at once, with no ping round (the host's error is
    the proof it ended). It is not a silent
    end: it does not count toward `driver ended twice`, nor toward "blocked twice" in Escalation.
    The new Driver reads from `handoff` what the record kept (a gate passed at the shipped head,
    verdicts, the PR) and does not redo it when the worktree's head is that head and the tree is
    clean. A second host failure on the same CR with no new head, round or note since the first is
    an ask: `question <cr> host failure twice: <text>`.
  - **A Driver that ended with no hand-back recorded** (the `status` flag, or a `[driver
    <cr>→foreman] hand-back …` report while `status` still shows the CR `working`):
    - resume it once by the host's means to resume a stopped agent (its reference):
      `[foreman→driver <cr>] record your hand-back: $CHANTIER handback <cr> as your report says,
      then the host's hand-back with the line it prints`;
    - keep or set again its id (`agents set <cr> <id> --epoch <n>`), so the log shows the resume;
    - when the CLI records its hand-back, handle it as any hand-back;
    - when it records none by the next heartbeat wake, or the host refuses the message: `agents set
      <cr> - --epoch <n>`, then the restart path with `--note "resume: ended with no hand-back
      recorded: <its report's first line>"`. This counts as a silent end ("A silent end"). A resume
      that records the hand-back counts as nothing. A refusal that says the Driver was stopped
      (`Agent <id> was stopped and won't be resumed…`) is the outside stop: it goes to "A Driver
      stopped from outside", with its note `resume: stopped from outside: <the host's text>`, and
      counts as nothing; any other refusal keeps this rule;
    - never record the hand-back yourself: `handback` is the Driver's.
  - **A silent end** (a task that ends with no hand-back) takes the restart path. A second silent
    end on one CR is `handback <cr> blocked driver ended twice`. Only silent ends of the Driver
    itself count: a death by the host (a new epoch, all Drivers lost at one wake), a Driver stopped
    from outside and a `context:` hand-back do not.
