# Live eval: a whole batch, with real agents (draft design)

## Goal

Run chantier for real, end to end, on a small fictional Python project, and check that **every
agent received the right role and behaved as its role says**: the Chief of Staff, the Foreman,
each Driver and each worker. The deterministic scenario (`evals/scenario/`) already checks the
CLI's state machine with scripted agents; this eval checks the *agents*.

## Shape of the run

1. **Fixture** (`evals/live/fixture/`, copied to a fresh folder): `tasks-cli`, a ~150-line Python
   to-do CLI (`tasks add/list/done`, JSON storage) with pytest tests, a `pyproject.toml` run by
   `uv`, and an `AGENTS.md` that states:
   - the fast gate `uv run pytest -q -x` and the long gate `uv run pytest -q`;
   - the default branch `main`, Conventional Commits;
   - a `chantier` section adding one review step,
     `docs-review: chantier-eval-docs-reviewer, after the Inspector: every new CLI option is in README.md`,
     whose agent file ships in the fixture's `.claude/agents/`.
2. **Five prepared CRs** in `.agents/changes/backlog/2-backlog/P1/` (intake, intent, answers,
   complete spec), sized for one or two rounds each:
   - A `--priority` option on `add` (touches README → exercises the docs review);
   - B fix: `done <unknown id>` crashes with a traceback instead of an error message;
   - C `list --json`;
   - D (added mid-batch) a `delete` command;
   - E (added later) "export tasks to CSV" with one decision deliberately left open in the spec
     (which columns), so a Driver must ask a question.
3. **Script of the user's turns** (played by the evaluator, as the user, in the Chief of Staff's
   session):
   1. "Run A, B and C in parallel, three slots, QA on C." → preflight, plan, go.
   2. While they run: "status?".
   3. After the first hand-back: "add D to the batch".
   4. A bit later: "add E too".
   5. When E's question arrives: answer it ("id, title, priority, done").
   6. A "change" order on a live CR: "for B, the error message must go to stderr".
   7. Merge each PR as it becomes ready (the evaluator merges), and say "I merged #n".
   8. Wait for the batch to land; ask "what did it cost?".
4. **Audit** (`evals/live/audit.py`, no model): reads the Foreman's transcript and its
   `subagents/` (`agent-*.jsonl` + `.meta.json`), `batch.json`, `events.jsonl`, the CR folders and
   git, and prints one PASS/FAIL line per check. The evaluator also reads the transcripts for the
   behavioral checks a script cannot judge.

## Checks

**Roles and prompts (script)**
- Every subagent's `agentType` is the plugin agent of its role (`chantier:cr-driver`,
  `chantier:coder`, …), or `chantier-eval-docs-reviewer` for the review step.
- Every subagent's first prompt is a `chantier spawn` prompt: it starts with `chantier <role> for
  CR-<n>`, names the right card section, the right worktree, specification and work folder.
- Drivers run in the background, workers in the foreground.
- One CR Driver per CR at a time; a QA driver only for C; no stack driver.
- The docs review step runs after an Inspector `APPROVE`, never before.
- The Foreman spawned nothing that no `chantier event` action line asked for.

**Behavior (script + evaluator)**
- Coder: changes only in its CR's worktree, never commits; writes `work/coder/r<n>.md`.
- Inspector and the docs reviewer: reply JSON only, edit nothing.
- Verifier: `work/verifier/verify.md` with the head SHA and `VERIFIED`.
- Drivers: commit, `chantier gate --long`, `chantier ship`, `chantier wait ci` in the background,
  `report` milestones, one hand-back, then end.
- QA driver for C: `qa.md` and `qa done`; no fix of its own.
- E: the Driver hands back `blocked question:`, the Foreman relays, the Chief of Staff asks the
  user, records the answer in E's `02-answers.md`, and a new Driver works with the answer.
- The change order on B reaches B's Driver and becomes a round.
- Nobody merges; every PR is opened against `main` with a body; the batch lands with a report.
- Nothing written in the main checkout outside `.agents/changes/`.
- Every state change went through `chantier` (events.jsonl is complete and consistent).

**Cost**: the run's cost from `chantier cost --by cr`, reported, not judged.

## Open decisions

1. **Where it runs.** Real Claude Desktop sessions need the plugin installed for the agents
   (`chantier:cr-driver`, …): install it from this checkout (`claude plugin marketplace add`,
   `claude plugin install`), which changes the user's Claude configuration.
2. **Forge.** `chantier ship` and `wait ci` need GitHub: a private throwaway repository
   (`gsemet/chantier-eval-tasks`) with a GitHub Actions workflow running pytest gives real PRs and
   real CI; the fake `gh` of the scenario cannot reach the Foreman's sessions (environment).
3. **Budget.** Opus Foreman + Sonnet Drivers and workers, five CRs, a few rounds each: estimated
   tens of dollars; a `--budget` on the batch caps new spawns.
