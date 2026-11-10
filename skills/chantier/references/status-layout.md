# The reports

The shape of a Progress report and of a Completion report. The user follows a batch through
them, often on a phone, and reads them at a glance: a report in another shape is a defect. This
card is read whole before every report, by the Chief of Staff and by `/chantier:status`.

`$CHANTIER` is the CLI of the prompt or the skill that sent you here.

## Before a report

Run `$CHANTIER status --refresh` with no epoch: it records the current spend and `STATUS.md` and
leaves the Foreman's heartbeat alone.

## The rules of every report

- **A CR's name:** name every CR by its number and slug together, like "CR-142 grill-rules",
  never one alone; an item with no number yet is named by its slug.
- A cost or a time chantier did not observe is written `unknown` (or as the CLI prints it: `-`,
  `never`, `not measured`), never 0; a 0 is only a measured zero.
- A Progress report and a Completion report always have the same shape: the columns
  are fixed, the text around them is yours to judge, in the user's language. Say "MR" on a GitLab
  remote, in the column and in the text, "PR" elsewhere (you know the forge from the remote).
  Icons, each with its word beside it: ⚪ not started or dropped, 🟡 working, 🟠 waiting,
  🔵 to review, 🔴 blocked, ✅ merged. Each icon is the one `status` draws in the CR's `label`
  (the same as `STATUS.md` and the board; read it there, in the Status column of the batch's `STATUS.md`, or in `label` of its `STATUS.json`, which `status --refresh` has just written): copy it, never judge it. 🟠 is a CR that waits for a
  thing already on its way, named: the stack driver, another CR, a fix of a release, a slot, the
  user's word on a release, the budget a queued CR cannot start on; ⚪ is a queued CR that could start now. 🔴 is a CR that
  nothing moves until someone decides or repairs it.

## Progress

On a CR ready or merged and on "status?":

- a header line (the batch's number and
  name, its mode, the slots in use, the CRs done, the spend and the budget);
- a legend line of
  the six icons, each with its word, which opens the table;
- a table, one row per
  CR: CR, subject (a few words, not the title), state, PR as a link, cost (from the row of `status --refresh`, a merged CR too); rows with one cause get the same words, whatever each
  Driver wrote;
- under the table, when a CR is 🟠 or 🔴, a short explanation: what it waits for,
  and who unblocks it;
- the cost table below (see Cost);
- a last line, always there, **For you:** what the user has to review or decide, or "nothing"
  (only a Tips line can follow it, see below).

🔵 to review is a ready PR only (a PR whose CR was handed back `ready` and whose base is the
default branch); a CR ready on another base says what it waits for, and **For you** does not ask
the user to merge it.

When a CR is chained (queued after another by the Foreman's decision, with no real dependency), your next report has a line with the chain and its reason.

On the Foreman's `ready` that is the last of a stack, when no CR of the batch is working, end
the Progress report with the offer of a demo of what the stack delivers.

## Completion

On the `final` message (Foreman mode) or right after your own `pause` (direct mode):

- a header line (the batch, the CRs merged out of how many, the spend and the
  budget);
- a table, one row per CR: CR, subject, result, PR, rounds, cost;
- the cost table (see Cost), then its explanation from `cost --explain`, both run at the pause:
  the cost to date;
- what the batch did not prove;
- a last line, **For you:** the batch is paused, the inbox ideas
  ready for a grill (each by its slug), and, if it fits, an invitation to add other CRs to this
  batch later or to close it ("close the batch")
  (only a Tips line can follow it, see below).

## Cost

The cost table of a report: on a CR ready or merged, on "status?" and at the pause, the
lines of `$CHANTIER cost`, as printed and in that order (a CR's own figure is the last field of
its row in `status --refresh`, a merged CR's included, never looked up elsewhere): the Foreman
(in direct mode, `Chief of Staff (steering)`), one line per Driver type, one per worker type, and your own session apart, the `Chief of Staff:`
line of that output, with its two figures (since the batch opened, the whole session) and its
context size. The CLI knows who is who from the record, not from a role name: the Foreman is
the main agent (the steering session), a Driver has no parent, a worker has one, and a Driver of the user's own gets
its line under the type the host gives it. You group, add and regroup nothing: no orchestration,
implementation or review lines. Give no figure when it fails; `not measured` stays `not
measured` (on Copilot, where the host gives no parent link, an agent's line says only its
type). A Driver's line covers its own rebases, gates and file writes, besides the workers it
starts, which have their own lines. Your session is never in the batch's spend nor in its
budget.

- **Explaining the figures:** in the Completion report, and when the user asks why it cost
  that, run `$CHANTIER cost --explain` and say it in a few plain lines in the user's language:
  from the measures under each line (the agents, the calls, the model, the share of cost in
  cache reads, cache writes and output, the calls after the cache expired, the Drivers
  restarted on a CR that already had one) and its last lines (the cache's lifetime, what the
  figures do not count: compaction calls leave no record). Say only what the output says; no
  subagent is started for it, and nothing is guessed where it says `not measured`.

## Tips

A tip comes only at four key moments: first use, after a status (a Progress report), the end of a
batch (a Completion report or the bilan of `close`), and during a release. It is one short line,
starting with 💡, in the user's language, with the exact words to type: the last line of the
report, after the **For you:** line. At most one per moment and per session. A report that asks a
question or reports a blocker carries none, so the question stays last in mind. A tip names only
what chantier really answers, and never a command the host refuses in this session, nor what the
user cannot take from where they are (the host's signal of where the user is, if it gives one). It
may name `/chantier:status`, for a progress table at once. After "plus de conseils" (or the same in
any language) a report carries none for the rest of the session. The examples and the full rule
are in [chief-of-staff](chief-of-staff.md), "Tips".