# real-foreman

chantier on its own repository: real CRs, real `git`, `gh` and CI, in the main checkout, with no
workspace to stage. It proves the path a user takes. It does not exercise the failures the
scripted campaign [claude-planted](../claude-planted/RUNBOOK.md) plants. The same run steered by
the Chief of Staff alone is [real-direct](../real-direct/RUNBOOK.md).

| | |
| --- | --- |
| CRs | 1 to 5 real, small items from the inbox (`.agents/changes/1-inbox/`), picked by the Chief of Staff with the user's go. Each goes through the usual grill and Spec-writer before `open`, like any CR: they are not invented defects. An item already specified (in the backlog or `3-ready`) skips the grill |
| Open | `$CHANTIER open <A> <B> … --mode parallel --default-branch main --slots 3 --budget 20` |
| Team | the plugin's agents |
| Cost and time | about $2.50 per CR (2026-11-12: $5.03 for 2 CRs). Time grows with the CR count: the long gate takes about 16 min on this repository and runs one at a time, so the gates queue. Plan about 30 min plus 16 min per CR, and 16 min more for each long gate that fails (2026-11-12: 2 CRs, one failed gate, 64 min); 4 CRs take about 1 h 35 min or more |

The two `3-ready` CRs prepared for `real` (`handback-after-rebase`, `heartbeat-odd-values`) run here, in
real-foreman; [real-direct](../real-direct/RUNBOOK.md) takes fresh items. After this CR merges and before
`open`, the Chief of Staff updates their `evals/real/` citations in the planning folder (it is not in the PR).

The plugin is read live from the checkout: the main checkout stays on `main` during the run, and
any other work goes in another worktree.

## Start

The user types, in a new Code session of the Claude Desktop app opened on this repository's main
checkout, on `main`:

```text
/chantier:chief-of-staff Run the chantier eval campaign real-foreman: follow evals/real-foreman/RUNBOOK.md.
```

That session is the operator: a Chief of Staff in Foreman mode. Here the user is the real user:
the go, the item picks and the decisions on the PRs are theirs, and the operator does not play
them. The host's limits of the [evals README](../README.md#the-hosts-limits) hold: 10 messages per
session, and the go typed in the desktop app. Under Remote Control the user starts the Foreman's
session, as the [README](../README.md#the-hosts-limits) says. It may open outside the repository:
the prompt then adds `CHANTIER_ROOT=<this checkout>`.

One new Foreman session per batch: `cost` counts a session's calls from the batch's creation, but
the session's context still costs each turn.

Right after `open` (it makes the batch's folder), save the main checkout's state for the audit in
that folder:

```bash
git status --porcelain -uall > .agents/changes/4-batch/porcelain-at-open.txt
```

The audit compares the main checkout with this file: nothing outside `.agents/changes/` may have
changed since.

## Nothing merges

Each specification and the brief say so: the PR opens as a draft and its Driver turns it ready
once it can merge (base on the default branch, CI green, evidence in; on another base it stays a
draft), the first line of its body is
`**Eval run: do not merge.** The maintainer decides what happens to this PR.`, and nobody merges
it or enables auto-merge. The batch stops at `ready` for each CR. The run ends when every CR is
`ready` (or `blocked`, with its reason) and nothing has merged. Whatever comes next is the user's
word, as below.

## Audit and report

Before any merge, any `pause` or any `close`, run the audit from this checkout and the cost:

```bash
uv run --no-project python evals/kit/audit.py . --real
```

then `$CHANTIER cost --explain` and `$CHANTIER cost --by cr`. The audit prints the scorecard of
[`SCORECARD.md`](../SCORECARD.md); the rows marked `by hand` there are read by hand, from
`$CHANTIER log <cr>` (the rounds, the gates, the verifier's proof), the transcripts and a sample of
the diffs read against each specification. The audit exits 1 on a failed check.

Write the report, as the [evals README](../README.md#the-report) describes, in
`results/real-foreman-<date>.md`, with the scorecard, the cost and the steering share. Write it in a
worktree of this repository, on its own branch, and open its PR: the main checkout changes
neither its files nor its branch during the eval.

## After the report

Each of the run's PRs is merged or closed **within the day**, so a real CR opened as a "do not
merge" draft does not go stale.

- Merged by the user: `$CHANTIER order merged <cr>`. Closed: `$CHANTIER order drop <cr>`. The
  Chief of Staff sends the line to the Foreman, as usual.
- **A CR still blocked at the report** is kept for a later batch, its reason in the report. A
  blocked CR refuses both `pause` and `close`, so keeping it takes the user's word: `$CHANTIER
  order drop <cr>` moves its folder to `6-trash/`, and the Chief of Staff puts the folder back in
  `1-inbox/` by hand. `order drop` alone, with the folder left in the trash, is for an item the
  user no longer wants.
- Then the Foreman pauses the batch (`pause --epoch <n>`), the Chief of Staff gives the Completion
  report, and `close` comes on the user's word.

Until then no other batch can open (`open` exits 2): the next real campaign waits for this one
to close.
