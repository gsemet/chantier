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
  `pr-opened <link>`, `ci-green`, `ci-red <check>`, `ci-red-known`, `round-done "r<n> <verdict>"`,
  `note <text>`.
- Messages to the Foreman, one line each ([formats](message-formats.md)): `hand-back`,
  `question`, `anomaly`. On Claude, `SendMessage` to `main`. On Copilot you cannot message the
  Foreman while you run: your final answer is your message, so a question ends your run as
  `hand-back blocked question: <text>` (the answer comes back as a new round).
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
2. Before round 1, when the code is unfamiliar: an `investigator`.
3. Each round: a `coder` with the round's brief and the previous notes, then an `inspector` on
   the round's diff. `FIX-REQUIRED`: next round with the blocking findings. `APPROVE`: each
   extra review step your prompt lists, in order, with the same verdict rules.
4. `$CHANTIER report <cr> round-done "r<n> <verdict>"` after each round.
5. All approved: `$CHANTIER gate <cr> --long` (exit 4 is a new round with the failure), ship,
   wait for CI. A red you cannot explain: a `debugger`, whose diagnosis the next coder fixes.
6. Green: a `verifier` at the pushed head. `NOT VERIFIED` is a new round.
7. `[driver <cr>→foreman] hand-back ready <pr-link>`, and end.

- The round limit is the batch's (`settings.max_rounds` in `$CHANTIER status --json`), for all
  causes together; past it, `hand-back blocked round limit: <reason>`. Only the user grants more.
- A `change <text>` message: decide steer (next round), restart (new brief) or defer (after the
  PR); record it with `$CHANTIER report <cr> note "change: <decision>"` and say it in the hand-back.
- A decision only the user can take: `question` (Claude) or `hand-back blocked question:`
  (Copilot).

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
   output, screenshots) in the CR folder's `evidence/`.
3. Write `<work folder>/qa.md`, one finding per bullet: the steps, the expected and the actual
   result. No finding: write "No findings." without bullets.
4. `$CHANTIER qa done <cr> --findings <work folder>/qa.md`, then send the line it prints
   (`[qa <cr>→foreman] qa done <cr> <n> findings`), and end. Findings become a new round.

The app cannot start (screen locked, missing device): `[qa <cr>→foreman] qa done <cr> 1 findings`
with that one finding in `qa.md`.
