# Campaign claude-smoke

One CR, end to end, with real agents on Claude: the quick check after a change to chantier.
About $1 and 15 minutes.

**What it proves:** the Chief of Staff opens a batch, the Foreman starts as its own session and
spawns a Driver; the Driver runs a coder, an Inspector, the project's own review step (a custom
agent), the long gate, ships, waits for the simulated CI and starts a verifier; the user merges;
the batch lands with its STATUS.md as the report and a measured cost. Every agent gets its role and stays in it.

Follow the common steps in [the evals README](../README.md#run-a-campaign), with:

| Step | Value |
| --- | --- |
| Setup | `uv run --no-project python evals/kit/setup.py claude-smoke <workspace>` |
| Batch | `smoke` |
| CRs | `done-unknown-id` (a bug: `tasks done 42` crashes with a traceback) |
| Open | `$CHANTIER open smoke @.agents/changes/2-backlog/P1/done-unknown-id --slots 1 --budget 5 --fast-gate "uv run pytest -q -x" --long-gate "uv run pytest -q" --default-branch main --review "docs-review=chantier-eval-docs-reviewer:every new or changed CLI command or option is documented in README.md, with an example"` |

## The user's turns

1. Give the go once the plan is shown.
2. When `ask ready CR-101 <link>` arrives: merge the PR (`evals/kit/merge.py <workspace> 1`),
   then `$CHANTIER order merged CR-101` and send the line it prints.
3. Wait for `final <report>`. Run the audit, then `$CHANTIER close --yes`.

## Expected

- One Driver; one coder, one Inspector, one docs reviewer, one verifier, all started by it.
- The docs reviewer runs after the Inspector approves.
- CI is green on the first run; the CR ends `merged`, the batch `landed`; the CR is in `4-archives/`.
- The audit passes every check, run before `$CHANTIER close --yes` (it needs the batch folder); the cost is under $2.
