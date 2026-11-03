# The scripted scenario

One whole batch through the real CLI, with no model: a test of chantier's mechanics, free and
about a minute per forge. The evals with real agents are in [`evals/`](../evals/README.md).

```bash
just scenario
```

runs it on a fake `gh` (GitHub), then on a fake `glab` (GitLab); one forge alone:

```bash
uv run --no-project python scenario/run_scenario.py --forge gitlab [--verbose] [--keep]
```

In a temporary git repository with a bare origin, a scripted Foreman feeds every event to
`chantier event` and carries out the actions it prints, scripted Drivers commit, gate, ship and
wait on CI, and the Chief of Staff steers with `chantier order`. It covers:

- preflight refusing Claude in VS Code and passing on Desktop with no setup and nothing written;
- the batch opened with the gates and branch from `AGENTS.md`, one `chantier spawn` per Driver,
  nothing written outside `.agents/changes/`;
- slots, hand-backs, a PR body required before shipping, a product-red CI with a second round,
  a QA run refused without proof, a QA finding that resumes the CR and a clean QA pass;
- dropping a live CR (its processes stopped), adding an item, an order read twice;
- a Foreman restart (the stale epoch refused), a lost Driver resumed;
- `land` refused while PRs are open, then landing after the merges;
- Claude cost by CR; Copilot cost by role and CR, estimated calls, updates and failures;
- prepared-CR filing, lifecycle moves, collisions and rollback;
- the event log.

The transcript goes to `scenario/results/<forge>-<time>.md` (not committed); exit 1 if any check
fails.
