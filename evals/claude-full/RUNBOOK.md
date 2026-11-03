# Campaign claude-full

Six CRs with real agents on Claude, in parallel and added on the way, with the user's questions
and orders in the middle, and two failure paths. The check before a release. About $12 and
2 h 30.

**What it proves**, on top of [claude-smoke](../claude-smoke/RUNBOOK.md):

- three CRs in parallel, then two added to the running batch;
- a change ordered on a CR a Driver is working on;
- a decision only the user can take: the Driver hands back `blocked question:`, the answer goes
  to a new Driver;
- QA on one CR;
- rebases: after each merge, the ready CRs that no longer merge cleanly go back to a Driver on
  their own;
- **a red CI from the product**: CI runs a contract test the agents never see (the delete
  command's specification, checked as written); the Driver classifies the red as `product` and
  fixes it in a new round, with a Debugger when it cannot explain it;
- **the round limit**: the project's own style reviewer demands what the specification forbids
  (French output for `stats`); the CR stops at the limit, or its Driver asks the user, and the
  user drops it.

Follow the common steps in [the evals README](../README.md#run-a-campaign), with:

| Step | Value |
| --- | --- |
| Setup | `uv run --no-project python evals/kit/setup.py claude-full <workspace>` |
| Batch | `full` |
| CRs | A `add-priority`, B `done-unknown-id`, C `list-json` (QA), D `delete-command` (CI contract), E `export-csv` (question), F `stats-command` (round limit) |
| Open | `$CHANTIER open full @<A> @<B> @<C> --slots 3 --qa 3 --budget 25 --fast-gate "uv run pytest -q -x" --long-gate "uv run pytest -q" --default-branch main --review "docs-review=chantier-eval-docs-reviewer:every new or changed CLI command or option is documented in README.md, with an example" --review "style-review=chantier-eval-strict-reviewer:the house style of the command line"`, each `@<X>` its folder in `.agents/changes/backlog/2-backlog/P1/` |

## The user's turns

1. Give the go for A, B and C once the plan is shown.
2. While they run: "status?".
3. After the first hand-back: add D (`$CHANTIER order add --note "@<D>"`), then a bit later E,
   then F.
4. While B's Driver works: `$CHANTIER order change CR-<B> --note "the error message goes to
   stderr"`.
5. E's question (which CSV columns): answer "id, title, priority, done, in that order; done as
   true or false". Record it in E's `02-answers.md`, then `$CHANTIER order change CR-<E> --note
   "answer: …"`.
6. F blocked (round limit, or a question about the style review against the specification):
   drop it, `$CHANTIER order drop CR-<F>`.
7. Each `ask ready`: merge the PR alone (`evals/kit/merge.py <workspace> <n>`; a conflict
   merges nothing, never chain the next command), then `order merged` and send its line.
8. Wait for `final <report>`, then "what did it cost?".

## Expected

- A, B, C, D and E end `merged`; F ends `cancelled`.
- D: at least one CI run red, classified `product`, then green after a new round. If D's CI is
  green on the first run, the coder already met the contract: say so in the report, it is not a
  failure of chantier.
- F: blocked by the round limit or by a question; no Driver goes past the limit.
- E: one blocked hand-back with a question, then a new Driver with the answer.
- The audit passes every check; the cost is under $20.
