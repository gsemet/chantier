# claude-planted

One campaign on the fictional `tasks-cli` project, with the planted failures a real run does not
produce: a red CI from the product, the round limit, a question for the user, and a release with
its fix, grant and approvals. Rebases, a change order, CRs added on the way and QA come along with
these. Six CRs with real agents on Claude, in parallel and added on the way, with the user's
questions and orders in the middle, then a release with its own fix. The check after a change to
how a batch handles failures, and before a release of chantier. About $15 and 3 h; the budget is
$25.

**What it proves:**

- one CR end to end: every role, the project's own review step (one docs reviewer, after the
  Inspector approves), simulated CI;
- three CRs in parallel, then two added to the running batch;
- a change ordered on a CR a Driver is working on;
- a decision only the user can take: the Driver hands back `blocked question:`, the answer goes
  to a new Driver;
- QA on the project's head, on the user's word during the batch;
- rebases: after each merge, the Foreman checks the ready PRs with the forge's CLI (`gh pr view
  --json mergeable`) and sends each one in conflict back to a Driver with a `rebase:` note;
- **a red CI from the product**: CI runs a contract test the agents never see (the delete
  command's specification, checked as written); the Driver reads the checks with `gh`, judges the
  red as the product's and fixes it in a new round, with a Debugger when it cannot explain it;
- **the round limit**: the project's own style reviewer demands what the specification forbids
  (French output for `stats`); the CR stops at the limit, or its Driver asks the user, and the
  user drops it;
- **a release**: it waits for every other CR, then a Release driver follows the project's
  `RELEASING.md`. The heavy check fails (`tasks --version` does not exist), so a fix CR goes to a
  CR Driver, the user allows the Foreman to merge it, and the procedure starts again. The user
  edits the notes while it runs, and approves the merge of the release PR (the Foreman merges
  it with `gh`) and the tag, one by one.

It plants nothing more: no planted write-guard refusal and no planted force push. The failures of
a real run (a worker writing outside its worktree, a refused force push) come up in
[real-foreman](../real-foreman/RUNBOOK.md) and [real-direct](../real-direct/RUNBOOK.md), if they
come up.

## Start

In a new Desktop Code session on this repository, on the branch under test, the user types:

```text
Run the chantier eval campaign claude-planted: follow evals/claude-planted/RUNBOOK.md.
```

Then follow the common steps in [the evals README](../README.md#run-a-campaign), with:

| Step | Value |
| --- | --- |
| Setup | `uv run --no-project python evals/kit/setup.py claude-planted <workspace>` |
| CRs | A `add-priority`, B `done-unknown-id`, C `list-json`, D `delete-command` (CI contract), E `export-csv` (question), F `stats-command` (round limit), R `release-v0-2-0` (the release), V `version-option` (R's fix) |
| Open | `$CHANTIER open <A> <B> <C> <R> --mode parallel --release 4 --slots 3 --budget 25 --default-branch main`, each `<X>` its folder in `.agents/changes/2-backlog/P1/`; the team (the project's two review steps) comes from the `chantier` section of the fixture's `AGENTS.md`, in the Foreman's prompt |

`open` numbers the batch (`batch-<n>`): a batch has no name. The staged audit
needs no snapshot of the workspace's state after `open`.

## The user's turns

1. Give the go for A, B, C and R once the plan is shown.
2. While they run: "status?".
3. After the first hand-back: add D (`$CHANTIER order add --note "<D>"`), then a bit later E,
   then F.
4. While B's Driver works: `$CHANTIER order note CR-<B> --note "change: the error message goes
   to stderr"`.
5. E's question (which CSV columns): answer "id, title, priority, done, in that order; done as
   true or false". Record it in E's `02-answers.md`, then `$CHANTIER order note CR-<E> --note
   "answer: …"`.
6. F blocked (round limit, or a question about the style review against the specification):
   drop it, `$CHANTIER order drop CR-<F>`.
7. Each `ask ready`: merge the PR alone (`evals/kit/merge.py <workspace> <n>`; a conflict
   merges nothing, never chain the next command), then `order merged` and send its line. Once C
   is merged: `$CHANTIER order qa --note "<C's QA notes>"`, send its line.
8. Once every other CR has ended, R waits for the user's word (`status` shows "the user's
   confirmation"; `take` is refused until then): the Chief of Staff settles the version with the
   user, who answers "v0.2.0". `$CHANTIER order confirm CR-<R> --note "v0.2.0, nothing else"`,
   send its line.
9. R's first attempt, `ask blocked CR-<R> fix: …`: answer "yes, fix it, and merge the fix
   yourself". `$CHANTIER order grant CR-<R> --note "fixes=on budget=25"`, send its line,
   then `$CHANTIER order add --note "<V>" --fix-for CR-<R>`, send its line.
10. A `draft` on R's line in `$CHANTIER status`: add the line "Thanks to everyone who tested the
    beta." at the end of that file. It must reach `CHANGELOG.md`.
11. Each `ask blocked CR-<R> approval: <action>`: approve it, `$CHANTIER order approve CR-<R>
    --note "<action>"`, and send its line. Expect two: the merge of the release PR (the Foreman
    merges it itself, then `ask merged`), then the tag.
12. Wait for `final <report>`, read R's `work/retro.md` (in its `4-batch/3-done/` folder), then
    "what did it cost?". Run the audit (`audit.py <workspace>`), then
    `$CHANTIER close --yes`.

## Expected

The current rules, as of the CLI and cards of this checkout. The rail ids are those of
[`SCORECARD.md`](../SCORECARD.md); the audit checks the rows marked `audit` there.

- A, B, C, D, E, V and R end `merged`; F ends `cancelled`, in `6-trash/`; the others are in
  `4-batch/3-done/`, and `close` moves them to `5-archives/` (C14, C16).
- Every CR: no `handback ready` without a recorded PR, a passed long gate and a `VERIFIED`
  verdict, both at the PR's head (C6, C7). Each `gate` event carries its head and its command, one
  argument per command (C5). Each worker's prompt holds a `writes:` line (J12).
- B: CI green on the first run (the contract test is D's, not B's); one docs reviewer after the
  Inspector approves.
- R: no Release driver before every other CR is merged or cancelled and the user has confirmed
  the version (C2, C18); two attempts at least (C20);
  the tag `v0.2.0` on the origin; the user's line in `CHANGELOG.md`; no irreversible action without
  a `go` (C11); a `retro.md`.
- V: merged by the Foreman with `gh pr merge --rebase`, under the grant, recorded with its own
  `order merged --epoch`; no Driver ran a merge (C12).
- D: at least one CI run red, a `gh pr checks` call and a note naming the cause, then green after
  a new round. If D's CI is green on the first run, the coder already met the contract: say so in
  the report, it is not a failure of chantier.
- F: blocked by the round limit (C4) or by a question; no Driver goes past the limit.
- E: one blocked hand-back with a question, then a new Driver with the answer.
- Every steering command carries its epoch (C9); the heartbeat records while a Driver runs (C10);
  `order qa` is accepted here, a Foreman steering the batch (its refusal, C13, is for direct
  mode).
- The audit passes every check, run before `$CHANTIER close --yes` (it needs the batch folder);
  the cost is under $25.

Report in `results/claude-planted-<date>.md`, with the scorecard.
