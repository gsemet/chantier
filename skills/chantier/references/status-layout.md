# The reports

The shape of a Progress report and of a Completion report. The user follows a batch through
them, often on a phone, and reads them at a glance: a report in another shape is a defect. This
card is read whole before every report, by the Chief of Staff and by `/chantier:status`.

`$CHANTIER` is the CLI of the prompt or the skill that sent you here.

## Before a report

Run `$CHANTIER status --refresh` with no epoch: it records the current spend and `STATUS.md` and
leaves the Foreman's heartbeat alone (only the loop's wake, `--refresh --epoch <n>`, moves it).

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

On a CR ready or merged and on "status?", written in this order, exactly this skeleton (angle
brackets are yours to fill, from the CLI as printed; the icons and their words stay as written):

```markdown
**<batch> <name>** · <who steers> · <shape> · slots <live>/<slots> · <done> CRs done · spent <spent> of <budget>

⚪ not started · 🟡 working · 🟠 waiting · 🔵 to review · 🔴 blocked · ✅ merged

| CR | Subject | State | PR | Cost |
| --- | --- | --- | --- | ---: |
| <CR-n slug> | <a few words> | <icon word> | [PR](https://<the PR's url>) | <cost> |

**Notes**
- <short line>

| Who | Cost | Share | Calls |
| --- | ---: | ---: | ---: |
| <label as printed> | <amount as printed> | <share as printed> | <calls> |
| Total | <total> | 100% | <calls> |

<the ratio line, as printed>

| Outside the batch's spend | Cost | Detail |
| --- | ---: | --- |
| <Chief of Staff line's label> | <amount> | <the rest of its line> |

**Cost notes**
- <short line>

**For you:** <what to review or decide, or "nothing">
💡 <tip>
```

- **Header line:** the batch's number and name, who steers it and its shape, the slots in use,
  the CRs done, the spend and the budget. Who steers (`direct (the Chief of Staff)` or `Foreman`)
  and the shape (`parallel`, `series` or `stack`) are copied from the first line of
  `$CHANTIER status`, never judged; `unknown` stays `unknown`; the spend is copied as `status`
  prints it (`at least $1.61` while calls are not priced).
- **CR table:** one row per CR: CR, subject (a few words, not the title), state, PR as a link,
  cost (from the row of `status --refresh`, a merged CR too, `at least` copied when its row says
  so); rows with one cause get the same words, whatever each Driver wrote.
- **Notes and Cost notes are the only places for extra messages:** short lines in the user's
  language (explanations, warnings, tips on reading the figures). An empty place is left out, not
  written "none". **Notes** holds what a 🟠 or 🔴 CR waits for and who unblocks it, a chain and its
  reason, a force push run for a Driver, the main checkout's line after a merge (below). **Cost notes** holds the CLI's not-priced lines
  (`<model> has no price: add it under prices: in chantier.yaml (exact id: <model>)`, said in the
  user's language with the id kept) and, in the Completion report, the few plain lines of `cost
  --explain`. Nothing but the Tip follows **For you**.
- **For you:** always there: what the user has to review or decide, or "nothing" (only a Tips
  line can follow it, see below).

🔵 to review is a ready PR only (a PR whose CR was handed back `ready` and whose base is the
default branch); a CR ready on another base says what it waits for, and **For you** does not ask
the user to merge it.

When a CR is chained (queued after another by the Foreman's decision or the plan's, with no real dependency), your next report has a line with the chain and its reason, in **Notes**.

When you ran a Driver's refused force push since the last report, your next report has one line in **Notes**: the CR (number and slug), the branch and "pushed for the Driver (host refused its push)". A push held for the user's word or failed was already told at once; **For you** still names a push question while it is open.

When a CR merged since the last report carries a `main checkout:` note, your next report has one line in **Notes**: `main checkout: fast-forwarded to <sha7>` (or `already at <sha7>`), or `main checkout not fast-forwarded: <why>`, the latest one only. The Completion report has it too, by the same skeleton. It is not a **For you** item: nothing waits on the user (a `tracked changes` or `on <branch>` line may leave the user something to do, which they judge).

When you named a trace in the main checkout since the last report (`chief-of-staff.md`, "Reports": `git status --porcelain`, a path outside the planning folder), your next report has one line with the paths, and **For you** asks what to do with them.

On the Foreman's `ready` that is the last of a stack, when no CR of the batch is working, end
the Progress report with the offer of a demo of what the stack delivers (in **For you**).

## Completion

On the `final` message (Foreman mode) or right after your own `pause` (direct mode): the same
skeleton as a Progress report, with these differences, `cost` and `cost --explain` both run at
the pause (the cost to date):

- the header line has the batch, who steers it and its shape as in a Progress report, the CRs
  merged out of how many, the spend and the budget (no slots);
- the CR table has the columns CR, subject, result, PR, rounds, cost;
- after **Cost notes**, in this order:
  - **What the batch did not prove:** each CR handed back with `--no-gate` and its reason (the
    CR's "Long gate" step shows `waived: <reason>`);
  - the **Retro**: the points of `4-batch/retro.md` written at this pause (and of the release's
    `work/retro.md` if the batch had a release, each point once), one numbered line each,
    `<n>. [<tag>] <problem>: <long-term fix>`, one numbering across both tags so the user answers
    by number; a `project` point that matches an inbox or backlog item names that item, a
    `chantier` point that matches an open issue on chantier's repository names that issue's link;
  - **For you:** the batch is paused, which `project` points to file as inbox items (by their
    numbers), which `chantier` points to draft as an issue (by their numbers; several may go in
    one issue; when the project is chantier itself, the one line the Chief of Staff card gives),
    the inbox ideas ready for a grill (each by its slug), and, if it fits, an
    invitation to add other CRs to this batch later or to close it ("close the batch"); the
    Retro is offered before the close, which writes `4-batch/retro.md` into `5-archives/batches/batch-NN.md` (only a Tips line can
    follow it, see below).

## Cost

The cost of a report is two tables and one line, never raw output in a code block. The rows are
the lines of `$CHANTIER cost`, in its order (a CR's own figure is the last field of its row in
`status --refresh`, a merged CR's included, never looked up elsewhere):

- **First table, the batch's spend:** the steering session (the Foreman; in direct mode `Chief of
  Staff, steering the batch`), its own subagents, one row per Driver type, one per worker type,
  then the Total row from `cost`'s first line. Each row has its cost, its share of the spend and
  its calls, as printed. Below it, the ratio line `Orchestration (steering + Drivers): N% of the
  batch's spend`, as printed.
- **Second table, outside the batch's spend:** the `Chief of Staff, ...` lines of that output:
  `steering the batch` (Foreman mode: what you spent relaying and reporting; in direct mode the
  line outside the budget appears too when you spent outside your claim window, before the claim
  or after a Foreman took over; when the only calls of that part carry no time, it says `unknown
  (<n> calls without a time, not placed)`), `grill and specifications with the user` (every call
  of a turn that writes a CR's `01-intent.md`, `02-answers.md`, `03-change-spec.md` or
  `work/specifying`, or starts a spec-writer, in your claim window, and, in the rest of the time
  since the batch opened, of a turn that names one; and the spec-writers' own calls; a turn is
  attributed whole), each since the batch opened, and `whole session` with its context size and
  its compaction count. These lines carry no share. In a direct batch the grill and
  specifications are outside the batch's spend, as the spec-writer is.

The CLI knows who is who from the record, not from a role name: the Foreman is the main agent
(the steering session), a Driver has no parent, a worker has one, and a Driver of the user's own
gets its line under the type the host gives it. No line that starts with "Driver" names the
steering session or its own subagents. A Driver's line covers its own rebases, gates and file
writes, besides the workers it starts, which have their own lines. Your session is in the
batch's spend and budget only as the steering row of a direct batch.

**You copy, you compute nothing.** Every amount, share, call count and the ratio come from `cost`
as printed. You group, add and regroup nothing: the ratio line is the one grouping, and the CLI
makes it. Give no figure when it fails; `unknown`, `not measured` and `share not measured` stay
as printed (never `$0.00`; the compactions leave no record: they are counted, not priced, and
the count is said with them; calls with no time are said as such; on Copilot, where the host
gives no parent link, an agent's line says only its type, the ratio line says `not measured (no
parent link on this host)`, and the Chief of Staff's two lines say unknown).

**A floor.** A figure that leaves calls of a model with no price out of it is a floor: it is
shown as `cost` prints it (`at least $1.61`, `3 calls of <model> not priced`, `not priced`),
never as a plain total, and the shares and the ratio read `not measured` while any call is not
priced.

- **Explaining the figures:** in the Completion report, and when the user asks why it cost
  that, run `$CHANTIER cost --explain` and say it in a few plain lines in the user's language
  (in **Cost notes** of the Completion report):
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
