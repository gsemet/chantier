# real-foreman

A quick campaign: 5 frozen CRs on the eval sandbox (`shelf`), in the mode chosen at launch,
steered by a Foreman, with the real `gh` and CI. It proves the path a user takes. It does not
exercise the failures the scripted campaign [claude-planted](../claude-planted/RUNBOOK.md)
plants. The same run steered by the Chief of Staff alone is [real-direct](../real-direct/RUNBOOK.md);
two releases and an injected CR are in [full](../full/RUNBOOK.md).

The text common to the sandbox campaigns (preparation, the operator, a merge, a question, a stuck
CR, the audit, the report) is in [the evals README](../README.md#a-sandbox-campaign).

| | |
| --- | --- |
| Setup | `uv run --no-project python evals/kit/setup.py real-foreman <workspace>` (after `sandbox.py reset --yes`, see the README) |
| CRs | `delete-item`, `edit-item`, `status-filter`, `json-api`, `stats-page`: frozen and specified, no grill, no release |
| Open | `$CHANTIER open .agents/changes/3-ready/delete-item .agents/changes/3-ready/edit-item .agents/changes/3-ready/status-filter .agents/changes/3-ready/json-api .agents/changes/3-ready/stats-page --mode <mode> --slots 3 --budget 20 --default-branch main` (`setup.py` prints it) |
| Mode | chosen at launch: `stack`, `parallel` or `series`; the same 5 CRs in every mode |
| Team | the plugin's agents |
| Cost and time | the budget caps the cost at $20; the first run measures cost and time and this table is then written from its report |

The mode is written in the report, so runs of one mode compare with each other, and the modes
with each other.

## Start

In a new Code session of the Claude Desktop app opened on the workspace (not under Remote
Control), with the plugin installed from this checkout, the user types, with `<mode>` one of
`stack`, `parallel`, `series` and `<this checkout>` its absolute path:

```text
/chantier:chief-of-staff foreman Run the chantier eval campaign real-foreman in <mode> mode: follow <this checkout>/evals/real-foreman/RUNBOOK.md.
```

That session is the operator: a Chief of Staff in Foreman mode, playing the user in full (Q7):
the go after the plan, every merge, every answer. Nothing waits on the real user. The host's
limits of the [evals README](../README.md#the-hosts-limits) hold: 10 messages per session, and
the go typed in the desktop app. A quick campaign stays under the limit: the Foreman's start and
at most one send per merge wave.

One new Foreman session per batch: `cost` counts a session's calls from the batch's creation, but
the session's context still costs each turn.

## The user's turns

1. The go once the plan is shown.
2. Each `ask ready`: merge the PR with `uv run --no-project python <this
   checkout>/evals/kit/sandbox.py merge <n>` (from the workspace, alone, as the README says), then
   `$CHANTIER order merged CR-<n>` and send its line. In the chosen mode: parallel in the order
   the CRs become ready, series in the series' order, a stack from the bottom up.
3. A question, a stuck CR or a `budget:` ask: as the README says (the raise on a `budget:` ask is
   to `$30`: `$CHANTIER order budget --note 30`).
4. `final`: the audit, the cost, `close --yes`.

## If the 10-message limit is reached

The quick campaign aims to stay under it. Past it, the operator follows the host's notes of each
of the Foreman's turns and `$CHANTIER status` / `$CHANTIER asks`, records every order with
`$CHANTIER` before sending, and sends at most one message per wave. A refused send is reported
(J15) and never sent another way; the Foreman reads the recorded order at its next heartbeat wake.
If its heartbeat has ended while an order waits (`status` says `heartbeat stopped`), the user types
`ping` in the Foreman's session, as many times as needed, and the report counts each as a human
step.

## Expected

- Every CR `merged` (or `cancelled`, with its reason in the report).
- The judge `pass` on every merged CR and on `main`.
- The scorecard rows the mode can show, marked.

## Audit and report

When the steering session reports `final`, before `close --yes`, run the audit from this checkout:

```bash
uv run --no-project python evals/kit/audit.py <workspace> --sandbox
```

then `$CHANTIER cost --explain` and `$CHANTIER cost --by cr`. The audit prints the run's table,
the facts, the checks, the judge and the scorecard of [`SCORECARD.md`](../SCORECARD.md); the rows
marked `by hand` there are read by hand, from `$CHANTIER log <cr>` (the rounds, the gates, the
verifier's proof), the transcripts and a sample of the diffs read against each specification.

Write the report, as the [evals README](../README.md#the-report) describes, in
`results/real-foreman-<date>-run<n>.md`, with the scorecard, the cost and the steering share, in a
worktree of this repository on its own branch, and open its PR: the main checkout changes neither
its files nor its branch during the eval.

The sandbox is left as the run ends; the next `sandbox.py reset --yes` cleans it up.
