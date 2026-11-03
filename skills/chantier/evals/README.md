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

- preflight refusing Claude in VS Code and passing on Desktop with no setup and nothing written;
- the batch opened with the gates and branch from `AGENTS.md`, one `chantier spawn` per Driver,
  nothing written outside `.agents/changes/`;
- slots, hand-backs, a PR body required before shipping, a product-red CI with a second round,
  a QA finding that resumes the CR and a clean QA pass;
- dropping a live CR (its processes stopped), adding an item, an order read twice;
- a Foreman restart (the stale epoch refused), a lost Driver resumed;
- `land` refused while PRs are open, then landing after the merges;
- Claude cost by CR; Copilot cost by role and CR, estimated calls, updates and failures;
- prepared-CR filing, lifecycle moves, collisions and rollback;
- the event log.

The transcript goes to `evals/results/scenario-<time>.md`; exit 1 if any check fails.

## 2. Behavior cases (`claude plugin eval`, uses a model)

| Case | Checks |
| --- | --- |
| [refuses-outside-desktop](refuses-outside-desktop/case.yaml) | under the CLI, preflight fails on P1 and nothing starts, with no fallback |
| [reports-batch-status](reports-batch-status/case.yaml) | status comes from `chantier status`, every CR right, the blocked one raised as a question |
| [steers-through-foreman](steers-through-foreman/case.yaml) | a drop is a `chantier order` for the Foreman, never a direct cancel or a Driver message |
| [reports-cost](reports-cost/case.yaml) | the total and split come from `chantier cost` |
| [learns-project](learns-project/case.yaml) | gates and branch come from `AGENTS.md`; nothing is written |
| [customizes-team](customizes-team/case.yaml) | "use my agent as the coder, add a security review" becomes a `chantier` section in `AGENTS.md` |
| [no-fire-unrelated](no-fire-unrelated/case.yaml) | a general git question does not load chantier |

Each case stages its workspace with `place-files.sh` (`lib/seed.py`: a git repo and a batch of
prepared CRs reached through `chantier` commands only). Run from the skill folder:

```bash
claude plugin eval . --scaffold --allow-tools Bash --judge-model sonnet --runs 3
```

`--scaffold` runs the cases' own scripts and `--allow-tools Bash` lets the agent run `chantier`. The
default Haiku judge misread the cost case; use Sonnet. Run it on Linux or macOS: on Windows,
`claude plugin eval` refuses to grant Bash without a sandbox backend, and the scaffold scripts
need `bash` on the PATH.

Last result (2026-11-03, Windows, so run by hand: one Opus 5.5 agent per case, playing the
Chief of Staff from `SKILL.md` in a workspace staged by `lib/seed.py`, graded against each case's
criteria): learns-project, customizes-team, reports-batch-status and steers-through-foreman pass.
The structure tests are separate: `just test` at the repository root. They also cover a role
run by the user's own agent and an extra review step.
