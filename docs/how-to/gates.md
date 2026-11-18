# Your gates

The fast gate and the long gate that guard every change, and how to declare them.

Two checks guard every change, in any project. You declare them in your `AGENTS.md`.

- **The fast gate** (a short check): what the Coder runs after every round, and the Inspector may
  run to check a claim. It should take seconds to a minute: lint, type check, the tests near the
  change. The Driver also runs it once more before the CR's first push, at the rebased head. Your
  project may also name an extra pre-push check in its `AGENTS.md`: it runs at the same time and
  the same way (one command per item, never through `chantier gate`).
- **The long gate**: the full check the Driver runs once before the PR with `chantier gate`,
  as many at once as your `chantier.yaml` allows (one by default, see below); when more wait,
  the CR you merge next goes first in a stack or series batch, then those the Foreman moved
  first, then arrival order. `handback ready` requires it passed at the PR's head (or carried
  over a clean rebase), and the Verifier's `VERIFIED` there. Both carry over a clean rebase that
  leaves the patch unchanged: `ship` proves it with git, by the exact patch-ids of the CR's own
  commits, and records it. CI still runs at the new head. One command may serve as both gates. The fast gate is never run
  through `chantier gate`.

Declare them with one line each, the exact commands, one command per item, never chained with
`&&` or `;` (the Driver passes each as its own argument to `chantier gate`, so it runs the same
way on every OS):

```markdown
- Fast gate (after each change): `npm run lint`, `npm test -- --changed`.
- Long gate (before a pull request): `npm test`.
- Before the first push, for a change under `src/`: `<cmd>`.
- A change to the docs alone needs no long gate.
```

An exemption (the last line) and a project with no long gate at all (`This project has no long
gate: <why>`) are written there too: the Driver quotes that rule with `handback ready
--no-gate`, and the Foreman (or the Chief of Staff steering) checks it. A rule that is not
written is a question for you, never a pass.

A project whose CI runs the long suite faster than the machine may name that pipeline job as its
long gate instead:

```markdown
- Long gate: the pipeline's `test` job, green at the PR's head.
```

The Driver then runs no local gate, waits for that job on the forge and quotes the rule with
`--no-gate`, and the Foreman (or the Chief of Staff steering) reads the job's state at the PR's
head. A project with no CI, or whose runner is the same slow machine, gains nothing. GitLab and
Copilot: unproved.

A long gate that is isolated per worktree (its own ports, folders and services) can run several at
once with `long_gate:` then `parallel: <n>` in `chantier.yaml`; the number is what your machine
carries. With no such key the long gates run one at a time.

To have chantier declare them, say "init" (the tour looks for both gates and proposes the exact
lines), or tell the Chief of Staff "our long gate is `<command>`". Either writes them only on
your yes.
