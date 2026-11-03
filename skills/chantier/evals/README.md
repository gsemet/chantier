# chantier evals

Two layers.

## 1. Global scenario (deterministic, free)

```bash
uv run --no-project python evals/scenario/run_scenario.py [--verbose] [--keep]
```

One whole batch through the real CLI, in a temporary git repository with a bare origin and a
fake `gh`. Nothing calls a model: a scripted Foreman feeds every event to `chantier event` and carries
out the actions it prints, scripted Drivers commit, gate, ship and wait on CI, and the Chief of
Staff steers with `chantier order`. It covers:

- preflight refusing Claude in VS Code and passing on Desktop;
- slots, hand-backs, a product-red CI with a second round, a QA finding and a clean QA pass;
- dropping a live CR (its processes stopped), adding an item, an order read twice;
- a Foreman restart (the stale epoch refused), a lost Driver resumed;
- `land` refused while PRs are open, then landing after the merges;
- cost by CR, and the event log.

The transcript goes to `evals/results/scenario-<time>.md`; exit 1 if any check fails.

## 2. Behavior cases (`claude plugin eval`, uses a model)

| Case | Checks |
| --- | --- |
| [refuses-outside-desktop](refuses-outside-desktop/case.yaml) | under the CLI, preflight fails on P1 and nothing starts, with no fallback |
| [reports-batch-status](reports-batch-status/case.yaml) | status comes from `chantier status`, every CR right, the blocked one raised as a question |
| [steers-through-foreman](steers-through-foreman/case.yaml) | a drop is a `chantier order` for the Foreman, never a direct cancel or a Driver message |
| [reports-cost](reports-cost/case.yaml) | the total and split come from `chantier cost` |
| [no-fire-unrelated](no-fire-unrelated/case.yaml) | a general git question does not load chantier |

Each case stages its workspace with `place-files.sh` (`lib/seed.py`: a git repo, `chantier setup`, a
batch reached through `chantier` commands only). Run from the skill folder:

```bash
claude plugin eval . --scaffold --allow-tools Bash --judge-model sonnet --runs 3
```

`--scaffold` runs the cases' own scripts and `--allow-tools Bash` lets the agent run `chantier`. The
default Haiku judge misread the cost case; use Sonnet. Last result (2026-10-31, one run each,
Opus 5.5 agent): 5 of 5 cases pass, about $1.8 for all the runs that got there. The
The structure tests are separate: `just test` at the repository root.
