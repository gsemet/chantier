# chantier by use case: Foreman mode

In Foreman mode a separate session, the **Foreman**, runs the batch: it starts the Drivers, hears
them and reports to the Chief of Staff. It is the default, and the most dynamic mode:

- CRs join the batch while it runs (`order add`), and QA runs during it;
- your Chief of Staff session stays free: you grill, file, triage and discuss there while the batch
  runs.

It runs in Claude Desktop (the Foreman is a nested session) and in a Copilot agent session. With no
argument, at the desktop (`/chief-of-staff`), or forced with `/chief-of-staff foreman`, the plan
names Foreman mode and why. Under Remote Control, or where a host cannot start a Foreman session,
the mode with no argument is [direct](use-cases-direct.md), and a forced `foreman` is refused with
the reason. The mode is yours to change before the go. The situations that do not depend on the steering (a new project, ready work, PR
descriptions, your own agents, cost) are on the [common page](use-cases.md).

## Run a batch overnight

> "Run the P1s, three slots, budget 20 dollars, I'm going to bed."

After the preflight, the plan and your go, the Foreman runs up to three CRs at once. The plan
names who steers; here, a Foreman. A CR that needs you is parked as blocked with its question; the
others go on. Past the budget, nothing new starts until you answer. In the morning:

> "Status?" · "What did it cost, by CR?"

## Build independent pull requests

> "These three do not depend on each other: run them."

Parallel is the default: no flag, no word. Every CR starts from the default branch at once and its
PR is on the default branch. The first one ready wins: you merge in the order things become ready,
unless you say otherwise. After each merge you report, every PR still open is rebased onto the
default branch and its checks run again, conflict or not.

## Build a stack of pull requests

> "Build a stack of these three."

Asked for, `open --mode stack`. The CRs run in parallel, each PR based on the default branch. The
stack comes after: when every CR is ready, a stack driver orders the stack, rebases and pushes each
PR on the one below it, and heavy CI runs once at the top; you merge from the bottom up. A CR
stands on another before that only by a dependency or a chain the Foreman decided, which you can
turn off while the CR is queued. After each merge you report, it restacks the rest on the default
branch.

## Build a series of pull requests

> "Run these three in series, in this order."

Asked for, `open --mode series`: the CRs have a precise order, the one you gave. Only the first
starts. The next starts once the previous one is handed back ready, from the previous CR's pushed
branch, and its PR is a draft. The Chief of Staff tells you which PR to merge next, the bottom one,
ready on the default branch; the others are drafts waiting on it. After you say it is merged, the
next one is rebased onto the default branch and turns ready; if the previous one changes during
review, the next is rebased on it. You can switch at any time:

> "Switch to a stack."

Every CR left then starts at once, each on the previous one, and a stack driver keeps the stack up
to date.

## Steer a running batch

| You say | What happens |
| --- | --- |
| "Add the rate-limit item to tonight's batch." | the CR (already specified) joins the queue |
| "Drop CR-104 export-csv, we'll do it later." | its Driver stops; its folder goes to `6-trash/`, not back to the backlog, and `status` shows it as `cancelled`; a second drop of it is refused ("already dropped"); its branch and worktree stay until you close the batch and say yes |
| "CR-103 goes first." | a note on the CR; the Foreman gives it the next free slot |
| "For CR-102, keep the old API too." | a note on the CR; its Driver decides: next round, restart, or after the PR, and says which |
| "Hold." · "Resume." | slots 0: no new CR starts (a hold); a number resumes |
| "Switch to a stack." | a series becomes a stack at once (`order mode --note stack`): every CR left starts, each on the previous one |
| "I merged #42." | the CR moves to `3-done`; a ready PR that stops merging goes back to a Driver, which rebases it |

Every order goes to the Foreman with an id, and `status` shows it until it is done; an order read
twice runs once. `status` keeps two lines: `orders pending` for the orders nothing has touched yet
(a note, a QA, the drop of a live CR), and one for those the CLI has applied, which the Foreman
still has to mark `order done`. `pause` waits until both are done. Without a Foreman, `order done
<O-k>` ends them so that `pause` can pass, but `close` needs a recorded steering transcript, here
the Foreman's: it prices the batch from it.

## When the batch is paused, and when you close it

When every CR is merged or cancelled, the Foreman removes the merged CRs' worktrees and branches
and pauses the batch. You get the Completion report: the cost to date, what the batch did not
prove, and what is for you. The batch is **paused**: nothing runs, and it stays paused, however
long, until you say so.

> "Add the CSV export to this batch."

Several CRs can join a paused batch; it stays paused until the first one starts, then runs again and pauses again at the end, with the cost to date
grown. A paused batch still blocks a new plan: new work joins it.

> "Close the batch."

Only on your word. The Chief of Staff runs the check: it refuses, naming the cause, while a CR is
not merged or cancelled, an order is open, an agent of the batch still runs, or nothing at all
can be priced. When it passes, you see the final cost and what goes, and you say yes. Then the
batch's own files are deleted, each merged CR moves to `5-archives`, and the dropped CRs' worktrees and branches are removed. Without your yes,
everything stays.

## Ask for user testing

> "Run QA on the CSV export."

During a batch, a QA driver uses the project as a user would, at the head of its default branch,
never an unmerged PR. It leaves its findings, its proof and its long tests in a `qa-<date>` folder
in the inbox: an ordinary item you triage, which holds no CR back. It takes a slot.

## Make a release

Say "release v1.4.0" along with the work, best in a stack batch. The release is a CR of the batch:
it waits for every other CR, starts once they are all ready, and its PR is the top of the stack.
You review the work and the release together, and merge from the bottom up; the release PR is
last, and your merge of it starts your release procedure. In a parallel batch no branch holds all
the work before the merges, so the release is prepared after them, and your merge of its PR is the
go there too. The version is the one you settled when you filed the release; if you left it open,
the Release driver picks the best one and says why in the release PR. It never asks you.

Your project describes how it releases, in `AGENTS.md` or a document it links: a tag, a release commit, heavy checks, notes
edited by hand. chantier adds no procedure of its own; if yours is missing or unclear, the Chief
of Staff asks you and offers to write the answer in the project. If it has no long check on the
default branch's exact head before the version commit, the Chief of Staff asks whether to plan
one; your answer rules, chantier imposes no gate.

A Release driver follows that procedure and stops before each irreversible action, as your
procedure names them, until the release PR is merged and, where the procedure asks for a go, you
approve it. If your procedure has no release PR, the Chief of Staff asks you, once the other CRs
are merged, whether to run it. Release notes wait in the CR's folder from the start: you get a
link and can edit them while the release runs.

When a step finds a defect, the driver does not fix it: a fix CR goes to a CR Driver and, once it
is merged, the procedure starts again from its first step. For a release that may take several
attempts, you can allow more up front, always within a budget:

| You say | What it allows |
| --- | --- |
| "up to 3 releases without asking, budget $20" | the Foreman merges the release PR for you, and the steps your procedure asks a go for go ahead, up to that number of releases |
| "merge the fixes yourself" | the Foreman merges a release's ready fixes with `gh` or `glab`, by your project's method, if the forge gives it the rights |

The release's own PR is yours to merge, last. The Foreman merges it only under that grant, once
every other CR of the batch is merged or cancelled; an approval never lets it.

At each pause of the batch, and once a release is out, a retrospective lists each problem met with
its long-term fix, one line each; each point becomes an inbox item only on your word.

## Recover after a restart

> "I restarted the app." · "Resume."

The Chief of Staff checks whether the Foreman is alive. If not, it tells you what it found and,
on your word, runs the preflight again and starts a new Foreman, which relaunches the Driver of
every CR still in progress, from its recorded state and worktree. Uncommitted work in a worktree
is kept.

## On GitHub Copilot

Everything above works in a Copilot agent session the same way, with two differences: the
Foreman's heartbeat runs every four minutes through `/every` (the Chief of Staff arms it, and asks
you to delete it when the batch is paused); and your own agents are named by their file in
`.github/agents/` or `~/.copilot/agents/`.
