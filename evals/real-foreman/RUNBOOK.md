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
| Setup | `uv run --no-project python evals/kit/setup.py real-foreman <workspace>` (a new folder inside the eval root, after `sandbox.py reset --yes`, see the README) |
| CRs | `delete-item`, `edit-item`, `status-filter`, `json-api`, `stats-page`: frozen and specified, no grill, no release |
| Open | `$CHANTIER open 3-ready/delete-item 3-ready/edit-item 3-ready/status-filter 3-ready/json-api 3-ready/stats-page --mode <mode> --slots 3 --budget 20 --default-branch main` (`setup.py` prints it) |
| Mode | chosen at launch: `stack`, `parallel` or `series`; the same 5 CRs in every mode |
| Team | the plugin's agents |
| Cost and time | the budget caps the cost at $20; run 2 (2026-11-15, stack): $10.28 (steering 20%), about 28 min from `open` to the last merge and 36 to the close, [report](../results/real-foreman-2026-11-15-run2.md) |

The mode is written in the report, so runs of one mode compare with each other, and the modes
with each other.

## Start

In a new Code session of the Claude Desktop app opened on the workspace (not under Remote
Control), with the plugin installed from this checkout, the user types, with `<mode>` one of
`stack`, `parallel`, `series` and `<this checkout>` its absolute path:

```text
/chantier:chief-of-staff foreman Run the chantier eval campaign real-foreman in <mode> mode: follow <this checkout>/evals/real-foreman/RUNBOOK.md.
```

Setup prints this as its last line, the `prompt` line, with the path filled in. Start the
operator from New session in the Claude Desktop Code tab (pick the workspace folder in its native
spelling, then paste the line), or ask a Desktop session at the desk to start a new session on the
workspace with it. This campaign needs the desk, to start the Foreman and type the go, and the eval
root does not change that (the evals README, "The host's limits"). The workspace is inside the trusted eval
root, so the app does not ask to trust it (setup refuses a workspace outside it; **unproved** until the trial reports).

That session is the operator: a Chief of Staff in Foreman mode, playing the user in full (Q7):
the go after the plan, every merge, every answer. Nothing waits on the real user. The host's
limits of the [evals README](../README.md#the-hosts-limits) hold: 10 messages per session, and
the go typed in the desktop app. A quick campaign stays under the limit: the Foreman's start and
at most one send per merge wave.

One new Foreman session per batch: `cost` counts a session's calls from the batch's creation, but
the session's context still costs each turn.

## The user's turns

On each new PR of the run (a PR of the sandbox whose title starts with the run's prefix), the first
act is to turn that PR's Auto-fix monitor off with `mcp__ccd_pr__set_monitor`; never on another PR,
never to arm one. When the call is refused, turn it off from the PR's menu in the Changes card and
record the refusal as a finding (the evals README, "Auto-fix during the run").

1. The go once the plan is shown.
2. Each `ask ready`: merge the PR with `uv run --no-project python <this
   checkout>/evals/kit/sandbox.py merge <n>` (from the workspace, alone, as the README says), then
   `$CHANTIER order merged CR-<n>` and send its line (the Foreman then fast-forwards the
   workspace's main checkout to `main`: it no longer stays at the base, the audit's J26 reads it).
   In the chosen mode: parallel in the order
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
`results/real-foreman-<date>-run<n>.md`, with the scorecard, the cost (read after `close --yes`
from the closed batch's record, `.agents/changes/5-archives/batches/batch-NN.md`; the audit's cost
and `cost --explain` stay before it) and the steering share, in a
worktree of this repository on its own branch, and open its PR: the main checkout changes neither
its files nor its branch during the eval.

The sandbox is left as the run ends; the next `sandbox.py reset --yes` cleans it up.
