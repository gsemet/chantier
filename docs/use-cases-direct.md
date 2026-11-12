# chantier by use case: direct mode

In direct mode there is no Foreman session: the Chief of Staff starts the Drivers on the free
slots and steers the batch from your own session. The limits (slots, budget, rounds), the folders,
`STATUS.md`, the reports, the costs and your boundaries are the same as in
[Foreman mode](use-cases-foreman.md). The situations that do not depend on the steering (a new
project, ready work, PR descriptions, your own agents, cost) are on the
[common page](use-cases.md).

With no argument (`/chantier:chief-of-staff`), the plan names direct mode, and why, when the
session is under Remote Control or the host cannot start a Foreman session (a terminal or IDE
host). Your go approves it. You can also force it for the session
(`/chantier:chief-of-staff direct`) or say so.

## Same lifecycle, less dynamic

A direct batch has the same lifecycle as a Foreman batch: **running**, **paused**, then **closed**
on your word only (see [the life of a batch](use-cases.md#the-life-of-a-batch)). It is less
dynamic while it runs, in two ways.

**The running batch is strict.** No CR joins it while it runs: `order add` and `order qa` are
refused. The exception is a release: a release CR and its fixes are accepted. Once the batch is
paused, it takes any number of new CRs, like any paused batch, and the first one to start sets it running again.

**No grill in the same session.** While the batch runs, the Chief of Staff, busy steering,
answers only:

- "status?" and "what did it cost?";
- your answers to a blocked CR of the batch;
- orders on the batch itself: "I merged #42", "drop CR-140 grill-rules", "stop the batch", more
  rounds, slots or budget;
- work on the backlog's files: filing, triage, reorganising, merging items, dropping (on your
  explicit word), and recording answers in a CR's `02-answers.md`; a triage to `3-ready` does not
  join the running batch;
- the spec-writer, on your word that a CR already grilled (by a Griller, or before the batch) is
  grilled enough.

It does not grill, and it does not touch the running batch from backlog work. Any other request is noted word for word and handed back when the batch completes. An idea you
raise meanwhile is filed in the inbox at once, without a grill.

To grill meanwhile, open a Griller (`/chantier:griller`, or a fork in remote: see
[the how-to](use-cases.md#a-chief-of-staff-and-grillers-in-remote)). It grills, files and
specifies your own ideas into the backlog, beside the batch. Those
CRs join the batch through the steering session once it is paused (you say so there, and it adds
them), or wait for the next batch.

## Run a batch

> "Run the P1s, budget 20 dollars."

After the preflight, the plan and your go, the Chief of Staff opens the batch in direct mode and
starts the Drivers itself, several in parallel on the free slots. A CR that needs you is parked
as blocked with its question, and the Chief of Staff tells you at once, in the shape of a
progress report; the others go on. Past the budget, nothing new starts until you answer. Parallel
(the default), series and stacked pull requests work as in Foreman mode: parallel CRs are all based
on the default branch and rebased after each merge, a series goes one CR after the other, each on
the previous one's branch, and a stack driver orders a stack afterwards.

The orders of Foreman mode that act on the batch itself work the same: drop a CR, a note on a CR,
"I merged #42", more rounds, slots or budget, and a hold ("Hold" sets the slots to 0, "Resume"
gives a number back). The orders that add work to a running batch do not, as above.

## When the batch is paused, and when you close it

When every CR is merged or cancelled, the Chief of Staff removes the merged CRs' worktrees and
branches, then pauses the batch, and gives you the Completion report: the cost to date, what the
batch did not prove, the inbox ideas ready for a grill. Now it can grill, with you, in this
session.

> "Grill the CSV export and the import, then add them to this batch."

Once it is specified and you say so, the CRs are added, as many as you want: the batch stays paused until the first one starts, then runs again, and pauses again at
the end, with the cost to date grown. A paused batch stays paused, however long, until you say:

> "Close the batch."

Only on your word, and exactly as in Foreman mode: the check and the final cost, then your yes,
then the batch's own files are deleted, each merged CR moves to `5-archives`, and the dropped CRs' worktrees and branches are removed. In
direct mode the check counts only your Drivers' session files as something that runs, not your
own session. Without a recorded steering transcript, nothing can be priced and `close` refuses.

## Where it runs, and the preflight

Direct mode runs on any Claude Code entry point (the Desktop app, the terminal, VS Code, a Remote
Control session with no Foreman to reuse) and in a Copilot agent session. `chantier preflight
--direct` checks it: the host check passes on all of them; an unattended run, a linked worktree,
missing project instructions or an unauthenticated forge are refused, as in Foreman mode.

The batch's heartbeat runs in your own session, as the Foreman's does in Foreman mode: it
refreshes the status on a timer and stops at the pause. "Heartbeat N min" in `chantier status` is
the minutes since its last wake, and "heartbeat stopped" is a loop it ended on purpose. On Claude Code that a Driver reaches the
Chief of Staff the way it reaches a Foreman is not yet proved until a direct batch runs.

## What it costs

The steering is one `Chief of Staff, steering the batch` line in the cost table. It counts in the batch's
spend and budget as a Foreman's does; the grill and specifications with you, and the whole
session (with its compaction count), stay apart on their own `Chief of Staff, ...` lines and are never in the batch's spend.

## Switch to Foreman mode

> "Switch to Foreman mode."

On your word, and only where a Foreman can start. The Chief of Staff checks the Foreman-mode
preflight first, and on a Remote Control session the switch needs a Foreman to reuse, else it is
refused with the reason. No new Driver starts; the running ones hand back (or are stopped and
resumed later); then a Foreman takes over the batch. A Foreman batch never switches back to
direct mode.

## Make a release

A release works as in [Foreman mode](use-cases-foreman.md#make-a-release), with two differences.
A release CR joins a running direct batch, as does a fix of it, since the running batch is strict
about everything else. The release's own PR is yours to merge, last; the steering session, the
Chief of Staff here, merges it only under your grant, once every other CR of the batch is merged
or cancelled. An approval never lets it.

## On GitHub Copilot

Direct mode works in a Copilot agent session. There is no Foreman chat: the Chief of Staff runs
the same `/every` heartbeat in its own session. This path is not yet proved on Copilot, nor is the
Drivers' hand-back to the Chief of Staff that started them: nobody has run a direct batch there
yet. Your own agents are named by their file in `.github/agents/` or `~/.copilot/agents/`.
