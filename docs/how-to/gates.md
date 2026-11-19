# Your gates

Declare the two checks that guard every change, in your `AGENTS.md`.

## The two gates

- **The fast gate**: a short check, kept under a minute (lint, type check, the tests near the
  change). The Coder runs it after every round, and the Inspector may run it to check a claim. The
  Driver runs it once more before the CR's first push, at the rebased head. Your project may also
  name an extra pre-push check in its `AGENTS.md`: it runs at the same time and the same way (one
  command per item, never through `chantier gate`).
- **The long gate**: the full check, run once before the PR with `chantier gate`. It runs one at a
  time unless your `chantier.yaml` allows more (see below). When several wait, the CR you merge
  next goes first in a stack or series batch, then those the Foreman moved first, then arrival
  order.

One command may serve as both gates, but the fast gate is never run through `chantier gate`.

The Driver does not open the PR until the long gate has passed at the PR's head and the Verifier
has said `VERIFIED` there. Both carry over a clean rebase that leaves the patch unchanged: git
proves it by the patch-ids of the CR's own commits. CI still runs at the new head.

## Declare them

Write one line each, with the exact commands. Give one command per item and never chain them with
`&&` or `;`: the Driver passes each as its own argument to `chantier gate`, so it runs the same
way on every OS.

```markdown
- Fast gate (after each change): `npm run lint`, `npm test -- --changed`.
- Long gate (before a pull request): `npm test`.
- Before the first push, for a change under `src/`: `<cmd>`.
- A change to the docs alone needs no long gate.
```

Write an exemption (the last line) and a project with no long gate at all (`This project has no
long gate: <why>`) there too. The Driver quotes that rule instead of running the gate, and the
Foreman (or the Chief of Staff steering) checks it. A rule that is not written is a question for
you, never a pass.

## When CI is the long gate

If your CI runs the long suite faster than your machine, name that pipeline job as the long gate:

```markdown
- Long gate: the pipeline's `test` job, green at the PR's head.
```

The Driver then runs no local gate and waits for that job on the forge. The Foreman (or the Chief
of Staff steering) reads the job's state at the PR's head. A project with no CI, or whose runner is
the same slow machine, gains nothing. GitLab and Copilot: unproved.

## Run several long gates at once

If your long gate is isolated per worktree (its own ports, folders and services), set
`long_gate:` then `parallel: <n>` in `chantier.yaml`. Pick the number your machine carries. With no
such key the long gates run one at a time.

## Let chantier write them

Say "init": the tour looks for both gates and proposes the exact lines. Or tell the Chief of Staff
"our long gate is `<command>`". Either writes them only on your yes.
