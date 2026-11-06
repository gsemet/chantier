# chantier by use case

Each section is a situation, what you say to the Chief of Staff, and what happens. New to
chantier? Start with the [tutorial](tutorial-claude-code.md).

## Start on a new project

> "chantier, prepare yourself to work on this project."

The Chief of Staff reads `AGENTS.md` (or `CLAUDE.md`, or `.github/copilot-instructions.md`) and
tells you how it will build, test, ship, merge and release here, and on which branch. It asks
about what the instructions leave open (a long gate, say), with a recommended answer, and offers
to write that answer in `AGENTS.md`. There is no other configuration: every agent reads
`AGENTS.md`, at every session, and chantier writes only in `.agents/changes/`.

## Turn ideas into ready work

> "File this: export the report as CSV." · "Make it a P2." · "Let's refine the CSV export."

Each item becomes a CR folder in the inbox, with the raw request kept as received. Refining
(the "grill") can happen at any stage: the Chief of Staff asks only the questions that change the
result, writes your answers in `02-answers.md`, and keeps the Change Specification self-contained.
Only you set priorities.

> "Drop the dark-mode idea for good."

Only on your explicit word does a CR go to `5-trash/`.

## Run a batch overnight

> "Run the P1s, three slots, budget 20 dollars, I'm going to bed."

After the preflight, the plan and your go, the Foreman runs up to three CRs at once. A CR that
needs you is parked as blocked with its question; the others go on. Past the budget, nothing new
starts until you answer. In the morning:

> "Status?" · "What did it cost, by CR?"

## Build independent pull requests

> "These three do not depend on each other: run them in parallel."

Each CR is based on the default branch (`open --parallel`); a batch is a stack by default.

## Build a stack of pull requests

> "Run these three."

Each PR is based on the one below it. When every CR is ready, a stack driver orders the stack,
rebases and pushes each PR on the one below it, and heavy CI runs once at the top. After each
merge you report, it restacks the rest on the default branch: the batch stays open, and work you add
joins it.

## Steer a running batch

| You say | What happens |
| --- | --- |
| "Add the rate-limit item to tonight's batch." | the CR (already refined) joins the queue |
| "Drop CR-104, we'll do it later." | its Driver stops; its folder goes to `5-trash/`, not back to the backlog; its branch and worktree stay until you close the batch and say yes |
| "CR-103 goes first." | a note on the CR; the Foreman gives it the next free slot |
| "For CR-102, keep the old API too." | a note on the CR; its Driver decides: next round, restart, or after the PR, and says which |
| "Pause." · "Resume." | slots 0: no new CR starts; a number resumes |
| "I merged #42." | the CR is archived; a ready PR that stops merging goes back to a Driver, which rebases it |

Every order goes to the Foreman with an id, and `status` shows it until it is done; an order read twice runs once.

## Ask for user testing

> "Run QA on the CSV export."

During a batch, a QA driver uses the project as a user would, at the head of its default branch,
never an unmerged PR. It leaves its findings, its proof and its long tests in a `qa-<date>` folder
in the inbox: an ordinary item you triage, which holds no CR back.

## Make a release

Say "release v1.4.0" once the work is merged and validated. Your project describes how it
releases, in `AGENTS.md` or a document it links: a tag, a release commit, heavy checks, notes
edited by hand. chantier adds no procedure of its own; if yours is missing or unclear, the Chief
of Staff asks you and offers to write the answer in the project. If it has no long check on the
default branch's exact head before the version commit, the Chief of Staff asks whether to plan
one; your answer rules, chantier imposes no gate.

A Release driver follows that procedure and stops before each irreversible action, such as a
pushed tag or a published package, until you approve it. Release notes wait in the CR's folder
from the start: you get a link and can edit them while the release runs.

When a step finds a defect, the driver does not fix it: a fix CR goes to a CR Driver and, once it
is merged, the procedure starts again from its first step. For a release that may take several
attempts, you can allow more up front, always within a budget:

| You say | What it allows |
| --- | --- |
| "up to 3 releases without asking, budget $20" | irreversible actions go ahead, up to that number of releases |
| "merge the fixes yourself" | the Foreman merges a release's ready fixes with `gh` or `glab`, by your project's method, if the forge gives it the rights |

The release's own PR is merged by the Foreman too, on your approval or under that grant; every
other PR is yours to merge.

Once the release is out, the driver writes a retrospective and proposes long-term fixes; each
becomes a CR only on your word.

## Use your own agents

> "Use my `rust-coder` agent as the coder."

The Chief of Staff writes it in the `chantier` section of your `AGENTS.md`; every Driver's prompt
names it, and the coder role runs your agent with the same contract as ours: it gets the
specification, the worktree, the work folder and the project's rules in its prompt.

> "Add a security review with `sec-reviewer`: OWASP top 10 on the diff."

A new role becomes an extra review step: after the Inspector approves a round, your reviewer
checks the diff from its angle and answers APPROVE or FIX-REQUIRED; a fix sends the CR into
another round.

> "Which agents and models?" · "Back to the default coder."

The Chief of Staff writes the team in a `chantier` section of `AGENTS.md`, so your colleagues get
the same one. The next batch uses it; a running batch keeps the team it started with.

## Recover after a restart

> "I restarted the app." · "Resume."

The Chief of Staff checks whether the Foreman is alive. If not, it tells you what it found and,
on your word, runs the preflight again and starts a new Foreman, which relaunches the Driver of
every CR still in progress, from its recorded state and worktree. Uncommitted work in a worktree
is kept.

## Know what it costs

> "What did tonight's batch cost?" · "Who cost the most?"

`chantier cost` measures the Foreman's session and every agent under it, by role or by CR, from
the transcripts (Claude) or the billed records (Copilot). A missing transcript or an unknown
model is an error, never an estimate. Your own session is not included.

You also get it unasked: one line per CR when it is ready or merged, and a summary when the batch
lands (total, budget, the split between Foreman, Drivers and workers, the costliest CRs).

## On GitHub Copilot

Everything above works in a Copilot SDK host (the Copilot app) the same way, with two
differences: the Foreman's heartbeat runs every four minutes through `/every` (the Chief of Staff
arms it, and asks you to delete it when the batch lands); and your own agents are named by their
file in `.github/agents/` or `~/.copilot/agents/`.

## When chantier says no

chantier stops instead of improvising: outside the Desktop app or a Copilot SDK host, in a linked
worktree, without project instructions, with a missing agent, a refused tool or an unknown model.
It tells you which condition failed and what you can do; it never offers a workaround.
