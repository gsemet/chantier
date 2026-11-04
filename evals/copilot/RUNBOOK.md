# Campaign copilot

One CR on a Copilot SDK host (the Copilot app): the mechanics that differ from Claude, as cheaply
as possible. About $1.

**What it proves:**

- **The Foreman and its heartbeat:** the Foreman starts with `create_session`, the Chief of Staff
  arms `/every` in its chat, and a wake runs `chantier heartbeat`.
- **The Driver and its workers:** the Driver runs in the background (`task`), starts each worker
  with the prompt `chantier spawn` prints, and ends with a hand-back.
- **The cost:** `chantier cost` measures the batch through copilot-session-usage, by role.

Follow the common steps in [the evals README](../README.md#run-a-campaign), on Copilot, with:

| Step | Value |
| --- | --- |
| Setup | `uv run --no-project python evals/kit/setup.py copilot <workspace>` |
| Batch | `copilot` |
| CRs | `done-unknown-id` |
| Open | `$CHANTIER open copilot @.agents/changes/2-backlog/P1/done-unknown-id --slots 1 --budget 3 --fast-gate "uv run pytest -q -x" --long-gate "uv run pytest -q" --default-branch main` |

## The user's turns

1. Give the go once the plan is shown.
2. When `ask ready CR-101 <link>` arrives: merge the PR (`evals/kit/merge.py <workspace> 1`),
   then `$CHANTIER order merged CR-101` and send the line it prints.
3. Wait for `final <report>`, then "what did it cost?", run the audit, then `$CHANTIER close --yes`, and delete the `/every` heartbeat.

## Expected

- At least one heartbeat in the batch's event log.
- One Driver; one coder, one Inspector, one verifier.
- The audit runs before `close --yes` (it needs the batch folder).
- The CR ends `merged` (in `4-archives/`), the batch `landed`; `chantier cost --by role` gives a figure per role.

## Still to fill in from a real run

- How the Copilot sessions of the batch get the local forge's environment (`setup.py` prints
  it): Claude reads it from `.claude/settings.local.json`.
- The Copilot part of `evals/kit/audit.py` (roles, prompts and tools from the host's logs): until
  then the audit checks only what every host shares.
