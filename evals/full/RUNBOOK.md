# full

Two batches end to end on the eval sandbox (`shelf`), releases included, with no human step but a
`ping` when the host's limit calls for one: the operator plays the user. The text common to the sandbox campaigns (preparation, the operator, a
merge, a question, a stuck CR, the audit, the report) is in
[the evals README](../README.md#a-sandbox-campaign); this runbook adds what is specific to `full`.

**What it proves:** two batches on a real forge, with merges and the rebases they cause (four
slots, CRs that touch the same files); a CR injected into a running Foreman batch, which the
release then waits for; two releases made by the project's own procedure (the operator confirms,
approves the notes and each irreversible step, and the Foreman merges the release PR); and the
judge on every CR and on both releases.

| | |
| --- | --- |
| Setup | `uv run --no-project python evals/kit/setup.py full <workspace>` (after `sandbox.py reset --yes`, see the README) |
| Batch 1 | `delete-item`, `edit-item`, `status-filter`, `json-api`, `stats-page`, `csv-export`, `item-notes`, `title-search`, then `release-v0-2-0` (item 9, the last); `item-rating` is added during it. Four slots, budget $40 |
| Batch 2 | `sort-list`, `duplicate-url`, then `release-v0-3-0` (item 3, the last). Four slots, budget $15 |
| Mode | parallel; the Foreman steers |
| Team | the plugin's agents |

The CRs are frozen: they are specified already, with no grill to replay. They sit in
`<workspace>/.agents/changes/3-ready/` and `setup.py` prints each batch's `open` line.

## Start

In a new Code session of the Claude Desktop app opened on the workspace (not under Remote
Control), with the plugin installed from this checkout, the user types:

```text
/chantier:chief-of-staff foreman Run the chantier eval campaign full: follow <this checkout>/evals/full/RUNBOOK.md.
```

with `<this checkout>` as its absolute path. That session is the operator: the Chief of Staff in
Foreman mode, playing the user in full. One new Foreman session per batch.

## Batch 1

Open, from the workspace:

```bash
$CHANTIER open .agents/changes/3-ready/delete-item .agents/changes/3-ready/edit-item \
  .agents/changes/3-ready/status-filter .agents/changes/3-ready/json-api \
  .agents/changes/3-ready/stats-page .agents/changes/3-ready/csv-export \
  .agents/changes/3-ready/item-notes .agents/changes/3-ready/title-search \
  .agents/changes/3-ready/release-v0-2-0 --release 9 --mode parallel --slots 4 --budget 40 \
  --default-branch main
```

A new Foreman session starts. The user's turns, played by the operator:

1. The go once the plan is shown.
2. At the first `ask ready` (the first CR handed back ready), before or with its merge:
   `$CHANTIER order add --note ".agents/changes/3-ready/item-rating"`, and its line to the
   Foreman. The release waits for this CR too.
3. Each `ask ready`: the merge (`uv run --no-project python <this checkout>/evals/kit/sandbox.py
   merge <n>`, from the workspace, alone, as the README says), `$CHANTIER order merged CR-<n>`,
   its line.
4. Once every other CR has ended, the release waits for the user's confirmation (`status` says
   so): `$CHANTIER order confirm CR-<release> --note "v0.2.0, nothing else"`, its line.
5. A `draft` on the release's line in `status` (the notes): the operator reads it, checks that it
   has one bullet per merged feature, and leaves it as written. Each `ask blocked CR-<release>
   approval: <action>` (the notes, the merge of the release PR, the tag, the GitHub release, as
   the procedure asks): `$CHANTIER order approve CR-<release> --note "<action>"`, its line. The
   Foreman merges the release PR itself.
6. If the release needs a fix (`ask blocked CR-<release> fix: …`): `$CHANTIER order grant
   CR-<release> --note "fixes=on budget=40"`, then `$CHANTIER order add --note "<fix file>"
   --fix-for CR-<release>`, and their lines.
7. A `budget:` ask (`ask blocked CR-<n> budget: …`, or `status` says the budget is spent), as the
   README says: the first in the batch, `$CHANTIER order budget --note 60` and its line (a finding
   in the report); any later one in the batch, `$CHANTIER order drop CR-<n>` for the CR that asked.
8. `final`: the audit, the cost, `close --yes` (the README's "The audit").

The release is made on the sandbox by its own `RELEASING.md`; its step 3 does not name `uv.lock`,
so the frozen release CRs do.

## Batch 2

Open, in the same workspace:

```bash
$CHANTIER open .agents/changes/3-ready/sort-list .agents/changes/3-ready/duplicate-url \
  .agents/changes/3-ready/release-v0-3-0 --release 3 --mode parallel --slots 4 --budget 15 \
  --default-branch main
```

A new Foreman session; the same turns, with `v0.3.0` and no added CR (the raise on a `budget:`
ask is to `$23`: `$CHANTIER order budget --note 23`). Run the audit again,
`audit.py <workspace> --sandbox`, before this batch's `close --yes`: its judge covers the CRs of
both batches. The sandbox is left as the run ends; the next reset cleans up the two releases.

## Expected

- Every CR `merged` (or `cancelled`, with its reason in the report).
- The tags `v0.2.0` and `v0.3.0` and their GitHub releases on the sandbox.
- The injected CR merged before the release of batch 1 started (C2).
- The release taken only on the confirmation (C18), and no irreversible action without a `go`
  (C11).
- The judge `pass` on every merged CR, on `main` and on both releases.

## Living with the 10-message limit

This campaign goes past the host's limit, and its report says so. The Foreman's messages past its
tenth are lost: the operator follows the host's notes of each of the Foreman's turns and
`$CHANTIER status` / `$CHANTIER asks`, and acts from there. The operator records every order with
`$CHANTIER` before sending, and sends at most one message per wave, holding every line recorded
since its last send (merges that come together go in one message).

Expected sends: about 9 to 12 in batch 1 (the Foreman's start, the added CR, the merge waves, the
confirmation, the approvals) and 6 to 8 in batch 2. Past the limit, a refused send is reported
(J15) and never sent another way; the order is already recorded, and the Foreman reads it at its
next heartbeat wake.

If the Foreman's heartbeat has already ended (`status` says `heartbeat stopped`) while an order
waits, the user types one line, `ping`, in the Foreman's session. This may be needed more than
once; each `ping` is a human step, and the report counts them. They are the only human steps a
`full` run may have.

## Report

`results/full-<date>-run<n>.md`: one report for both batches, with one scorecard where a row is
`seen, wrong` if it was wrong in either batch, and the cost per batch and in total. It names each
human step and gives their count.

## Cost and time

The budgets cap them: $40 and $15. The first run measures them; the figures are written here from
its report.
