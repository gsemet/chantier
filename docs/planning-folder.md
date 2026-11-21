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
│   ├── 2-actives/<number>-<slug>/         taken by a Driver: working, handed back ready or blocked; named
│   │                                      branch chantier/batch-<n>/… and worktree next to the repo
│   └── 3-done/<number>-<slug>/            merged, until `close`
├── 5-archives/<YYMMDD-HHMM>-<number>-<slug>/   merged, after `close` (time of the merge, UTC)
├── 5-archives/<YYMMDD-HHMM>-outside-<number>-<slug>/   a PR merged without chantier, archived on your word
├── 5-archives/batches/batch-NN.json|md          each batch's record: for a UI, for a person (the retro)
└── 6-trash/<YYMMDD-HHMM>-<number>-<slug>/      dropped on your word (cancelled)
```

The folder moves, it is never copied; collisions are errors rather than overwrites. `3-ready`
holds what you say waits for the next batch (`chantier triage --ready`), with a specification or
without one (then its Driver works from the request alone). A CR moves to `3-done` alone and at
once when it merges, a stack's too, and to `5-archives` at `close`. `order drop` names where a
CR goes, and you say it (the Chief of Staff asks when you have not): `6-trash/` (cancelled; it
does not return to the backlog by itself), `1-inbox/` (to look at again) or `2-backlog/P1`..`P4`
(postponed or handed off). Whatever the destination, the CR keeps its work, its worktree, its
branch and its PR; only the trash closes the PR. A CR moved to the inbox or the backlog keeps its
number, in `<number>-<slug>/`, and a `formerly.json` records where it came from. A batch has no name, only a
number, and `--batch` takes it (`4` or `batch-04`). One batch at a time, from `open` to your `close`: new work joins it
through the Foreman (in direct mode, once it is paused). Its CRs run in one of three [modes](../README.md#batch-modes), `open --mode parallel|series|stack`
(parallel unless you ask otherwise). While a CR runs, the team writes its notes, gate logs and PR body in the CR's own
`work/` folder.

External layout, beside it:

```text
<surface>/
├── AGENTS.md                the surface's own rules; its sync is the surface server's writer
└── projects/<name>/
    ├── project.md           the project: remote, default branch, `- Archive in the PR: yes|no`
    ├── checkout.yml         `repo:` and `worktrees:`, relative to this folder
    └── changes/             the planning folder, as above
```

What is published and what stays local: the batch's own files (`batch.json`, `events.jsonl`,
`brief.md`, the STATUS files, locks, `.batch-number`, `seat.json`, `forge-journal.jsonl`, which also holds the board's writes and the writer's lines, and the `.lease-hold.*.run` records of a running `lease hold`) and the detailed logs
(`work/gates/`, `*.log`), the scratch folder (`work/scratch/`) and downloaded CI artifacts (any
`artifacts-*/` folder under a `work/` folder) are ignored by git, by a `.gitignore` the CLI keeps in the planning
folder. A running CR's documents, reports and evidence are pushed with the surface, by the surface server's writer, within 5 minutes; with no writer running, a write to the surface is refused. A path too
long for git blocks the writer with the reason `path-too-long`; its line names the file and the
way out. A CR's folder
may also hold `prototypes/NN-<idea>/` and `experiments/`, created only when used and published
with the CR like its documents. A backlog CR may hold a `waits.json` (`wait <folder> add`): its typed waits, published and moved
with the folder; `open` or `order add` carries its open waits into the batch's record and removes
the file, and `order drop` writes a dropped CR's open waits back into one. The archive
has two places: the surface's `5-archives/` (with a `delivery.md`: the PR, the merge time) and,
by the project's setting (default no), a cleaned copy in the CR's PR, in external mode.

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

`chantier validate` checks the whole planning folder and writes nothing: a backlog CR's `waits.json` must be `{"schema": 1, "waits": [...]}` of waits with an `id`
(`w<n>`), a `type` and text fields (an error otherwise), and under `4-batch/` it is an unknown file (a gap); the placement of CR folders
(a CR outside a stage, nested in another, a priority folder outside `2-backlog`) and the names of outside archives (`<YYMMDD-HHMM>-outside-<number>-<slug>`) and the format of
every `summary.json`, in every stage; the missing or late summaries, the shape of each CR folder
(a request, the entries of its tree) and the broken links between Markdown files, in the live
stages only (`5-archives` and `6-trash` are history). Its first line gives the counts
(`no error, no gap (<k> CRs)`, `<m> gap(s) in <k> CRs` or `<n> error(s), <m> gap(s) in <k> CRs`),
then one line per finding, errors first. Exit 0 when there is no error (gaps pass), 3 on an error
(chantier or the board misreads the folder), 1 when it cannot run. A planning surface's
`just validate` calls it and keeps no validation of its own.

The agents own the worktrees as they own git: a CR's Driver creates its worktree and branch
(named by chantier, next to the repository), the CLI removes a merged CR's when the batch's last CR ends (a leftover it cannot remove is kept and named, and `close` names it), and the Chief of Staff
removes a dropped CR's only on your word. When every CR is merged or cancelled, the batch is
**paused** (`chantier pause`), not closed: its cost to date is computed and shown, and the
steering session stays idle. Several CRs can be added to a paused batch, which stays paused until the first one starts, then runs
again; it pauses again at the end, with the cost to date grown. A batch is closed only on your
word ("close the batch"): `chantier close` refuses, naming the
cause, while anything still runs (a CR not merged, an open order, a stack agent, an agent of the batch (one it recorded and still holds, or the current Foreman) whose
transcript shows it still runs; one that stopped without handing back passes on your word, and
the batch's record keeps it; on Copilot, until `copilot-close-end-event` lands, a held agent runs while its lease is live, and the current Foreman while its heartbeat is under 10 minutes old; the session's other subagents and replaced Foremans are listed, not a block); on a batch set running again it names what runs. Once nothing runs, it prices the final cost and shows it with
what goes (the batch's own files, the dropped CRs' worktrees and branches) and what moves to `5-archives`; if it cannot price it (no
priced call, no Foreman transcript recorded) it refuses, naming the cause, and the Chief of Staff
reports it to you. On your yes, `chantier close --yes` moves each merged CR to `5-archives`, writes the batch's record (`5-archives/batches/batch-NN.json`) and its Markdown, retro included (`batch-NN.md`), keeps in each CR of the record its `order` and its `after` list (the CRs it waited for), deletes the batch's other files and removes the rest with git;
without a yes, everything stays. Close last: those files hold the exit report and the event log.

## The event journal

`forge-journal.jsonl`, at the planning folder's root, never published, holds every event of the
project: the forge's (a merge the record does not hold, a CI turning red on a PR ready to merge)
the board's writes, the writer's (a conflict, a block, a push that is late, the resumption) and the issue events an outside poller writes. Its name is historical, it is not only the forge's. One line is one JSON
object, written by one function (`hub/journal.py`, `append`), under the project's lifecycle lock:

```json
{"v": 2, "seq": 41, "t": "2026-11-18T10:02:03Z", "type": "merged@1", "source": "hub",
 "audience": ["project"], "batch": "batch-29", "cr": "CR-12", "pr": "#88", "into": "main",
 "into_cr": null, "merged_at": "2026-11-18T10:01:40Z"}
```

| Field | Holds |
|---|---|
| `v` | the line's version, 2 (0 and 1 still read) |
| `seq` | 1 for the first line, then the highest readable `seq` plus one; a watcher's cursor counts it |
| `t` | the time of the append |
| `type` | `name@N`, the published type (`merged@1`, `checks-red@1`, `wait-cleared@1`, `config@1`, `board@1`, `issue@1` or `sync-*@1`), then the fields of that type |
| `source` | who wrote it: `hub` (the forge hub), `board` (its PRs page, Configuration page and backlog writes), `writer` (the surface's writer), `cli` (room for a command), `poller` (an outside poller, through `chantier journal add`) |
| `audience` | whom it is for: one or more of `project`, `role:<name>`, `cr:<id>`, `session:<key>`, `user` |

A published `name@N` never changes; a change is a new `name@N+1`, and every type's JSON Schema
ships in `hub/schemas.json`.

Every line written today is for `["project"]`: `merged@1` and `checks-red@1` by the hub or the
board's PRs page, `wait-cleared@1` by the hub, `config@1` by the Configuration page, `board@1` by the backlog writes, `issue@1` by an outside poller, `sync-*@1` by the writer. The CLI
checks an audience value's form, never what it names, and routes to no role, CR or user yet.

| Type | Written by | Wakes a watcher |
|---|---|---|
| `merged@1` | the hub, the board's PRs page | yes |
| `checks-red@1` | the hub | yes |
| `wait-cleared@1` | the hub | yes |
| `config@1` | the board's Configuration page | yes |
| `board@1` | the board's backlog writes | when `wakes`: true for `new`, `move`, `edit` and `running-batch` |
| `issue@1` | an outside poller, through `chantier journal add`, only for an issue a CR's `issue:` line names | when `wakes` (default true) |
| `sync-conflict@1` | the writer | yes |
| `sync-blocked@1` | the writer | yes |
| `sync-late@1` | the writer | yes |
| `sync-resumed@1` | the writer | no |

An event the hub or the board builds from a forge read or a backlog or Configuration write that its
type's model refuses is not written, the others are, and the hub's entry or the page's reply names
it (`skipped: journal payload <type>: ...`).

A version 0 or 1 line's `kind` is read as `<kind>@1` and never rewritten (version 0's `by` is its
source and it is for the project). A version 2 line of an unknown type or a refused payload counts
for `seq` and wakes no one, and `status` names it (`line <n> is of type <t>, unknown to this
chantier: update it`; `line <n> unreadable`). A line of a newer version counts for `seq`, wakes no
one and is named by `status`.

`chantier watch` reads the lines for it: `project`, its own `session:<key>` and each `--for`
value (repeatable; none is the default command). A line for another audience moves its cursor and
is never printed. The watcher ends 20 s after the last new event for it that wakes, and no sooner
than `events.wake_every` (`chantier.yaml`, default `20s`, 20 s or more) after its start.
