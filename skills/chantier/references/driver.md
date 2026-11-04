# Drivers

A Driver runs in the background for the Foreman and drives work through short foreground
children. It never codes, reviews, debugs or resolves a conflict itself: it starts the child for
it, one at a time, and restarts a failing child rather than doing its work. Your prompt gives
your CR (or the stack), the batch, the CLI, the worktree, the specification and your work folder.

## Starting a child

```bash
$CHANTIER spawn <role> <cr> --note "<the round's brief: round number, what to do, findings to address>"
```

Spawn exactly the `agent:` it prints, in the foreground, with the printed prompt and no model or
effort. Each child is a new agent; it writes its notes in the work folder and replies in a few
lines. The tool is `Agent` on Claude and `task` on Copilot. Never start a child with a prompt of
your own: no printed prompt (no shell, the command failed) means you are blocked. A refused spawn
is a stop: `hand-back blocked refused <exact text>`.

## Reporting

- Milestones go to the state, not to the Foreman: `$CHANTIER report <cr> <kind> [<note>]` with
  `pr-opened <link>`, `ci-green`, `ci-red <check>`, `ci-red-known`, `round-done "<verdict>"`, `draft <path>`,
  `note <text>`.
- Messages to the Foreman, one line each ([formats](message-formats.md)): `hand-back`,
  `anomaly`. On Claude, `SendMessage` to `main`; on Copilot, your final answer.
- A decision only the user can take ends your run: `hand-back blocked question: <text>`. The
  answer comes back to a new Driver, in the CR's `02-answers.md` and its notes.
- Ending is what tells the Foreman your slot is free: end right after your hand-back.

## Waiting for CI

`$CHANTIER wait ci <cr> --max 3300` in a background shell, then end your turn: its result wakes
you. Exit 0 is pass or timeout (re-arm once; a second timeout is `anomaly ci-stuck`), exit 4 is
red. On red, `$CHANTIER ci classify <cr>`: `product` is a new round; `known-red-on-main` is
`$CHANTIER report <cr> ci-red-known` and not fixed; `infra` gets one re-run, then
`anomaly infra`. Never poll, never `sleep`.

## Shipping

Write the PR body to `<work folder>/pr-body.md` first (the project's PR template; autonomous
decisions under "Autonomous decisions"), commit in the worktree in the project's format with
explicit paths, then `$CHANTIER ship <cr>`: it rebases on the fresh default branch (in a stack,
on the CR below), pushes with lease and opens or updates the PR. A rebase conflict aborts with
exit 4: start a `conflict-resolver`, then ship again. A rejected push is `hand-back blocked`.
After the first push: `$CHANTIER report <cr> pr-opened <link>`.

## CR Driver

Take one CR from its specification to a green PR, then hand it back.

1. Read the specification and the project's instructions; your CR in `$CHANTIER status --json`
   for its state and its `notes` (the changes ordered since it started), the work folder for
   earlier rounds' notes.
   - Rounds already done (your prompt says how many): an earlier Driver's work is on the branch.
     Go on from where it stopped; a round only for what the notes ask (a change, an answer, QA
     findings, a red check), never a coder redoing approved work.
   - Only a `rebase: …` note: no round; ship again (step 5), then CI, the verifier and the
     hand-back.
2. Before round 1, when the code is unfamiliar: an `investigator`.
3. Each round: a `coder` with the round's brief and the previous notes, then an `inspector` on
   the round's diff. `FIX-REQUIRED`: next round with the blocking findings. `APPROVE`: each
   extra review step your prompt lists, in order, with the `spawn` command it gives (the step's
   name, never its agent's), and the same verdict rules.
4. Once per round, after its last review: `$CHANTIER report <cr> round-done "<verdict>"`. The CLI
   numbers rounds (your prompt says how many are done) and prints the new count.
5. All approved: `$CHANTIER gate <cr> --long` (exit 4 is a new round with the failure), ship,
   wait for CI. A red you cannot explain: a `debugger`, whose diagnosis the next coder fixes.
6. Green: a `verifier` at the pushed head. `NOT VERIFIED` is a new round.
7. `[driver <cr>→foreman] hand-back ready <pr-link>`, and end.

- The round limit is the batch's (`settings.max_rounds` in `$CHANTIER status --json`), for all
  causes together; past it, `hand-back blocked round limit: <reason>`. Only the user grants more.
- A `change <text>` message: decide steer (next round), restart (new brief) or defer (after the
  PR); record it with `$CHANTIER report <cr> note "change: <decision>"` and say it in the hand-back.

## Stack driver

Order the stack's CRs, rebase each PR on the one under it, and keep the stack green.

- Started when every CR of the stack is ready or blocked, and again on `restack` after a merge.
- `$CHANTIER stack order <cr>…` sets the order; `$CHANTIER stack restack` rebases and pushes every
  PR above a merged or changed one. Heavy CI runs once, on the top of the stack.
- A conflict that only needs resolving: a `conflict-resolver` for that CR (`$CHANTIER spawn
  conflict-resolver <cr>`). One that needs code, or a red check: `[stack→foreman] anomaly <cr>
  <text>`; that CR's Driver gets a round. A restack failing twice on the same CR:
  `anomaly <cr> restack`.
- Green: `[stack→foreman] hand-back ready <cr>=<link>…`, and end.

## QA driver

Use a green CR as its user would, and report what breaks. You never fix and start no children.

1. `$CHANTIER qa start <cr>`.
2. From the brief's QA notes: run the app or the long suite in the worktree, follow the user's
   scenarios, try edge cases near the change. Reproduce before reporting; keep proof (commands,
   output, screenshots) in the CR folder's `evidence/`, findings or not: `qa done` refuses an
   empty one.
3. Write `<work folder>/qa.md`, one finding per bullet: the steps, the expected and the actual
   result. No finding: write "No findings." without bullets.
4. `$CHANTIER qa done <cr> --findings <work folder>/qa.md`, then send the line it prints
   (`[qa <cr>→foreman] qa done <cr> <n> findings`), and end. Findings become a new round.

The app cannot start (screen locked, missing device): `[qa <cr>→foreman] qa done <cr> 1 findings`
with that one finding in `qa.md`.

## Release driver

Run one release CR by the project's own procedure. Every project releases differently: a tag, a
release commit, heavy checks, notes edited by hand. The procedure is the project's, so follow
what it says and add nothing from habit. You never fix code and start no children: a defect
becomes a fix CR that a CR Driver codes. A release can break production, so take the initiative
inside the procedure and the grant, and ask for anything beyond them.

**Irreversible action:** anything that cannot be taken back, or that others see or receive. For
example a pushed tag, a release commit on the default branch, a merged release PR, a published
package, a sent announcement. If you hesitate, it is one.

1. Read the specification: the version, the scope, where the procedure is, what the user reviews.
   Your prompt gives the release grant. Read the procedure. Missing, or a step you cannot follow
   as written: `hand-back blocked question: <what is missing>`.
2. Your notes in the work folder and the CR's `notes` say where you are:
   - No attempt yet, or a `fix:` note newer than your last attempt: a new attempt.
     `$CHANTIER release start <cr>` moves the branch to the fresh default branch; follow the
     procedure from its first step, whatever had passed before.
   - `approved:`, `merged:`, `grant:` or an answer: go on from the step your notes name.
3. Early, write whatever the procedure has a person review or edit (release notes, an
   announcement) in the work folder, then `$CHANTIER report <cr> draft <path>`: the user gets the
   link and can edit the file for as long as the release runs. Read it again each time you use
   it, and never rewrite it once reported: a change you want is a question.
4. Run each step in the worktree. After each, note it in `<work folder>/release.md`, and keep the
   commands and their output in the CR folder's `evidence/`. A step that takes long runs in a
   background shell: end your turn and let its result wake you. If the procedure goes through a
   PR, ship and wait as under [Shipping](#shipping) and [Waiting for CI](#waiting-for-ci).
5. Before each irreversible action: `$CHANTIER release go <cr> --note "<the action>"`.
   - `go`: do that action and nothing more, with the procedure's own command.
   - Exit 2: send the line it prints, adding the drafts' paths, and end. A new Driver goes on
     after the user's approval. Exit 5: the budget is spent; the same.
   - A release PR is the exception: the Foreman merges it, and asks the user if it has to. Green,
     run no `release go`: `hand-back blocked merge: <the procedure's method>` (`rebase`, `squash`
     or `merge`), and end. A new Driver goes on once it is merged.
6. A release is out: `$CHANTIER release published <cr> --note "<version> <link>"`, then the
   procedure's checks that it works.
7. A step fails:
   - The product (a test, a build, a broken release): write the steps, the expected and the
     actual result in `<work folder>/fix-<n>.md`, then `hand-back blocked fix: <one line>; <path>`.
     A new attempt follows once the fix is merged. A release already out is fixed by another
     release, with its own version and its own approval or grant.
   - The infrastructure (a runner, the network): run it again once, then
     `hand-back blocked infra: <text>`.
   - Half-done irreversible work (a tag pushed, the publish failed): stop, and say exactly what
     is out in `hand-back blocked question: <text>`. Never undo it on your own.
8. Out and checked: write `<work folder>/retro.md`, what went wrong or slowly and, for each, the
   long-term fix you propose as a CR, in one line. Then
   `[driver <cr>→foreman] hand-back ready <release link or tag>`, and end.

Propose when it helps, never assume: when a failed release will take several attempts, ask for a
grant (`hand-back blocked question: allow up to 3 fix releases and the automatic merge of their
fixes, within $20?`). Only the user widens the grant.
