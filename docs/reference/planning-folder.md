# The planning folder

Look up where each file of a batch lives: the folder layout, what is published, the STATUS files,
the worktrees, and what a batch's pause and close do. [Planning modes](../explanation/planning-modes.md)
gives the full account of a surface.

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
│   ├── 2-actives/<number>-<slug>/         taken by a Driver: working, handed back ready or blocked; named
│   │                                      branch chantier/batch-<n>/… and worktree next to the repo
│   └── 3-done/<number>-<slug>/            merged, until `close`
├── 5-archives/<YYMMDD-HHMM>-<number>-<slug>/   merged, after `close` (time of the merge, UTC)
├── 5-archives/batches/batch-NN.json|md          each batch's record: for a UI, for a person (the retro)
└── 6-trash/<YYMMDD-HHMM>-<number>-<slug>/      dropped on your word
```

## How a CR moves

- A CR's folder moves, it is never copied. Collisions are errors rather than overwrites.
- `3-ready` holds what you say waits for the next batch (`chantier triage --ready`), with a
  specification or without one (then its Driver works from the request alone).
- A CR moves to `3-done` alone and at once when it merges, a stack's too, and to `5-archives` at
  `close`.
- A dropped CR goes to `6-trash/` and does not return to the backlog.

## Batches

- A batch has no name, only a number, and `--batch` takes it (`4` or `batch-04`).
- There is one batch at a time, from `open` to your `close`. New work joins it through the Foreman
  (in direct mode, once it is paused).
- Its CRs run in one of three [modes](../explanation/batches-and-lifecycle.md#batch-modes), set by
  `open --mode parallel|series|stack` (parallel unless you ask otherwise).
- While a CR runs, the team writes its notes, gate logs and PR body in the CR's own `work/` folder.

## External layout

```text
<surface>/
├── AGENTS.md                the surface's own rules (its sync, among others)
└── projects/<name>/
    ├── project.md           the project: remote, default branch, `- Archive in the PR: yes|no`
    ├── checkout.yml         `repo:` and `worktrees:`, relative to this folder
    └── changes/             the planning folder, as above
```

## What is published, what stays local

The batch's own files (`batch.json`, `events.jsonl`, `brief.md`, the STATUS files, locks,
`.batch-number`, `seat.json`, `forge-journal.jsonl`) and the detailed logs (`work/gates/`, `*.log`)
are ignored by git, by a `.gitignore` the CLI keeps in the planning folder.

A running CR's documents, reports and evidence are pushed with the surface. A CR's folder may also
hold `prototypes/NN-<idea>/` and `experiments/`, created only when used and published with the CR
like its documents.

The archive has two places: the surface's `5-archives/` (with a `delivery.md`: the PR, the merge
time) and, by the project's setting (default yes), a cleaned copy in the CR's PR, in external mode.

## The STATUS files

`STATUS.md` and `STATUS.json` exist at three levels (the planning folder, `4-batch/`, the CR), each
linking to the others. The CLI rewrites them at every state change, from the state alone. A status
cell reads like `🔴 blocked Question 1/3`.

## `summary.json`

Each CR folder may also hold a `summary.json`. It holds the CR's title, a one-line summary of what
it means now, where its request came from (a GitHub, GitLab or Jira issue read from its `issue:`
line, or a verbal request), its labels and its group. It also holds a checksum of the Markdown
files it covers (`intake/*.md`, `01-intent.md`, `02-answers.md`, `03-change-spec.md`,
`delivery.md`), so that a late summary can be told.

An agent writes it, never the CLI. The agent that edits a CR's Markdown runs
`chantier summary lint <folder>`, which lists the gaps and the command for each, and closes them
with `chantier summary set`. The Chief of Staff closes what is left.

It is published with the CR (it is not ignored by git), so every device sees it, and the board
reads it instead of the Markdown. A late summary blocks nothing, and the STATUS files read the same
with or without it.

## Validate

`chantier validate` checks the whole planning folder and writes nothing: the placement of CR folders
(a CR outside a stage, nested in another, a priority folder outside `2-backlog`) and the format of
every `summary.json`, in every stage; the missing or late summaries, the shape of each CR folder
(a request, the entries of its tree) and the broken links between Markdown files, in the live
stages only (`5-archives` and `6-trash` are history). Its first line gives the counts
(`no error, no gap (<k> CRs)`, `<m> gap(s) in <k> CRs` or `<n> error(s), <m> gap(s) in <k> CRs`),
then one line per finding, errors first. Exit 0 when there is no error (gaps pass), 3 on an error
(chantier or the board misreads the folder), 1 when it cannot run. A planning surface's
`just validate` calls it and keeps no validation of its own.

## Worktrees

The agents own the worktrees as they own git. A CR's Driver creates its worktree and branch (named
by chantier, next to the repository). The CLI removes a merged CR's when the batch's last CR ends;
a leftover it cannot remove is kept and named, and `close` names it. The Chief of Staff removes a
dropped CR's only on your word.

## Pause

When every CR is merged or cancelled, the batch is paused (`chantier pause`), not closed. Its cost
to date is computed and shown, and the steering session stays idle. Several CRs can be added to a
paused batch, which stays paused until the first one starts, then runs again. It pauses again at
the end, with the cost to date grown.

## Close

A batch is closed only on your word ("close the batch").

`chantier close` refuses, naming the cause, while anything still runs:

- a CR not merged;
- an open order;
- a stack agent;
- an agent of the batch (one it recorded and still holds, or the current Foreman) whose transcript
  shows it still runs. One that stopped without handing back passes on your word, and the batch's
  record keeps it. The session's other subagents and replaced Foremans are listed, not a block.

On a batch set running again, it names what runs.

Once nothing runs, `close` prices the final cost and shows it with what goes (the batch's own
files, the dropped CRs' worktrees and branches) and what moves to `5-archives`. If it cannot price
it (no priced call, no Foreman transcript recorded), it refuses, naming the cause, and the Chief of
Staff reports it to you.

On your yes, `chantier close --yes`:

- moves each merged CR to `5-archives`;
- writes the batch's record (`5-archives/batches/batch-NN.json`) and its Markdown, retro included
  (`batch-NN.md`), and keeps in each CR of the record its `order` and its `after` list (the CRs it
  waited for);
- deletes the batch's other files and removes the rest with git.

Without a yes, everything stays. Close last: those files hold the exit report and the event log.
