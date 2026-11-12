# Your gates

The fast gate and the long gate that guard every change, and how to declare them.

Two checks guard every change, in any project. You declare them in your `AGENTS.md`.

- **The fast gate** (a short check): what the Coder runs after every round, and the Inspector may
  run to check a claim. It should take seconds to a minute: lint, type check, the tests near the
  change.
- **The long gate**: the full check the Driver runs once before the PR with `chantier gate`,
  alone in the repository. `handback ready` requires it passed at the PR's head, and the
  Verifier's `VERIFIED` there. One command may serve as both gates.

Declare them with one line each, the exact commands, one command per item, never chained with
`&&` or `;` (the Driver passes each as its own argument to `chantier gate`, so it runs the same
way on every OS):

```markdown
- Fast gate (after each change): `npm run lint`, `npm test -- --changed`.
- Long gate (before a pull request): `npm test`.
- A change to the docs alone needs no long gate.
```

An exemption (the last line) and a project with no long gate at all (`This project has no long
gate: <why>`) are written there too: the Driver quotes that rule with `handback ready
--no-gate`, and the Foreman (or the Chief of Staff steering) checks it. A rule that is not
written is a question for you, never a pass.

To have chantier declare them, say "init" (the tour looks for both gates and proposes the exact
lines), or tell the Chief of Staff "our long gate is `<command>`". Either writes them only on
your yes.
