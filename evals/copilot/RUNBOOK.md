# Campaign copilot

One frozen CR on a Copilot SDK host (the Copilot app), on the eval sandbox with the real `gh`: the
mechanics that differ from Claude, as cheaply as possible. About $1.

**What it proves:**

- **The Foreman and its heartbeat:** the Foreman starts with `create_session`, the Chief of Staff
  arms `/every` in its chat, and a wake runs `chantier status --refresh`.
- **The Driver and its workers:** the Driver runs in the background (`task`), starts each worker
  with a prompt written from its card and the facts `chantier round` prints, and ends with a
  hand-back.
- **The cost:** `chantier cost` measures the batch through copilot-session-usage, as a breakdown (`Agent <type>` lines).

Follow the sandbox campaign text in [the evals README](../README.md#a-sandbox-campaign) (the
preparation, the run's number and prefix, a merge, the audit), on Copilot, with:

| Step | Value |
| --- | --- |
| Setup | `uv run --no-project python evals/kit/setup.py copilot <workspace>` |
| Batch | `copilot` |
| CRs | `delete-item` |
| Open | `$CHANTIER open .agents/changes/3-ready/delete-item --slots 1 --budget 3 --default-branch main` |

## The user's turns

1. Give the go once the plan is shown.
2. When `ask ready CR-<n> <link>` arrives: merge the PR (`uv run --no-project python <this
   checkout>/evals/kit/sandbox.py merge <pr>`, from the workspace, alone), then `$CHANTIER order
   merged CR-<n>` and send the line it prints.
3. A `budget:` ask, as the README says (the raise is to `$5`: `$CHANTIER order budget --note 5`).
4. Wait for `final <report>`, then "what did it cost?", run the audit (`audit.py <workspace>
   --sandbox`), then `$CHANTIER close --yes`, and delete the `/every` heartbeat.

## Expected

- At least one heartbeat in the batch's event log.
- One Driver; one coder, one Inspector, one verifier.
- The audit runs before `close --yes` (it needs the batch folder).
- The CR ends `merged` (in `4-batch/3-done/`, waiting for `close`), the batch `paused`; `chantier cost` prints the breakdown, an `Agent <type>` line per agent type.
- The judge: the hidden tests of `delete-item` on the PR's head.

## Still to fill in from a real run

- The Copilot part of `evals/kit/audit.py` (roles, prompts and tools from the host's logs): until
  then the audit checks only what every host shares, the run, the judge and the cost, with no rail
  ids and no scorecard.
