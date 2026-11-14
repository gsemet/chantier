# The planning folder

The layout of the planning folder, in your project or in an external surface (see [planning modes](planning-modes.md) for the full account of a surface), what is published, the STATUS files, the worktrees, and a batch's pause and close.

Everything lives in the planning folder, `.agents/changes/` in your project or
`<surface>/projects/<name>/changes/` in an external surface:

```text
<planning folder>/
├── 1-inbox/<slug>/                        filed, not prioritized
├── 2-backlog/P1…P4/<slug>/                prioritized by you
├── 3-ready/<slug>/                        waiting for the next batch, specified or automatable
├── STATUS.md, STATUS.json                 the index: live batch, backlog table
├── 4-batch/                             the one batch, until `close`; n counts all batches
│   ├── batch.json, events.jsonl, brief.md, .lock   the batch's own files, local
│   ├── retro.md                           the pauses' retro; `close` writes it into batch-NN.md
│   ├── STATUS.md, STATUS.json             the batch; once paused, its exit report
│   ├── 1-pending/<number>-<slug>/         in the batch, not started
│   ├── 2-actives/<number>-<slug>/         taken by a Driver: working, ready or blocked; named
│   │                                      branch chantier/batch-<n>/… and worktree next to the repo
│   └── 3-done/<number>-<slug>/            merged, until `close`
├── 5-archives/<YYMMDD-HHMM>-<number>-<slug>/   merged, after `close` (time of the merge, UTC)
├── 5-archives/batches/batch-NN.json|md          each batch's record: for a UI, for a person (the retro)
└── 6-trash/<YYMMDD-HHMM>-<number>-<slug>/      dropped on your word
```

The folder moves, it is never copied; collisions are errors rather than overwrites. `3-ready`
holds what you say waits for the next batch (`chantier triage --ready`), with a specification or
without one (then its Driver works from the request alone). A CR moves to `3-done` alone and at
once when it merges, a stack's too, and to `5-archives` at `close`. A dropped CR goes to
`6-trash/` and does not return to the backlog. A batch has no name, only a
number, and `--batch` takes it (`4` or `batch-04`). One batch at a time, from `open` to your `close`: new work joins it
through the Foreman (in direct mode, once it is paused). Its CRs run in one of three [modes](../README.md#batch-modes), `open --mode parallel|series|stack`
(parallel unless you ask otherwise). While a CR runs, the team writes its notes, gate logs and PR body in the CR's own
`work/` folder.

External layout, beside it:

```text
<surface>/
├── AGENTS.md                the surface's own rules (its sync, among others)
└── projects/<name>/
    ├── project.md           the project: remote, default branch, `- Archive in the PR: yes|no`
    ├── checkout.yml         `repo:` and `worktrees:`, relative to this folder
    └── changes/             the planning folder, as above
```

What is published and what stays local: the batch's own files (`batch.json`, `events.jsonl`,
`brief.md`, the STATUS files, locks, `.batch-number`, `seat.json`) and the detailed logs
(`work/gates/`, `*.log`) are ignored by git, by a `.gitignore` the CLI keeps in the planning
folder. A running CR's documents, reports and evidence are pushed with the surface. The archive
has two places: the surface's `5-archives/` (with a `delivery.md`: the PR, the merge time) and,
by the project's setting (default yes), a cleaned copy in the CR's PR, in external mode.

`STATUS.md` and `STATUS.json` exist at three levels (the planning folder, `4-batch/`, the CR), each
linking to the others. The CLI rewrites them at every state change, from the state alone; a
status cell reads like `🔴 blocked Question 1/3`.

Each CR folder may also hold a `summary.json`: the CR's title, a one-line summary of what it means
now, where its request came from (a GitHub, GitLab or Jira issue read from its `issue:` line, or a
verbal request), its labels and its group, with a checksum of the Markdown files it covers
(`intake/*.md`, `01-intent.md`, `02-answers.md`, `03-change-spec.md`, `delivery.md`) so that a late
summary can be told. An agent writes it, never the CLI: the agent that edits a CR's Markdown runs
`chantier summary lint <folder>`, which lists the gaps and the command for each, and closes them
with `chantier summary set`; the Chief of Staff closes what is left. It is published with the CR
(it is not ignored by git), so every device sees it, and the board reads it instead of the
Markdown. A late summary blocks nothing, and the STATUS files read the same with or without it.

The agents own the worktrees as they own git: a CR's Driver creates its worktree and branch
(named by chantier, next to the repository), the steering session (the Foreman, or the Chief of
Staff in direct mode) removes a merged CR's before the batch is paused, and the Chief of Staff
removes a dropped CR's only on your word. When every CR is merged or cancelled, the batch is
**paused** (`chantier pause`), not closed: its cost to date is computed and shown, and the
steering session stays idle. Several CRs can be added to a paused batch, which stays paused until the first one starts, then runs
again; it pauses again at the end, with the cost to date grown. A batch is closed only on your
word ("close the batch"): `chantier close` refuses, naming the
cause, while anything still runs (a CR not merged, an open order, a stack agent, a session
written in the last 5 minutes); on a batch set running again it names what runs. Once nothing runs, it prices the final cost and shows it with
what goes (the batch's own files, the dropped CRs' worktrees and branches) and what moves to `5-archives`; if it cannot price it (no
priced call, no Foreman transcript recorded) it refuses, naming the cause, and the Chief of Staff
reports it to you. On your yes, `chantier close --yes` moves each merged CR to `5-archives`, writes the batch's record (`5-archives/batches/batch-NN.json`) and its Markdown, retro included (`batch-NN.md`), deletes the batch's other files and removes the rest with git;
without a yes, everything stays. Close last: those files hold the exit report and the event log.
